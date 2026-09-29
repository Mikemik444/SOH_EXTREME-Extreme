[CmdletBinding()]
param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$BuildRoot = '',
    [string]$Destination = ''
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
function Get-RuntimeSHA256([string]$Path) {
    $algorithm = [Security.Cryptography.SHA256]::Create()
    $stream = [IO.File]::OpenRead($Path)
    try {
        return [BitConverter]::ToString($algorithm.ComputeHash($stream))
    } finally {
        $stream.Dispose()
        $algorithm.Dispose()
    }
}
if (-not $BuildRoot) { $BuildRoot = Join-Path $ProjectRoot 'build-vs' }
if (-not $Destination) { $Destination = $ProjectRoot }
$manifest = Join-Path $BuildRoot 'soh-extreme-runtime-Release.txt'
if (-not (Test-Path -LiteralPath $manifest -PathType Leaf)) {
    throw "CMake runtime manifest missing: $manifest. Configure and build the patched source first."
}
$paths = @(Get-Content -LiteralPath $manifest | Where-Object { $_.Trim() })
if ($paths.Count -ne 2 -or [IO.Path]::GetFileName($paths[0]) -ne 'soh.exe' -or
    [IO.Path]::GetFileName($paths[1]) -ne 'APCpp.dll') {
    throw 'The runtime manifest must contain the exact soh.exe and APCpp.dll target paths.'
}
# Validate the complete pair before replacing either destination file.
foreach ($path in $paths) {
    if (-not [IO.Path]::IsPathRooted($path) -or -not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Built runtime file missing: $path"
    }
}
if (-not (Test-Path -LiteralPath $Destination -PathType Container)) {
    throw "Runtime destination does not exist: $Destination"
}
foreach ($path in $paths) {
    $target = Join-Path $Destination ([IO.Path]::GetFileName($path))
    if ([IO.Path]::GetFullPath($path) -ne [IO.Path]::GetFullPath($target)) {
        Copy-Item -LiteralPath $path -Destination $target -Force
    }
    if ((Get-RuntimeSHA256 $path) -ne (Get-RuntimeSHA256 $target)) {
        throw "Runtime copy verification failed: $target"
    }
    Write-Host "Verified runtime: $target"
}
