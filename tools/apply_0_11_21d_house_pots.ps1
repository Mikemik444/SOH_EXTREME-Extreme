param(
    [string]$Root = ""
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($Root)) {
    $Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
} else {
    $Root = (Resolve-Path $Root).Path
}

$replacement = 'logic->CanBreakPots() && (logic->HasItem(RG_POWER_BRACELET) || logic->CanJumpslash() || logic->CanUse(RG_GIANTS_KNIFE) || logic->CanUse(RG_BOOMERANG) || logic->CanUse(RG_HOOKSHOT) || logic->CanUse(RG_LONGSHOT) || logic->CanUse(RG_FAIRY_SLINGSHOT) || logic->CanUse(RG_FAIRY_BOW))'

$targets = @(
    @{
        Path = 'soh\Enhancements\randomizer\location_access\overworld\kokiri_forest.cpp'
        Expected = 5
        Patterns = @('RC_KF_LINKS_HOUSE_POT', 'RC_KF_TWINS_HOUSE_POT_', 'RC_KF_BROTHERS_HOUSE_POT_')
    },
    @{
        Path = 'soh\Enhancements\randomizer\location_access\overworld\market.cpp'
        Expected = 58
        Patterns = @('RC_MK_GUARD_HOUSE_CHILD_POT_', 'RC_MK_GUARD_HOUSE_ADULT_POT_', 'RC_MK_BACK_ALLEY_HOUSE_POT_')
    },
    @{
        Path = 'soh\Enhancements\randomizer\location_access\overworld\lon_lon_ranch.cpp'
        Expected = 3
        Patterns = @('RC_LLR_TALONS_HOUSE_POT_')
    }
)

function Matches-TargetLine([string]$line, [string[]]$patterns) {
    foreach ($pattern in $patterns) {
        if ($line.Contains($pattern)) { return $true }
    }
    return $false
}

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$totalChanged = 0

foreach ($target in $targets) {
    $path = Join-Path $Root $target.Path
    if (-not (Test-Path $path)) {
        throw "Required source file not found: $path"
    }

    $lines = [System.IO.File]::ReadAllLines($path)
    $matched = 0
    $changed = 0

    for ($i = 0; $i -lt $lines.Length; $i++) {
        if (-not (Matches-TargetLine $lines[$i] $target.Patterns)) { continue }
        $matched++

        if ($lines[$i].Contains($replacement)) {
            continue
        }

        if (-not $lines[$i].Contains('logic->CanBreakPots()')) {
            throw "0.11.21d refused to edit an unexpected house-pot rule in $path at line $($i + 1):`n$($lines[$i])"
        }

        $lines[$i] = $lines[$i].Replace('logic->CanBreakPots()', $replacement)
        $changed++
    }

    if ($matched -ne $target.Expected) {
        throw "0.11.21d expected $($target.Expected) house-pot rules in $path but found $matched. Source layout changed; nothing was written to this file."
    }

    if ($changed -gt 0) {
        $backup = "$path.pre-0.11.21d.bak"
        if (-not (Test-Path $backup)) {
            Copy-Item -LiteralPath $path -Destination $backup
        }
        [System.IO.File]::WriteAllLines($path, $lines, $utf8NoBom)
    }

    Write-Host ("{0}: {1} house-pot rules verified, {2} changed" -f $target.Path, $matched, $changed)
    $totalChanged += $changed
}

Write-Host ""
if ($totalChanged -eq 0) {
    Write-Host "SOH-EXTREME 0.11.21d house-pot source rules were already installed."
} else {
    Write-Host "SOH-EXTREME 0.11.21d patched $totalChanged house-pot rules."
}
Write-Host "Bombs/Bombchus no longer count as a break method in residential interiors."
