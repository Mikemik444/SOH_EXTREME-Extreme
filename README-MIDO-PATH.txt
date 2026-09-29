SOH-EXTREME Mido path / Closed Forest fix - 2026-09-29
Version 0.11.26; cumulative Windows x64 Release
Repository: https://github.com/Mikemik444/SOH_EXTREME-Extreme
Base: 9bc10e7191b546754a50da6463e074276d33862f

WHAT WAS WRONG
The five child Withered Deku Babas in Kokiri Forest Room 1 were assigned to
the main Kokiri Forest region instead of the area beyond Mido. This bypassed
his path requirements in both the APWorld generator/tracker and native finder.
They now use KF Outside Deku Tree. Their names, network IDs and spawn identities
are unchanged, so existing server checks still refer to the same enemies.

Before Mido moves, Closed Forest ON or DEKU ONLY requires Kokiri Sword and
Deku Shield, plus NPC Soul and Kokiri speech when those shuffles are enabled.
Your seed enables NPC Soul and individual languages, so Speak Kokiri is needed.
Deku Baba Soul and a usable sword or boomerang are still needed for the enemies.
Closed Forest OFF still bypasses Mido's path gate.

The full-settings validation also caught an adult-only Gerudo Valley upper-
waterfall Wonder attached to Menu. That made it stay unavailable in child-start
seeds. It now uses its physical Gerudo Valley parent and retains its route,
Climb, water access and age requirements.

SOURCE OVERLAY
1. Close SOH and Archipelago/Universal Tracker.
2. Extract the CONTENTS of SOH-EXTREME-Mido-Path-Source-Patch.zip into your source
   root, E:/test/bb, beside CMakeLists.txt and build.cmd. Merge and replace files.
3. Open a FRESH Command Prompt in that folder and run build.cmd.
4. Wait for BUILD COMPLETE, then restart the game and Archipelago/Universal Tracker.

build.cmd builds and installs the matching APWorld and copies the EXE/DLL to
the source root. The included .patch is for review/Git use; do not apply it
again after copying the replacement files. All earlier fixes are included.

READY-BUILT ALTERNATIVE
1. Close SOH and Archipelago/Universal Tracker.
2. From SOH-EXTREME-Mido-Path-Windows-x64.zip, replace soh.exe and APCpp.dll in
   your existing game folder. Keep existing assets, configuration and saves.
3. Install its soh_extreme.apworld using Archipelago's Install APWorld action.
4. Restart Archipelago/Universal Tracker and SOH. Both must use 0.11.26.

YOUR EXISTING SEED NEEDS RECOVERY OR REGENERATION
The supplied seed places Climb on Withered Deku Baba 4, behind Mido. With the
correct rules it stalls after 33 checks even if all 39 incoming SOH items from
Jigsaw are supplied. Updating source or the tracker cannot move those items.

To keep playing this seed, ask its host to run this once in the ARCHIPELAGO
SERVER CONSOLE (not the game's chat):

    /send mikemik44 Climb

That sends one extra Climb through Archipelago and leaves existing placements
intact. In the offline replay, supplying Climb reaches the goal and all 3,258
checks. That recovery test assumes the other game's SOH deliveries eventually
arrive; it does not run Jigsaw logic. No server command or save edit has been
performed by this patch. Alternatively, generate a new multiworld using 0.11.26.

VALIDATION
- Reproduced the wrong-region failures against 0.11.25, then passed 1,116 AP/UT
  route checks across Closed Forest On, Deku Only and Off; each missing Mido
  requirement, wrong language, missing enemy soul and combat alternatives.
- 91 compiled native finder assertions verify the actual region/combat code,
  exact region assignment, all Room 1 mappings and child-only spawn access.
- 123 earlier Deku/live-shield tests and six waterfall parent/age checks passed.
- All 216 SOH settings were reconstructed from the supplied spoiler. A new
  seed with those settings passed full generation and independent collection
  replay: 3,258 network checks, beatable, no blocked checks.
- Existing-seed replay used its exact slot data, shops and placements.
- Windows x64 Release build completed; APWorld 100-file source parity, stable
  network IDs, cumulative patch forward/reverse application and ZIP hashes verified.

Tests use real AP/UT and extracted native functions with controlled engine/UI
services. No connected in-game playthrough was performed. All settings
combinations are not exhaustively certified.
See VALIDATION-MIDO-PATH.json and SHA256SUMS-MIDO-PATH.txt.
