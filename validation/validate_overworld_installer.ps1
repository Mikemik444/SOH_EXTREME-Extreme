#requires -Version 5.1
<#
Run from a disposable test environment. The installer is parsed with the
PowerShell AST; its production functions are loaded without executing its main
Windows-only entry point. Every source fixture comes from the supplied original
archive, and only a uniquely named temporary directory is changed or removed.

Example:
  ./tests/validate_overworld_installer.ps1 `
    -PackageDirectory ./delivery/SOH-EXTREME-1.8.2-overworld-entrances `
    -OriginalArchive ./upload/haha.zip `
    -PreviousPackageArchives @('./tests/installer_revision_1_reference.zip', `
      './delivery/SOH-EXTREME-1.8.1-coupled-entrances.zip')

On Unix, only Join-SafePath is overridden to use the native directory separator.
Save-RestoreManifest, Read-PatchPlan, Apply-PatchFiles and Restore-AppliedFiles
run exactly as parsed from the actual installer, without transaction mocks.
This is not a Windows PowerShell 5.1 or in-game test when run on Unix.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$PackageDirectory,
    [Parameter(Mandatory = $true)][string]$OriginalArchive,
    [Parameter(Mandatory = $true)][Alias('PreviousPackageArchive')][string[]]$PreviousPackageArchives,
    [int]$ExpectedPayloadCount = 0,
    [string]$ExpectedVersion = '1.8.2',
    [string]$ResultPath = (Join-Path $PSScriptRoot 'installer_1_8_2_validation.json'),
    [switch]$KeepFixtures
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$PackageDirectory = [IO.Path]::GetFullPath($PackageDirectory)
$OriginalArchive = [IO.Path]::GetFullPath($OriginalArchive)
$PreviousPackageArchives = @($PreviousPackageArchives | ForEach-Object { [IO.Path]::GetFullPath($_) })
$ResultPath = [IO.Path]::GetFullPath($ResultPath)
$script:PackageRoot = $PackageDirectory
$script:BackupRoot = $null
$script:RestoreManifest = $null
$script:Cases = [Collections.Generic.List[object]]::new()
$script:FixtureRoot = Join-Path ([IO.Path]::GetTempPath()) ('soh-installer-test-' + [Guid]::NewGuid().ToString('N'))
[void][IO.Directory]::CreateDirectory($script:FixtureRoot)
$script:Baseline = Join-Path $script:FixtureRoot 'baseline'
$installer = Join-Path $PackageDirectory 'APPLY_AND_BUILD.ps1'
$manifestPath = Join-Path $PackageDirectory 'manifest.json'
$report = [ordered]@{
    status = 'running'
    created_utc = [DateTime]::UtcNow.ToString('o')
    powershell_version = $PSVersionTable.PSVersion.ToString()
    powershell_edition = $PSVersionTable.PSEdition
    platform = [Environment]::OSVersion.Platform.ToString()
    operating_system = [Environment]::OSVersion.VersionString
    framework = [Runtime.InteropServices.RuntimeInformation]::FrameworkDescription
    installer_sha256 = (Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash.ToLowerInvariant()
    manifest_sha256 = (Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash.ToLowerInvariant()
    previous_packages = @($PreviousPackageArchives | ForEach-Object {
        [PSCustomObject]@{
            name = [IO.Path]::GetFileName($_)
            sha256 = (Get-FileHash -LiteralPath $_ -Algorithm SHA256).Hash.ToLowerInvariant()
        }
    })
    target_version = $ExpectedVersion
    functions_loaded_from_actual_installer_ast = @()
    test_overrides = @()
    limitations = @(
        'The installer main entry point and CMD wrapper are not executed.',
        'This run does not compile or launch SOH-EXTREME.',
        'PowerShell Core on Unix does not constitute a Windows PowerShell 5.1 execution test.'
    )
    payload_file_count = 0
    cases = @()
}

function Assert-Condition {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw $Message }
}

function Assert-Throws {
    param([scriptblock]$Action, [string]$ExpectedMessage)
    $caught = $null
    try { & $Action | Out-Null } catch { $caught = $_.Exception.Message }
    Assert-Condition ($null -ne $caught) 'Expected an exception but the operation succeeded.'
    if (-not [string]::IsNullOrEmpty($ExpectedMessage)) {
        Assert-Condition ($caught -like ('*' + $ExpectedMessage + '*')) ('Unexpected exception: ' + $caught)
    }
    return $caught
}

function Invoke-ValidationCase {
    param([string]$Name, [scriptblock]$Action)
    $timer = [Diagnostics.Stopwatch]::StartNew()
    try {
        $details = & $Action
        $script:Cases.Add([PSCustomObject]@{
            name = $Name; status = 'passed'; seconds = [math]::Round($timer.Elapsed.TotalSeconds, 3)
            details = $details
        })
        Write-Host ('PASS: ' + $Name) -ForegroundColor Green
    } catch {
        $script:Cases.Add([PSCustomObject]@{
            name = $Name; status = 'failed'; seconds = [math]::Round($timer.Elapsed.TotalSeconds, 3)
            error = $_.Exception.Message
        })
        throw
    }
}

function New-SourceFixture {
    param([string]$Name)
    $repository = Join-Path $script:FixtureRoot $Name
    [void][IO.Directory]::CreateDirectory($repository)
    foreach ($file in $script:Files) {
        if ($null -eq $file.original_sha256) { continue }
        $target = Join-SafePath $repository $file.path
        [void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($target))
        [IO.File]::Copy((Join-SafePath $script:Baseline $file.path), $target, $false)
    }
    # Explicit sentinels establish that patch application does not touch these.
    foreach ($relative in @('Save/test-save.sav', 'Config/test-config.cfg', 'mods/test-mod.txt')) {
        $path = Join-SafePath $repository $relative
        [void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($path))
        [IO.File]::WriteAllText($path, 'untouched fixture sentinel')
    }
    return $repository
}

function Reset-PatchState {
    param([string]$Package = $PackageDirectory)
    $script:PackageRoot = $Package
    $script:BackupRoot = $null
    $script:RestoreManifest = $null
}

function Assert-OriginalSource {
    param([string]$Repository)
    foreach ($file in $script:Files) {
        $path = Join-SafePath $Repository $file.path
        if ($null -eq $file.original_sha256) {
            Assert-Condition (-not [IO.File]::Exists($path)) ('A new file survived rollback: ' + $file.path)
        } else {
            Assert-Condition ((Get-Sha256 $path) -eq $file.original_sha256) ('Original file was not restored: ' + $file.path)
        }
    }
    foreach ($relative in @('Save/test-save.sav', 'Config/test-config.cfg', 'mods/test-mod.txt')) {
        Assert-Condition ([IO.File]::ReadAllText((Join-SafePath $Repository $relative)) -eq 'untouched fixture sentinel') ('Unrelated file changed: ' + $relative)
    }
}

function New-RepackedApWorld {
    param([string]$Source, [string]$Destination, [switch]$ChangeWorldEntry)
    $inputArchive = $null
    $outputArchive = $null
    $outputFile = $null
    $changedEntry = $null
    $fileCount = 0
    try {
        $inputArchive = [IO.Compression.ZipFile]::OpenRead($Source)
        $outputFile = [IO.File]::Open($Destination, [IO.FileMode]::Create, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
        $outputArchive = [IO.Compression.ZipArchive]::new($outputFile, [IO.Compression.ZipArchiveMode]::Create, $false)
        # Reverse order, disable compression, replace timestamps, and add a
        # directory record. Only packaging differs unless mutation is requested.
        for ($index = $inputArchive.Entries.Count - 1; $index -ge 0; --$index) {
            $entry = $inputArchive.Entries[$index]
            if ($entry.FullName.EndsWith('/', [StringComparison]::Ordinal)) { continue }
            $copy = $outputArchive.CreateEntry($entry.FullName, [IO.Compression.CompressionLevel]::NoCompression)
            $copy.LastWriteTime = [DateTimeOffset]::new(2001, 2, 3, 4, 5, 6, [TimeSpan]::Zero)
            $inputStream = $null
            $outputStream = $null
            try {
                $inputStream = $entry.Open()
                $outputStream = $copy.Open()
                if ($ChangeWorldEntry -and $null -eq $changedEntry -and $entry.Length -gt 0 -and
                    $entry.FullName.StartsWith('soh_extreme/', [StringComparison]::Ordinal) -and
                    $entry.FullName.EndsWith('.py', [StringComparison]::Ordinal)) {
                    $buffer = [IO.MemoryStream]::new()
                    try {
                        $inputStream.CopyTo($buffer)
                        $bytes = $buffer.ToArray()
                        $bytes[0] = [byte]($bytes[0] -bxor 1)
                        $outputStream.Write($bytes, 0, $bytes.Length)
                        $changedEntry = $entry.FullName
                    } finally { $buffer.Dispose() }
                } else {
                    $inputStream.CopyTo($outputStream)
                }
            } finally {
                if ($null -ne $outputStream) { $outputStream.Dispose() }
                if ($null -ne $inputStream) { $inputStream.Dispose() }
            }
            ++$fileCount
        }
        [void]$outputArchive.CreateEntry('metadata-only-directory/', [IO.Compression.CompressionLevel]::NoCompression)
    } finally {
        if ($null -ne $outputArchive) { $outputArchive.Dispose() }
        if ($null -ne $outputFile) { $outputFile.Dispose() }
        if ($null -ne $inputArchive) { $inputArchive.Dispose() }
    }
    if ($ChangeWorldEntry) { Assert-Condition ($null -ne $changedEntry) 'The APWorld fixture had no Python world entry to mutate.' }
    return [PSCustomObject]@{ file_count = $fileCount; changed_entry = $changedEntry }
}

function Assert-RepackedApWorldReplacement {
    param([string]$Repository, [string]$RepackedHash)
    $relative = 'archipelago/soh_extreme.apworld'
    $file = @($script:Files | Where-Object { $_.path -ceq $relative })[0]
    $exactHashes = @($file.original_sha256, $file.sha256)
    if ($null -ne $file.PSObject.Properties['previous_sha256']) { $exactHashes += @($file.previous_sha256) }
    Assert-Condition ($exactHashes -notcontains $RepackedHash) 'Repack unexpectedly matches an exact approved archive hash.'
    $plan = @(Read-PatchPlan $Repository)
    Assert-Condition ($plan.Count -eq $script:Files.Count) 'Repacked archive did not reach complete preflight.'
    $entry = @($plan | Where-Object { $_.Relative -ceq $relative })[0]
    Assert-Condition ($entry.Action -eq 'replace') 'The repacked APWorld was not scheduled for exact-payload replacement.'
    Assert-Condition ($entry.CurrentHash -eq $RepackedHash) 'APWorld preflight lost the actual repacked file hash.'
    Apply-PatchFiles -Repository $Repository -Plan $plan
    Assert-Condition ((Get-Sha256 $entry.Target) -eq $file.sha256) 'APWorld replacement does not match the exact payload.'
    $backup = Join-SafePath (Join-Path $script:BackupRoot 'originals') $relative
    Assert-Condition ((Get-Sha256 $backup) -eq $RepackedHash) 'APWorld backup did not preserve the actual repacked bytes.'
    $saved = Get-Content -LiteralPath (Join-Path $script:BackupRoot 'restore-manifest.json') -Raw | ConvertFrom-Json
    $record = @($saved.files | Where-Object { $_.path -ceq $relative })[0]
    Assert-Condition ($record.original_sha256 -eq $RepackedHash) 'Restore manifest records the wrong repacked original hash.'
    Assert-Condition ($saved.status -eq 'applied') 'Repacked archive installation did not complete.'
    return [PSCustomObject]@{
        original_repacked_sha256 = $RepackedHash; installed_sha256 = [string]$file.sha256
        backed_up_actual_archive = $true; restore_manifest_uses_actual_hash = $true
    }
}

$failed = $false
try {
    $tokens = $null
    $parseErrors = $null
    $ast = [Management.Automation.Language.Parser]::ParseFile($installer, [ref]$tokens, [ref]$parseErrors)
    Assert-Condition (@($parseErrors).Count -eq 0) ('Installer parse errors: ' + ($parseErrors | Out-String))
    $functions = @($ast.EndBlock.Statements | Where-Object { $_ -is [Management.Automation.Language.FunctionDefinitionAst] })
    foreach ($function in $functions) {
        . ([scriptblock]::Create($function.Extent.Text))
    }
    $report.functions_loaded_from_actual_installer_ast = @($functions.Name)
    $required = @('Read-PatchPlan', 'Save-RestoreManifest', 'Apply-PatchFiles', 'Restore-AppliedFiles',
                  'Get-AcceptedZipContentSnapshots', 'Test-AcceptedZipContents')
    foreach ($name in $required) { Assert-Condition ($functions.Name -contains $name) ('Missing actual installer function: ' + $name) }
    $replaceCalls = @($ast.FindAll({
        param($node)
        $node -is [Management.Automation.Language.InvokeMemberExpressionAst] -and
            $node.Member.Value -eq 'Replace' -and $node.Expression.Extent.Text -eq '[IO.File]'
    }, $true))
    Assert-Condition ($replaceCalls.Count -eq 3) 'Expected all three production File.Replace calls.'
    foreach ($call in $replaceCalls) {
        Assert-Condition ($call.Arguments.Count -eq 3 -and $call.Arguments[2].Extent.Text -eq '[NullString]::Value') 'A production File.Replace backup path is not typed null.'
    }
    if ([IO.Path]::DirectorySeparatorChar -ne '\') {
        # The only transaction dependency changed for Unix: path separators.
        function Join-SafePath {
            param([string]$Root, [string]$Relative)
            $prefix = Get-NormalizedPath $Root
            if (-not $prefix.EndsWith([string][IO.Path]::DirectorySeparatorChar)) {
                $prefix += [IO.Path]::DirectorySeparatorChar
            }
            $full = [IO.Path]::GetFullPath([IO.Path]::Combine($Root, $Relative.Replace('\', '/')))
            if (-not $full.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
                throw "A manifest path escapes its destination folder: $Relative"
            }
            return $full
        }
        $report.test_overrides = @('Join-SafePath: native Unix directory separator; same root containment check.')
    }
    $packageManifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $script:ManifestVersion = [string]$packageManifest.version
    Assert-Condition ($script:ManifestVersion -eq $ExpectedVersion) 'Unexpected package version.'
    $script:Files = @($packageManifest.files)
    $report.payload_file_count = $script:Files.Count
    Assert-Condition ($script:Files.Count -gt 0) 'The package has no payload files.'
    if ($ExpectedPayloadCount -gt 0) {
        Assert-Condition ($script:Files.Count -eq $ExpectedPayloadCount) ('Expected the actual ' + $ExpectedPayloadCount + '-file package.')
    }
    $script:OriginalCount = @($script:Files | Where-Object { $null -ne $_.original_sha256 }).Count
    $script:NewCount = $script:Files.Count - $script:OriginalCount

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = [IO.Compression.ZipFile]::OpenRead($OriginalArchive)
    try {
        foreach ($file in $script:Files) {
            if ($null -eq $file.original_sha256) { continue }
            $entry = $archive.GetEntry([string]$file.path)
            Assert-Condition ($null -ne $entry) ('Original archive lacks required fixture: ' + $file.path)
            $target = Join-SafePath $script:Baseline $file.path
            [void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($target))
            [IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $target, $false)
            Assert-Condition ((Get-Sha256 $target) -eq $file.original_sha256) ('Original fixture hash mismatch: ' + $file.path)
        }
    } finally { $archive.Dispose() }

    Invoke-ValidationCase 'plain null reproduces invalid backup path; typed null replaces correctly' {
        $directory = Join-Path $script:FixtureRoot 'null-reproduction'
        [void][IO.Directory]::CreateDirectory($directory)
        $source = Join-Path $directory 'source.txt'
        $target = Join-Path $directory 'target.txt'
        [IO.File]::WriteAllText($source, 'new content')
        [IO.File]::WriteAllText($target, 'old content')
        $legacyError = Assert-Throws { [IO.File]::Replace($source, $target, $null) } 'path'
        Assert-Condition ([IO.File]::ReadAllText($target) -eq 'old content') 'Failed legacy replacement changed its target.'
        [IO.File]::Replace($source, $target, [NullString]::Value)
        Assert-Condition ([IO.File]::ReadAllText($target) -eq 'new content') 'Typed-null replacement failed.'
        Assert-Condition (-not [IO.File]::Exists($source)) 'Typed-null replacement did not consume its source.'
        [PSCustomObject]@{ legacy_error = $legacyError; typed_null_target_verified = $true }
    }

    Invoke-ValidationCase 'actual restore manifest creation and repeated atomic updates' {
        Reset-PatchState
        $script:BackupRoot = Join-Path $script:FixtureRoot 'manifest-updates'
        [void][IO.Directory]::CreateDirectory($script:BackupRoot)
        $script:RestoreManifest = [PSCustomObject]@{ status = 'preparing'; files = @(); build_status = 'not_started' }
        foreach ($state in @('preparing', 'prepared', 'applied')) {
            $script:RestoreManifest.status = $state
            Save-RestoreManifest
            $saved = Get-Content -LiteralPath (Join-Path $script:BackupRoot 'restore-manifest.json') -Raw | ConvertFrom-Json
            Assert-Condition ($saved.status -eq $state) ('Restore manifest update failed: ' + $state)
            Assert-Condition (-not [IO.File]::Exists((Join-Path $script:BackupRoot 'restore-manifest.json.tmp'))) 'Manifest temporary file survived a successful update.'
        }
        'Creation followed by two File.Replace updates succeeded.'
    }

    Invoke-ValidationCase 'all real payload files apply with verified backups and source hashes' {
        Reset-PatchState
        $repository = New-SourceFixture 'full-apply'
        $plan = @(Read-PatchPlan $repository)
        Assert-Condition ($plan.Count -eq $script:Files.Count) 'Preflight did not return every manifest entry.'
        Assert-Condition (@($plan | Where-Object Action -eq 'replace').Count -eq $script:OriginalCount) 'Preflight original replacement count is wrong.'
        Assert-Condition (@($plan | Where-Object Action -eq 'create').Count -eq $script:NewCount) 'Preflight new file count is wrong.'
        Apply-PatchFiles -Repository $repository -Plan $plan
        foreach ($file in $script:Files) {
            Assert-Condition ((Get-Sha256 (Join-SafePath $repository $file.path)) -eq $file.sha256) ('Patched source hash mismatch: ' + $file.path)
            if ($null -ne $file.original_sha256) {
                $backup = Join-SafePath (Join-Path $script:BackupRoot 'originals') $file.path
                Assert-Condition ((Get-Sha256 $backup) -eq $file.original_sha256) ('Backup hash mismatch: ' + $file.path)
            }
        }
        $saved = Get-Content -LiteralPath (Join-Path $script:BackupRoot 'restore-manifest.json') -Raw | ConvertFrom-Json
        Assert-Condition ($saved.status -eq 'applied' -and @($saved.files).Count -eq $script:Files.Count) 'Final restore manifest is incomplete.'
        Assert-Condition ($saved.version -eq $ExpectedVersion) 'The restore manifest records the wrong release version.'
        foreach ($relative in @('Save/test-save.sav', 'Config/test-config.cfg', 'mods/test-mod.txt')) {
            Assert-Condition ([IO.File]::ReadAllText((Join-SafePath $repository $relative)) -eq 'untouched fixture sentinel') ('Unrelated file changed: ' + $relative)
        }
        $script:AppliedRepository = $repository
        [PSCustomObject]@{ applied = $script:Files.Count; verified_original_backups = $script:OriginalCount; unrelated_sentinels_unchanged = 3 }
    }

    Invoke-ValidationCase 'reapplying the real package is idempotent and skips every file' {
        Reset-PatchState
        $repository = $script:AppliedRepository
        $before = @([IO.Directory]::GetDirectories((Join-Path $repository 'soh-extreme-patch-backups'))).Count
        $plan = @(Read-PatchPlan $repository)
        Assert-Condition ($plan.Count -eq $script:Files.Count -and @($plan | Where-Object Action -ne 'skip').Count -eq 0) 'Previously patched files were not all skipped.'
        Apply-PatchFiles -Repository $repository -Plan $plan
        Assert-Condition ($null -eq $script:BackupRoot) 'Idempotent application created a backup transaction.'
        $after = @([IO.Directory]::GetDirectories((Join-Path $repository 'soh-extreme-patch-backups'))).Count
        Assert-Condition ($before -eq $after) 'Idempotent application created an extra backup directory.'
        ('All ' + $script:Files.Count + ' current hashes accepted; no source copies or extra backup created.')
    }

    $previousIndex = 0
    foreach ($previousArchivePath in $PreviousPackageArchives) {
    ++$previousIndex
    Invoke-ValidationCase ('upgrade from ' + [IO.Path]::GetFileName($previousArchivePath) + ' accepts its exact hashes') {
        Reset-PatchState
        $repository = New-SourceFixture ('prior-package-upgrade-' + $previousIndex)
        $previous = [IO.Compression.ZipFile]::OpenRead($previousArchivePath)
        try {
            $manifests = @($previous.Entries | Where-Object { $_.FullName -match '(^|/)manifest\.json$' })
            Assert-Condition ($manifests.Count -eq 1) 'The previous package must contain exactly one manifest.'
            $prefix = $manifests[0].FullName.Substring(0, $manifests[0].FullName.Length - 'manifest.json'.Length)
            $reader = [IO.StreamReader]::new($manifests[0].Open())
            try { $oldManifest = $reader.ReadToEnd() | ConvertFrom-Json } finally { $reader.Dispose() }
            Assert-Condition (@($oldManifest.files).Count -gt 0) 'The prior delivered package has no payload files.'
            foreach ($file in $oldManifest.files) {
                $entry = $previous.GetEntry($prefix + 'payload/' + $file.path)
                Assert-Condition ($null -ne $entry) ('Old package lacks payload: ' + $file.path)
                $target = Join-SafePath $repository $file.path
                [void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($target))
                [IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $target, $true)
                Assert-Condition ((Get-Sha256 $target) -eq $file.sha256) ('Old delivered payload checksum failed: ' + $file.path)
            }
        } finally { $previous.Dispose() }
        # Derive expected upgrade paths from the actual fixture bytes before
        # invoking installer preflight. No release-specific skip count is fixed.
        $beforeHashes = @{}
        $expectedReplacements = [Collections.Generic.List[string]]::new()
        $expectedAdditions = [Collections.Generic.List[string]]::new()
        foreach ($file in $script:Files) {
            $path = Join-SafePath $repository $file.path
            $before = $null
            if ([IO.File]::Exists($path)) { $before = Get-Sha256 $path }
            $beforeHashes[$file.path] = $before
            if ($before -eq $file.sha256) { continue }
            if ($null -eq $before) { $expectedAdditions.Add([string]$file.path) }
            else { $expectedReplacements.Add([string]$file.path) }
        }
        $expectedChanges = @($expectedReplacements.ToArray()) + @($expectedAdditions.ToArray())
        Assert-Condition ($expectedChanges.Count -gt 0) 'The prior package fixture already has the entire new payload.'
        $plan = @(Read-PatchPlan $repository)
        Assert-Condition ($plan.Count -eq $script:Files.Count) 'The upgrade did not preflight every final file.'
        $changes = @($plan | Where-Object Action -ne 'skip')
        Assert-Condition ($changes.Count -eq $expectedChanges.Count) 'The prior package upgrade changed an unexpected number of files.'
        Assert-Condition (@($plan | Where-Object Action -eq 'skip').Count -eq ($script:Files.Count - $expectedChanges.Count)) 'The prior package upgrade has an unexpected skip count.'
        Assert-Condition (@($changes | Where-Object Action -eq 'replace').Count -eq $expectedReplacements.Count) 'The prior package upgrade has an unexpected replacement count.'
        Assert-Condition (@($changes | Where-Object Action -eq 'create').Count -eq $expectedAdditions.Count) 'The prior package upgrade has an unexpected addition count.'
        foreach ($path in $expectedChanges) {
            Assert-Condition ($changes.Relative -contains $path) ('Expected upgrade replacement missing: ' + $path)
        }
        Apply-PatchFiles -Repository $repository -Plan $plan
        foreach ($file in $script:Files) {
            Assert-Condition ((Get-Sha256 (Join-SafePath $repository $file.path)) -eq $file.sha256) ('Upgrade final hash mismatch: ' + $file.path)
        }
        foreach ($entry in $changes) {
            Assert-Condition ($entry.CurrentHash -eq $beforeHashes[$entry.Relative]) ('Upgrade preflight recorded the wrong current hash: ' + $entry.Relative)
            if (-not $entry.ExistedBefore) { continue }
            $backup = Join-SafePath (Join-Path $script:BackupRoot 'originals') $entry.Relative
            Assert-Condition ((Get-Sha256 $backup) -eq $entry.CurrentHash) ('Upgrade did not back up the actual prior content: ' + $entry.Relative)
        }
        $saved = Get-Content -LiteralPath (Join-Path $script:BackupRoot 'restore-manifest.json') -Raw | ConvertFrom-Json
        Assert-Condition ($saved.status -eq 'applied' -and @($saved.files).Count -eq $expectedChanges.Count) 'Upgrade restore manifest has an unexpected changed-file count.'
        Assert-Condition ($saved.version -eq $ExpectedVersion) 'Upgrade restore manifest records the wrong release version.'
        [PSCustomObject]@{
            old_payload_files = @($oldManifest.files).Count; final_payload_files = $script:Files.Count
            skipped = ($script:Files.Count - $expectedChanges.Count)
            replaced = $expectedReplacements.Count; added = $expectedAdditions.Count
            expected_changed_paths = $expectedChanges; actual_changed_paths = @($changes.Relative)
        }
    }
    }

    Invoke-ValidationCase 'mixed old and already-patched source versions are accepted' {
        Reset-PatchState
        $repository = New-SourceFixture 'mixed-preflight'
        $file = $script:Files[0]
        [IO.File]::Copy((Join-SafePath (Join-Path $PackageDirectory 'payload') $file.path), (Join-SafePath $repository $file.path), $true)
        $plan = @(Read-PatchPlan $repository)
        Assert-Condition (@($plan | Where-Object Action -eq 'skip').Count -eq 1) 'Matching patched file was not skipped.'
        Assert-Condition (@($plan | Where-Object Action -eq 'replace').Count -eq ($script:OriginalCount - 1)) 'Matching original files were not accepted.'
        Assert-Condition (@($plan | Where-Object Action -eq 'create').Count -eq $script:NewCount) 'Missing permitted new files were not accepted.'
        [PSCustomObject]@{ patched = 1; originals = ($script:OriginalCount - 1); new_files = $script:NewCount }
    }

    Invoke-ValidationCase 'repacked earlier APWorld contents are accepted, replaced, and backed up exactly' {
        $results = [Collections.Generic.List[object]]::new()
        $index = 0
        foreach ($previousArchivePath in $PreviousPackageArchives) {
            ++$index
            Reset-PatchState
            $repository = New-SourceFixture ('repacked-prior-apworld-' + $index)
            $source = Join-Path $script:FixtureRoot ('prior-apworld-' + $index + '.apworld')
            $previous = [IO.Compression.ZipFile]::OpenRead($previousArchivePath)
            try {
                $entries = @($previous.Entries | Where-Object { $_.FullName -cmatch '(^|/)payload/archipelago/soh_extreme\.apworld$' })
                Assert-Condition ($entries.Count -eq 1) 'The previous package must contain exactly one APWorld payload.'
                [IO.Compression.ZipFileExtensions]::ExtractToFile($entries[0], $source, $false)
            } finally { $previous.Dispose() }
            $target = Join-SafePath $repository 'archipelago/soh_extreme.apworld'
            $repack = New-RepackedApWorld -Source $source -Destination $target
            $details = Assert-RepackedApWorldReplacement -Repository $repository -RepackedHash (Get-Sha256 $target)
            $results.Add([PSCustomObject]@{
                prior_package = [IO.Path]::GetFileName($previousArchivePath)
                unchanged_world_files = $repack.file_count; installation = $details
            })
        }
        Assert-Condition ($results.Count -gt 0) 'No earlier APWorld was exercised.'
        return $results.ToArray()
    }

    Invoke-ValidationCase 'repacked current APWorld contents are accepted and replaced with exact payload' {
        Reset-PatchState
        $repository = New-SourceFixture 'repacked-current-apworld'
        $relative = 'archipelago/soh_extreme.apworld'
        $source = Join-SafePath (Join-Path $PackageDirectory 'payload') $relative
        $target = Join-SafePath $repository $relative
        $repack = New-RepackedApWorld -Source $source -Destination $target
        $details = Assert-RepackedApWorldReplacement -Repository $repository -RepackedHash (Get-Sha256 $target)
        [PSCustomObject]@{ unchanged_world_files = $repack.file_count; installation = $details }
    }

    Invoke-ValidationCase 'changed uncompressed APWorld entry is rejected before any transaction' {
        Reset-PatchState
        $repository = New-SourceFixture 'modified-apworld-entry'
        $relative = 'archipelago/soh_extreme.apworld'
        $source = Join-SafePath (Join-Path $PackageDirectory 'payload') $relative
        $target = Join-SafePath $repository $relative
        $repack = New-RepackedApWorld -Source $source -Destination $target -ChangeWorldEntry
        $before = Get-Sha256 $target
        $original = [IO.Compression.ZipFile]::OpenRead($source)
        $modified = [IO.Compression.ZipFile]::OpenRead($target)
        try {
            $originalEntry = $original.GetEntry($repack.changed_entry)
            $modifiedEntry = $modified.GetEntry($repack.changed_entry)
            Assert-Condition ($null -ne $originalEntry -and $null -ne $modifiedEntry) 'The changed entry name was not preserved.'
            Assert-Condition ($originalEntry.Length -eq $modifiedEntry.Length) 'The mutation must preserve length to exercise the content hash check.'
        } finally { $modified.Dispose(); $original.Dispose() }
        $errorMessage = Assert-Throws {
            $plan = @(Read-PatchPlan $repository)
            Apply-PatchFiles -Repository $repository -Plan $plan
        } 'differs from'
        Assert-Condition ((Get-Sha256 $target) -eq $before) 'Preflight overwrote the edited APWorld.'
        foreach ($file in $script:Files) {
            if ($file.path -ceq $relative) { continue }
            $path = Join-SafePath $repository $file.path
            if ($null -eq $file.original_sha256) {
                Assert-Condition (-not [IO.File]::Exists($path)) ('APWorld rejection created a source file: ' + $file.path)
            } else {
                Assert-Condition ((Get-Sha256 $path) -eq $file.original_sha256) ('APWorld rejection changed another source: ' + $file.path)
            }
        }
        Assert-Condition (-not [IO.Directory]::Exists((Join-Path $repository 'soh-extreme-patch-backups'))) 'Modified APWorld started a transaction.'
        [PSCustomObject]@{
            changed_entry = $repack.changed_entry; entry_name_and_length_preserved = $true
            source_copies = 0; transaction_started = $false; error = $errorMessage
        }
    }

    Invoke-ValidationCase 'source mismatch fails full preflight before any copying' {
        Reset-PatchState
        $repository = New-SourceFixture 'source-mismatch'
        $originals = @($script:Files | Where-Object { $null -ne $_.original_sha256 })
        $last = $originals[$originals.Count - 1]
        $tampered = Join-SafePath $repository $last.path
        [IO.File]::AppendAllText($tampered, 'user edit preserved')
        $before = Get-Sha256 $tampered
        $errorMessage = Assert-Throws {
            $plan = @(Read-PatchPlan $repository)
            Apply-PatchFiles -Repository $repository -Plan $plan
        } 'differs from'
        Assert-Condition ((Get-Sha256 $tampered) -eq $before) 'Preflight overwrote the edited file.'
        foreach ($file in $originals) {
            if ($file.path -eq $last.path) { continue }
            Assert-Condition ((Get-Sha256 (Join-SafePath $repository $file.path)) -eq $file.original_sha256) ('Preflight copied an earlier source: ' + $file.path)
        }
        Assert-Condition (-not [IO.Directory]::Exists((Join-Path $repository 'soh-extreme-patch-backups'))) 'A source mismatch started a transaction.'
        $errorMessage
    }

    Invoke-ValidationCase 'conflicting new-file contents cannot be overwritten' {
        Reset-PatchState
        $repository = New-SourceFixture 'new-file-mismatch'
        $file = @($script:Files | Where-Object { $null -eq $_.original_sha256 })[0]
        $target = Join-SafePath $repository $file.path
        [void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($target))
        [IO.File]::WriteAllText($target, 'existing user file')
        [void](Assert-Throws { $null = @(Read-PatchPlan $repository) } 'differs from')
        Assert-Condition ([IO.File]::ReadAllText($target) -eq 'existing user file') 'New-file collision was not preserved.'
        Assert-Condition (-not [IO.Directory]::Exists((Join-Path $repository 'soh-extreme-patch-backups'))) 'New-file mismatch started a transaction.'
        'Conflicting user file preserved before transaction creation.'
    }

    Invoke-ValidationCase 'forced later copy failure rolls back all actual payload files' {
        Reset-PatchState
        $repository = New-SourceFixture 'forced-rollback'
        $package = Join-Path $script:FixtureRoot 'rollback-package'
        [void][IO.Directory]::CreateDirectory($package)
        $payload = Join-Path $package 'payload'
        foreach ($file in $script:Files) {
            $target = Join-SafePath $payload $file.path
            [void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($target))
            [IO.File]::Copy((Join-SafePath (Join-Path $PackageDirectory 'payload') $file.path), $target, $false)
        }
        $failureRelative = 'occupied-parent/late-new-file.txt'
        $failurePayload = Join-SafePath $payload $failureRelative
        [void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($failurePayload))
        [IO.File]::WriteAllText($failurePayload, 'deliberate fixture payload')
        # Preflight can read every file. Commit then fails naturally after all
        # real payload files have been applied:
        # an existing regular file cannot become its required parent directory.
        [IO.File]::WriteAllText((Join-Path $repository 'occupied-parent'), 'preserve this regular file')
        $files = @($script:Files) + @([PSCustomObject]@{
            path = $failureRelative; original_sha256 = $null; sha256 = Get-Sha256 $failurePayload
        })
        $manifest = [PSCustomObject]@{ version = $script:ManifestVersion; files = $files }
        [IO.File]::WriteAllText((Join-Path $package 'manifest.json'), ($manifest | ConvertTo-Json -Depth 10), [Text.UTF8Encoding]::new($false))
        $script:PackageRoot = $package
        $plan = @(Read-PatchPlan $repository)
        Assert-Condition ($plan.Count -eq ($script:Files.Count + 1)) 'The rollback fixture did not reach complete preflight.'
        [void](Assert-Throws { Apply-PatchFiles -Repository $repository -Plan $plan } 'Patch application failed')
        Assert-OriginalSource $repository
        Assert-Condition ([IO.File]::ReadAllText((Join-Path $repository 'occupied-parent')) -eq 'preserve this regular file') 'Failure fixture collateral file changed.'
        $saved = Get-Content -LiteralPath (Join-Path $script:BackupRoot 'restore-manifest.json') -Raw | ConvertFrom-Json
        Assert-Condition ($saved.status -eq 'rolled_back') 'Rollback did not record completion.'
        Assert-Condition (@($saved.rollback_errors).Count -eq 0) 'Rollback reported an error.'
        Assert-Condition ($saved.build_status -eq 'not_started') 'A failed transaction started a build.'
        foreach ($file in $script:Files) {
            Assert-Condition (-not [IO.File]::Exists((Join-SafePath (Join-Path $script:BackupRoot 'staged') $file.path))) ('Actual payload was not committed before the forced failure: ' + $file.path)
        }
        [PSCustomObject]@{ committed_before_failure = $script:Files.Count; originals_restored = $script:OriginalCount; new_files_removed = $script:NewCount; rollback_errors = 0; build_started = $false }
    }

    $report.status = 'passed'
} catch {
    $failed = $true
    $report.status = 'failed'
    $report.failure = $_.Exception.Message
    Write-Host ('VALIDATION FAILED: ' + $_.Exception.Message) -ForegroundColor Red
} finally {
    $report.cases = @($script:Cases.ToArray())
    $report.completed_utc = [DateTime]::UtcNow.ToString('o')
    [void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($ResultPath))
    [IO.File]::WriteAllText($ResultPath, ($report | ConvertTo-Json -Depth 10), [Text.UTF8Encoding]::new($false))
    Write-Host ('Validation result: ' + $ResultPath)
    if ($KeepFixtures) { Write-Host ('Fixtures retained: ' + $script:FixtureRoot) }
    else { Remove-Item -LiteralPath $script:FixtureRoot -Recurse -Force }
}
if ($failed) { exit 1 }
Write-Host ('All ' + $script:Cases.Count + ' focused installer validation cases passed.') -ForegroundColor Green
exit 0
