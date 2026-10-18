#requires -Version 5.1
<# Load and execute actual installer functions against a disposable CMake fixture.
   This intentionally bypasses only the Windows main-entry OS check. On Unix,
   Join-SafePath retains its containment validation but uses '/' separators.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$PackageDirectory,
    [Parameter(Mandatory = $true)][string]$RepositoryPath,
    [Parameter(Mandatory = $true)][string]$BuildDirectory,
    [Parameter(Mandatory = $true)][string]$ResultPath
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$script:PackageRoot = [IO.Path]::GetFullPath($PackageDirectory)
$script:BackupRoot = $null
$script:RestoreManifest = $null
$tokens = $null
$parseErrors = $null
$installer = Join-Path $script:PackageRoot 'APPLY_AND_BUILD.ps1'
$ast = [Management.Automation.Language.Parser]::ParseFile($installer, [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count -ne 0) { throw 'Installer parse failed.' }
$functions = @($ast.FindAll({ param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] }, $true))
foreach ($definition in $functions) {
    . ([ScriptBlock]::Create($definition.Extent.Text))
}
if ([IO.Path]::DirectorySeparatorChar -ne '\') {
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
}
$plan = @(Read-PatchPlan $RepositoryPath)
Apply-PatchFiles -Repository $RepositoryPath -Plan $plan
$code = Build-ExistingRelease $RepositoryPath
$header = Join-SafePath $RepositoryPath 'soh/SohExtremeVersion.h'
$exe = Join-Path $BuildDirectory 'soh.exe'
$report = [ordered]@{
    platform = [Environment]::OSVersion.Platform.ToString()
    powershell = $PSVersionTable.PSVersion.ToString()
    installer_sha256 = Get-Sha256 $installer
    manifest_sha256 = Get-Sha256 (Join-Path $script:PackageRoot 'manifest.json')
    installer_build_exit_code = $code
    applied_files = @($plan | Where-Object { $_.Action -ne 'skip' }).Count
    skipped_files = @($plan | Where-Object { $_.Action -eq 'skip' }).Count
    source_version = [IO.File]::ReadAllText($header).Trim()
    source_last_write_utc = [IO.File]::GetLastWriteTimeUtc($header).ToString('o')
    executable_version_output = ((& $exe) | Out-String).Trim()
    executable_sha256 = Get-Sha256 $exe
    executable_last_write_utc = [IO.File]::GetLastWriteTimeUtc($exe).ToString('o')
    backup_root = $script:BackupRoot
    functions_loaded_from_installer = @($functions | ForEach-Object { $_.Name })
    limitations = @(
        'This compiles a minimal program including the real patched native version header, not the complete game.',
        'The CMake fixture uses Unix Makefiles and GCC; Windows MSBuild and Windows PowerShell 5.1 are not executed.',
        'The installer main Windows OS check is bypassed and only Join-SafePath receives the Unix separator adapter.'
    )
}
$receipts = @(Get-ChildItem -LiteralPath (Join-Path $RepositoryPath 'soh-extreme-patch-backups') -Filter 'build-receipt.json' -Recurse -File -ErrorAction SilentlyContinue)
if ($receipts.Count -eq 1) {
    $report.build_receipt = Get-Content -LiteralPath $receipts[0].FullName -Raw -Encoding UTF8 | ConvertFrom-Json
} else {
    $report.build_receipt = $null
}
[IO.File]::WriteAllText($ResultPath, ($report | ConvertTo-Json -Depth 10), [Text.UTF8Encoding]::new($false))
if ($code -ne 0) { exit $code }
