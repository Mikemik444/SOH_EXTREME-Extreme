SOH-EXTREME Deku logic fix - 2026-09-29
APWorld / in-game tracker version 0.11.23; Windows x64 Release.
Repository: https://github.com/Mikemik444/SOH_EXTREME-Extreme
Base: 9bc10e7191b546754a50da6463e074276d33862f

RECOMMENDED: SOURCE OVERLAY
1. Close the game and Archipelago/Universal Tracker.
2. Extract the CONTENTS of SOH-EXTREME-Deku-Logic-Source-Patch.zip into
   E:\test\bb, beside your existing CMakeLists.txt and build.cmd.
   Merge the folders and replace matching files.
3. Open a FRESH Command Prompt in E:\test\bb and run build.cmd.
4. Wait for BUILD COMPLETE, then restart Archipelago and launch
   E:\test\bb\soh.exe.

build.cmd rebuilds and installs the matching soh_extreme.apworld, then
copies the rebuilt EXE and APCpp.dll to the source root. Do not use an
older executable with the new APWorld; their tracker versions must match.

This is a cumulative overlay containing 33 source/test files: it
includes AP Audit v2, the scrub/shop price fix, and this Deku correction.
You do not need to apply the earlier patches first. It uses your existing
configured build-vs folder and normal build dependencies.
The .patch file is only for review/Git use; do not apply it after copying
the replacement files. It is a cumulative diff against the base above.

READY-BUILT ALTERNATIVE
Use SOH-EXTREME-Deku-Logic-Windows-x64.zip if you do not want to compile:
1. Close the game and Archipelago/Universal Tracker.
2. Replace soh.exe AND APCpp.dll in your existing game folder with the two
   files in the ZIP. Keep your existing game assets and saves.
3. Copy the ZIP's soh_extreme.apworld over the existing file in your
   Archipelago installation's custom_worlds folder. A copy beside soh.exe
   alone is not enough for the tracker to load it.
4. Restart Archipelago and the game.
Apply the source overlay too if you intend to build again later.

WHAT CHANGED
- The solid upright/spinning plant is a Withered Deku Baba. Its native
  collision rules accept swords or a boomerang, not sticks or a hammer.
  AP combat helpers, all ten finite Withered Baba placements, and the
  native finder now use that requirement. Ordinary Deku Babas still allow
  sticks. Enemy Soul requirements and location IDs remain intact.
- The in-game AP tracker now receives Link's actual Deku/Hylian shield
  ownership. A shield that can be bought at a reachable shop no longer
  substitutes for a shield you actually own in this live view. This fixes
  the child Slingshot Room route, including its side chest and scrub check.
  Buying/receiving a shield and losing one both refresh the result. Stale
  snapshots with different shield equipment are hidden while refreshing.
- Child Link still needs a Deku Shield to reflect nuts. Adult Hylian
  reflection and the existing hammer alternative remain in the rules.
  Generation and standalone UT retain planned-purchase logic so seeds can
  correctly rely on an accessible stock shield in a shop.

EXISTING SEEDS
The updated in-game tracker can be used with your current seed/save.
It corrects availability; it does not move already-generated items or
change which weapons damage the enemies. Newly generated seeds use the
corrected Withered Baba combat rules during item placement.

VALIDATION
- Windows x64 Release build completed with MSVC 2022; DLL loader passed.
- 128 AP logic/transport checks passed, including the installed Universal
  Tracker's actual evaluator with controlled display/network services.
- Compiled production combat helpers and the actual C++ finder client
  consumed Python callback packets and rejected stale shield inventory,
  mismatched tracker versions, pending receipts, and non-AP saves.
- AP 0.6.7 generated and sphere-replayed a 3,258-check seed: beatable,
  no unreachable network checks or blocked progression replay.
- Both APWorld manifests and tracker versions match; all 99 archive files
  match canonical source bytes. Cumulative patch forward/reverse checks
  and both ZIP integrity checks passed.

These are build and code/evaluator tests, not a connected gameplay test.
The earlier crash without a log cannot be identified from that report.
The previous AP stability fixes remain included.
See VALIDATION-DEKU-LOGIC.json for results and SHA256SUMS-DEKU.txt for hashes.
