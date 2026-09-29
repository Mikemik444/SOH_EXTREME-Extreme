SOH-EXTREME Archipelago gameplay hotfix - 2026-09-29

Built for https://github.com/Mikemik444/SOH_EXTREME-Extreme
Base commit: 9bc10e7191b546754a50da6463e074276d33862f
Windows x64 Release. APWorld protocol/version remains 0.11.22.

GAME INSTALL (no compiling needed)
1. Close SOH-EXTREME.
2. Extract soh.exe and APCpp.dll from this ZIP into the folder containing
   your existing soh.exe. Replace BOTH files together.
3. Keep your existing game assets, mods, configuration and saves.
4. Copy APWorld/soh_extreme.apworld into your Archipelago custom_worlds
   folder, replacing the previous soh_extreme.apworld. Keep only one copy
   of this world installed. Restart Archipelago / Universal Tracker.

The game files provide compatibility defaults for existing seeds whose
slot data omitted pond count/age settings. Location/item IDs and save format
are unchanged. New generations use the corrected APWorld slot settings.

FIXES
- Pond shuffle enables 15 ordinary fish checks per age. A catch registers
  once when the fish is hoisted, including rewards sent to another player.
- Uncollected shuffled fish display the scouted item. The mystery-item
  display option is respected. Collected/unshuffled fish retain their model.
- Enemy defeat rows are hidden in both Check Finder paths when enemy
  drop/check shuffle is disabled.
- AP Heart Pieces and Heart Containers refill health to current maximum;
  every fourth Heart Piece also converts into capacity correctly.
- Progressive Wallet fills its resulting capacity when Fill Wallet is on.
  An extra wallet at the maximum tier no longer blocks the receive queue.
- Triforce Hunt uses the seed's percentage-derived required count, reports
  completion to AP, and invokes the existing autosave/credits flow when
  gameplay is ready. Completed saves report their goal again after reconnect.
- AP slot updates now apply on the game thread. Item replay deduplication
  uses the active save's receipt cursor; rewards wait through death, pause
  and scene transitions. Malformed numeric slot data is rejected.
- The build now applies the repository's APCpp reconnect iterator repair
  and per-thread JSON codecs, plus synchronization of the AP message queue.

VALIDATION
- Full Windows x64 Release executable and APCpp DLL built with MSVC 2022.
- Nine focused suites passed, executing production function bodies with
  controlled engine services: health/wallet rewards, callback mailbox and
  replay, goal/reconnect, all 30 pond checks, enemy finder filtering, receipt
  safety, a 100,000-message queue stress test, fish/goal slot settings, and
  50 Triforce percentage/pool combinations.
- APWorld Python/JSON syntax and every ZIP entry verified against source.
- Rebuilt APCpp DLL loaded successfully through the Windows loader.

These checks do not replace an in-game connected AP playthrough. The original
intermittent crash could not be reproduced without its log; the changes
address concrete thread/queue hazards found in the reviewed AP code.

SOURCE PATCH
The separate SOH-EXTREME-AP-Fixes-Source-Patch.zip contains the eight changed
source/test files with repository-relative paths, plus a reviewable patch.
Extract it over the matching repository checkout to keep these fixes in
your source. For a configured Windows build, run:
  cmake -S . -B build-vs
  cmake --build build-vs --config Release --target soh
The exact EXE/DLL output paths are written to:
  build-vs/soh-extreme-runtime-Release.txt
Copy both listed outputs when distributing your own rebuilt game.

To rerun the focused tests from a VS x64 developer terminal:
  python validation/test_ap_gameplay_fixes.py --include-dir VCPKG_INCLUDE
    --apcpp-source build-vs/_deps/apcpp-src --output work/ap-gameplay-tests
VCPKG_INCLUDE is the directory containing nlohmann/json.hpp; configure
CMake first so the APCpp safety repairs have been applied.
