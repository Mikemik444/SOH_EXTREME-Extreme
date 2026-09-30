SOH-EXTREME Closed Forest / NPC route fix - 2026-09-29
Version 0.11.30; cumulative Windows x64 Release
Repository: https://github.com/Mikemik444/SOH_EXTREME-Extreme

WHAT WAS WRONG
The 0.11.29 speech-check patch let Speak and NPC Soul grant access to some
conversations without requiring their physical region. The child/adult helper
was only checking the current age during a location evaluation. The neutral
Menu parent did not supply the missing physical route. Earlier AP/UT comparisons
missed this because both used the same incorrect rule.

Your AP_77252263651583399414 seed had Closed Forest ON and Rock / Boulder Soul
shuffle ON. It put Crawl on the DMT Cavern Entrance Goron's conversation before
you could leave the forest. Bombchus do not replace Rock / Boulder Soul for the
Lost Woods-Goron City shortcut. The existing shortcut/Closed Forest rules were
being bypassed by the speech locations; those rules were not disabled.

WHAT IS FIXED
- Each NPC conversation now requires an actual route to that NPC's region.
- Child-only routes require child access; adult-only routes require adult access.
  Region-rule results cannot be reused across those two ages. Owning an adult
  item does not make an adult NPC reachable as child Link.
- Moving NPCs keep their legitimate alternative regions. Each alternative carries
  its own age, region, time and interaction requirements. Mido's house condition
  also explicitly checks the house, including its shuffled door key when enabled.
- Climb, Crawl, Swim, Grab, keys, souls and dungeon/clock requirements along the
  route apply before the NPC is in logic. NPC Soul and the proper language still
  apply to the conversation. Roll, Open Chest and Shovel apply to the physical
  actions/routes that need them; they are not arbitrary universal NPC requirements.
- Every earlier cumulative repair remains included. First-talk identities and
  location IDs have not changed since 0.11.29.

ABOUT MISSING NPC SOUL
The current runtime freezes NPC updates (including their collider registration)
while NPC Soul is missing. Receiving it can restore a physical blocker. Generation
must not rely on a passage that closes after obtaining an item. The corrected
logic retains the normal Closed Forest requirements regardless of this runtime
bypass. This patch does not change the NPC Soul actor behavior.

YOUR EXISTING SEED
The corrected read-only replay stops at 37/3325 checks, even if all 118 SOH items
placed in the other games are granted optimistically. An offline hypothetical
Climb + Rock / Boulder Soul reaches only 479 checks, not completion. Therefore
those two items are not a verified complete recovery. No items were granted and
no server or save was modified.

Install 0.11.30 BEFORE generating a NEW multiworld and start a save for that seed.
Updating an executable/APWorld cannot relocate items already placed by 0.11.29.
The updated finder can evaluate an old seed but cannot repair its placements.

WINDOWS DRAG-AND-DROP REPLACEMENT (NO BUILD REQUIRED)
1. Close SOH and Archipelago/Universal Tracker. Keep a copy of the old files.
2. Extract SOH-EXTREME-Forest-Speech-Fix-Windows-x64.zip. Replace soh.exe and
   APCpp.dll in your existing game folder. Keep assets, soh.o2r, saves and config.
3. Install the included soh_extreme.apworld with Archipelago's Install APWorld
   action. Restart all AP/Universal Tracker processes to load 0.11.30.
4. Generate the new multiworld and start the new seed/save.
Use this EXE together with this APWorld: both use tracker version 0.11.30.

SOURCE OVERLAY ALTERNATIVE
1. Extract the CONTENTS of SOH-EXTREME-Forest-Speech-Fix-Source-Patch.zip into
   the source root beside build.cmd and CMakeLists.txt. Merge/replace files.
2. Open a FRESH Command Prompt there and run build.cmd. Wait for BUILD COMPLETE.
3. Restart AP/Universal Tracker after the build installs its matching APWorld,
   then generate a new multiworld and start a new seed/save.
The .patch is for Git/review; do not apply it again after copying the files.

VERIFICATION
- 3,176 sparse-inventory, physical-region, AP/UT and child/adult-start assertions.
  These compare NPC access with the actual region graph, rather than relying on
  agreement between two consumers of the same rule. The test fails on 0.11.29.
- All 3,325 configured checks were evaluated in 181 fresh-inventory scenarios:
  601,825 AP/UT comparisons, with no failures. Coverage includes Roll, Grab and
  strength tiers, Climb, Crawl, Swim/scales, every language, chest opening,
  Shovel, time, souls, ocarina notes/buttons and related shuffled capabilities.
- First-talk/old-and-new-slot tests and compiled C++ conversation tests rerun.
- Enabled/disabled capability settings checked against native slot settings.
- New day-start and frozen-night seeds using your 216 resolved options filled
  successfully and independent collection replay reached the goal and every check.
- Windows x64 Release build completed. APWorld source/archive byte parity,
  DLL loading, cumulative patch application and ZIP contents verified.

LIMITS
No live connected gameplay session was performed. These tests do not certify
every physical obstacle or every combination of settings. The source audit keeps
its physical encounter and region-mapping review gaps visible. The 181-entry NPC
catalogue still excludes capturing Gerudo sentries and the transient membership-
card giver. Generation tests use a single SOH player; replay of your old multiworld
assumes external receipts rather than simulating the other games.

INCLUDED RECORDS
VALIDATION-FOREST-SPEECH-FIX.json: current results, hashes and limitations
CHECK-AUDIT-FOREST-SPEECH.json: per-location and inventory audit evidence
SOH_AP_FIX_HISTORY.txt: cumulative requirements, reports and corrections
SHA256SUMS-FOREST-SPEECH-FIX.txt: checksums of each ZIP's contents
