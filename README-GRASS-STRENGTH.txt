SOH-EXTREME Grass / Grab logic fix - 2026-09-29
Version 0.11.25; cumulative Windows x64 Release
Repository: https://github.com/Mikemik444/SOH_EXTREME-Extreme
Base: 9bc10e7191b546754a50da6463e074276d33862f

WHAT WAS WRONG
Grass lifting requires both basic Grab and real Strength in either age. The
first Strength Upgrade with Shuffle Grab ON grants only Grab / Power Bracelet.
It lifts small rocks, cuccos and similar objects, but not grass. The second
Strength Upgrade grants Goron's Bracelet and allows grass lifting.

Both native Check Finder and the APWorld rules incorrectly allowed grass with
basic Grab alone. They now require the real Strength tier for lifting, while
keeping valid sword, boomerang and explosive collection routes independent of
Grab. Grass/Bush Soul is still required if its shuffle is enabled. With Grab
shuffle OFF, the first ordinary Strength Upgrade provides the lifting tier.
This fixes the rules; the player's actual lifting behavior is unchanged.

SOURCE OVERLAY
1. Close SOH and Archipelago/Universal Tracker.
2. Extract the CONTENTS of SOH-EXTREME-Grass-Strength-Source-Patch.zip into your
   source root (E:/test/bb), beside CMakeLists.txt and build.cmd. Merge folders
   and replace matching files. Do not add an extra nested ZIP folder.
3. Open a FRESH Command Prompt there and run build.cmd.
4. Wait for BUILD COMPLETE, then restart Archipelago/Universal Tracker and SOH.

build.cmd builds and installs the matching APWorld, and copies the EXE/DLL to
the source root. The included .patch is for review/Git use; do not apply it
again after copying the replacement files.

READY-BUILT ALTERNATIVE
Use SOH-EXTREME-Grass-Strength-Windows-x64.zip to skip compiling:
1. Close SOH and Archipelago/Universal Tracker.
2. Replace soh.exe and APCpp.dll in your existing game folder.
3. Install the included soh_extreme.apworld through Archipelago's Install
   APWorld action, replacing the old SOH-EXTREME world.
4. Restart Archipelago/Universal Tracker and SOH.
Keep existing game assets, saves and configuration. Matching game and APWorld
0.11.25 are required for the game-owned Check Finder connection.

EXISTING SEEDS
Your current save can use the corrected Check Finder after updating both sides
and restarting the tracker. Existing item placements cannot be changed by this
patch. Generate future seeds with the updated APWorld so placement logic also
uses the corrected requirements.

PREVIOUS FIXES INCLUDED
This cumulative package retains the earlier network hints, named AP pickup and
scrub text, important remote item hold-ups, incoming-item priority, shield shop
restriction correction, Deku/Withered Baba logic, purchase prices, fishing,
hearts, full wallets, Triforce percentage completion and AP stability fixes.
There is no need to apply the older overlays first.

VALIDATION
- 852 AP/Universal Tracker assertions: Grab ON/OFF, 0-4 Strength pickups, both
  ages, missing/present Grass Soul, cutting alternatives, all 12 KF child grass
  checks and removal of a real Strength tier. Uses installed UT evaluator code.
- 768 compiled native assertions compare grass logic with the player's actual
  carry predicate and Player_GetStrength; basic rock lifting remains available.
- Your supplied options with Shuffle Grab ON generated and replayed in AP 0.6.7:
  2,770 network checks, 19 spheres, beatable, no blocked checks.
- Windows x64 Release build completed. All 100 APWorld files match the source;
  cumulative patch forward/reverse application and ZIP/hash verification passed.

Engine services/display/network are controlled in the focused tests; no live
connected gameplay session was performed. Earlier suites are recorded as
historical evidence, not represented as rerun for this narrow grass correction.
See VALIDATION-GRASS-STRENGTH.json and SHA256SUMS-GRASS-STRENGTH.txt.
