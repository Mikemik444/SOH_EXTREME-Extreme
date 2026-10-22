SOH-EXTREME 1.8.15 - complete replacement sources
=================================================

Based on the uploaded current(1).zip. This is not a patch script.
Includes the cumulative source replacements through 1.8.14 and this update.

INSTALL
-------
Close the game. Merge soh/, src/, archipelago/ and tools/ into E:\test\bb.
Replace matching files, including SOURCE_FILES.json and BUILD_RELEASE.* at
that repository root. Do not delete the rest of your complete checkout.

From Command Prompt:
  cd /d E:\test\bb
  BUILD_RELEASE.cmd -RepositoryPath "E:\test\bb" -BuildDirectory "build-vs"

Run the exact executable path printed after the clean Release build succeeds.
Install the TOP-LEVEL soh_extreme.apworld from this ZIP into:
  C:\ProgramData\Archipelago\custom_worlds\soh_extreme.apworld
Restart the generator and tracker. Update both if installed separately.
The dedicated SOH-EXTREME Universal Tracker launcher and in-game Check Finder
still read server slot data without needing a Players-folder YAML.

WHAT CHANGED
------------
1. Check Finder keeps its complete, same-session display while its next result
   is calculated. It removes locally completed checks immediately and swaps
   in newly calculated rows together. Search, dropdown choices and the list
   stay mounted; no UI reset is used. Updates caused by items, shields,
   ammunition or time no longer blank the list.
2. Relevant state changes trigger a request as soon as the 150 ms burst-rate
   limit permits, instead of waiting for the next 2-second heartbeat. Worker
   servicing uses a 100 ms cadence even when the Finder window is closed.
   Network round trips and UT evaluation still take time; instant computation
   is not promised. Unchanged state keeps the 2-second heartbeat.
3. The display cache cannot grant ammo refill authority. Gameplay still uses
   the strict inventory/clock/ammo/receipt-matching snapshot. Slot, manifest
   or session changes clear/refuse the old display. An expired same-session
   result stays visible with a delayed warning, not as freshly verified logic.
4. NPC Speech Sanity no longer depends on a scrub's reward being shuffled
   to discover its physical parent region. Off/one-time-only scrub reward
   settings can remove the reward anchor; the authored actor parent is now
   used instead. Conversation IDs, stun, Soul, speech and age requirements
   remain unchanged. No money/price gate is added to a first conversation.
   Invalid catalogue entries still raise an error rather than disappearing.
5. Gerudo guarded approaches no longer grant automatic access to child Link.
   They require the Membership Card, an age-usable means of passing the guard,
   or the explicitly enabled guard-passing trick. Missing NPC Soul does not
   count as a permanent bypass. Direct arrivals at safe upper ledges still
   reach their own doorways; the whole fortress is not blanket card-locked.
   Native and AP predicates are updated together. The direct GTG exit needs
   the card to pass its waiting guard at either age. The nearby NW crate also
   retains its actual crate-breaking requirement.

SEEDS
-----
The no-flicker client behavior alone needs no new save. Generate a fresh seed
with 1.8.15 to get item placements validated against the stricter Gerudo rules.
Existing server maps/placements are not rearranged by installing an APWorld;
this update has NOT certified that an old seed remains completable.

VALIDATION AND LIMITS
---------------------
See VALIDATION.txt and validation/*.json for the tests actually run here.
No complete Windows game build, full AP item fill, live-server session or
controller playthrough was performed. The complete AP core runtime was not
available in this environment; the tests execute production cache code,
resolver functions and route predicates using documented fixture boundaries.
No error traceback was supplied for the reported NPC failures. This release
fixes the reproduced missing scrub-parent path, not every possible NPC error.

NEW TESTS (from your full checkout)
----------------------------------
  python tools/tests/test_tracker_continuity_1815.py
  python tools/tests/test_npc_gerudo_1815.py
These tests need Python 3.11+ and g++ supporting C++20 and ASan/UBSan.
They do not require the AP runtime. Retained older test suites have their
own external dependency requirements and were not all rerun for this release.
