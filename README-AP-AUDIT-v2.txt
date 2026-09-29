SOH-EXTREME Archipelago fixes + delivery/logic audit v2 - 2026-09-29

Repository: https://github.com/Mikemik444/SOH_EXTREME-Extreme
Base: 9bc10e7191b546754a50da6463e074276d33862f
Windows x64 Release. APWorld/tracker version: 0.11.22.
This cumulative update includes the previous fishing/heart/wallet/goal fixes.

SOURCE PATCH: EXTRACT, REPLACE, BUILD
1. Close the game. Extract the CONTENTS of
   SOH-EXTREME-AP-Audit-v2-Source-Patch.zip into your SOH_EXTREME-Extreme
   source root, the folder containing CMakeLists.txt and build.cmd.
   Merge folders and replace the matching files.
2. Run build.cmd using your existing configured build-vs setup.
3. Wait for BUILD COMPLETE. Restart Archipelago/Universal Tracker.
4. Launch soh.exe in the SOURCE ROOT. The script now copies and verifies
   the exact rebuilt soh.exe and APCpp.dll together in that folder.

The source ZIP contains 17 changed/new files with repository-relative paths.
It is an overlay for the repository above, not a complete source checkout.
The included .patch is for review/Git users; do not apply it after copying
the replacement files. The normal build prerequisites still apply.
The updated APWorld is built and installed by the existing build.cmd step.

READY-BUILT GAME: NO COMPILATION
Alternatively, use SOH-EXTREME-AP-Audit-v2-Windows-x64.zip:
1. Close the game and extract soh.exe AND APCpp.dll over the matching files
   in your existing SOH-EXTREME game folder. Replace both together.
2. Keep your existing game assets, mods, settings, and saves.
3. Copy APWorld/soh_extreme.apworld to Archipelago/custom_worlds, replacing
   the previous soh_extreme.apworld. Keep one SOH-EXTREME world installed.
4. Restart Archipelago/Universal Tracker and launch the replaced soh.exe.

Use one installation method. A later build from unpatched source would
replace the ready-built fixes, so use the source overlay for future builds.

ADDITIONAL ISSUES FOUND AND FIXED IN THIS AUDIT
- Background saves could pair old inventory with a newer AP receipt count,
  potentially losing a reward after reload. All AP persistence fields are
  now captured alongside inventory before the save worker starts.
- NPC speech and enemy pickups confused locally queued checks with server
  acknowledgements. Local submission and server confirmation are now
  separate; pending checks and fallback NPC identities persist in saves.
- Partial location-scout replies could leave item information incomplete.
  The client now retries missing scouts in bounded batches with a delay.
- AP connection/placement logic could interfere with normal local saves;
  disabling/re-enabling AP could discard the current file's AP identity.
  Gameplay ownership and save metadata now follow the loaded file.
- An unrelated pickup could be mistaken for the awaited AP major reward.
  Receipt completion now requires the matching item; duplicate/capped
  rewards can complete without relying on an inventory change.
- build.cmd could replace a fresh APCpp.dll with a stale build-directory
  copy. It now reads CMake's exact target paths and checks copied hashes.
  APWorld/runtime hashing uses .NET without a Get-FileHash dependency.

PREVIOUS REQUESTED FIXES INCLUDED
- Pond catches register once when hoisted, including remote-player rewards.
  Uncollected shuffled fish display their item, respecting mystery display.
  Fish IDs and absent checks are validated before indexing/reporting.
- Check Finder excludes enemy check rows/counts when enemy checks are off,
  including the Universal Tracker mirror path.
- AP Heart Pieces and Heart Containers heal to maximum; every fourth piece
  increases capacity. Progressive Wallet fills to its resulting capacity
  when Fill Wallet is enabled; extra capped wallets do not stall delivery.
- Triforce Hunt uses the seed's percentage-derived required count and
  triggers AP completion plus the existing autosave/credits flow.
- AP slot callbacks apply gameplay changes on the main thread; replay
  deduplication uses the active save, and receipts wait through death,
  pause and transitions. Malformed slot data is validated.
- APCpp reconnect iteration, per-thread JSON codecs, and message queue
  synchronization address concrete crash hazards found in the code.

COMPATIBILITY
Existing compatible seeds/saves are supported; no new seed is required for
client fixes. Item/location IDs are unchanged. Older save metadata loads
with defaults; v3 metadata adds the pending-check outbox. Keep this patched
client for saves using that field. New-generation APWorld settings apply
when generating a new seed. Already-missed checks/rewards are not universally
recoverable automatically; these fixes prevent the identified failure paths.

VALIDATION
- Full Windows x64 Release EXE and APCpp.dll built successfully with MSVC 2022.
- 14 focused production-function/integration suites passed, including save
  snapshots, offline pending checks, scouting retries, receipts, pond
  catches, health/wallets/goals, replay, and a 100,000-message queue stress test.
- 11 tracker transport/lifecycle tests passed with a controlled host.
- 16,550 rule assertions passed across six logic suites, including 70,490
  location-reachability comparisons between AP and UT reconstruction.
- Three real Archipelago 0.6.7 seed generations/fill/progression replays
  passed: baseline, two-player with enemy/NPC/fish/Triforce options off,
  and pond shuffle with 100 pieces and a 50-percent Triforce goal.
  All three were beatable and had no blocked checks in their replay.
- Runtime-copy positive/failure cases passed; APWorld install/parity and
  repeated packaging passed in an isolated fake AP installation.
- Windows loaded the rebuilt APCpp.dll; ZIP bytes/CRCs and source patch
  application against the base commit were verified.

Older logic-test fixtures were adapted only for the current world version
and for an all-inventory assertion to check actual network locations, since
optional virtual action/event nodes need not be reachable in every option
combination. Normal AP dependencies were used for graph/generation tests.

LIMITS
This is code/build/automated-model validation, not a connected in-game
playthrough of every check. The original intermittent crash was not
reproduced without its log. Passing these checks cannot guarantee there
are no other gameplay bugs. Detailed results are in VALIDATION-AUDIT-v2.json.

Focused C++ tests can be rerun from a VS x64 developer terminal:
  python validation/test_ap_gameplay_fixes.py --include-dir VCPKG_INCLUDE
    --apcpp-source build-vs/_deps/apcpp-src --output work/ap-gameplay-tests
  python validation/test_ap_delivery_audit.py --include-dir VCPKG_INCLUDE
    --output work/ap-delivery-tests
VCPKG_INCLUDE is the folder containing nlohmann/json.hpp; configure CMake
first so the APCpp dependency safety repairs have been applied.
