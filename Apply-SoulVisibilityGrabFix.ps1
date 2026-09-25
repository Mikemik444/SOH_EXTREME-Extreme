[CmdletBinding()]
param([string]$ArchipelagoRoot = '')
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$Root = $PSScriptRoot
$Payload = Join-Path $Root 'patch-data\soul-visibility-grab-0.11.22'
$Manifest = Get-Content -LiteralPath (Join-Path $Payload 'manifest.json') -Raw | ConvertFrom-Json
$Utf8 = [System.Text.UTF8Encoding]::new($false)

function Get-NormalizedTextHash([string]$Path) {
    $Text = [IO.File]::ReadAllText($Path).Replace("`r`n", "`n")
    $Hash = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($Hash.ComputeHash($Utf8.GetBytes($Text)))).Replace('-', '').ToLowerInvariant() }
    finally { $Hash.Dispose() }
}
function Get-BytesHash([string]$Path) {
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}
function Assert-WorldCanUpgrade([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return }
    $Zip = [IO.Compression.ZipFile]::OpenRead($Path)
    try {
        $Entry = $Zip.GetEntry('archipelago.json')
        if ($null -eq $Entry) { $Entry = $Zip.GetEntry('soh_extreme/archipelago.json') }
        if ($null -eq $Entry) { throw "No SOH-EXTREME manifest in $Path" }
        $Reader = [IO.StreamReader]::new($Entry.Open())
        try { $Info = $Reader.ReadToEnd() | ConvertFrom-Json } finally { $Reader.Dispose() }
        if ($Info.game -ne 'SOH-EXTREME' -or [int]$Info.compatible_version -ne 7) {
            throw "The installed world has a different game/data compatibility version: $Path. It was not replaced."
        }
        $Match = [regex]::Match([string]$Info.world_version, '^\d+\.\d+\.\d+')
        if (-not $Match.Success -or [version]$Match.Value -gt [version]'0.11.22') {
            throw "Refusing to overwrite a newer or unrecognized world: $Path"
        }
    } finally { $Zip.Dispose() }
}

foreach ($Name in @('CMakeLists.txt', 'build.cmd', 'soh\Enhancements\randomizer\EnemySoulIcons.h')) {
    if (-not (Test-Path -LiteralPath (Join-Path $Root $Name) -PathType Leaf)) {
        throw "Extract this complete ZIP into E:\test\bb first. Missing: $Name"
    }
}
if (@(Get-Process -Name 'soh' -ErrorAction SilentlyContinue).Count -gt 0) {
    throw 'Close Ship of Harkinian before applying the patch. No files changed.'
}
Add-Type -AssemblyName System.IO.Compression.FileSystem

# Use the installation shown in this client's logs first, then conventional
# installer locations. A custom path can also be supplied as -ArchipelagoRoot.
if ([string]::IsNullOrWhiteSpace($ArchipelagoRoot)) {
    $Candidates = @(
        (Join-Path $env:ProgramData 'Archipelago'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Archipelago'),
        (Join-Path $env:ProgramFiles 'Archipelago')
    )
    foreach ($Candidate in $Candidates) {
        if ((Test-Path -LiteralPath (Join-Path $Candidate 'ArchipelagoLauncher.exe')) -or
            (Test-Path -LiteralPath (Join-Path $Candidate 'custom_worlds\soh_extreme.apworld'))) {
            $ArchipelagoRoot = $Candidate
            break
        }
    }
}
if ([string]::IsNullOrWhiteSpace($ArchipelagoRoot) -or -not (Test-Path -LiteralPath $ArchipelagoRoot -PathType Container)) {
    throw 'Archipelago installation not found. No source files changed. The README describes the custom-install command.'
}
$WorldFolder = Join-Path $ArchipelagoRoot 'custom_worlds'
$WorldTarget = Join-Path $WorldFolder 'soh_extreme.apworld'
if (Test-Path -LiteralPath (Join-Path $WorldFolder 'soh_extreme') -PathType Container) {
    throw "An unpacked duplicate world exists at $WorldFolder\soh_extreme. This installer will not silently overwrite a development world."
}
Assert-WorldCanUpgrade $WorldTarget
Assert-WorldCanUpgrade (Join-Path $Root 'soh_extreme.apworld')

# Verify all staged bytes and source baselines BEFORE replacing anything.
# Text comparisons normalize CRLF/LF to allow Windows Git checkouts.
foreach ($File in $Manifest.files) {
    $Relative = [string]$File.path
    if ([IO.Path]::IsPathRooted($Relative) -or $Relative.Split('/') -contains '..') { throw 'Unsafe package path.' }
    $Source = Join-Path $Payload $Relative
    if (-not (Test-Path -LiteralPath $Source -PathType Leaf) -or (Get-BytesHash $Source) -ne $File.sha256) {
        throw "Package integrity check failed: $Relative"
    }
    if ($File.protect_source) {
        $Target = Join-Path $Root $Relative
        if (-not (Test-Path -LiteralPath $Target -PathType Leaf)) { throw "Required source file missing: $Relative" }
        $Current = Get-NormalizedTextHash $Target
        if ($Current -ne $File.before_text_sha256 -and $Current -ne $File.after_text_sha256) {
            throw "Source differs from the reviewed GitHub version: $Relative. Nothing was overwritten; keep your local edits."
        }
    }
}

$Plans = [Collections.Generic.List[object]]::new()
foreach ($File in $Manifest.files) {
    $Relative = [string]$File.path
    $Plans.Add([pscustomobject]@{ Source=(Join-Path $Payload $Relative); Target=(Join-Path $Root $Relative); BackupName=('source\' + $Relative) })
    # The local GenerateSohOtr target reads root/assets/custom, while the GitHub
    # checkout stores these same textures under soh/assets/custom. Update both.
    if ($Relative.StartsWith('soh/assets/custom/')) {
        $Mirror = $Relative.Substring(4)
        $Plans.Add([pscustomobject]@{ Source=(Join-Path $Payload $Relative); Target=(Join-Path $Root $Mirror); BackupName=('source\' + $Mirror) })
    }
}
$Plans.Add([pscustomobject]@{ Source=(Join-Path $Payload 'soh_extreme.apworld'); Target=$WorldTarget; BackupName='installed-world\soh_extreme.apworld.backup' })
$Backup = Join-Path $Root ('patch-backups\soul-visibility-grab-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
New-Item -ItemType Directory -Path $Backup -Force | Out-Null
$Records = [Collections.Generic.List[object]]::new()
foreach ($Plan in $Plans) {
    $BackupPath = Join-Path $Backup $Plan.BackupName
    $Existed = Test-Path -LiteralPath $Plan.Target -PathType Leaf
    if ($Existed) {
        New-Item -ItemType Directory -Path (Split-Path -Parent $BackupPath) -Force | Out-Null
        Copy-Item -LiteralPath $Plan.Target -Destination $BackupPath -Force
    }
    $Records.Add([pscustomobject]@{ Source=$Plan.Source; Target=$Plan.Target; Backup=$BackupPath; Existed=$Existed })
}
$Records | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $Backup 'restore-manifest.json') -Encoding UTF8
$Written = [Collections.Generic.List[object]]::new()
try {
    foreach ($Record in $Records) {
        # Also avoids copying onto a junction's same file after its alias changed.
        if ((Test-Path -LiteralPath $Record.Target -PathType Leaf) -and
            (Get-BytesHash $Record.Target) -eq (Get-BytesHash $Record.Source)) { continue }
        New-Item -ItemType Directory -Path (Split-Path -Parent $Record.Target) -Force | Out-Null
        $Written.Add($Record)
        Copy-Item -LiteralPath $Record.Source -Destination $Record.Target -Force
    }
} catch {
    $OriginalError = $_
    for ($Index = $Written.Count - 1; $Index -ge 0; --$Index) {
        $Record = $Written[$Index]
        try {
            if ($Record.Existed) { Copy-Item -LiteralPath $Record.Backup -Destination $Record.Target -Force }
            elseif (Test-Path -LiteralPath $Record.Target -PathType Leaf) { Remove-Item -LiteralPath $Record.Target -Force }
        } catch { Write-Warning "Could not restore $($Record.Target); backup is in $Backup" }
    }
    throw "Patch copy failed; rollback attempted. Backup: $Backup. $OriginalError. For access denied in ProgramData, run APPLY_SOUL_VISIBILITY_GRAB_FIX.cmd as administrator."
}
Write-Host ''
Write-Host 'SOH-EXTREME 0.11.22 installed: clearer 47 enemy portraits and corrected Dodongo block-switch logic.'
Write-Host "Archipelago world: $WorldTarget"
Write-Host "Backups: $Backup"
Write-Host 'Previous Shovel/Roll, soul-linkage, APCpp, build.cmd and CMake fixes were preserved.'
Write-Host 'Building with your existing build.cmd (including soh.o2r generation)...'
Push-Location $Root
try {
    & $env:ComSpec /d /c 'call build.cmd'
    $Result = $LASTEXITCODE
} finally { Pop-Location }
if ($Result -ne 0) { throw 'The patch is installed, but the build failed. Do not launch an old executable; keep the first build error.' }
Write-Host ''
Write-Host 'COMPLETE. Restart Universal Tracker/Archipelago tools before using them again.'
Write-Host "Launch: $(Join-Path $Root 'soh.exe')"
Write-Host 'Existing seed placements were not changed. The corrected tracker does not relocate old rewards.'
