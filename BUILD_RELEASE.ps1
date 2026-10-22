#requires -Version 5.1
[CmdletBinding()]
param(
    [string]$RepositoryPath,
    [string]$BuildDirectory
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$script:PackageRoot = $PSScriptRoot
$script:BuildRecordRoot = $null


function Get-NormalizedPath {
    param([Parameter(Mandatory = $true)][string]$Path)
    $expanded = [Environment]::ExpandEnvironmentVariables($Path.Trim().Trim('"'))
    $full = [IO.Path]::GetFullPath($expanded)
    if ($full -eq [IO.Path]::GetPathRoot($full)) { return $full }
    return $full.TrimEnd([char[]]@('\', '/'))
}

function Test-SourceRepository {
    param([string]$Path)
    if ([string]::IsNullOrWhiteSpace($Path)) { return $false }
    return ([IO.File]::Exists((Join-Path $Path 'CMakeLists.txt')) -and
            [IO.File]::Exists((Join-Path $Path 'soh\Network\Archipelago\EntranceRuntime.inc')))
}

function Find-SourceRepository {
    if (-not [string]::IsNullOrWhiteSpace($RepositoryPath)) {
        $explicit = Get-NormalizedPath $RepositoryPath
        if (-not (Test-SourceRepository $explicit)) {
            throw "The supplied source folder must contain CMakeLists.txt and soh\Network\Archipelago\EntranceRuntime.inc: $explicit"
        }
        return $explicit
    }
    $directory = [IO.DirectoryInfo](Get-NormalizedPath $script:PackageRoot)
    while ($null -ne $directory) {
        if (Test-SourceRepository $directory.FullName) { return $directory.FullName }
        $directory = $directory.Parent
    }
    Write-Host 'The source files are not inside an existing SOH-EXTREME source repository.'
    while ($true) {
        $answer = Read-Host 'Enter your existing source folder (for example E:\test\bb), or press Enter to cancel'
        if ([string]::IsNullOrWhiteSpace($answer)) { throw 'Cancelled before changing source files.' }
        try {
            $candidate = Get-NormalizedPath $answer
            if (Test-SourceRepository $candidate) { return $candidate }
        } catch {
            Write-Host ('Invalid folder: ' + $_.Exception.Message) -ForegroundColor Yellow
            continue
        }
        Write-Host 'That folder does not contain the required source files. Choose the repository root.' -ForegroundColor Yellow
    }
}

function Get-SafeRelativePath {
    param([string]$Path)
    if ([string]::IsNullOrWhiteSpace($Path)) { throw 'The manifest contains an empty file path.' }
    $relative = $Path.Replace('\', '/')
    if ([IO.Path]::IsPathRooted($relative) -or $relative.Contains(':')) {
        throw "The manifest contains a non-relative file path: $Path"
    }
    foreach ($segment in $relative.Split('/')) {
        if ([string]::IsNullOrEmpty($segment) -or $segment -eq '.' -or $segment -eq '..' -or
            $segment.EndsWith(' ') -or $segment.EndsWith('.') -or
            $segment.IndexOfAny([IO.Path]::GetInvalidFileNameChars()) -ge 0 -or
            $segment -match '^(?i:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)') {
            throw "The manifest contains an invalid file path: $Path"
        }
    }
    return $relative
}

function Join-SafePath {
    param([string]$Root, [string]$Relative)
    $prefix = Get-NormalizedPath $Root
    if (-not $prefix.EndsWith([string][IO.Path]::DirectorySeparatorChar)) {
        $prefix += [IO.Path]::DirectorySeparatorChar
    }
    $full = [IO.Path]::GetFullPath([IO.Path]::Combine($Root, $Relative.Replace('/', '\')))
    if (-not $full.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "A manifest path escapes its destination folder: $Relative"
    }
    return $full
}

function Get-Sha256 {
    param([string]$Path)
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Assert-CopiedSourceFiles {
    param([string]$Repository)
    $manifestPath = Join-Path $script:PackageRoot 'SOURCE_FILES.json'
    $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($null -eq $manifest -or $null -eq $manifest.PSObject.Properties['version'] -or
        $null -eq $manifest.PSObject.Properties['files'] -or [string]$manifest.version -ne '1.8.15') {
        throw 'The source manifest is missing required fields or is not version 1.8.15.'
    }
    $files = @($manifest.files)
    if ($files.Count -eq 0) { throw 'The source manifest contains no files.' }
    $seen = @{}
    foreach ($entry in $files) {
        $relative = Get-SafeRelativePath ([string]$entry.path)
        if ($seen.ContainsKey($relative)) { throw "Duplicate source path: $relative" }
        $seen[$relative] = $true
        $expected = [string]$entry.sha256
        if ($expected -notmatch '^[0-9a-fA-F]{64}$') { throw "Invalid source SHA-256: $relative" }
        $source = Join-SafePath $Repository $relative
        if (-not [IO.File]::Exists($source)) {
            throw "An updated source file is missing: $source`nExtract the included source directories into your existing repository root before building."
        }
        if ((Get-Sha256 $source) -eq $expected.ToLowerInvariant()) { continue }
        # A CMake packaging target can rewrite ZIP metadata while retaining
        # the exact current APWorld files. No earlier release is accepted here.
        if ($relative -eq 'archipelago/soh_extreme.apworld' -and
            $null -ne $entry.PSObject.Properties['zip_contents']) {
            $snapshots = @(Get-AcceptedZipContentSnapshots -Relative $relative -Snapshots @($entry.zip_contents))
            if (Test-AcceptedZipContents -Path $source -Snapshots $snapshots) { continue }
        }
        throw "The updated source file does not match version 1.8.15: $source`nExtract the included source directories into this repository before building."
    }
    Write-Host ('Verified ' + $files.Count + ' source files for version 1.8.15.') -ForegroundColor Green
}

function Get-AcceptedZipContentSnapshots {
    param([string]$Relative, [object]$Snapshots)
    # Only this generated archive may differ in ZIP packaging metadata.
    # Every other source file remains subject to its exact whole-file hashes.
    if (-not [string]::Equals($Relative, 'archipelago/soh_extreme.apworld', [StringComparison]::Ordinal)) {
        throw "ZIP content acceptance is not permitted for this manifest path: $Relative"
    }
    if ($Snapshots -isnot [array] -or $Snapshots.Count -eq 0) {
        throw "The accepted ZIP contents must be a nonempty array: $Relative"
    }
    $validated = [Collections.Generic.List[object]]::new()
    foreach ($snapshot in $Snapshots) {
        if ($null -eq $snapshot -or $null -eq $snapshot.PSObject.Properties['entries'] -or
            $snapshot.entries -isnot [array] -or $snapshot.entries.Count -eq 0) {
            throw "An accepted ZIP snapshot must contain a nonempty entries array: $Relative"
        }
        $entries = [Collections.Generic.Dictionary[string, object]]::new([StringComparer]::Ordinal)
        foreach ($entry in $snapshot.entries) {
            foreach ($field in @('path', 'size_bytes', 'sha256')) {
                if ($null -eq $entry -or $null -eq $entry.PSObject.Properties[$field]) {
                    throw "An accepted ZIP entry is missing '$field': $Relative"
                }
            }
            if ($entry.path -isnot [string] -or [string]::IsNullOrEmpty($entry.path) -or
                $entry.path.EndsWith('/', [StringComparison]::Ordinal)) {
                throw "An accepted ZIP entry has an invalid file name: $Relative"
            }
            if (($entry.size_bytes -isnot [int] -and $entry.size_bytes -isnot [long]) -or
                $entry.size_bytes -lt 0) {
                throw "An accepted ZIP entry has an invalid uncompressed size: $Relative"
            }
            if ($entry.sha256 -isnot [string] -or $entry.sha256 -notmatch '^[0-9a-fA-F]{64}$') {
                throw "An accepted ZIP entry has an invalid SHA-256: $Relative"
            }
            if ($entries.ContainsKey($entry.path)) {
                throw "An accepted ZIP snapshot contains a duplicate file name: $($entry.path)"
            }
            $entries.Add($entry.path, [PSCustomObject]@{
                SizeBytes = [long]$entry.size_bytes
                Sha256 = $entry.sha256.ToLowerInvariant()
            })
        }
        $validated.Add([PSCustomObject]@{ Entries = $entries })
    }
    return $validated.ToArray()
}

function Test-AcceptedZipContents {
    param([string]$Path, [object[]]$Snapshots)
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = $null
    $hasher = $null
    try {
        $archive = [IO.Compression.ZipFile]::OpenRead($Path)
        $actual = [Collections.Generic.Dictionary[string, object]]::new([StringComparer]::Ordinal)
        foreach ($entry in $archive.Entries) {
            # ZIP directory records carry no world files and may be added or
            # omitted by a repack. File names, including case, stay exact.
            if ($entry.FullName.EndsWith('/', [StringComparison]::Ordinal)) { continue }
            if ([string]::IsNullOrEmpty($entry.FullName) -or $actual.ContainsKey($entry.FullName)) {
                return $false
            }
            $actual.Add($entry.FullName, $entry)
        }
        $hashes = [Collections.Generic.Dictionary[string, string]]::new([StringComparer]::Ordinal)
        $hasher = [Security.Cryptography.SHA256]::Create()
        foreach ($snapshot in $Snapshots) {
            $expected = $snapshot.Entries
            if ($actual.Count -ne $expected.Count) { continue }
            $matches = $true
            foreach ($name in $expected.Keys) {
                if (-not $actual.ContainsKey($name) -or
                    $actual[$name].Length -ne $expected[$name].SizeBytes) {
                    $matches = $false
                    break
                }
            }
            if (-not $matches) { continue }
            foreach ($name in $expected.Keys) {
                if (-not $hashes.ContainsKey($name)) {
                    $stream = $actual[$name].Open()
                    try {
                        $hash = [BitConverter]::ToString($hasher.ComputeHash($stream)).Replace('-', '').ToLowerInvariant()
                        $hashes.Add($name, $hash)
                    } finally { $stream.Dispose() }
                }
                if ($hashes[$name] -ne $expected[$name].Sha256) {
                    $matches = $false
                    break
                }
            }
            # A single complete approved archive must match. Files from
            # different approved versions cannot be combined into a match.
            if ($matches) { return $true }
        }
        return $false
    } catch {
        # Unreadable or malformed ZIP data cannot bypass source preflight.
        return $false
    } finally {
        if ($null -ne $hasher) { $hasher.Dispose() }
        if ($null -ne $archive) { $archive.Dispose() }
    }
}

function Read-BuildCache {
    param([string]$Directory, [string]$Repository)
    $directoryPath = Get-NormalizedPath $Directory
    $path = Join-Path $directoryPath 'CMakeCache.txt'
    if (-not [IO.File]::Exists($path)) { throw "No configured CMakeCache.txt in $directoryPath" }
    $values = @{}
    foreach ($line in [IO.File]::ReadAllLines($path)) {
        if ($line -match '^([^#/][^:=]*):[^=]*=(.*)$') { $values[$matches[1]] = $matches[2] }
    }
    if (-not $values.ContainsKey('CMAKE_HOME_DIRECTORY') -or -not $values.ContainsKey('CMAKE_GENERATOR')) {
        throw "The cache is incomplete: $path"
    }
    $source = Get-NormalizedPath ([string]$values['CMAKE_HOME_DIRECTORY'])
    if (-not $source.Equals((Get-NormalizedPath $Repository), [StringComparison]::OrdinalIgnoreCase)) {
        throw "This cache belongs to another source folder ($source): $path"
    }
    [PSCustomObject]@{ Directory = $directoryPath; CachePath = $path; Values = $values; Generator = [string]$values['CMAKE_GENERATOR'] }
}

function Select-BuildCache {
    param([string]$Repository)
    if (-not [string]::IsNullOrWhiteSpace($BuildDirectory)) {
        $supplied = $BuildDirectory.Trim().Trim('"')
        if (-not [IO.Path]::IsPathRooted($supplied)) { $supplied = Join-Path $Repository $supplied }
        return Read-BuildCache -Directory $supplied -Repository $Repository
    }
    $candidates = [Collections.Generic.List[string]]::new()
    foreach ($name in @('build-vs', 'build', 'build-vs2022')) { $candidates.Add((Join-Path $Repository $name)) }
    $candidates.Add($Repository)
    foreach ($directory in @(Get-ChildItem -LiteralPath $Repository -Directory -ErrorAction SilentlyContinue)) {
        if ($directory.Name -like 'build*') {
            $candidates.Add($directory.FullName)
            foreach ($child in @(Get-ChildItem -LiteralPath $directory.FullName -Directory -ErrorAction SilentlyContinue)) {
                $candidates.Add($child.FullName)
            }
        }
    }
    $outBuild = Join-Path $Repository 'out\build'
    if ([IO.Directory]::Exists($outBuild)) {
        $candidates.Add($outBuild)
        foreach ($directory in @(Get-ChildItem -LiteralPath $outBuild -Directory -ErrorAction SilentlyContinue)) {
            $candidates.Add($directory.FullName)
        }
    }
    $seen = @{}
    $valid = [Collections.Generic.List[object]]::new()
    foreach ($candidate in $candidates) {
        $path = Get-NormalizedPath $candidate
        if ($seen.ContainsKey($path)) { continue }
        $seen[$path] = $true
        if (-not [IO.File]::Exists((Join-Path $path 'CMakeCache.txt'))) { continue }
        try { $valid.Add((Read-BuildCache -Directory $path -Repository $Repository)) }
        catch { Write-Host ('Skipped cache: ' + $_.Exception.Message) -ForegroundColor Yellow }
    }
    if ($valid.Count -eq 1) { return $valid[0] }
    if ($valid.Count -gt 1) {
        Write-Host 'More than one configured build directory matches this repository:'
        for ($index = 0; $index -lt $valid.Count; ++$index) {
            Write-Host ('  [{0}] {1} ({2})' -f ($index + 1), $valid[$index].Directory, $valid[$index].Generator)
        }
    } else {
        Write-Host 'No configured CMake build directory was found for this source repository.' -ForegroundColor Yellow
    }
    while ($true) {
        $answer = Read-Host 'Enter a listed number or an existing build folder; press Enter to finish without building'
        if ([string]::IsNullOrWhiteSpace($answer)) { return $null }
        $selection = 0
        if ([int]::TryParse($answer, [ref]$selection) -and $selection -ge 1 -and $selection -le $valid.Count) {
            return $valid[$selection - 1]
        }
        try {
            $folder = $answer.Trim().Trim('"')
            if (-not [IO.Path]::IsPathRooted($folder)) { $folder = Join-Path $Repository $folder }
            return Read-BuildCache -Directory $folder -Repository $Repository
        } catch { Write-Host $_.Exception.Message -ForegroundColor Yellow }
    }
}

function Find-CMake {
    param([object]$Cache)
    $candidates = [Collections.Generic.List[string]]::new()
    if ($Cache.Values.ContainsKey('CMAKE_COMMAND')) { $candidates.Add([string]$Cache.Values['CMAKE_COMMAND']) }
    foreach ($command in @(Get-Command -Name 'cmake.exe', 'cmake' -CommandType Application -ErrorAction SilentlyContinue)) {
        $candidates.Add($command.Source)
    }
    foreach ($root in @($env:ProgramFiles, ${env:ProgramFiles(x86)})) {
        if (-not [string]::IsNullOrWhiteSpace($root)) { $candidates.Add((Join-Path $root 'CMake\bin\cmake.exe')) }
    }
    foreach ($candidate in $candidates) {
        if (-not [string]::IsNullOrWhiteSpace($candidate) -and [IO.File]::Exists($candidate)) { return $candidate }
    }
    $installerRoot = ${env:ProgramFiles(x86)}
    if (-not [string]::IsNullOrWhiteSpace($installerRoot)) {
        $vswhere = Join-Path $installerRoot 'Microsoft Visual Studio\Installer\vswhere.exe'
        if ([IO.File]::Exists($vswhere)) {
            $installations = @(& $vswhere -all -products '*' -property installationPath)
            if ($LASTEXITCODE -eq 0) {
                foreach ($installation in $installations) {
                    if ([string]::IsNullOrWhiteSpace([string]$installation)) { continue }
                    $installationPath = ([string]$installation).Trim()
                    $candidate = Join-Path $installationPath 'Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe'
                    if ([IO.File]::Exists($candidate)) { return $candidate }
                }
            }
        }
    }
    return $null
}

function Assert-ReleaseConfiguration {
    param([object]$Cache)
    if ($Cache.Values.ContainsKey('CMAKE_CONFIGURATION_TYPES') -and
        -not [string]::IsNullOrWhiteSpace([string]$Cache.Values['CMAKE_CONFIGURATION_TYPES'])) {
        if (([string]$Cache.Values['CMAKE_CONFIGURATION_TYPES']).Split(';') -notcontains 'Release') {
            throw 'This build cache does not have a Release configuration. Select an existing Release build directory.'
        }
    } elseif (-not $Cache.Values.ContainsKey('CMAKE_BUILD_TYPE') -or
              [string]$Cache.Values['CMAKE_BUILD_TYPE'] -ne 'Release') {
        throw 'This single-configuration build cache is not configured as Release. Configure a Release build using your existing setup, then run this build helper again.'
    }
}

function Find-GameExecutable {
    param([string]$Repository, [object]$Cache, [string]$LogPath, [DateTime]$BuildStartedUtc)
    $reported = [Collections.Generic.List[string]]::new()
    foreach ($line in [IO.File]::ReadAllLines($LogPath)) {
        if ($line -match '(?i)(?:->\s*|\bexecutable\s+)(?<exe>.+?\.exe)(?:"?\s|"?$)') {
            $path = $matches['exe'].Trim().Trim('"')
            if (-not [IO.Path]::IsPathRooted($path)) { $path = Join-Path $Cache.Directory $path }
            $path = Get-NormalizedPath $path
            if ([IO.Path]::GetFileName($path) -match '^(?i:soh|soh[-_]extreme|Ship of Harkinian)\.exe$' -and
                [IO.File]::Exists($path) -and [IO.File]::GetLastWriteTimeUtc($path) -ge $BuildStartedUtc.AddSeconds(-2)) {
                $reported.Add($path)
            }
        }
    }
    $uniqueReported = @($reported | Select-Object -Unique)
    if ($uniqueReported.Count -eq 1) {
        return [PSCustomObject]@{ Path = $uniqueReported[0]; Discovery = 'build_log'; ModifiedDuringBuild = $true }
    }
    if ($uniqueReported.Count -gt 1) { return $null }
    $directories = [Collections.Generic.List[string]]::new()
    foreach ($key in @('CMAKE_RUNTIME_OUTPUT_DIRECTORY_RELEASE', 'CMAKE_RUNTIME_OUTPUT_DIRECTORY')) {
        if ($Cache.Values.ContainsKey($key)) {
            $value = [string]$Cache.Values[$key]
            if (-not [string]::IsNullOrWhiteSpace($value) -and -not $value.Contains('$<')) {
                if (-not [IO.Path]::IsPathRooted($value)) { $value = Join-Path $Cache.Directory $value }
                $directories.Add($value)
                $directories.Add((Join-Path $value 'Release'))
            }
        }
    }
    foreach ($path in @((Join-Path $Repository 'x64\Release'), (Join-Path $Cache.Directory 'Release'),
                        (Join-Path $Cache.Directory 'soh\Release'), (Join-Path $Cache.Directory 'soh'), $Cache.Directory)) {
        $directories.Add($path)
    }
    $found = [Collections.Generic.List[string]]::new()
    foreach ($directory in $directories) {
        foreach ($name in @('soh.exe', 'SOH-EXTREME.exe', 'soh_extreme.exe')) {
            $candidate = Join-Path $directory $name
            if ([IO.File]::Exists($candidate) -and
                [IO.File]::GetLastWriteTimeUtc($candidate) -ge $BuildStartedUtc.AddSeconds(-2)) {
                $found.Add((Get-NormalizedPath $candidate))
            }
        }
    }
    $unique = @($found | Select-Object -Unique)
    if ($unique.Count -eq 1) {
        return [PSCustomObject]@{ Path = $unique[0]; Discovery = 'unique_recent_output'; ModifiedDuringBuild = $true }
    }
    return $null
}

function Write-BuildReceipt {
    param([string]$Repository, [object]$Cache, [string]$CMake, [string]$LogPath,
          [DateTime]$StartedUtc, [DateTime]$FinishedUtc, [int]$ExitCode, [object]$Executable)
    $manifestPath = Join-Path $script:PackageRoot 'SOURCE_FILES.json'
    $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $nativeSources = @($manifest.files | Where-Object { ([string]$_.path).StartsWith('soh/', [StringComparison]::Ordinal) } |
        ForEach-Object {
            $sourcePath = Join-SafePath $Repository ([string]$_.path)
            $actual = Get-Sha256 $sourcePath
            [PSCustomObject]@{
                path = [string]$_.path; expected_sha256 = [string]$_.sha256
                installed_sha256 = $actual; matches_manifest = $actual -eq [string]$_.sha256
            }
        })
    $binary = $null
    if ($null -ne $Executable) {
        $binary = [PSCustomObject]@{
            path = $Executable.Path; discovery = $Executable.Discovery
            modified_during_build = $Executable.ModifiedDuringBuild
            size_bytes = ([IO.FileInfo]$Executable.Path).Length
            sha256 = Get-Sha256 $Executable.Path
            last_write_utc = [IO.File]::GetLastWriteTimeUtc($Executable.Path).ToString('o')
        }
    }
    $receipt = [ordered]@{
        version = '1.8.15'; build_helper_revision = 4
        source_repository = Get-NormalizedPath $Repository
        cmake_home_directory = [string]$Cache.Values['CMAKE_HOME_DIRECTORY']
        build_directory = $Cache.Directory; generator = $Cache.Generator
        configuration = 'Release'; clean_first = $true; parallel_jobs = 8
        cmake_executable = $CMake
        cmake_arguments = @('--build', $Cache.Directory, '--config', 'Release', '--parallel', '8', '--clean-first')
        started_utc = $StartedUtc.ToString('o'); finished_utc = $FinishedUtc.ToString('o')
        exit_code = $ExitCode; build_log = $LogPath
        source_manifest_sha256 = Get-Sha256 $manifestPath
        build_helper_sha256 = Get-Sha256 (Join-Path $script:PackageRoot 'BUILD_RELEASE.ps1')
        native_sources = $nativeSources
        all_native_sources_match_manifest = @($nativeSources | Where-Object { -not $_.matches_manifest }).Count -eq 0
        game_executable = $binary
        game_launched_by_build_helper = $false
    }
    $receiptPath = Join-Path ([IO.Path]::GetDirectoryName($LogPath)) 'build-receipt.json'
    [IO.File]::WriteAllText($receiptPath, ($receipt | ConvertTo-Json -Depth 10), [Text.UTF8Encoding]::new($false))
    return $receiptPath
}

function Build-ExistingRelease {
    param([string]$Repository)
    $cache = Select-BuildCache $Repository
    if ($null -eq $cache) {
        Write-Host 'Source files verified. Build not performed because no build directory was selected.' -ForegroundColor Yellow
        return 2
    }
    Assert-ReleaseConfiguration $cache
    $cmake = Find-CMake $cache
    if ([string]::IsNullOrWhiteSpace($cmake)) {
        Write-Host 'Source files verified. CMake was not found in PATH, the cache, Program Files, or installed Visual Studio tools.' -ForegroundColor Yellow
        Write-Host 'Use your existing CMake/Visual Studio build environment and run this build helper again.'
        return 2
    }
    $logRoot = $script:BuildRecordRoot
    if ($null -eq $logRoot) {
        $logRoot = Join-Path (Join-Path $Repository 'soh-extreme-builds') ((Get-Date -Format 'yyyyMMdd-HHmmss') + '-build-' + [Guid]::NewGuid().ToString('N').Substring(0, 8))
        [void][IO.Directory]::CreateDirectory($logRoot)
    }
    $logPath = Join-Path $logRoot 'build-release.log'
    Write-Host ('CMake: ' + $cmake)
    Write-Host ('Build directory: ' + $cache.Directory)
    Write-Host 'Cleaning the selected build outputs, then rebuilding Release with 8 parallel jobs...'
    Write-Host 'This rebuild also applies when source files already match, so older object files cannot leave an outdated executable.'
    Write-Host ('Build log: ' + $logPath)
    $startedUtc = [DateTime]::UtcNow
    $previousErrorPreference = $ErrorActionPreference
    Push-Location -LiteralPath $Repository
    try {
        # Windows PowerShell 5.1 represents redirected native stderr as error
        # records. Continue lets the complete compiler output reach the log.
        $ErrorActionPreference = 'Continue'
        # A failed native launch must not reuse an earlier vswhere exit code.
        $global:LASTEXITCODE = $null
        & $cmake --build $cache.Directory --config Release --parallel 8 --clean-first 2>&1 |
            Tee-Object -FilePath $logPath -ErrorAction Stop | ForEach-Object { Write-Host $_ }
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousErrorPreference
        Pop-Location
    }
    if ($null -eq $exitCode) { throw 'CMake did not return a build exit code.' }
    $finishedUtc = [DateTime]::UtcNow
    $executable = $null
    if ($exitCode -eq 0) {
        try {
            $executable = Find-GameExecutable -Repository $Repository -Cache $cache -LogPath $logPath -BuildStartedUtc $startedUtc
        } catch { Write-Host ('Executable discovery could not finish. Build log: ' + $logPath) -ForegroundColor Yellow }
    }
    try {
        $receipt = Write-BuildReceipt -Repository $Repository -Cache $cache -CMake $cmake -LogPath $logPath `
            -StartedUtc $startedUtc -FinishedUtc $finishedUtc -ExitCode ([int]$exitCode) -Executable $executable
        Write-Host ('Build receipt: ' + $receipt)
    } catch { Write-Host ('The build receipt could not be saved: ' + $_.Exception.Message) -ForegroundColor Yellow }
    if ($exitCode -ne 0) {
        Write-Host ('Source files verified, but the Release build failed with exit code ' + $exitCode + '.') -ForegroundColor Red
        Write-Host ('Review or share this build log: ' + $logPath)
        return [int]$exitCode
    }
    Write-Host 'Source files verified and clean Release rebuild completed successfully.' -ForegroundColor Green
    if ($null -ne $executable) {
        Write-Host ('Game executable: ' + $executable.Path) -ForegroundColor Green
        Write-Host 'Launch that exact executable for this update.'
    } else {
        Write-Host ('The rebuilt game executable could not be uniquely identified. See the target output in: ' + $logPath) -ForegroundColor Yellow
    }
    Write-Host 'The build helper has not launched the game or performed an in-game test.'
    return 0
}

try {
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) { throw 'This build helper is for Windows.' }
    Write-Host 'SOH-EXTREME 1.8.15 - clean Release rebuild (build helper revision 4)' -ForegroundColor Cyan
    Write-Host 'Close the game and finish any active build before continuing.'
    $repository = Find-SourceRepository
    Write-Host ('Source repository: ' + $repository)
    Assert-CopiedSourceFiles $repository
    $buildResult = Build-ExistingRelease $repository
    exit [int]$buildResult
} catch {
    Write-Host ('BUILD NOT COMPLETED: ' + $_.Exception.Message) -ForegroundColor Red
    exit 1
}
