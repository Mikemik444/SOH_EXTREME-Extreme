SOH-EXTREME - APWORLD SOURCE UPDATE + SEPARATE PACKER PATH REPAIR
World version: 0.11.22
Source: Mikemik444/SOH_EXTREME-Extreme at
473e6c69d146fb426fd83f9d1278c3c717fa865d

1. UPDATE THE UNZIPPED APWORLD

Close Archipelago tools and Universal Tracker. Keep a backup of your current
arvhipelago folder outside custom_worlds. Extract this entire ZIP into:
  E:\test\bb
Merge arvhipelago and replace its files when asked.

The arvhipelago folder in this ZIP is COMPLETE: your last-working extracted
world, with the missing 0.11.22 AP logic applied. No installer needs to run for
these Python/source changes to take effect in the extracted folder.
No stock SoH helpers are downloaded or substituted. Your modified vendored
helpers, existing options, item/location IDs and other earlier rules are kept.

2. ZIP IT BACK INTO AN APWORLD

Open E:\test\bb\arvhipelago. Zip these TWO entries together:
  archipelago.json
  soh_extreme\
Rename the resulting ZIP to soh_extreme.apworld, replacing the .zip extension.
The outer arvhipelago folder must NOT be inside the APWorld archive.

Correct archive layout:
  soh_extreme.apworld
    archipelago.json
    soh_extreme/
      __init__.py
      archipelago.json
      Options.py
      TrackerMirror.py
      _vendor_oot_soh/
      ...the remaining package files...

Replace the installed file at:
  C:\ProgramData\Archipelago\custom_worlds\soh_extreme.apworld
Keep old backups OUTSIDE custom_worlds; do not leave a second .apworld for the
same SOH-EXTREME game alongside the installed one. Restart AP/Universal Tracker.

This updates your local files only. Commit/push arvhipelago to publish on GitHub.
You do NOT need CMake or build.cmd to zip or update the APWorld.

3. FIX THE SEPARATE GAME-BUILD ERROR

The optional, separate repair is for the missing source-file error:
  assets/tools/soh-o2r-packer/main.cpp
The repository's existing sources are actually under:
  soh/assets/tools/soh-o2r-packer/

Close the game and finish/stop any active build. Double-click:
  FIX_PACKER_PATH.cmd
Then run your existing build.cmd normally.

This helper backs up CMakeLists.txt, replaces only its asset-target block with
layout-aware tool discovery/staging, and excludes nested build tools from the
soh executable's recursive source glob. It preserves unrelated CMake settings
and does NOT edit build.cmd. Reapplying is safe and makes no further edits.

Both soh/assets/custom and any assets/custom overlay are staged for the packer.
The root overlay takes precedence, preserving textures from previous installers.
Shaders come from the selected LibUltraShip source. Source assets are not removed.
A failed/empty pack does not overwrite an existing soh.o2r.

FIX_PACKER_PATH.cmd does NOT package/install an APWorld and does NOT start a
build automatically. Do not delete build-vs. Do not rerun older patch installers.
After a successful game build use E:\test\bb\soh.exe, not an older Release2 copy.
This source update has NO client C++ files, soul textures or APCpp DLL changes.
The existing 0.11.22 client patch still needs a successful build for its visual
changes and matching 0.11.22 in-game tracker protocol to be active.

WHAT AP LOGIC CHANGED

The Dodongos Cavern Boss Region -> Boss Entryway route now uses can_grab()
instead of an unconditional True_(). With Shuffle Grab on, the actual Grab /
Power Bracelet capability is required to push the block onto the switch, for
both child and adult. With Shuffle Grab off, the capability remains innate.
The chest and boss beyond the gate inherit it; other existing requirements stay.

The native DODONGOS_CAVERN_BOSS_AREA token maps to AP's
DODONGOS_CAVERN_BOSS_REGION in both create_regions and set_rules. This allows the
existing native Grab dependency to survive region/rule projection.

Both archipelago.json manifests and the Python tracker use 0.11.22, matching the
already-delivered 0.11.22 client patch. No item/location IDs are renumbered.

The earlier house-pot, enemy-room, soul, ability, scale/strength, Shovel, time,
silver-rupee and slot-data code from the working 0.11.21d world is preserved.
The source comparison found 5 existing files changed and 1 release note added;
the other 96 existing files are unchanged. This is not a claim that every rule
in the entire game has been audited or that all possible seeds were tested.

EXISTING SEEDS

Updating an APWorld does not move rewards in an existing generated seed.
The updated rules apply to future generation and tracker evaluation. Generate a
new seed to have item placement use the corrected gate; an old circular placement
cannot be repaired just by repackaging its world. Save/received-item history is
not edited by this package.

VALIDATION

7 focused source/rule tests passed, including syntax checks for all 75 Python
modules, JSON validity, the actual Grab helper/entrance lambda for both ages,
setting/ownership/removal cases, both aliases, and tracker version encoding.
5 isolated build tests passed. CMake reproduced the original missing-source error
and then configured/built a MOCK packer and dummy game under both source layouts.
The tests also checked source-glob exclusion, base/overlay staging, failed-output
preservation, and idempotent edit plans using the actual PowerShell regex strings.
The original unconditional rule was separately verified to pass with Grab absent.

No full AP runtime import, complete seed generation, Windows/MSVC game build,
Windows PowerShell execution, or in-game visual testing was performed here.
Tests, actual output, Git-tree/source audit, and exact AP source diff are under
validation/. They are outside arvhipelago and should not be added to the APWorld.
