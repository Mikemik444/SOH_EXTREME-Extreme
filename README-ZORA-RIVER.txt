SOH-EXTREME Zora River logic fix - 2026-09-29
Version 0.11.27; cumulative Windows x64 Release
Repository: https://github.com/Mikemik444/SOH_EXTREME-Extreme
Base: 9bc10e7191b546754a50da6463e074276d33862f

CORRECTED REQUIREMENTS
- Wonder Near Cucco 1-3: child Link + the river route + Swim.
- Upper Circle Boulder and Upper Circle Rock 1-8:
    Climb AND (child + usable Cucco + Grab, OR reachable adult age).
  Climb is required on BOTH routes. Adult equipment alone is not adult access.
  Object-breaking and Rock / Boulder Soul requirements still apply.
- The Cucco requires Cucco Soul in individual mode, Animal Soul in shared mode,
  or no soul item with that shuffle disabled. Unshuffled abilities are innate.
- Both native Check Finder and AP generation/Universal Tracker are updated.
  Check names and IDs are unchanged. All earlier source-overlay fixes remain.

SOURCE OVERLAY
1. Close SOH and Archipelago/Universal Tracker.
2. Extract the CONTENTS of SOH-EXTREME-Zora-River-Source-Patch.zip into your
   source root, E:/test/bb, beside build.cmd and CMakeLists.txt. Merge/replace.
3. Open a FRESH Command Prompt there and run build.cmd.
4. Wait for BUILD COMPLETE; then restart the game and AP/Universal Tracker.

build.cmd builds/installs the matching APWorld and copies the runtime to the
source root. The included .patch is for review/Git use; do not also apply it
after copying the replacement files.

READY-BUILT ALTERNATIVE
1. Close SOH and Archipelago/Universal Tracker.
2. Replace soh.exe and APCpp.dll in your existing game folder with the files
   from SOH-EXTREME-Zora-River-Windows-x64.zip.
3. Install its soh_extreme.apworld using Archipelago's Install APWorld action.
4. Restart AP/Universal Tracker and SOH. Both must use version 0.11.27.
Keep existing assets, configuration and saves.

YOUR EXISTING SEED
The supplied AP_99430200357528780636 multiworld was generated with older rules.
Updating does not move its already placed items. Corrected rules expose a second
block: the Near Cucco Wonders hold required song notes but need Swim first.

Offline replay with all 39 incoming SOH items pregranted:
- Original placements: stalls after 33 of 3,258 checks.
- Extra Climb only: stalls after 355 checks. The previous Climb-only recovery
  recommendation is superseded by this release's corrected water requirements.
- Extra Climb plus one physical Progressive Scale: goal and all checks reachable.

For a new multiworld, regenerate after installing this APWorld.
To keep this old seed, its host can issue these in the ARCHIPELAGO SERVER CONSOLE:

    /send mikemik44 Climb
    /send mikemik44 Progressive Scale

Only send capabilities you still lack. If Climb was already sent/received, do
not send it again. With Swim shuffled, the first physical Progressive Scale
grants Swim. Do not send the logic-only virtual item named Swim.
These commands grant extra items rather than rearranging placements. No commands
were sent and no saves were edited by this patch. Replay assumes the other
game's SOH deliveries eventually arrive; it does not evaluate Jigsaw's logic.

SAVED HISTORY
SOH_AP_FIX_HISTORY.txt records the reports, requirements, prior fixes, tests,
current seed caveat and limits. Keep it with the source for future repairs.

VALIDATION
- Reproduced false positives against 0.11.26 before applying this fix.
- 3,412 real AP/installed-UT assertions: each missing ability, all animal-soul
  modes, abilities enabled/disabled, adult equipment without time travel, real
  age unlock, progressive ability receipts and object-soul gates.
- 768 compiled production native location-predicate assertions.
- 1,116 Mido route regressions rerun and passed.
- New generation with all 216 resolved SOH spoiler settings: goal reachable,
  all 3,258 network checks reachable in independent collection replay.
- Existing seed replay uses its exact slot data and placements.
- MSVC Windows x64 Release completed; APWorld 100-file source parity, cumulative
  patch forward/reverse application, DLL load and ZIP integrity checked.

Tests are automated with controlled engine/UI services. No connected in-game
playthrough was performed. Generation checks consistency of encoded logic;
they cannot prove every physical requirement or every settings combination.
See VALIDATION-ZORA-RIVER.json and SHA256SUMS-ZORA-RIVER.txt.
