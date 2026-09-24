param(
    [Parameter(Mandatory=$true)][string]$ProjectRoot,
    [string]$BuildDirectory = 'build-vs'
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0
$utf8 = New-Object System.Text.UTF8Encoding($false)
$marker = 'SOH-EXTREME APCpp safety hotfix 0.11.21a active'

function Same-Path([string]$A, [string]$B) {
    return [string]::Equals([IO.Path]::GetFullPath($A).TrimEnd([char[]]'\/'),
                           [IO.Path]::GetFullPath($B).TrimEnd([char[]]'\/'),
                           [StringComparison]::OrdinalIgnoreCase)
}
function Assert-GameClosed([string]$Root) {
    foreach ($process in @(Get-Process -Name 'soh' -ErrorAction SilentlyContinue)) {
        # Do not terminate the game, and do not mutate a running instance's files.
        try { $path = $process.Path } catch { throw 'Close all SoH game windows before applying the hotfix.' }
        if (-not $path -or $path.StartsWith($Root.TrimEnd([char[]]'\/') + '\', [StringComparison]::OrdinalIgnoreCase)) {
            throw 'Close Ship of Harkinian (including the crash dialog), then run this helper again.'
        }
    }
}
function Install-CheckedCopy([string]$Source, [string]$Destination) {
    if (Same-Path $Source $Destination) { return }
    $expected = (Get-FileHash -LiteralPath $Source -Algorithm SHA256).Hash
    if (Test-Path -LiteralPath $Destination -PathType Leaf) {
        if ((Get-FileHash -LiteralPath $Destination -Algorithm SHA256).Hash -eq $expected) { return }
        $backup = $Destination + '.before-soh-0.11.21a'
        if (-not (Test-Path -LiteralPath $backup)) {
            Copy-Item -LiteralPath $Destination -Destination $backup
        }
    }
    $temp = $Destination + '.soh-hotfix-' + [guid]::NewGuid().ToString('N') + '.tmp'
    try {
        Copy-Item -LiteralPath $Source -Destination $temp
        if ((Get-FileHash -LiteralPath $temp -Algorithm SHA256).Hash -ne $expected) {
            throw ('Copy verification failed: ' + $Destination)
        }
        Move-Item -LiteralPath $temp -Destination $Destination -Force
    } finally {
        if (Test-Path -LiteralPath $temp) { Remove-Item -LiteralPath $temp -Force }
    }
    if ((Get-FileHash -LiteralPath $Destination -Algorithm SHA256).Hash -ne $expected) {
        throw ('Deployed file verification failed: ' + $Destination)
    }
}

try {
    $root = (Resolve-Path -LiteralPath $ProjectRoot).Path.TrimEnd([char[]]'\/')
    $build = if ([IO.Path]::IsPathRooted($BuildDirectory)) { $BuildDirectory } else { Join-Path $root $BuildDirectory }
    $cmakeFile = Join-Path $root 'CMakeLists.txt'
    $cacheFile = Join-Path $build 'CMakeCache.txt'
    if (-not (Test-Path -LiteralPath $cmakeFile -PathType Leaf) -or
        -not (Test-Path -LiteralPath $cacheFile -PathType Leaf)) {
        throw 'Extract into your existing bb project root. Its CMakeLists.txt and configured build-vs folder are required.'
    }
    $cmake = (Get-Command cmake -ErrorAction Stop).Source
    Assert-GameClosed $root
    $cache = [IO.File]::ReadAllText($cacheFile)
    $home = [regex]::Match($cache, '(?m)^CMAKE_HOME_DIRECTORY:INTERNAL=([^\r\n]+)')
    if (-not $home.Success -or -not (Same-Path $home.Groups[1].Value $root)) {
        throw 'The build cache belongs to a different source directory. No cache was changed.'
    }

    Write-Host '[1/4] Installing the guarded APCpp configure-time repair...'
    $text = [IO.File]::ReadAllText($cmakeFile)
    $hook = 'include("${CMAKE_CURRENT_SOURCE_DIR}/CMake/SohExtremeAPCppSafety.cmake")'
    if (-not $text.Contains($hook)) {
        if ($text.Contains('SohExtremeAPCppSafety.cmake')) {
            throw 'A different APCpp safety hook already exists. No CMake source was overwritten.'
        }
        $matches = [regex]::Matches($text, 'FetchContent_MakeAvailable\s*\(\s*apcpp\s*\)', [Text.RegularExpressions.RegexOptions]::IgnoreCase)
        if ($matches.Count -ne 1) {
            throw 'Expected one FetchContent_MakeAvailable(apcpp) in CMakeLists.txt. No CMake source was overwritten.'
        }
        $match = $matches[0]
        $newline = if ($text.Contains("`r`n")) { "`r`n" } else { "`n" }
        $insertion = $newline + '    # SOH-EXTREME 0.11.21a: reapplies after dependency refreshes.' + $newline + '    ' + $hook
        $text = $text.Insert($match.Index + $match.Length, $insertion)
        $backup = $cmakeFile + '.before-soh-0.11.21a'
        if (-not (Test-Path -LiteralPath $backup)) { Copy-Item -LiteralPath $cmakeFile -Destination $backup }
        [IO.File]::WriteAllText($cmakeFile, $text, $utf8)
    }

    Write-Host '[2/4] Refreshing the existing configuration (no dependency folders deleted)...'
    & $cmake -S $root -B $build
    if ($LASTEXITCODE -ne 0) { throw ('CMake configuration failed: ' + $LASTEXITCODE) }

    Write-Host '[3/4] Rebuilding APCpp.dll and soh.exe with one build worker...'
    & $cmake --build $build --config Release --target APCpp soh --parallel 1
    if ($LASTEXITCODE -ne 0) { throw ('Build failed: ' + $LASTEXITCODE) }

    Write-Host '[4/4] Verifying and deploying the actual CMake target outputs...'
    $manifest = Join-Path $build 'soh-extreme-runtime-Release.txt'
    if (-not (Test-Path -LiteralPath $manifest -PathType Leaf)) { throw 'CMake did not emit the runtime output manifest.' }
    $paths = @([IO.File]::ReadAllLines($manifest) | Where-Object { $_.Trim() -ne '' })
    if ($paths.Count -ne 2) { throw 'Invalid CMake runtime output manifest.' }
    $exe = [IO.Path]::GetFullPath($paths[0])
    $dll = [IO.Path]::GetFullPath($paths[1])
    if ([IO.Path]::GetFileName($exe) -ine 'soh.exe' -or [IO.Path]::GetFileName($dll) -ine 'APCpp.dll' -or
        -not (Test-Path -LiteralPath $exe -PathType Leaf) -or -not (Test-Path -LiteralPath $dll -PathType Leaf)) {
        throw 'The configured Release EXE or APCpp DLL output is missing.'
    }
    $binary = [Text.Encoding]::ASCII.GetString([IO.File]::ReadAllBytes($dll))
    if (-not $binary.Contains($marker)) {
        throw 'The built APCpp.dll does not contain the hotfix marker. No runtime copies were replaced.'
    }
    Assert-GameClosed $root
    $destinations = @($root, [IO.Path]::GetDirectoryName($exe))
    # The supplied crash log loaded APCpp.dll from x64\Release2. Update that
    # existing runtime too; otherwise a successful rebuild leaves the crashing
    # DLL beside the EXE the player actually launches.
    $release2 = Join-Path $root 'x64\Release2'
    if (Test-Path -LiteralPath (Join-Path $release2 'soh.exe') -PathType Leaf) { $destinations += $release2 }
    $destinations = @($destinations | Select-Object -Unique)
    $report = @('SOH-EXTREME 0.11.21a', ('EXE source: ' + $exe), ('DLL source: ' + $dll),
        ('EXE SHA256: ' + (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash),
        ('DLL SHA256: ' + (Get-FileHash -LiteralPath $dll -Algorithm SHA256).Hash))
    foreach ($destination in $destinations) {
        Install-CheckedCopy $exe (Join-Path $destination 'soh.exe')
        Install-CheckedCopy $dll (Join-Path $destination 'APCpp.dll')
        foreach ($source in @($exe, $dll)) {
            $pdb = [IO.Path]::ChangeExtension($source, '.pdb')
            if (Test-Path -LiteralPath $pdb -PathType Leaf) {
                Install-CheckedCopy $pdb (Join-Path $destination ([IO.Path]::GetFileName($pdb)))
            }
        }
        $report += ('Verified runtime: ' + $destination)
        Write-Host ('Updated EXE and APCpp.dll: ' + $destination)
    }
    [IO.File]::WriteAllLines((Join-Path $root 'AP-CRASH-HOTFIX-DEPLOYMENT.txt'), $report, $utf8)
    Write-Host ('On startup, the game log should include: AP: ' + $marker)
    Write-Host 'No AP-world, asset, save, or seed change is required.'
    exit 0
} catch {
    Write-Error $_ -ErrorAction Continue
    exit 1
}
