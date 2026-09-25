[CmdletBinding()]
param([string]$ArchipelagoRoot = '', [switch]$SkipBuild)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$Root = $PSScriptRoot
$Payload = Join-Path $Root 'patch-data\build-source-fix'
$Utf8 = [Text.UTF8Encoding]::new($false)
$Manifest = [IO.File]::ReadAllText((Join-Path $Payload 'manifest.json')) | ConvertFrom-Json

function Get-Hash([string]$Path) {
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}
function Get-GitTextHash([string]$Path) {
    $Text = [IO.File]::ReadAllText($Path).Replace("`r`n", "`n")
    $Bytes = $Utf8.GetBytes($Text)
    $Prefix = [Text.Encoding]::ASCII.GetBytes(('blob ' + $Bytes.Length + [char]0))
    $Data = [byte[]]::new($Prefix.Length + $Bytes.Length)
    [Array]::Copy($Prefix, 0, $Data, 0, $Prefix.Length)
    [Array]::Copy($Bytes, 0, $Data, $Prefix.Length, $Bytes.Length)
    $Hasher = [Security.Cryptography.SHA1]::Create()
    try { return ([BitConverter]::ToString($Hasher.ComputeHash($Data))).Replace('-', '').ToLowerInvariant() }
    finally { $Hasher.Dispose() }
}

foreach ($Relative in @('CMakeLists.txt', 'build.cmd', 'build-vs\CMakeCache.txt')) {
    if (-not (Test-Path -LiteralPath (Join-Path $Root $Relative) -PathType Leaf)) {
        throw "Extract the complete ZIP into E:\test\bb. Required file missing: $Relative"
    }
}
if (@(Get-Process -Name 'soh', 'MSBuild', 'cl' -ErrorAction SilentlyContinue).Count -gt 0) {
    throw 'Close SoH and finish/stop any running build before applying this fix. No existing files changed.'
}
$Plans = [Collections.Generic.List[object]]::new()
foreach ($File in $Manifest.files) {
    $Relative = [string]$File.path
    if ([IO.Path]::IsPathRooted($Relative) -or $Relative.Split('/') -contains '..') { throw 'Unsafe payload path.' }
    $Source = Join-Path $Payload $Relative
    $Target = Join-Path $Root $Relative
    if (-not (Test-Path -LiteralPath $Source -PathType Leaf) -or (Get-Hash $Source) -ne $File.sha256) {
        throw "Payload integrity failure: $Relative"
    }
    if (Test-Path -LiteralPath $Target -PathType Leaf) {
        if ($File.mode -eq 'missing_only') { continue }
        $Hash = Get-GitTextHash $Target
        if ($File.allowed_git_text_hashes -notcontains $Hash) {
            throw "Unrecognized local edits in $Relative. Nothing was overwritten. Keep this file for comparison."
        }
        if ((Get-Hash $Target) -eq $File.sha256) { continue }
    }
    $Plans.Add([pscustomobject]@{ Target=$Target; Relative=$Relative; Bytes=[IO.File]::ReadAllBytes($Source) })
}

# Repair only the asset target block in the user's actual CMakeLists, retaining
# dependency paths, toolchain, runtime flags, and every unrelated local change.
$CMakePath = Join-Path $Root 'CMakeLists.txt'
$Before = [IO.File]::ReadAllText($CMakePath)
$CMake = $Before.Replace("`r`n", "`n")
$Include = 'include("${CMAKE_CURRENT_SOURCE_DIR}/tools/cmake/SohExtremeAssets.cmake")'
if (-not $CMake.Contains($Include)) {
    $Pattern = '(?ms)^[ \t]*add_executable[ \t]*\([ \t]*soh-o2r-packer\b.*?^[ \t]*add_custom_target[ \t]*\([ \t]*GenerateSohOtr\b.*?^[ \t]*\)[ \t]*(?=\n|$)'
    $Matches = [regex]::Matches($CMake, $Pattern)
    if ($Matches.Count -ne 1) { throw 'The packer/GenerateSohOtr CMake block is not recognized. No files overwritten.' }
    $Match = $Matches[0]
    $CMake = $CMake.Substring(0, $Match.Index) + $Include + $CMake.Substring($Match.Index + $Match.Length)
}
# The build-time tools must never be pulled into soh.exe by its recursive glob.
$Filter = 'list(FILTER soh__ EXCLUDE REGEX "(^|/)assets/tools/")'
if (-not $CMake.Contains($Filter)) {
    $Globs = [regex]::Matches($CMake, '(?ms)^[ \t]*file[ \t]*\([ \t]*GLOB_RECURSE[ \t]+soh__\b.*?\)')
    if ($Globs.Count -ne 1) { throw 'The soh__ source glob is not recognized. No files overwritten.' }
    $At = $Globs[0].Index + $Globs[0].Length
    $CMake = $CMake.Insert($At, "`n# SOH-EXTREME: build tools are separate executables.`n" + $Filter)
}
if ($CMake -ne $Before) {
    $Plans.Add([pscustomobject]@{ Target=$CMakePath; Relative='CMakeLists.txt'; Bytes=$Utf8.GetBytes($CMake) })
}

# Insert the canonical AP source build into the existing pipeline rather than
# replacing the user's full build.cmd. Preserve AP asset installation and copies.
$BuildPath = Join-Path $Root 'build.cmd'
$OriginalBuild = [IO.File]::ReadAllText($BuildPath)
$Build = $OriginalBuild.Replace("`r`n", "`n")
$StartMarker = 'rem BEGIN SOH-EXTREME CANONICAL APWORLD BUILD'
$EndMarker = 'rem END SOH-EXTREME CANONICAL APWORLD BUILD'
$Block = @'
rem BEGIN SOH-EXTREME CANONICAL APWORLD BUILD
rem _CL_ is appended after generated compiler arguments; retain other user flags.
set "_CL_=%_CL_% /FS /MP1"
echo Verifying/building Archipelago directly from arvhipelago...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\build_standalone_apworld.ps1"
if errorlevel 1 goto :fail
rem END SOH-EXTREME CANONICAL APWORLD BUILD

'@
if ($Build.Contains($StartMarker)) {
    $BlockPattern = '(?ms)^' + [regex]::Escape($StartMarker) + '.*?^' + [regex]::Escape($EndMarker) + '[ \t]*\n*'
    $Hit = [regex]::Matches($Build, $BlockPattern)
    if ($Hit.Count -ne 1) { throw 'Duplicate or incomplete APWorld build block. No files overwritten.' }
    $Build = $Build.Substring(0, $Hit[0].Index) + $Block.TrimEnd() + "`n`n" + $Build.Substring($Hit[0].Index + $Hit[0].Length)
} else {
    $At = [regex]::Match($Build, '(?m)^echo \[0/6\]')
    if (-not $At.Success -or $Build -notmatch '(?m)^:fail\s*$') {
        throw 'The existing build.cmd pipeline is not recognized. No files overwritten.'
    }
    $Build = $Build.Insert($At.Index, $Block.TrimEnd() + "`n`n")
}
# Keep an existing one/two/three-job preference; lower old eight-job scripts to 3.
$ParallelPattern = '(?m)^([^\n]*cmake --build[^\n]*--target soh[ \t]+[^\n]*--parallel[ \t]+)(\d+)'
$Build = [regex]::Replace($Build, $ParallelPattern, [Text.RegularExpressions.MatchEvaluator]{
    param($Match)
    return $Match.Groups[1].Value + [string][Math]::Min(3, [int]$Match.Groups[2].Value)
})
# Avoid an unrelated old script version looking like the installed world version.
$Build = [regex]::Replace($Build, '(?m)^echo SOH-EXTREME [0-9.]+ - SAFE BUILD$', 'echo SOH-EXTREME - SAFE BUILD / CANONICAL AP SOURCE')
$Build = $Build.Replace("`n", "`r`n")
if ($Build -ne $OriginalBuild) {
    $Plans.Add([pscustomobject]@{ Target=$BuildPath; Relative='build.cmd'; Bytes=$Utf8.GetBytes($Build) })
}

# No arbitrary deletion: back up every file that will change, and roll back
# file-write failures. All backups live outside any soh/src compiler glob.
$BackupRoot = Join-Path $Root ('patch-backups\build-source-fix-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
New-Item -ItemType Directory -Path $BackupRoot -Force | Out-Null
$Records = [Collections.Generic.List[object]]::new()
foreach ($Plan in $Plans) {
    $Existed = Test-Path -LiteralPath $Plan.Target -PathType Leaf
    $Backup = Join-Path $BackupRoot $Plan.Relative
    if ($Existed) {
        New-Item -ItemType Directory -Path (Split-Path -Parent $Backup) -Force | Out-Null
        Copy-Item -LiteralPath $Plan.Target -Destination $Backup -Force
    }
    $Records.Add([pscustomobject]@{ Target=$Plan.Target; Backup=$Backup; Existed=$Existed })
}
[IO.File]::WriteAllText((Join-Path $BackupRoot 'restore-manifest.json'), ($Records | ConvertTo-Json -Depth 4), $Utf8)
$Written = [Collections.Generic.List[object]]::new()
try {
    for ($Index = 0; $Index -lt $Plans.Count; ++$Index) {
        $Plan = $Plans[$Index]
        New-Item -ItemType Directory -Path (Split-Path -Parent $Plan.Target) -Force | Out-Null
        $Written.Add($Records[$Index])
        [IO.File]::WriteAllBytes($Plan.Target, $Plan.Bytes)
    }
} catch {
    $OriginalError = $_
    for ($Index = $Written.Count - 1; $Index -ge 0; --$Index) {
        $Record = $Written[$Index]
        try {
            if ($Record.Existed) { Copy-Item -LiteralPath $Record.Backup -Destination $Record.Target -Force }
            elseif (Test-Path -LiteralPath $Record.Target -PathType Leaf) { Remove-Item -LiteralPath $Record.Target -Force }
        } catch { Write-Warning "Rollback failed for $($Record.Target); original is in $BackupRoot" }
    }
    throw "File installation failed; rollback attempted. $OriginalError"
}
Write-Host ''
Write-Host 'Installed build-path repair and complete 0.11.22 arvhipelago source.'
Write-Host "Backup: $BackupRoot"
Write-Host 'Gameplay logic version remains 0.11.22. No settings, saves or received-item history were reset.'
if (-not [string]::IsNullOrWhiteSpace($ArchipelagoRoot)) { $env:SOH_EXTREME_AP_ROOT = $ArchipelagoRoot }
if ($SkipBuild) {
    Write-Host 'Build skipped by request. Run build.cmd to package/verify/install the APWorld and rebuild the game.'
    exit 0
}
Push-Location $Root
try {
    & $env:ComSpec /d /c 'call build.cmd'
    $Result = $LASTEXITCODE
} finally { Pop-Location }
if ($Result -ne 0) {
    throw 'Source/build fix installed, but build.cmd failed. Keep the FIRST error. Do not launch an older executable.'
}
Write-Host ''
Write-Host 'Build and source-package parity checks completed.'
Write-Host 'Restart Universal Tracker to load the installed world.'
Write-Host "Launch: $(Join-Path $Root 'soh.exe')"
