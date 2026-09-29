SOH-EXTREME Archipelago network fix - 2026-09-29
Version 0.11.24; Windows x64 Release
Repository: https://github.com/Mikemik444/SOH_EXTREME-Extreme
Base: 9bc10e7191b546754a50da6463e074276d33862f

SOURCE OVERLAY (recommended for your existing source folder)
1. Close SOH and Archipelago/Universal Tracker. Keep a backup of your source/save.
2. Extract the CONTENTS of SOH-EXTREME-AP-Network-Fix-Source-Patch.zip into
   E:\test\bb, beside CMakeLists.txt and build.cmd. Merge folders and replace
   matching files. Do not put everything into an extra nested ZIP folder.
3. Open a FRESH Command Prompt in E:\test\bb and run build.cmd.
4. Wait for BUILD COMPLETE, then restart Archipelago/Universal Tracker and
   launch E:\test\bb\soh.exe.

build.cmd rebuilds and installs the matching soh_extreme.apworld and copies
the freshly built EXE and APCpp.dll to the source root. It selects 64-bit build
tools and resets the two generated incremental link caches, matching the
successful clean-link build used for this package. Use matching versions.
This cumulative overlay includes all previous fixes from this conversation.
You do not need the older patches. The included .patch is for review/Git use;
do not apply it a second time after copying the replacement source files.

READY-BUILT ALTERNATIVE
Use SOH-EXTREME-AP-Network-Fix-Windows-x64.zip to skip compiling:
1. Close the game and Archipelago/Universal Tracker.
2. Replace BOTH soh.exe and APCpp.dll in your existing game folder.
3. Install the included soh_extreme.apworld using Archipelago's Install APWorld
   action, replacing the old SOH-EXTREME world; restart the launcher/tracker.
Keep your existing game assets, save files and configuration.

CHANGES
- Network > Archipelago now has a wider two-column layout and a searchable
  server hint list, with recipient, location, finding player and found status.
  Hints load on connection and update when found, including at file select.
  The list reads already-revealed server hints; it does not buy new hints.
- Scrub and merchant dialogue uses scouted remote item/recipient names instead
  of the AP placeholder's empty 'No Hint' entry. Existing mysterious-text
  preferences still apply; your clear scrub/merchant hints are supported.
- Important/useful items sent to another player get a queued hold-up AP model
  and named pickup textbox. Filler keeps a named quick notification.
  Remote models are presentation-only and never grant someone else's item.
- Incoming item deliveries take priority over new remote presentation animations.
  Important animations still wait for Link to be safe on land and out of dialogue,
  pauses, transitions and existing cutscenes. Server/network latency remains.
- Extra Open Chest ability copies no longer stall the receipt queue at the cap.
- AP seeds no longer inherit native refill-only shield/tunic shop restrictions,
  native-only starting inventory, entrance/MQ selections and unsupported rules.
  Defaults also apply to older seeds' cached slot settings. Explicit AP starting
  items still override those defaults.
- Fixed a possible AP client crash from string-valued player IDs in PrintJSON
  chat messages. The old crash without a log cannot be positively identified.
- Earlier pond fish checks/models, disabled enemy-check filtering, scrub/shop
  prices, heart healing, full wallets, Triforce goal and Deku/Baba logic fixes
  are all included.

YOUR SETTINGS
- There is no progressive-shield option in the YAML you supplied. You can buy
  your first stock Deku Shield with this fix. Stock shop items retain vanilla
  prices (the Deku Shield normally costs 40); randomized shop checks cost 0.
- Enemy-drop checks are ON in this YAML; enemy souls are OFF. Ordinary enemy
  checks are therefore expected, subject to their weapon/access requirements.
- Child Deku Scrub reflection requires an owned Deku Shield in live Check Finder.
  Upright/Withered Babas use the sword-or-boomerang rule, not Deku Sticks.
- Your Triforce target is 24 of 60 pieces (40%).

CURRENT SEED
These client, hint, shop restriction and live tracker fixes support your current
save/seed. They do not move items already placed by an older generator. New
generation uses the corrected APWorld rules and settings bridge.

VALIDATION
- Windows x64 Release build completed; built DLL loader and packet-parser tests.
- Built APCpp parser: server hint subscription, team IDs, cross-game names,
  delayed data packages, found updates, empty/malformed hints, PrintJSON text IDs.
- Compiled production presentation/message/settings and existing reward,
  check-delivery, save snapshot, price and capped-ability regression tests.
- 128 Deku combat/live tracker tests using installed Universal Tracker's actual
  evaluator with controlled display/network services; 23 slot contract tests.
- All 216 resolved AP options published; 120 native defaults checked against
  the real native option names and the older-seed C++ fallback.
- Your settings generated/replayed successfully in AP 0.6.7: 2,770 network
  checks, no unreachable network checks, no blocked replay, beatable goal.
- All 100 APWorld archive entries match source bytes. Cumulative patch
  forward/reverse application and ZIP/hash checks passed.

These are build, production-function, protocol and logic tests. A connected
in-game playthrough was not performed, and this is not a guarantee that every
possible settings combination is bug-free.
See VALIDATION-AP-NETWORK-FIX.json and SHA256SUMS-AP-NETWORK.txt.
