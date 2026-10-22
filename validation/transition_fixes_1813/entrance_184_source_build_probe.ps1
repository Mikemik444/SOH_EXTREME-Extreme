#requires -Version 5.1
<# Execute the shipped source-build helper functions against a disposable
   configured CMake project; only the main Windows OS check is bypassed.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$PackageDirectory,
    [Parameter(Mandatory = $true)][string]$RepositoryPath,
    [Parameter(Mandatory = $true)][string]$BuildDirectory,
    [Parameter(Mandatory = $true)][string]$ResultPath,
    [switch]$VerifyOnly
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$script:PackageRoot = [IO.Path]::GetFullPath($PackageDirectory)
$script:BuildRecordRoot = $null
$tokens = $null
$parseErrors = $null
$helper = Join-Path $script:PackageRoot 'BUILD_RELEASE.ps1'
$ast = [Management.Automation.Language.Parser]::ParseFile($helper, [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count -ne 0) { throw 'Build helper parse failed.' }
$functions = @($ast.FindAll({ param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] }, $true))
foreach ($definition in $functions) { . ([ScriptBlock]::Create($definition.Extent.Text)) }
$sourceCopyCalls = @($ast.FindAll({
    param($node)
    $node -is [Management.Automation.Language.InvokeMemberExpressionAst] -and
        $node.Expression.Extent.Text -eq '[IO.File]' -and $node.Member.Value -in @('Copy', 'Move', 'Replace')
}, $true))
if ($sourceCopyCalls.Count -ne 0) { throw 'The source-build helper must not copy, move or replace source files.' }
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
    function Test-SourceRepository {
        param([string]$Path)
        return ([IO.File]::Exists((Join-Path $Path 'CMakeLists.txt')) -and
            [IO.File]::Exists((Join-Path $Path 'soh/Network/Archipelago/EntranceRuntime.inc')))
    }
}
$repository = Find-SourceRepository
Assert-CopiedSourceFiles $repository
if ($VerifyOnly) {
    [IO.File]::WriteAllText($ResultPath, '{"status":"passed","source_verification_only":true}', [Text.UTF8Encoding]::new($false))
    exit 0
}
$code = Build-ExistingRelease $repository
$header = Join-SafePath $repository 'soh/SohExtremeVersion.h'
$exe = Join-Path $BuildDirectory 'soh.exe'
$receipts = @(Get-ChildItem -LiteralPath (Join-Path $repository 'soh-extreme-builds') -Filter 'build-receipt.json' -Recurse -File)
if ($receipts.Count -ne 1) { throw 'Expected exactly one build receipt.' }
$receipt = Get-Content -LiteralPath $receipts[0].FullName -Raw -Encoding UTF8 | ConvertFrom-Json
$report = [ordered]@{
    platform = [Environment]::OSVersion.Platform.ToString()
    powershell = $PSVersionTable.PSVersion.ToString()
    build_helper_sha256 = Get-Sha256 $helper
    fixture_manifest_sha256 = Get-Sha256 (Join-Path $script:PackageRoot 'SOURCE_FILES.json')
    build_exit_code = $code
    executable_version_output = ((& $exe) | Out-String).Trim()
    executable_sha256 = Get-Sha256 $exe
    source_last_write_utc = [IO.File]::GetLastWriteTimeUtc($header).ToString('o')
    executable_last_write_utc = [IO.File]::GetLastWriteTimeUtc($exe).ToString('o')
    build_receipt = $receipt
    functions_loaded_from_helper = @($functions | ForEach-Object { $_.Name })
    source_copy_move_replace_calls = $sourceCopyCalls.Count
    limitations = @(
        'This compiles a minimal program including the real delivered native version header, not the complete game.',
        'The CMake fixture uses Unix Makefiles and GCC; Windows MSBuild and Windows PowerShell 5.1 are not executed.',
        'The main Windows OS check is bypassed. Two path helpers receive equivalent Unix separators.'
    )
}
[IO.File]::WriteAllText($ResultPath, ($report | ConvertTo-Json -Depth 10), [Text.UTF8Encoding]::new($false))
if ($code -ne 0) { exit $code }
