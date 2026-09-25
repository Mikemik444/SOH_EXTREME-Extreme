[CmdletBinding()]
param(
    [string]$ProjectRoot = '',
    [string]$ArchipelagoRoot = '',
    [switch]$SkipInstall,
    [switch]$CheckOnly
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $ProjectRoot = Split-Path -Parent $PSScriptRoot
}

$Root = [IO.Path]::GetFullPath($ProjectRoot)
$SourceRoot = Join-Path $Root 'archipelago'
$PackageRoot = Join-Path $SourceRoot 'soh_extreme'
$Output = Join-Path $Root 'soh_extreme.apworld'

function Get-Hash([string]$Path) {
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Get-ZipEntryHash($Entry) {
    $Stream = $Entry.Open()
    $Hasher = [Security.Cryptography.SHA256]::Create()
    try {
        return ([BitConverter]::ToString($Hasher.ComputeHash($Stream))).Replace('-', '').ToLowerInvariant()
    } finally {
        $Stream.Dispose()
        $Hasher.Dispose()
    }
}

function Get-ZipEntryText($Archive, [string]$Name) {
    $Entry = $Archive.GetEntry($Name)
    if ($null -eq $Entry) {
        throw "Archive is missing $Name"
    }
    $Reader = [IO.StreamReader]::new($Entry.Open(), [Text.Encoding]::UTF8, $true)
    try {
        return $Reader.ReadToEnd()
    } finally {
        $Reader.Dispose()
    }
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

    if ($env:ProgramData) {
        $Candidates.Add((Join-Path $env:ProgramData 'Archipelago'))
    }
    if ($env:LOCALAPPDATA) {
        $Candidates.Add((Join-Path $env:LOCALAPPDATA 'Programs\Archipelago'))
    }
    if ($env:ProgramFiles) {
        $Candidates.Add((Join-Path $env:ProgramFiles 'Archipelago'))
    }

    foreach ($Candidate in $Candidates) {
        if ((Test-Path -LiteralPath (Join-Path $Candidate 'ArchipelagoLauncher.exe')) -or
            (Test-Path -LiteralPath (Join-Path $Candidate 'custom_worlds') -PathType Container) -or
            (Test-Path -LiteralPath (Join-Path $Candidate 'custom_worlds\soh_extreme.apworld'))) {
            return [IO.Path]::GetFullPath($Candidate)
        }
    }

    throw 'Archipelago installation not found. Specify -ArchipelagoRoot, set SOH_EXTREME_AP_ROOT, or use -SkipInstall.'
}

function Assert-SourceTree {
    if (-not (Test-Path -LiteralPath $SourceRoot -PathType Container)) {
        throw "Canonical AP source directory is missing: $SourceRoot"
    }

    foreach ($Relative in @(
        'archipelago.json',
        'soh_extreme\archipelago.json',
        'soh_extreme\__init__.py',
        'soh_extreme\Options.py',
        'soh_extreme\TrackerMirror.py',
        'soh_extreme\TrackerWorker.py',
        'soh_extreme\TrackerClient.py',
        'soh_extreme\EnemyDropRules.py',
        'soh_extreme\EnemyRoomLogic.py',
        'soh_extreme\NativeLogic.py',
        'soh_extreme\NativeLogicAlternatives.py',
        'soh_extreme\_vendor_oot_soh\Items.py',
        'soh_extreme\_vendor_oot_soh\Locations.py',
        'soh_extreme\_vendor_oot_soh\LogicHelpers.py',
        'soh_extreme\_vendor_oot_soh\Regions.py'
    )) {
        $Path = Join-Path $SourceRoot $Relative
        if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
            throw "Required canonical AP source is missing: archipelago\$Relative"
        }
    }
}

function Get-SourceRecords {
    $Files = [Collections.Generic.List[IO.FileInfo]]::new()

    $RootManifest = Get-Item -LiteralPath (Join-Path $SourceRoot 'archipelago.json')
    $Files.Add($RootManifest)

    foreach ($Node in @(Get-ChildItem -LiteralPath $PackageRoot -Recurse -Force)) {
        if (($Node.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "Links are not allowed inside canonical AP source: $($Node.FullName)"
        }
        if ($Node.PSIsContainer) {
            continue
        }

        $Relative = $Node.FullName.Substring($SourceRoot.Length + 1).Replace('\', '/')
        if ($Relative -match '(^|/)(__pycache__|\.git)(/|$)') {
            continue
        }

        if ($Node.Extension -notin @('.py', '.json', '.txt', '.md')) {
            continue
        }

        $Files.Add($Node)
    }

    return @($Files | Sort-Object FullName | ForEach-Object {
        [pscustomobject]@{
            Name = $_.FullName.Substring($SourceRoot.Length + 1).Replace('\', '/')
            Path = $_.FullName
            Hash = Get-Hash $_.FullName
        }
    })
}

function Assert-ManifestsAndTracker {
    $OuterManifestPath = Join-Path $SourceRoot 'archipelago.json'
    $InnerManifestPath = Join-Path $PackageRoot 'archipelago.json'

    $Outer = [IO.File]::ReadAllText($OuterManifestPath) | ConvertFrom-Json
    $Inner = [IO.File]::ReadAllText($InnerManifestPath) | ConvertFrom-Json

    if ($Outer.game -ne 'SOH-EXTREME' -or
        $Inner.game -ne 'SOH-EXTREME' -or
        $Outer.world_version -ne $Inner.world_version -or
        [int]$Outer.compatible_version -ne [int]$Inner.compatible_version) {
        throw 'The SOH-EXTREME outer and inner APWorld manifests disagree.'
    }

    if ([string]$Outer.world_version -notmatch '^\d+\.\d+\.\d+$') {
        throw "Invalid SOH-EXTREME world_version: $($Outer.world_version)"
    }

    $PythonTracker = [IO.File]::ReadAllText((Join-Path $PackageRoot 'TrackerMirror.py'))
    $HeaderPath = Join-Path $Root 'soh\Network\Archipelago\TrackerMirror.h'
    if (-not (Test-Path -LiteralPath $HeaderPath -PathType Leaf)) {
        throw "C++ tracker header is missing: $HeaderPath"
    }
    $CppTracker = [IO.File]::ReadAllText($HeaderPath)

    $PyMatch = [regex]::Match($PythonTracker, '(?m)^VERSION\s*=\s*"([0-9.]+)"')
    $CppMatch = [regex]::Match($CppTracker, 'kTrackerVersion\s*=\s*"([0-9.]+)"')

    if (-not $PyMatch.Success -or -not $CppMatch.Success) {
        throw 'Could not read the SOH-EXTREME tracker version from Python/C++.'
    }

    if ($PyMatch.Groups[1].Value -ne [string]$Outer.world_version -or
        $CppMatch.Groups[1].Value -ne [string]$Outer.world_version) {
        throw "APWorld/Python tracker/C++ tracker versions disagree. APWorld=$($Outer.world_version), Python=$($PyMatch.Groups[1].Value), C++=$($CppMatch.Groups[1].Value)"
    }

    return $Outer
}

function Write-Archive([string]$Path, $Records) {
    if (Test-Path -LiteralPath $Path) {
        Remove-Item -LiteralPath $Path -Force
    }

    $Zip = [IO.Compression.ZipFile]::Open($Path, [IO.Compression.ZipArchiveMode]::Create)
    try {
        foreach ($Record in $Records) {
            $Entry = $Zip.CreateEntry($Record.Name, [IO.Compression.CompressionLevel]::Optimal)
            $Entry.LastWriteTime = [DateTimeOffset]::new(2020, 1, 1, 0, 0, 0, [TimeSpan]::Zero)

            $Stream = $Entry.Open()
            try {
                $Bytes = [IO.File]::ReadAllBytes($Record.Path)
                $Stream.Write($Bytes, 0, $Bytes.Length)
            } finally {
                $Stream.Dispose()
            }
        }
    } finally {
        $Zip.Dispose()
    }
}

function Assert-ArchiveMatches([string]$Path, $Records) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "APWorld archive is missing: $Path"
    }

    $Zip = [IO.Compression.ZipFile]::OpenRead($Path)
    try {
        $Entries = @($Zip.Entries | Where-Object { -not $_.FullName.EndsWith('/') })
        if ($Entries.Count -ne $Records.Count) {
            throw "Archive/source file counts differ: archive=$($Entries.Count), source=$($Records.Count)"
        }

        $Names = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
        foreach ($Entry in $Entries) {
            if (-not $Names.Add($Entry.FullName)) {
                throw "Duplicate archive entry: $($Entry.FullName)"
            }
        }

        foreach ($Record in $Records) {
            $Entry = $Zip.GetEntry($Record.Name)
            if ($null -eq $Entry) {
                throw "Archive is missing $($Record.Name)"
            }

            $Hash = Get-ZipEntryHash $Entry
            if ($Hash -ne $Record.Hash) {
                throw "Archive/source bytes differ: $($Record.Name)"
            }
        }
    } finally {
        $Zip.Dispose()
    }
}

function Publish-Archive([string]$From, [string]$To) {
    $Directory = Split-Path -Parent $To
    New-Item -ItemType Directory -Path $Directory -Force | Out-Null

    if ((Test-Path -LiteralPath $To -PathType Leaf) -and
        (Get-Hash $From) -eq (Get-Hash $To)) {
        return
    }

    $Temp = Join-Path $Directory ('.soh_extreme-' + [Guid]::NewGuid().ToString('N') + '.tmp')
    Copy-Item -LiteralPath $From -Destination $Temp -Force

    if ((Get-Hash $Temp) -ne (Get-Hash $From)) {
        Remove-Item -LiteralPath $Temp -Force
        throw "Copy verification failed: $To"
    }

    if (Test-Path -LiteralPath $To -PathType Leaf) {
        $BackupRoot = Join-Path $Root 'patch-backups'
        New-Item -ItemType Directory -Path $BackupRoot -Force | Out-Null
        $BackupName = 'soh_extreme-before-sync-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff') + '.apworld'
        Copy-Item -LiteralPath $To -Destination (Join-Path $BackupRoot $BackupName) -Force
        Remove-Item -LiteralPath $To -Force
    }

    Move-Item -LiteralPath $Temp -Destination $To
}

Assert-SourceTree
$Manifest = Assert-ManifestsAndTracker
$Records = Get-SourceRecords

foreach ($Record in $Records) {
    if ($Record.Name.EndsWith('.json')) {
        $null = [IO.File]::ReadAllText($Record.Path) | ConvertFrom-Json
    }

    if ($Record.Name.EndsWith('.py')) {
        $Text = [IO.File]::ReadAllText($Record.Path)
        if ($Text -match '(?m)^\s*(?:from\s+worlds\.oot_soh(?:\.|\s|$)|import\s+worlds\.oot_soh(?:\.|\s|$))') {
            throw "External stock-world import remains in $($Record.Name)"
        }
    }
}

if ($CheckOnly) {
    Assert-ArchiveMatches $Output $Records

    if (-not $SkipInstall) {
        $ApRoot = Find-ArchipelagoRoot $ArchipelagoRoot
        $Installed = Join-Path $ApRoot 'custom_worlds\soh_extreme.apworld'
        Assert-ArchiveMatches $Installed $Records
    }

    Write-Host "APWORLD PARITY OK: $($Records.Count) files; version $($Manifest.world_version)." -ForegroundColor Green
    exit 0
}

$Temporary = Join-Path $Root ('.soh-extreme-source-' + [Guid]::NewGuid().ToString('N') + '.tmp')
try {
    Write-Archive $Temporary $Records
    Assert-ArchiveMatches $Temporary $Records
    Publish-Archive $Temporary $Output
} finally {
    if (Test-Path -LiteralPath $Temporary -PathType Leaf) {
        Remove-Item -LiteralPath $Temporary -Force
    }
}

Assert-ArchiveMatches $Output $Records

$Installed = ''
if (-not $SkipInstall) {
    $ApRoot = Find-ArchipelagoRoot $ArchipelagoRoot
    $WorldDirectory = Join-Path $ApRoot 'custom_worlds'
    $Installed = Join-Path $WorldDirectory 'soh_extreme.apworld'

    # Refuse an unpacked duplicate development world because AP can load both.
    if (Test-Path -LiteralPath (Join-Path $WorldDirectory 'soh_extreme') -PathType Container) {
        throw "Duplicate unpacked world exists: $WorldDirectory\soh_extreme"
    }

    # Refuse another .apworld that advertises the same game.
    if (Test-Path -LiteralPath $WorldDirectory -PathType Container) {
        foreach ($Other in @(Get-ChildItem -LiteralPath $WorldDirectory -Filter '*.apworld' -File)) {
            if ($Other.FullName -ieq $Installed) {
                continue
            }

            $OtherZip = $null
            try {
                $OtherZip = [IO.Compression.ZipFile]::OpenRead($Other.FullName)
                $Entry = $OtherZip.GetEntry('archipelago.json')
                if ($null -eq $Entry) {
                    $Entry = $OtherZip.GetEntry('soh_extreme/archipelago.json')
                }
                if ($null -ne $Entry) {
                    $Reader = [IO.StreamReader]::new($Entry.Open(), [Text.Encoding]::UTF8, $true)
                    try {
                        $OtherManifest = $Reader.ReadToEnd() | ConvertFrom-Json
                    } finally {
                        $Reader.Dispose()
                    }
                    if ($OtherManifest.game -eq 'SOH-EXTREME') {
                        throw "Another SOH-EXTREME APWorld is installed: $($Other.FullName)"
                    }
                }
            } finally {
                if ($null -ne $OtherZip) {
                    $OtherZip.Dispose()
                }
            }
        }
    }

    Publish-Archive $Output $Installed
    Assert-ArchiveMatches $Installed $Records
}

$Report = [ordered]@{
    version = [string]$Manifest.world_version
    canonical_source = $SourceRoot
    output = $Output
    installed = $Installed
    files = $Records.Count
    source_archive_parity = $true
    sha256 = Get-Hash $Output
    checked_utc = [DateTime]::UtcNow.ToString('o')
}

$ReportPath = Join-Path $Root 'APWORLD_SOURCE_SYNC_REPORT.json'
[IO.File]::WriteAllText(
    $ReportPath,
    ($Report | ConvertTo-Json -Depth 4),
    [Text.UTF8Encoding]::new($false)
)

Write-Host ""
Write-Host "SOH-EXTREME APWORLD SYNC OK" -ForegroundColor Green
Write-Host "Source:    $SourceRoot"
Write-Host "Version:   $($Manifest.world_version)"
Write-Host "Files:     $($Records.Count)"
Write-Host "APWorld:   $Output"
if ($Installed) {
    Write-Host "Installed: $Installed"
}
Write-Host "Report:    $ReportPath"
