$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$Root = Split-Path -Parent $PSScriptRoot
$Utf8 = [System.Text.UTF8Encoding]::new($false)
$CMakePath = Join-Path $Root 'CMakeLists.txt'
$ItemPath = Join-Path $Root 'soh\Enhancements\randomizer\item_list.cpp'
$TrackerPath = Join-Path $Root 'soh\Enhancements\randomizer\randomizer_item_tracker.cpp'
$GuiPath = Join-Path $Root 'soh\SohGui\ImGuiUtils.cpp'
$ModulePath = Join-Path $Root 'CMake\SoHExtremeAPCppSafety.cmake'
$HeaderPath = Join-Path $Root 'soh\Enhancements\randomizer\ProgressionItemVisuals.h'
foreach ($Path in @($CMakePath, $ItemPath, $TrackerPath, $GuiPath, $ModulePath, $HeaderPath, (Join-Path $Root 'build.cmd'))) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Missing file: $Path. Extract this complete ZIP into E:\test\bb first."
    }
}
$CMakeOriginal = [IO.File]::ReadAllText($CMakePath)
$ItemsOriginal = [IO.File]::ReadAllText($ItemPath)
$TrackerOriginal = [IO.File]::ReadAllText($TrackerPath)
$GuiOriginal = [IO.File]::ReadAllText($GuiPath)
$CMake = $CMakeOriginal.Replace("`r`n", "`n")
$Items = $ItemsOriginal.Replace("`r`n", "`n")
$Tracker = $TrackerOriginal.Replace("`r`n", "`n")
$Gui = $GuiOriginal.Replace("`r`n", "`n")

# Validate every source edit before changing any existing file.
foreach ($Id in @('RG_SHOVEL', 'RG_ROLL')) {
    if (-not [regex]::IsMatch($Items, 'itemTable\[' + $Id + '\]\s*=\s*Item\(')) {
        throw "Cannot find the native $Id entry. No existing files have been changed."
    }
}
$Begin = '    // SOH-EXTREME SHOVEL/ROLL VISUALS v1 BEGIN'
$End = '    // SOH-EXTREME SHOVEL/ROLL VISUALS v1 END'
$Block = @'
    // SOH-EXTREME SHOVEL/ROLL VISUALS v1 BEGIN
    // Both the world/get-item model and the native message/UI icon are replaced.
    // Preserve item IDs, ownership effects, chest animation and AP mappings.
    itemTable[RG_SHOVEL].CustomIcon(gExtremeShovelIconTex);
    itemTable[RG_SHOVEL].SetCustomDrawFunc(SohExtreme_DrawShovel);
    itemTable[RG_ROLL].CustomIcon(gExtremeRollIconTex);
    itemTable[RG_ROLL].SetCustomDrawFunc(SohExtreme_DrawRoll);
    // SOH-EXTREME SHOVEL/ROLL VISUALS v1 END
'@
$Block = $Block.Replace("`r`n", "`n")
if ($Items.Contains($Begin)) {
    $Pattern = '(?s)' + [regex]::Escape($Begin) + '.*?' + [regex]::Escape($End)
    $ExistingBlocks = [regex]::Matches($Items, $Pattern)
    if ($ExistingBlocks.Count -ne 1) { throw 'Invalid/incomplete existing Shovel/Roll patch marker.' }
    $Match = $ExistingBlocks[0]
    $Items = $Items.Substring(0, $Match.Index) + $Block + $Items.Substring($Match.Index + $Match.Length)
} else {
    $Anchor = '    // Init itemNameToEnum'
    if ([regex]::Matches($Items, [regex]::Escape($Anchor)).Count -ne 1) {
        throw 'Cannot find the item-table initialization boundary. No existing files changed.'
    }
    $Items = $Items.Replace($Anchor, $Block + "`n`n" + $Anchor)
}
$Include = '#include "ProgressionItemVisuals.h"'
if (-not $Items.Contains($Include)) { $Items = $Include + "`n" + $Items }

# The tracker previously forced unrelated boots/hammer icons, bypassing CustomIcon.
foreach ($Spec in @(@('RG_SHOVEL', 'SHOVEL'), @('RG_ROLL', 'ROLL'))) {
    $Pattern = 'ITEM_TRACKER_RG(?:_CUSTOM)?\(\s*' + $Spec[0] + '\s*,[^\r\n)]*\)'
    if ([regex]::Matches($Tracker, $Pattern).Count -ne 1) {
        throw "Expected exactly one $($Spec[0]) tracker entry. No existing files changed."
    }
    $Replacement = 'ITEM_TRACKER_RG(' + $Spec[0] + ', "' + $Spec[1] + '", 0, DrawItem)'
    $Tracker = [regex]::Replace($Tracker, $Pattern, $Replacement)
}

# Register the actual custom texture names used by those tracker entries.
# Restrict replacements to this map, preserving all soul and other GUI mappings.
$MapPattern = '(?s)(std::map<uint32_t,\s*ItemMapEntry>\s+customItemsMapping\s*=\s*\{)(.*?)(\n\};)'
$MapMatches = [regex]::Matches($Gui, $MapPattern)
if ($MapMatches.Count -ne 1) { throw 'Cannot locate the custom GUI icon map. No existing files changed.' }
$MapMatch = $MapMatches[0]
$MapBody = $MapMatch.Groups[2].Value
foreach ($Spec in @(@('RG_SHOVEL', 'gExtremeShovelIconTex'), @('RG_ROLL', 'gExtremeRollIconTex'))) {
    $Id = $Spec[0]
    $Entry = '    { ' + $Id + ', { ' + $Id + ', "' + $Id + '", "' + $Id + '_Faded", ' + $Spec[1] + ' } },'
    $EntryPattern = '(?m)^[ \t]*\{\s*' + $Id + '\s*,\s*\{\s*' + $Id + '\s*,\s*"' + $Id + '"\s*,\s*"' + $Id + '_Faded"\s*,\s*[^{}]*?\}\s*\},?[ \t]*$'
    $EntryMatches = [regex]::Matches($MapBody, $EntryPattern)
    if ($EntryMatches.Count -eq 1) {
        $MapBody = [regex]::Replace($MapBody, $EntryPattern, $Entry)
    } elseif ($EntryMatches.Count -eq 0 -and -not [regex]::IsMatch($MapBody, '\b' + $Id + '\b')) {
        $MapBody = "`n" + $Entry + $MapBody
    } else {
        throw "Unexpected or duplicate $Id GUI entry. No existing files changed."
    }
}
$Gui = $Gui.Substring(0, $MapMatch.Index) + $MapMatch.Groups[1].Value + $MapBody + $MapMatch.Groups[3].Value + $Gui.Substring($MapMatch.Index + $MapMatch.Length)
$GuiInclude = '#include "soh/Enhancements/randomizer/ProgressionItemVisuals.h"'
if (-not $Gui.Contains($GuiInclude)) { $Gui = $GuiInclude + "`n" + $Gui }

$CMakeInclude = 'include("${CMAKE_CURRENT_LIST_DIR}/CMake/SoHExtremeAPCppSafety.cmake")'
if (-not $CMake.Contains($CMakeInclude)) {
    $CMake += "`n# SOH-EXTREME: generated APCpp request-safety fixes; preserve existing build settings.`n" + $CMakeInclude + "`n"
}

$Textures = Join-Path $Root 'assets\custom\textures\parameter_static'
$TextureNames = @('gExtremeShovelIcon', 'gExtremeRollIcon', 'gExtremeShovelWood', 'gExtremeAbilityMetal')
foreach ($Name in $TextureNames) {
    $Source = Join-Path $Textures ($Name + '.rgba32.png')
    if (-not (Test-Path -LiteralPath $Source -PathType Leaf)) { throw "Missing packaged texture: $Source" }
}
$Changes = @(
    @{ Path = $CMakePath; Name = 'CMakeLists.txt'; Original = $CMakeOriginal; New = $CMake },
    @{ Path = $ItemPath; Name = 'item_list.cpp'; Original = $ItemsOriginal; New = $Items },
    @{ Path = $TrackerPath; Name = 'randomizer_item_tracker.cpp'; Original = $TrackerOriginal; New = $Tracker },
    @{ Path = $GuiPath; Name = 'ImGuiUtils.cpp'; Original = $GuiOriginal; New = $Gui }
)
$Backup = Join-Path $Root ('patch-backups\shovel-roll-apcpp-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
New-Item -ItemType Directory -Path $Backup -Force | Out-Null
foreach ($Change in $Changes) {
    Copy-Item -LiteralPath $Change.Path -Destination (Join-Path $Backup $Change.Name)
}
try {
    foreach ($Change in $Changes) {
        if ($Change.New -ne $Change.Original.Replace("`r`n", "`n")) {
            [IO.File]::WriteAllText($Change.Path, $Change.New, $Utf8)
        }
    }
    # Active packer uses root/assets/custom. Mirror to the repository layout too.
    $Mirror = Join-Path $Root 'soh\assets\custom\textures\parameter_static'
    New-Item -ItemType Directory -Path $Mirror -Force | Out-Null
    foreach ($Name in $TextureNames) {
        $Source = Join-Path $Textures ($Name + '.rgba32.png')
        $Destination = Join-Path $Mirror ($Name + '.rgba32.png')
        # Avoid copying onto itself when assets is a junction into soh/assets.
        if ((Test-Path -LiteralPath $Destination) -and
            ((Get-FileHash -LiteralPath $Source).Hash -eq (Get-FileHash -LiteralPath $Destination).Hash)) {
            continue
        }
        Copy-Item -LiteralPath $Source -Destination $Destination -Force
    }
} catch {
    foreach ($Change in $Changes) {
        Copy-Item -LiteralPath (Join-Path $Backup $Change.Name) -Destination $Change.Path -Force
    }
    throw
}
Write-Host 'Applied Shovel/Roll models, message icons, tracker icons and APCpp request-safety integration.'
Write-Host "Backup: $Backup"
Write-Host 'Existing soul files, build.cmd, /FS /MP1 settings, saves and AP logic were not replaced.'
Write-Host 'The next build regenerates the patched APCpp sources and rebuilds APCpp.dll.'
