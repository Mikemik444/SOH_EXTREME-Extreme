SOH-EXTREME all-abilities logic audit - 2026-09-29
Version 0.11.28; cumulative Windows x64 Release
Repository: https://github.com/Mikemik444/SOH_EXTREME-Extreme
Base: 9bc10e7191b546754a50da6463e074276d33862f

WHAT CHANGED
- Gerudo Valley Crate Ledge: the child route requires a usable Cucco and Grab.
  The Cucco requires Cucco Soul in individual mode, Animal Soul in shared mode,
  or no soul item when that shuffle is disabled. Reachable adult + Longshot
  remains a valid alternative. Both the crate and heart-piece checks use this.
- Hyrule Field drawbridge Wonder Items 1-3 require child Link and reachable day.
  Frozen night without Flow of Time no longer passes. The ordinary castle
  approach remains day-gated; legitimate alternate routes are preserved.
- AP boss souls are always progression, even if a caller requests filler.
  The other souls already have progression classification. All 84 native soul
  entries have important-item metadata and long hold-up animations.
- Crates were checked: Crate Soul AND a valid breaking action is required.
  Large crates: Roll, explosives or usable Hammer. Small crates also allow
  appropriate jumpslashes or Grab. Soul alone and basic Grab alone do not break
  a fixed large crate. The existing action rules passed the expanded tests.
- Retains every earlier overlay: Zora River Swim/Cucco/Grab/Climb, Mido,
  grass strength tiers, scrub payment, fishing, pickup names/hold-up, hints,
  heart healing, wallet filling, Triforce completion and AP safety repairs.

ALL ABILITIES WERE INCLUDED
Roll; Grab and strength tiers; Climb; Crawl; Swim and scales; speech/languages;
chest opening; Shovel; Flow of Time and frozen clock; fishing pole; stick/nut
bags; ocarina/buttons/song notes; wallets; and enemy, boss, animal, object,
NPC and bean souls. This means checks require valid capabilities. They were
not made universally reachable, removed, or restricted to filler placement.

SOURCE OVERLAY
1. Close SOH and Archipelago/Universal Tracker.
2. Extract the CONTENTS of SOH-EXTREME-All-Abilities-Source-Patch.zip into your
   source root, E:/test/bb, beside build.cmd and CMakeLists.txt. Merge/replace.
3. Open a FRESH Command Prompt there and run build.cmd.
4. Wait for BUILD COMPLETE, then restart SOH and AP/Universal Tracker.

build.cmd builds/installs the matching APWorld and copies the runtime to the
source root. The .patch is included for Git/review; do not apply it again after
copying the replacement files. This overlay includes the earlier fixes.

READY-BUILT ALTERNATIVE (NO BUILD REQUIRED)
1. Close SOH and Archipelago/Universal Tracker.
2. Replace soh.exe and APCpp.dll in your existing game folder with those from
   SOH-EXTREME-All-Abilities-Windows-x64.zip.
3. Install its soh_extreme.apworld using Archipelago's Install APWorld action.
4. Restart SOH and AP/Universal Tracker. Both must use 0.11.28.
Keep your existing assets, configuration and saves.

EXISTING SEEDS
Updating logic cannot move items already placed by an older APWorld. Install
this APWorld before generating a new multiworld so placement uses these rules.
Existing saves can use the corrected finder, but old placements can reveal
missing-item deadlocks. The prior Climb/Scale recovery advice was tested for
0.11.27 and is not a guarantee for 0.11.28. No server items were granted and
no saves were modified. Keep backups before replacing a seed or runtime.

VALIDATION
- Used your latest SOH-EXTREME.yaml, saved under validation/fixtures.
- Source audit enumerated 3,266 candidate network checks. Eight ordinary shop
  slots become stock events during prefill, leaving 3,258 final AP checks.
- Every final AP check was evaluated in 181 fresh-inventory scenarios:
  589,698 actual AP/installed-Universal-Tracker comparisons, no failures.
  Inventory is rebuilt before events are swept, avoiding stale ability events.
- 2,002 source-proven ability/soul requirements; 795 object-action cases;
  579 explicit age cases; 26 explicit time cases; 1,816 equipment cases passed.
- 1,007 focused route/action/soul assertions; 384 compiled native assertions;
  84 native soul metadata checks; capability, enemy-mode and clock suites passed.
- All resolved settings reconstructed from slot data despite conflicting local
  controls. Native capability settings passed 80 enabled/disabled contract tests.
- Fresh day-start and frozen-night generation/replay both reached the goal and
  all 3,258 final AP checks using Archipelago 0.6.7 with normal dependencies.
- MSVC Windows x64 Release build completed; 100-file APWorld/source parity,
  cumulative patch application, DLL loading and ZIP integrity checked.

LIMITS / AUDIT EVIDENCE
This is a source and automated logic audit, not a connected in-game playthrough.
The check-by-check evidence retains 741 native/AP region-name crosswalks that
need physical/manual review, 114 first-talk identities and 753 enemy encounters
not playtested. Those are review coverage gaps, not 1,608 confirmed bugs.
Link's Pocket is intentionally rooted at Menu; that structural flag is expected.
The item-expression audit lists 80 skipped cases rather than marking them passed.
Matching AP and UT alone does not prove every physical obstacle is represented,
and every possible option combination has not been certified.

READ THESE WITH THE PATCH
README-ALL-ABILITIES.txt              Install instructions and tested scope
VALIDATION-ALL-ABILITIES.json         Results, artifact hashes and limitations
CHECK-AUDIT-ALL-ABILITIES.json        Per-location source and inventory evidence
SOH_AP_FIX_HISTORY.txt               Your reports and cumulative requirements
SHA256SUMS-ALL-ABILITIES.txt          File checksums inside each ZIP
