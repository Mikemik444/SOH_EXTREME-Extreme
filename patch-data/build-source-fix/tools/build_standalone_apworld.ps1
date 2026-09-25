[CmdletBinding()]
param(
    [string]$ProjectRoot = '',
    [string]$ArchipelagoRoot = '',
    [switch]$SkipInstall,
    [switch]$CheckOnly
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
Add-Type -AssemblyName System.IO.Compression.FileSystem
if ([string]::IsNullOrWhiteSpace($ProjectRoot)) { $ProjectRoot = Split-Path -Parent $PSScriptRoot }
$Root = [IO.Path]::GetFullPath($ProjectRoot)
$SourceRoot = Join-Path $Root 'arvhipelago'
$PackageRoot = Join-Path $SourceRoot 'soh_extreme'
$Output = Join-Path $Root 'soh_extreme.apworld'

function Get-Hash([string]$Path) {
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}
function Get-ZipEntryText($Archive, [string]$Name) {
    $Entry = $Archive.GetEntry($Name)
    if ($null -eq $Entry) { throw "Archive is missing $Name" }
    $Reader = [IO.StreamReader]::new($Entry.Open(), [Text.Encoding]::UTF8, $true)
    try { return $Reader.ReadToEnd() } finally { $Reader.Dispose() }
}
function Assert-Upgradeable([string]$Path, [version]$SourceVersion, [int]$Compatibility) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return }
    $Zip = [IO.Compression.ZipFile]::OpenRead($Path)
    try {
        $Name = 'archipelago.json'
        if ($null -eq $Zip.GetEntry($Name)) { $Name = 'soh_extreme/archipelago.json' }
        $Info = (Get-ZipEntryText $Zip $Name) | ConvertFrom-Json
        if ($Info.game -ne 'SOH-EXTREME' -or [int]$Info.compatible_version -ne $Compatibility) {
            throw "Refusing to replace an incompatible APWorld: $Path"
        }
        if ([string]$Info.world_version -notmatch '^\d+\.\d+\.\d+$' -or
            [version]$Info.world_version -gt $SourceVersion) {
            throw "Refusing to replace a newer or unrecognized APWorld: $Path"
        }
    } finally { $Zip.Dispose() }
}
function Find-ArchipelagoRoot([string]$Requested) {
    if (-not [string]::IsNullOrWhiteSpace($Requested)) {
        if (-not (Test-Path -LiteralPath $Requested -PathType Container)) {
            throw "Archipelago directory not found: $Requested"
        }
        return [IO.Path]::GetFullPath($Requested)
    }
    if (-not [string]::IsNullOrWhiteSpace($env:SOH_EXTREME_AP_ROOT)) {
        return Find-ArchipelagoRoot $env:SOH_EXTREME_AP_ROOT
    }
    $Candidates = [Collections.Generic.List[string]]::new()
    if ($env:ProgramData) { $Candidates.Add((Join-Path $env:ProgramData 'Archipelago')) }
    if ($env:LOCALAPPDATA) { $Candidates.Add((Join-Path $env:LOCALAPPDATA 'Programs\Archipelago')) }
    if ($env:ProgramFiles) { $Candidates.Add((Join-Path $env:ProgramFiles 'Archipelago')) }
    foreach ($Candidate in $Candidates) {
        if ((Test-Path -LiteralPath (Join-Path $Candidate 'ArchipelagoLauncher.exe')) -or
            (Test-Path -LiteralPath (Join-Path $Candidate 'custom_worlds\soh_extreme.apworld'))) {
            return $Candidate
        }
    }
    throw 'Archipelago installation not found. Specify -ArchipelagoRoot, or use -SkipInstall to build only.'
}
function Assert-ArchiveMatches([string]$Path, $Records) {
    $Zip = [IO.Compression.ZipFile]::OpenRead($Path)
    try {
        $Entries = @($Zip.Entries | Where-Object { -not $_.FullName.EndsWith('/') })
        if ($Entries.Count -ne $Records.Count) { throw "Archive/source file counts differ: $Path" }
        $Names = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
        foreach ($Entry in $Entries) {
            if (-not $Names.Add($Entry.FullName)) { throw "Duplicate archive entry: $($Entry.FullName)" }
        }
        foreach ($Record in $Records) {
            $Entry = $Zip.GetEntry($Record.Name)
            if ($null -eq $Entry) { throw "Archive is missing $($Record.Name)" }
            $Stream = $Entry.Open()
            $Hasher = [Security.Cryptography.SHA256]::Create()
            try {
                $Hash = ([BitConverter]::ToString($Hasher.ComputeHash($Stream))).Replace('-', '').ToLowerInvariant()
            } finally { $Stream.Dispose(); $Hasher.Dispose() }
            if ($Hash -ne $Record.Hash) { throw "Archive/source bytes differ: $($Record.Name)" }
            if ((Get-Hash $Record.Path) -ne $Record.Hash) {
                throw "Source changed during packaging: $($Record.Name). Retry the build."
            }
        }
    } finally { $Zip.Dispose() }
}
function Write-Archive([string]$Path, $Records) {
    $Zip = [IO.Compression.ZipFile]::Open($Path, [IO.Compression.ZipArchiveMode]::Create)
    try {
        foreach ($Record in $Records) {
            $Entry = $Zip.CreateEntry($Record.Name, [IO.Compression.CompressionLevel]::Optimal)
            $Entry.LastWriteTime = [DateTimeOffset]::new(2020, 1, 1, 0, 0, 0, [TimeSpan]::Zero)
            $Stream = $Entry.Open()
            try {
                $Bytes = [IO.File]::ReadAllBytes($Record.Path)
                $Stream.Write($Bytes, 0, $Bytes.Length)
            } finally { $Stream.Dispose() }
        }
    } finally { $Zip.Dispose() }
}
function Publish-Archive([string]$From, [string]$To, [string]$BackupName, [string]$BackupRoot) {
    if ((Test-Path -LiteralPath $To -PathType Leaf) -and (Get-Hash $From) -eq (Get-Hash $To)) { return }
    $Directory = Split-Path -Parent $To
    New-Item -ItemType Directory -Path $Directory -Force | Out-Null
    $Temp = Join-Path $Directory ('.soh_extreme-' + [Guid]::NewGuid().ToString('N') + '.tmp')
    try {
        Copy-Item -LiteralPath $From -Destination $Temp -Force
        if ((Get-Hash $Temp) -ne (Get-Hash $From)) { throw "Copy verification failed: $To" }
        if (Test-Path -LiteralPath $To -PathType Leaf) {
            New-Item -ItemType Directory -Path $BackupRoot -Force | Out-Null
            Copy-Item -LiteralPath $To -Destination (Join-Path $BackupRoot $BackupName) -Force
            # Replacement temp and destination share a volume; backup was copied separately.
            [IO.File]::Replace($Temp, $To, $null)
        } else { [IO.File]::Move($Temp, $To) }
    } finally {
        if (Test-Path -LiteralPath $Temp -PathType Leaf) { Remove-Item -LiteralPath $Temp -Force }
    }
}

foreach ($Relative in @(
    'archipelago.json', 'soh_extreme\archipelago.json', 'soh_extreme\__init__.py',
    'soh_extreme\Options.py', 'soh_extreme\TrackerMirror.py', 'soh_extreme\TrackerWorker.py',
    'soh_extreme\TrackerClient.py', 'soh_extreme\EnemyDropRules.py', 'soh_extreme\EnemyRoomLogic.py',
    'soh_extreme\EnemyRoomGraph.json', 'soh_extreme\EnemyRoomMap.json', 'soh_extreme\SilverRoomLogic.py',
    'soh_extreme\NativeLogic.py', 'soh_extreme\NativeLogicAlternatives.py',
    'soh_extreme\_vendor_oot_soh\LogicHelpers.py', 'soh_extreme\_vendor_oot_soh\Regions.py',
    'soh_extreme\_vendor_oot_soh\Items.py', 'soh_extreme\_vendor_oot_soh\Locations.py',
    'soh_extreme\_vendor_oot_soh\location_access\dungeons\dodongos_cavern.py'
)) {
    if (-not (Test-Path -LiteralPath (Join-Path $SourceRoot $Relative) -PathType Leaf)) {
        throw "Required canonical AP source is missing: arvhipelago\$Relative"
    }
}
$ManifestPath = Join-Path $SourceRoot 'archipelago.json'
$InnerManifest = Join-Path $PackageRoot 'archipelago.json'
$Info = [IO.File]::ReadAllText($ManifestPath) | ConvertFrom-Json
$Inner = [IO.File]::ReadAllText($InnerManifest) | ConvertFrom-Json
if ($Info.game -ne 'SOH-EXTREME' -or $Inner.game -ne $Info.game -or
    $Inner.world_version -ne $Info.world_version -or
    [int]$Inner.compatible_version -ne [int]$Info.compatible_version -or
    [string]$Info.world_version -notmatch '^\d+\.\d+\.\d+$') {
    throw 'The two SOH-EXTREME source manifests disagree or have an invalid version. They were not rewritten.'
}
$Version = [string]$Info.world_version
$PythonTracker = [IO.File]::ReadAllText((Join-Path $PackageRoot 'TrackerMirror.py'))
$HeaderPath = Join-Path $Root 'soh\Network\Archipelago\TrackerMirror.h'
if (-not (Test-Path -LiteralPath $HeaderPath -PathType Leaf)) { throw 'C++ TrackerMirror.h is missing.' }
$CppTracker = [IO.File]::ReadAllText($HeaderPath)
$PyMatch = [regex]::Match($PythonTracker, '(?m)^VERSION\s*=\s*"([0-9.]+)"')
$CppMatch = [regex]::Match($CppTracker, 'kTrackerVersion\s*=\s*"([0-9.]+)"')
if (-not $PyMatch.Success -or -not $CppMatch.Success -or
    $PyMatch.Groups[1].Value -ne $Version -or $CppMatch.Groups[1].Value -ne $Version) {
    throw "APWorld/Python tracker/C++ tracker versions disagree. Source version: $Version. Build stopped before deployment."
}
$Files = [Collections.Generic.List[IO.FileInfo]]::new()
$Files.Add((Get-Item -LiteralPath $ManifestPath))
# Reject directory junctions in the canonical package rather than following a
# second checkout into this archive. This never modifies the source directory.
$Nodes = @(Get-ChildItem -LiteralPath $PackageRoot -Recurse -Force)
foreach ($Node in $Nodes) {
    if (($Node.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "Links are not allowed inside canonical AP source: $($Node.FullName)"
    }
    if ($Node.PSIsContainer) { continue }
    $Relative = $Node.FullName.Substring($SourceRoot.Length + 1).Replace('\', '/')
    if ($Relative -match '(^|/)(__pycache__|\.git)(/|$)') { continue }
    if ($Node.Extension -notin @('.py', '.json', '.txt', '.md')) { continue }
    $Files.Add($Node)
}
$Records = @($Files | Sort-Object FullName | ForEach-Object {
    [pscustomobject]@{ Name=$_.FullName.Substring($SourceRoot.Length + 1).Replace('\', '/'); Path=$_.FullName; Hash=(Get-Hash $_.FullName) }
})
foreach ($Record in $Records) {
    if ($Record.Name.EndsWith('.json')) { $null = [IO.File]::ReadAllText($Record.Path) | ConvertFrom-Json }
    if ($Record.Name.EndsWith('.py') -and [IO.File]::ReadAllText($Record.Path) -match
        '(?m)^\s*(?:from\s+worlds\.oot_soh(?:\.|\s|$)|import\s+worlds\.oot_soh(?:\.|\s|$))') {
        throw "External stock-world import in $($Record.Name). Existing modified helpers were left intact."
    }
}
$Installed = ''
if (-not $SkipInstall) {
    $ArchipelagoRoot = Find-ArchipelagoRoot $ArchipelagoRoot
    $WorldDirectory = Join-Path $ArchipelagoRoot 'custom_worlds'
    $Installed = Join-Path $WorldDirectory 'soh_extreme.apworld'
    if (Test-Path -LiteralPath (Join-Path $WorldDirectory 'soh_extreme') -PathType Container) {
        throw 'An unpacked custom_worlds\soh_extreme development world exists. Resolve this duplicate before deployment.'
    }
    # Do not create another active copy alongside a renamed Extreme APWorld.
    if (Test-Path -LiteralPath $WorldDirectory) {
        foreach ($Other in @(Get-ChildItem -LiteralPath $WorldDirectory -Filter '*.apworld' -File)) {
            if ($Other.FullName -ieq $Installed) { continue }
            $Zip = $null
            try {
                $Zip = [IO.Compression.ZipFile]::OpenRead($Other.FullName)
                $EntryName = if ($null -ne $Zip.GetEntry('archipelago.json')) { 'archipelago.json' } else { 'soh_extreme/archipelago.json' }
                if ($null -ne $Zip.GetEntry($EntryName)) {
                    $OtherInfo = (Get-ZipEntryText $Zip $EntryName) | ConvertFrom-Json
                    if ($OtherInfo.game -eq 'SOH-EXTREME') { throw "DUPLICATE_EXTREME: $($Other.FullName)" }
                }
            } catch {
                if ($_.Exception.Message.StartsWith('DUPLICATE_EXTREME:')) { throw }
                Write-Warning "Could not inspect unrelated APWorld $($Other.Name); it was not modified."
            } finally { if ($null -ne $Zip) { $Zip.Dispose() } }
        }
    }
    Assert-Upgradeable $Installed ([version]$Version) ([int]$Info.compatible_version)
}
Assert-Upgradeable $Output ([version]$Version) ([int]$Info.compatible_version)
if ($CheckOnly) {
    Assert-ArchiveMatches $Output $Records
    if ($Installed) { Assert-ArchiveMatches $Installed $Records }
    Write-Host "APWORLD PARITY OK: $($Records.Count) source files; world/tracker version $Version."
    exit 0
}
$Unchanged = $false
if (Test-Path -LiteralPath $Output -PathType Leaf) {
    try { Assert-ArchiveMatches $Output $Records; $Unchanged = $true } catch { $Unchanged = $false }
}
$Backup = Join-Path $Root ('patch-backups\apworld-source-sync-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
if (-not $Unchanged) {
    $Temporary = Join-Path $Root ('.soh-extreme-source-' + [Guid]::NewGuid().ToString('N') + '.tmp')
    try {
        Write-Archive $Temporary $Records
        Assert-ArchiveMatches $Temporary $Records
        Publish-Archive $Temporary $Output 'root-soh_extreme.apworld.backup' $Backup
    } finally { if (Test-Path -LiteralPath $Temporary) { Remove-Item -LiteralPath $Temporary -Force } }
}
if ($Installed) {
    Publish-Archive $Output $Installed 'installed-soh_extreme.apworld.backup' $Backup
    Assert-ArchiveMatches $Installed $Records
}
Assert-ArchiveMatches $Output $Records
$Report = [ordered]@{
    version=$Version; canonical_source=$SourceRoot; output=$Output; installed=$Installed
    files=$Records.Count; source_archive_parity=$true; sha256=(Get-Hash $Output)
    checked_utc=[DateTime]::UtcNow.ToString('o')
}
$ReportPath = Join-Path $Root 'APWORLD_SOURCE_SYNC_REPORT.json'
[IO.File]::WriteAllText($ReportPath, ($Report | ConvertTo-Json -Depth 4), [Text.UTF8Encoding]::new($false))
Write-Host "APWORLD PARITY OK: $($Records.Count) files from arvhipelago; world/tracker version $Version."
Write-Host "APWorld: $Output"
if ($Installed) { Write-Host "Installed: $Installed" }
Write-Host 'Modified vendor rules are preserved. No stock download, archive guessing, or version downgrade was performed.'
Write-Host "Report: $ReportPath"
