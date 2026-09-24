param([Parameter(Mandatory=$true)][string]$ProjectRoot)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath $ProjectRoot).Path
$manifest = @(Get-Content -Raw -LiteralPath (Join-Path $PSScriptRoot 'enemy-soul-assets.json') | ConvertFrom-Json)
if ($manifest.Count -ne 47) { throw 'Expected the 47-entry soul texture manifest.' }
Add-Type -AssemblyName System.IO.Compression.FileSystem
$candidates = @(
    'build-vs\soh\soh.o2r', 'build-vs\soh.o2r',
    'build-vs\Release\soh.o2r', 'build-vs\soh\Release\soh.o2r'
) | ForEach-Object { Join-Path $root $_ } | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf }
$pack = $null
foreach ($candidate in $candidates) {
    $archive = [System.IO.Compression.ZipFile]::OpenRead($candidate)
    try {
        $missing = @($manifest | Where-Object {
            $entry = $archive.GetEntry($_.resource)
            $null -eq $entry -or $entry.Length -lt 4096
        })
        if ($missing.Count -eq 0) { $pack = $candidate; break }
        Write-Warning ("Archive is missing {0} packed soul textures: {1}" -f $missing.Count, $candidate)
    } finally { $archive.Dispose() }
}
if ($null -eq $pack) {
    throw 'No rebuilt soh.o2r contains all 47 textures. Ensure GenerateSohOtr packs bb\assets\custom, then retry. The old archive was not replaced.'
}
$executables = @(
    'x64\Release\soh.exe', 'build-vs\Release\soh.exe',
    'build-vs\soh\Release\soh.exe', 'build-vs\soh\soh.exe', 'build-vs\soh.exe'
) | ForEach-Object { Join-Path $root $_ } | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } |
    ForEach-Object { Get-Item -LiteralPath $_ } | Sort-Object LastWriteTimeUtc -Descending
if (@($executables).Count -eq 0) {
    throw 'The Release executable was not found in a standard build output folder. No runtime files were replaced.'
}
$exe = @($executables)[0]
$destPack = Join-Path $root 'soh.o2r'
if ([IO.Path]::GetFullPath($pack) -ne [IO.Path]::GetFullPath($destPack)) {
    Copy-Item -LiteralPath $pack -Destination $destPack -Force
}
# Both launching from bb and launching directly from the Release folder get the same assets.
$exePack = Join-Path $exe.DirectoryName 'soh.o2r'
if ([IO.Path]::GetFullPath($pack) -ne [IO.Path]::GetFullPath($exePack)) {
    Copy-Item -LiteralPath $pack -Destination $exePack -Force
}
$destExe = Join-Path $root 'soh.exe'
if ($exe.FullName -ne [IO.Path]::GetFullPath($destExe)) {
    Copy-Item -LiteralPath $exe.FullName -Destination $destExe -Force
}
Get-ChildItem -LiteralPath $exe.DirectoryName -Filter '*.dll' -File | ForEach-Object {
    $dest = Join-Path $root $_.Name
    if ($_.FullName -ne [IO.Path]::GetFullPath($dest)) { Copy-Item -LiteralPath $_.FullName -Destination $dest -Force }
}
$apDll = Join-Path $root 'build-vs\_deps\apcpp-build\Release\APCpp.dll'
if (Test-Path -LiteralPath $apDll -PathType Leaf) {
    Copy-Item -LiteralPath $apDll -Destination (Join-Path $root 'APCpp.dll') -Force
    $exeDll = Join-Path $exe.DirectoryName 'APCpp.dll'
    if ([IO.Path]::GetFullPath($apDll) -ne [IO.Path]::GetFullPath($exeDll)) {
        Copy-Item -LiteralPath $apDll -Destination $exeDll -Force
    }
}
Write-Host 'Verified: all 47 compiled soul textures are in soh.o2r.'
Write-Host ("Game: {0}" -f $destExe)
Write-Host ("Assets: {0}" -f $destPack)
