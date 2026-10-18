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
$script:BackupRoot = $null
$script:RestoreManifest = $null

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
    Write-Host 'The package is not inside an existing SOH-EXTREME source repository.'
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

function Read-PatchPlan {
    param([string]$Repository)
    $manifestPath = Join-Path $script:PackageRoot 'manifest.json'
    if (-not [IO.File]::Exists($manifestPath)) { throw "Missing package manifest: $manifestPath" }
    $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($null -eq $manifest -or $null -eq $manifest.PSObject.Properties['version'] -or
        $null -eq $manifest.PSObject.Properties['files'] -or [string]$manifest.version -ne '1.8.3') {
        throw 'The package manifest is missing required fields or is not version 1.8.3.'
    }
    $files = @($manifest.files)
    if ($files.Count -eq 0) { throw 'The package manifest contains no files.' }
    $payloadRoot = Join-Path $script:PackageRoot 'payload'
    $seen = @{}
    foreach ($file in $files) {
        foreach ($field in @('path', 'original_sha256', 'sha256')) {
            if ($null -eq $file -or $null -eq $file.PSObject.Properties[$field]) {
                throw "A manifest file entry is missing '$field'."
            }
        }
        $relative = Get-SafeRelativePath ([string]$file.path)
        if ($seen.ContainsKey($relative)) { throw "Duplicate manifest path: $relative" }
        $seen[$relative] = $true
        $expected = [string]$file.sha256
        if ($expected -notmatch '^[0-9a-fA-F]{64}$') { throw "Invalid payload SHA-256: $relative" }
        $original = $null
        if ($null -ne $file.original_sha256) {
            $original = [string]$file.original_sha256
            if ($original -notmatch '^[0-9a-fA-F]{64}$') { throw "Invalid original SHA-256: $relative" }
            $original = $original.ToLowerInvariant()
        }
        $expected = $expected.ToLowerInvariant()
        $acceptedOriginalHashes = [Collections.Generic.List[string]]::new()
        if ($null -ne $original) { $acceptedOriginalHashes.Add($original) }
        # Support exact earlier payloads when an update was already copied.
        # Arbitrary locally modified files still fail the complete preflight.
        if ($null -ne $file.PSObject.Properties['previous_sha256']) {
            foreach ($previous in @($file.previous_sha256)) {
                $previousHash = [string]$previous
                if ($previousHash -notmatch '^[0-9a-fA-F]{64}$') {
                    throw "Invalid previous payload SHA-256: $relative"
                }
                $previousHash = $previousHash.ToLowerInvariant()
                if (-not $acceptedOriginalHashes.Contains($previousHash)) {
                    $acceptedOriginalHashes.Add($previousHash)
                }
            }
        }
        $acceptedZipContents = @()
        if ($null -ne $file.PSObject.Properties['accepted_zip_contents']) {
            $acceptedZipContents = @(Get-AcceptedZipContentSnapshots -Relative $relative -Snapshots $file.accepted_zip_contents)
        }
        $payload = Join-SafePath $payloadRoot $relative
        $target = Join-SafePath $Repository $relative
        if (-not [IO.File]::Exists($payload)) { throw "A payload file is missing: $relative" }
        if ((Get-Sha256 $payload) -ne $expected) { throw "A payload file failed its SHA-256 check: $relative" }
        if ([IO.Directory]::Exists($target)) { throw "A directory occupies a patched file path: $target" }
        $exists = [IO.File]::Exists($target)
        $current = $null
        if ($exists) { $current = Get-Sha256 $target }
        if ($exists -and $current -eq $expected) {
            $action = 'skip'
        } elseif ($exists -and $acceptedOriginalHashes.Contains($current)) {
            $action = 'replace'
        } elseif ($exists -and $acceptedZipContents.Count -gt 0 -and
                  (Test-AcceptedZipContents -Path $target -Snapshots $acceptedZipContents)) {
            # Install the exact payload even when only packaging metadata
            # changed. CurrentHash still records the actual bytes we back up.
            $action = 'replace'
        } elseif (-not $exists -and $null -eq $original) {
            $action = 'create'
        } elseif (-not $exists) {
            throw "A required original file is missing: $relative. No source files have been copied."
        } else {
            throw "Your source file differs from all supported original and patched versions: $relative`nCurrent SHA-256: $current`nNo source files have been copied. Use the matching source checkout or request a patch for this updated file."
        }
        [PSCustomObject]@{
            Relative = $relative; Payload = $payload; Target = $target
            OriginalHash = $original; ExpectedHash = $expected
            CurrentHash = $current; ExistedBefore = $exists; Action = $action
        }
    }
}

function Save-RestoreManifest {
    if ($null -eq $script:BackupRoot -or $null -eq $script:RestoreManifest) { return }
    $path = Join-Path $script:BackupRoot 'restore-manifest.json'
    $temporary = Join-Path $script:BackupRoot 'restore-manifest.json.tmp'
    $json = $script:RestoreManifest | ConvertTo-Json -Depth 10
    [IO.File]::WriteAllText($temporary, $json, [Text.UTF8Encoding]::new($false))
    # A plain $null becomes an empty System.String in Windows PowerShell.
    # NullString passes a true null backup path to this .NET string overload.
    if ([IO.File]::Exists($path)) { [IO.File]::Replace($temporary, $path, [NullString]::Value) }
    else { [IO.File]::Move($temporary, $path) }
}

function Restore-AppliedFiles {
    param([object[]]$Applied)
    $errors = [Collections.Generic.List[string]]::new()
    if ($null -eq $Applied -or $Applied.Count -eq 0) { return }
    for ($index = $Applied.Count - 1; $index -ge 0; --$index) {
        $entry = $Applied[$index]
        try {
            $exists = [IO.File]::Exists($entry.Target)
            $current = $null
            if ($exists) { $current = Get-Sha256 $entry.Target }
            if ($entry.ExistedBefore -and $current -eq $entry.CurrentHash) { continue }
            if ($exists -and $current -ne $entry.ExpectedHash) {
                throw 'The file changed after installation; its later edit was preserved.'
            }
            if ($entry.ExistedBefore) {
                $backup = Join-SafePath (Join-Path $script:BackupRoot 'originals') $entry.Relative
                if ((Get-Sha256 $backup) -ne $entry.CurrentHash) { throw 'The original backup failed verification.' }
                $restore = Join-SafePath (Join-Path $script:BackupRoot 'rollback') $entry.Relative
                [void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($restore))
                [IO.File]::Copy($backup, $restore, $true)
                if ($exists) { [IO.File]::Replace($restore, $entry.Target, [NullString]::Value) }
                else { [IO.File]::Move($restore, $entry.Target) }
            } elseif ($exists) {
                [IO.File]::Delete($entry.Target)
            }
        } catch {
            $errors.Add(($entry.Relative + ': ' + $_.Exception.Message))
        }
    }
    return $errors.ToArray()
}

function Apply-PatchFiles {
    param([string]$Repository, [object[]]$Plan)
    $changes = @($Plan | Where-Object { $_.Action -ne 'skip' })
    if ($changes.Count -eq 0) {
        Write-Host 'All source files already match version 1.8.3. No files need copying.' -ForegroundColor Green
        return
    }
    $stamp = (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [Guid]::NewGuid().ToString('N').Substring(0, 8)
    $script:BackupRoot = Join-Path (Join-Path $Repository 'soh-extreme-patch-backups') $stamp
    [void][IO.Directory]::CreateDirectory($script:BackupRoot)
    $records = @($changes | ForEach-Object {
        $backupName = $null
        if ($_.ExistedBefore) { $backupName = 'originals/' + $_.Relative }
        [PSCustomObject]@{
            path = $_.Relative; existed_before = $_.ExistedBefore
            original_sha256 = $_.CurrentHash; patched_sha256 = $_.ExpectedHash
            backup = $backupName
        }
    })
    $script:RestoreManifest = [PSCustomObject]@{
        version = '1.8.3'; created_utc = [DateTime]::UtcNow.ToString('o')
        repository = $Repository; status = 'preparing'; files = $records
        build_status = 'not_started'; rollback_errors = @()
    }
    Save-RestoreManifest
    $applied = [Collections.Generic.List[object]]::new()
    try {
        # All manifest/payload/source hashes were checked before any copying.
        # Stage every new file and verify every backup before replacing sources.
        foreach ($entry in $changes) {
            $stage = Join-SafePath (Join-Path $script:BackupRoot 'staged') $entry.Relative
            [void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($stage))
            [IO.File]::Copy($entry.Payload, $stage, $false)
            if ((Get-Sha256 $stage) -ne $entry.ExpectedHash) { throw "Staging verification failed: $($entry.Relative)" }
            if ($entry.ExistedBefore) {
                if ((Get-Sha256 $entry.Target) -ne $entry.CurrentHash) { throw "The source changed during preflight: $($entry.Relative)" }
                $backup = Join-SafePath (Join-Path $script:BackupRoot 'originals') $entry.Relative
                [void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($backup))
                [IO.File]::Copy($entry.Target, $backup, $false)
                if ((Get-Sha256 $backup) -ne $entry.CurrentHash) { throw "Backup verification failed: $($entry.Relative)" }
            }
        }
        $script:RestoreManifest.status = 'prepared'
        Save-RestoreManifest
        foreach ($entry in $changes) {
            if ($entry.ExistedBefore) {
                if ((Get-Sha256 $entry.Target) -ne $entry.CurrentHash) { throw "The source changed before copying: $($entry.Relative)" }
            } elseif (Test-Path -LiteralPath $entry.Target) {
                throw "A new file path became occupied before copying: $($entry.Relative)"
            }
            $stage = Join-SafePath (Join-Path $script:BackupRoot 'staged') $entry.Relative
            [void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($entry.Target))
            # Staging is in this repository so Replace/Move stays on its volume.
            if ($entry.ExistedBefore) { [IO.File]::Replace($stage, $entry.Target, [NullString]::Value) }
            else { [IO.File]::Move($stage, $entry.Target) }
            $applied.Add($entry)
            if ((Get-Sha256 $entry.Target) -ne $entry.ExpectedHash) { throw "Installed file verification failed: $($entry.Relative)" }
            Write-Host ('Applied: ' + $entry.Relative)
        }
        $script:RestoreManifest.status = 'applied'
        Save-RestoreManifest
    } catch {
        $failure = $_.Exception.Message
        $rollbackErrors = @(Restore-AppliedFiles -Applied $applied.ToArray())
        $script:RestoreManifest.rollback_errors = $rollbackErrors
        if ($rollbackErrors.Count -eq 0) { $script:RestoreManifest.status = 'rolled_back' }
        else { $script:RestoreManifest.status = 'rollback_incomplete' }
        try { Save-RestoreManifest } catch { Write-Host ('Could not update restore manifest: ' + $_.Exception.Message) -ForegroundColor Yellow }
        Write-Host ('Copy failed: ' + $failure) -ForegroundColor Red
        if ($rollbackErrors.Count -eq 0) { Write-Host 'Every source replacement made by this attempt was rolled back.' }
        else {
            Write-Host 'Some files require restoration from the verified backups:' -ForegroundColor Red
            foreach ($message in $rollbackErrors) { Write-Host ('  ' + $message) -ForegroundColor Red }
        }
        Write-Host ('Backup and restore manifest: ' + $script:BackupRoot)
        throw 'Patch application failed. No build was started.'
    }
    Write-Host ('Source patch applied. Backup and restore manifest: ' + $script:BackupRoot) -ForegroundColor Green
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
        throw 'This single-configuration build cache is not configured as Release. Configure a Release build using your existing setup, then run this installer again.'
    }
}

function Find-GameExecutable {
    param([string]$Repository, [object]$Cache, [string]$LogPath)
    $reported = [Collections.Generic.List[string]]::new()
    foreach ($line in [IO.File]::ReadAllLines($LogPath)) {
        if ($line -match '(?i)(?:->\s*|\bexecutable\s+)(?<exe>.+?\.exe)(?:"?\s|"?$)') {
            $path = $matches['exe'].Trim().Trim('"')
            if (-not [IO.Path]::IsPathRooted($path)) { $path = Join-Path $Cache.Directory $path }
            $path = Get-NormalizedPath $path
            if ([IO.Path]::GetFileName($path) -match '^(?i:soh|soh[-_]extreme|Ship of Harkinian)\.exe$' -and [IO.File]::Exists($path)) {
                $reported.Add($path)
            }
        }
    }
    $uniqueReported = @($reported | Select-Object -Unique)
    if ($uniqueReported.Count -eq 1) { return $uniqueReported[0] }
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
            if ([IO.File]::Exists($candidate)) { $found.Add((Get-NormalizedPath $candidate)) }
        }
    }
    $unique = @($found | Select-Object -Unique)
    if ($unique.Count -eq 1) { return $unique[0] }
    return $null
}

function Build-ExistingRelease {
    param([string]$Repository)
    $cache = Select-BuildCache $Repository
    if ($null -eq $cache) {
        Write-Host 'Source patch applied. Build not performed because no build directory was selected.' -ForegroundColor Yellow
        return 2
    }
    Assert-ReleaseConfiguration $cache
    $cmake = Find-CMake $cache
    if ([string]::IsNullOrWhiteSpace($cmake)) {
        Write-Host 'Source patch applied. CMake was not found in PATH, the cache, Program Files, or installed Visual Studio tools.' -ForegroundColor Yellow
        Write-Host 'Use your existing CMake/Visual Studio build environment and run this installer again.'
        return 2
    }
    $logRoot = $script:BackupRoot
    if ($null -eq $logRoot) {
        $logRoot = Join-Path (Join-Path $Repository 'soh-extreme-patch-backups') ((Get-Date -Format 'yyyyMMdd-HHmmss') + '-build-' + [Guid]::NewGuid().ToString('N').Substring(0, 8))
        [void][IO.Directory]::CreateDirectory($logRoot)
    }
    $logPath = Join-Path $logRoot 'build-release.log'
    Write-Host ('CMake: ' + $cmake)
    Write-Host ('Build directory: ' + $cache.Directory)
    Write-Host 'Building Release with 8 parallel jobs...'
    Write-Host ('Build log: ' + $logPath)
    $previousErrorPreference = $ErrorActionPreference
    Push-Location -LiteralPath $Repository
    try {
        # Windows PowerShell 5.1 represents redirected native stderr as error
        # records. Continue lets the complete compiler output reach the log.
        $ErrorActionPreference = 'Continue'
        # A failed native launch must not reuse an earlier vswhere exit code.
        $global:LASTEXITCODE = $null
        & $cmake --build $cache.Directory --config Release --parallel 8 2>&1 |
            Tee-Object -FilePath $logPath -ErrorAction Stop | ForEach-Object { Write-Host $_ }
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousErrorPreference
        Pop-Location
    }
    if ($null -eq $exitCode) { throw 'CMake did not return a build exit code.' }
    if ($null -ne $script:RestoreManifest) {
        if ($exitCode -eq 0) { $script:RestoreManifest.build_status = 'succeeded' }
        else { $script:RestoreManifest.build_status = 'failed' }
        Save-RestoreManifest
    }
    if ($exitCode -ne 0) {
        Write-Host ('Source patch applied, but the Release build failed with exit code ' + $exitCode + '.') -ForegroundColor Red
        Write-Host ('Review or share this build log: ' + $logPath)
        return [int]$exitCode
    }
    Write-Host 'Source patch applied and Release build completed successfully.' -ForegroundColor Green
    try {
        $executable = Find-GameExecutable -Repository $Repository -Cache $cache -LogPath $logPath
        if ($null -ne $executable) { Write-Host ('Game executable: ' + $executable) -ForegroundColor Green }
        else { Write-Host ('The game executable could not be uniquely identified. See the target output in: ' + $logPath) }
    } catch { Write-Host ('Executable discovery could not finish. Build log: ' + $logPath) -ForegroundColor Yellow }
    Write-Host 'The installer has not launched the game or performed an in-game test.'
    return 0
}

try {
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) { throw 'This installer is for Windows.' }
    Write-Host 'SOH-EXTREME 1.8.3 - playable random spawn placement and cumulative entrance fixes (installer revision 3)' -ForegroundColor Cyan
    Write-Host 'Close the game and finish any active build before continuing.'
    $repository = Find-SourceRepository
    Write-Host ('Source repository: ' + $repository)
    Write-Host 'Verifying every payload and source file before copying...'
    $plan = @(Read-PatchPlan $repository)
    Write-Host ('Verified ' + $plan.Count + ' manifest files.')
    Apply-PatchFiles -Repository $repository -Plan $plan
} catch {
    Write-Host ('PATCH FAILED: ' + $_.Exception.Message) -ForegroundColor Red
    exit 1
}

try {
    $buildResult = Build-ExistingRelease $repository
    exit [int]$buildResult
} catch {
    Write-Host ('Source patch applied, but the build could not complete: ' + $_.Exception.Message) -ForegroundColor Yellow
    if ($null -ne $script:BackupRoot) { Write-Host ('Backup and restore manifest: ' + $script:BackupRoot) }
    Write-Host 'Run this installer again after resolving the build setup; matching patched files will be skipped.'
    exit 2
}
