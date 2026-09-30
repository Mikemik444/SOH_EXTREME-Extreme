SOH-EXTREME Beatability Validation Update - 2026-09-29
Version 0.11.33; cumulative Windows x64 Release
Repository: https://github.com/Mikemik444/SOH_EXTREME-Extreme

YOUR CURRENT SEED
AP_71565912878447906591 (generated with 0.11.32) passed an offline replay of
the original placements in all four worlds: SOH slot 4 and Jigsaw slots 1-3.
All 3,319 SOH checks and all 138 Jigsaw checks became reachable; all four goals
were met. Remote items were delivered only after their source checks became
reachable. No extra/recovery items were assumed or sent. Jigsaw merge limits
were checked against its actual PuzzleBoard and the seed's saved piece order.

You do not need to regenerate this specific 0.11.32 seed for this update.
0.11.33 adds final generation validation; its location rules, item IDs and
placements are unchanged from 0.11.32. This finding does not cover older seeds
that were generated with the incorrect forest, grotto or dusk rules.

NEW SAFETY CHECK
The old SOH strict post-fill validator skipped multiplayer. The new final
validator runs once before export, after progression balancing and finalization.
It replays all players' real placements from starting inventory, including
cross-game deliveries. Generation fails if any goal stalls or if SOH Full
accessibility leaves checks or remote SOH progression unreachable. Unfilled
SOH network checks also fail. Minimal accessibility retains its usual behavior.
Successful generation logs "SOH-EXTREME final multiworld validation passed".
Keep Accessibility set to Full for the all-checks requirement you requested.

WINDOWS DRAG-AND-DROP (NO BUILD NEEDED)
1. Close SOH and Archipelago/Universal Tracker. Keep a copy of the old files.
2. Extract SOH-EXTREME-Beatability-Fix-Windows-x64.zip and replace soh.exe and
   APCpp.dll in the folder you launch from. Your previously running game was
   E:\test\bb\x64\Release\soh.exe; replacing only E:\test\bb\soh.exe would
   update a different copy. The x64\Release copy matches the tested 0.11.32
   executable before this update.
3. Install the included soh_extreme.apworld through Archipelago's Install
   APWorld action. Restart AP/Universal Tracker so it loads 0.11.33.
4. Launch the replaced executable. EXE and APWorld must both be 0.11.33 for
   the Check Finder tracker protocol to match.
Keep game assets, soh.o2r, saves and configuration. The repair task did not
install anything in your game/AP directories or change the server or saves.

SOURCE OVERLAY ALTERNATIVE
Extract the CONTENTS of SOH-EXTREME-Beatability-Fix-Source-Patch.zip into the
source root beside build.cmd and CMakeLists.txt; merge/replace files. Open a
fresh Command Prompt there and run build.cmd. Wait for complete build and
verification success, install its matching APWorld, and restart AP/Tracker.
The .patch file is for Git/review; do not apply it again after copying files.

VALIDATION
See VALIDATION-BEATABILITY-FIX.json for exact results and source/runtime hashes.
The audit includes all shuffled abilities/souls, separate child/adult access,
frozen time, physical NPC routes, object-breaking actions and item prerequisites.
Deliberately broken test worlds verify that the validator rejects self locks,
cross-player cycles and unreachable Full checks even when victory is reachable.
The generated-seed matrix covers Dawn/Day/Dusk/Night, Triforce/Ganon goals,
adult starts, individual song notes and two SOH players with balancing enabled.
All previous cumulative fixes remain included; see SOH_AP_FIX_HISTORY.txt.

LIMIT
These are source, rule-graph, generation and build checks, not a connected
in-game playthrough. They support beatability under the corrected rules and
catch modeled deadlocks; they cannot guarantee that every physical interaction
or every possible settings combination has no undiscovered bug.
