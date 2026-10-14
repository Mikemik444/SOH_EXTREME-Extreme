[CmdletBinding()]
param([switch]$Apply)

$ErrorActionPreference = 'Stop'

function Invoke-CheckedGit {
    param([string[]]$GitArguments)
    & git @GitArguments
    if ($LASTEXITCODE -ne 0) {
        throw "Git stopped with exit code $LASTEXITCODE. No commit or push was performed."
    }
}

$repoRoot = & git rev-parse --show-toplevel 2>$null
if ($LASTEXITCODE -ne 0 -or !$repoRoot) {
    throw 'Open PowerShell inside your SOH_EXTREME-Extreme Git repository first.'
}
$repoRoot = $repoRoot.Trim()
Push-Location -LiteralPath $repoRoot
try {
    $remoteUrl = & git remote get-url origin 2>$null
    if ($LASTEXITCODE -ne 0 -or $remoteUrl -notmatch '(?i)(github\.com[:/])Mikemik444/SOH_EXTREME-Extreme(?:\.git)?/?$') {
        throw 'This is not the Mikemik444/SOH_EXTREME-Extreme repository. Nothing was changed.'
    }

    $staged = @(& git diff --cached --name-only)
    if ($LASTEXITCODE -ne 0) { throw 'Could not inspect staged changes.' }
    if ($staged.Count -gt 0) {
        throw 'You already have staged changes. Commit or unstage those first so this cleanup stays separate.'
    }

    # Only the reviewed SOH-EXTREME output rules are used. Do not untrack
    # everything matching .gitignore: older asset rules can match source assets.
    $cleanupPaths = @(
        ':(top,glob)build-vs/**',
        ':(top,glob)patch-backups/**',
        ':(top,glob)validation/results/**',
        ':(top,glob)soh.exe',
        ':(top,glob)APCpp.dll',
        ':(top,glob)soh.o2r',
        ':(top,glob)soh_extreme.apworld',
        ':(top,glob)*.patch',
        ':(top,glob)*.diff',
        ':(top,glob)CMakeLists.txt.before_torch_fix',
        ':(top,glob)APWORLD_SOURCE_SYNC_REPORT.json',
        ':(top,glob)FILE_MANIFEST.json',
        ':(top,glob)MANIFEST.json',
        ':(top,glob)PATCH_MANIFEST.json',
        ':(top,glob)SHA256.json',
        ':(top,glob)SHA256SUMS.json',
        ':(top,glob)SHA256SUMS-*.txt',
        ':(top,glob)CHECK-AUDIT-*.json',
        ':(top,glob)TEST-EVIDENCE-*.json',
        ':(top,glob)VALIDATION-*.json',
        ':(top,glob)VALIDATION.json',
        ':(top,glob)THREE-SEED-BEATABILITY-AUDIT.json',
        ':(top,glob)THREE-SEED-BEATABILITY-AUDIT.txt',
        ':(top,glob)manifest_all_souls_render_fix.json',
        ':(top,glob)manifest_shovel_roll_apcpp_fix.json',
        ':(top,glob)soul_render_coverage.json',
        ':(top,glob)validation/APWORLD_TEST_RESULTS.txt',
        ':(top,glob)validation/AP_FILE_HASHES.json',
        ':(top,glob)validation/AP_SOURCE.diff',
        ':(top,glob)validation/AP_SOURCE_AUDIT.json',
        ':(top,glob)validation/PACKER_TEST_RESULTS.txt',
        ':(top,glob)validation/installer-static-audit.json',
        ':(top,glob)validation/logic-results.json',
        ':(top,glob)validation/package-audit.json',
        ':(top,glob)validation/source-changes.diff',
        ':(top,glob)validation/source-parity-audit.json',
        ':(top,glob)validation/test-results.json',
        ':(top,glob)validation/test-run.txt',
        ':(top,glob)error.txt',
        ':(top,glob)testlog.txt',
        ':(top,glob)wow.txt',
        ':(top,glob)Added',
        ':(top,glob)^'
    )

    Write-Host 'Preview: files to remove from Git tracking (local files stay on disk):'
    Invoke-CheckedGit -GitArguments (@('rm', '-r', '--cached', '--dry-run', '--ignore-unmatch', '--') + $cleanupPaths)

    if (!$Apply) {
        Write-Host ''
        Write-Host 'Preview only. Run this script again with -Apply to stage these removals.'
        return
    }

    # --cached changes only the Git index. Never use filesystem deletion here.
    Invoke-CheckedGit -GitArguments (@('rm', '-r', '--cached', '--ignore-unmatch', '--') + $cleanupPaths)
    Write-Host ''
    Invoke-CheckedGit -GitArguments @('diff', '--cached', '--stat')
    Write-Host ''
    Write-Host 'Cleanup staged. Local game/build files are still on disk.'
    Write-Host 'Review with: git diff --cached --name-status'
    Write-Host 'Then commit and push when ready. This script does neither.'
    Write-Host 'Undo staging with: git restore --staged .'
}
finally {
    Pop-Location
}
