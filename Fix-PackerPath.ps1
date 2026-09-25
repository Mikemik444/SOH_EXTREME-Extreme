[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$Root = $PSScriptRoot
$Path = Join-Path $Root 'CMakeLists.txt'
if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
    throw 'Extract the complete ZIP into your source root (E:\test\bb), next to CMakeLists.txt.'
}
if (@(Get-Process -Name 'soh', 'MSBuild', 'cl' -ErrorAction SilentlyContinue).Count -gt 0) {
    throw 'Close the game and finish any active build before repairing its CMake configuration.'
}
foreach ($Relative in @('tools\cmake\SohExtremeAssets.cmake', 'tools\cmake\PackSohExtremeAssets.cmake')) {
    if (-not (Test-Path -LiteralPath (Join-Path $Root $Relative) -PathType Leaf)) {
        throw "Missing repair module: $Relative. Extract the complete ZIP."
    }
}
$Packer = ''
foreach ($Relative in @('soh\assets\tools\soh-o2r-packer', 'assets\tools\soh-o2r-packer')) {
    $Candidate = Join-Path $Root $Relative
    $Complete = $true
    foreach ($Name in @('main.cpp', 'PngTexture.cpp', 'PngTexture.h')) {
        if (-not (Test-Path -LiteralPath (Join-Path $Candidate $Name) -PathType Leaf)) { $Complete = $false }
    }
    if ($Complete) { $Packer = $Candidate; break }
}
if ([string]::IsNullOrEmpty($Packer)) {
    throw 'The three packer source files are missing from both supported folders. No CMake changes were made.'
}
$Before = [IO.File]::ReadAllText($Path)
$Text = $Before.Replace("`r`n", "`n")
$Include = 'include("${CMAKE_CURRENT_SOURCE_DIR}/tools/cmake/SohExtremeAssets.cmake")'
if (-not $Text.Contains($Include)) {
    # Replace only the packer + GenerateSohOtr block, not unrelated dependencies,
    # runtime/compiler flags, or other targets in the user's existing CMake file.
    $Pattern = '(?ms)^[ \t]*add_executable[ \t]*\([ \t]*soh-o2r-packer\b.*?^[ \t]*add_custom_target[ \t]*\([ \t]*GenerateSohOtr\b.*?^[ \t]*\)[ \t]*(?=\n|$)'
    $Hits = [regex]::Matches($Text, $Pattern)
    if ($Hits.Count -ne 1) {
        throw 'The existing asset-target block is not recognized. No CMake changes were made.'
    }
    $Hit = $Hits[0]
    $Text = $Text.Substring(0, $Hit.Index) + $Include + $Text.Substring($Hit.Index + $Hit.Length)
}
$Filter = 'list(FILTER soh__ EXCLUDE REGEX "(^|/)assets/tools/")'
if (-not $Text.Contains($Filter)) {
    # Prevent nested packer and torch-cli main.cpp from becoming soh.exe sources.
    $Hits = [regex]::Matches($Text, '(?ms)^[ \t]*file[ \t]*\([ \t]*GLOB_RECURSE[ \t]+soh__\b.*?\)')
    if ($Hits.Count -ne 1) { throw 'The soh__ source glob is not recognized. No CMake changes were made.' }
    $Text = $Text.Insert($Hits[0].Index + $Hits[0].Length,
        "`n# Build tools belong to their own executables.`n" + $Filter)
}
# Reapplying makes no further changes. Preserve the original line-ending style.
if ($Before.Contains("`r`n")) { $Text = $Text.Replace("`n", "`r`n") }
if ($Text -ne $Before) {
    $BackupDir = Join-Path $Root ('patch-backups\packer-path-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
    New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
    $Backup = Join-Path $BackupDir 'CMakeLists.txt'
    Copy-Item -LiteralPath $Path -Destination $Backup
    try {
        [IO.File]::WriteAllText($Path, $Text, [Text.UTF8Encoding]::new($false))
    } catch {
        Copy-Item -LiteralPath $Backup -Destination $Path -Force
        throw
    }
    Write-Host "CMake backup: $Backup"
} else {
    Write-Host 'The packer configuration is already repaired.'
}
Write-Host "Packer sources: $Packer"
Write-Host 'CMake will stage the complete nested custom assets plus existing root-level overlays.'
Write-Host 'Packer-path repair complete. Run your existing build.cmd to rebuild the game.'
Write-Host 'No APWorld was packaged or installed, and build.cmd was not changed.'
