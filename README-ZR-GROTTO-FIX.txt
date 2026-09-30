SOH-EXTREME ZR Grotto and Skull Kid Logic Fix
Version 0.11.34 - cumulative Windows x64/source update
Repository: https://github.com/Mikemik444/SOH_EXTREME-Extreme

FIXES
The raised ZR Open/Fairy Grotto entrances require Climb and the child's
Grab + Cucco Soul route, or real adult access. The Fairy Grotto additionally
requires opening its rock cover. Existing Shovel and item-interaction gates
remain. Every check and resource event inside inherits the entrance rule.

Skull Kid dialogue, song/memory-game rewards and the mask trade now respect
Skull Kid Soul (shared Enemy Soul in shared mode) when enemies are Gone Until
Found. The child NPCs, language, instrument and physical route still matter.
Invincible Until Found does not block their noncombat interaction.

Skeleton Key satisfies the existing small-key and overworld-door predicates;
it does not grant other route/action abilities or boss keys. The audit compares
AP/UT reachability with ordinary keys versus Skeleton Key, plus native key tests.
All earlier cumulative repairs are retained in this package.

IMPORTANT CORRECTION FOR THE CURRENT SEED
AP_47506236260385279514 does NOT pass the corrected replay. The original
SOH + three Jigsaw placements stall after 220 of 3457 checks, without a goal.
The earlier passed report relied on missing physical requirements. In particular,
Flow of Time is in ZR Fairy Grotto before the raised ledge can be reached.
Installing new code cannot reposition items already generated. Generate a NEW
multiworld using this APWorld and keep Accessibility set to Full. Updating only
the tracker will show corrected reachability but will not repair these placements.
The included seed-correction report supersedes the earlier passed result.

WINDOWS DRAG-AND-DROP (NO BUILD NEEDED)
1. Close SOH and Archipelago/Universal Tracker. Keep copies of replaced files.
2. Extract SOH-EXTREME-ZR-Grotto-Fix-Windows-x64.zip. Replace soh.exe and APCpp.dll
   in the folder containing the EXE you actually launch (for source builds this
   may be x64\Release rather than the source root).
3. Install the included soh_extreme.apworld using Archipelago's Install APWorld
   action. Restart AP/Universal Tracker. Both EXE and APWorld must be 0.11.34.
4. Generate the new multiworld, start its server and use its matching new save.
Keep existing game assets, soh.o2r, configuration and old saves. This task did
not install files or alter the server. Keep old saves separate from the new seed.

SOURCE OVERLAY ALTERNATIVE
Extract the CONTENTS of SOH-EXTREME-ZR-Grotto-Fix-Source-Patch.zip into your source
root beside build.cmd and CMakeLists.txt, merging/replacing files. Open a fresh
Command Prompt there and run build.cmd. Wait for build and verification success;
install its matching APWorld and restart AP/Universal Tracker before generation.
The included .patch is for review/Git; do not apply it again after copying files.

VALIDATION
See VALIDATION-ZR-GROTTO-FIX.json and CHECK-AUDIT-ZR-GROTTO.json for exact results,
source/runtime hashes and regression evidence. Generation tests cover frozen
Dawn/Day/Dusk/Night, two SOH players, Triforce/Ganon goals, adult starts and
individual song notes. The final generation guard replays actual placements.
These tests validate the modeled rules; this is not a live full-game playthrough
or proof that every possible setting/physical interaction has no remaining bug.
