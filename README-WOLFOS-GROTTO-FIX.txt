SOH-EXTREME Wolfos / grotto fix - 2026-09-29
Version 0.11.31; cumulative Windows x64 Release
Repository: https://github.com/Mikemik444/SOH_EXTREME-Extreme

WHAT WAS WRONG
The two checks labeled "LW Scrubs Grotto ... Wolfos" used the wrong grotto ID.
They are the two Wolfos in the Sacred Forest Meadow Wolfos Grotto. The actual
scene maps entrance/spawn 8 to room 7, while the old exporter assumed entrance
numbers were room numbers. The native death hook already existed, but couldn't
match the Wolfos to their pending AP checks.

WHAT IS FIXED
- Both grotto Wolfos have separate stable AP IDs (9800505 and 9800506), correct
  SFM names/regions, and the actual physical grotto ID 22 instead of LW's 25.
- The outdoor child Wolfos check belongs to SFM Entryway, before its gate.
- The same error affected other grottos. All 28 non-fairy entrance mappings were
  checked against the supplied game assets. The eight real enemy placements are
  SFM's two Wolfos, Kak's two Redeads, HF Tektite, HF Cow Skulltula, HF Near Kak
  Skulltula, and GV Octorok. Their runtime/finder/AP mappings now agree.
- Six duplicate/nonexistent enemy checks are excluded from new seeds. Their
  IDs stay reserved and saved receipt indices remain unchanged.
- Physical routes, Shovel, usable age-specific weapons, enemy souls and other
  configured requirements still apply. Adult access does not unlock the
  child-only outdoor Wolfos. Both ages can reach the grotto if their route and
  combat requirements are met.
- All earlier cumulative repairs are included. See SOH_AP_FIX_HISTORY.txt.

WINDOWS DRAG-AND-DROP (NO BUILD REQUIRED)
1. Close SOH and Archipelago/Universal Tracker. Keep a copy of the old files.
2. Extract SOH-EXTREME-Wolfos-Grotto-Fix-Windows-x64.zip. Copy soh.exe and
   APCpp.dll into your existing game folder, replacing those files. Keep your
   assets, soh.o2r, saves and configuration.
3. Install the included soh_extreme.apworld with Archipelago's Install APWorld
   action. Restart AP/Universal Tracker to load 0.11.31.
4. Generate a NEW multiworld with 0.11.31 and start its new game save for the
   complete placement correction. Keep the new EXE and APWorld together.

SOURCE OVERLAY ALTERNATIVE
1. Extract the CONTENTS of SOH-EXTREME-Wolfos-Grotto-Fix-Source-Patch.zip into
   the source root beside build.cmd and CMakeLists.txt; merge/replace files.
2. Open a FRESH Command Prompt in that folder and run build.cmd. Wait for the
   entire build and verification to finish successfully.
3. Restart AP/Universal Tracker after installing the matching APWorld, then
   generate a new multiworld and start its new save.
The included .patch is for Git/review. Do not apply it again after copying files.

EXISTING SEEDS
Runtime matching for the eight real enemies uses their existing AP IDs, so
uncollected Wolfos can be retried by leaving and re-entering their scene after
updating. Already collected IDs stay collected. Old server data may retain the
old incorrect names. This does NOT repair existing item placements or remove
the six nonexistent checks from an existing multiworld. The complete repair
requires new generation; no server-side recovery or item grants were performed.
The previous Closed Forest/NPC route defects also require corrected generation.

VERIFICATION
- Successful Windows x64 Release build and APWorld/source parity (102 files).
- 131 compiled production spawn/reward assertions, including wrong grotto,
  actor/index/params, soul gating, separate Wolfos IDs, duplicate suppression,
  failed allocation retry and normal drops after collection.
- 58 source/asset mapping assertions, covering all 28 non-fairy grotto routes.
- 97 real AP/UT assertions for grotto access, Shovel, souls, combat and ages.
- 181 fresh inventories across 3319 network checks: 600739 AP/UT comparisons,
  zero failures. This agreement alone is not proof of physical game correctness.
- Day-start and night-start seeds generated and replayed through all checks
  and the goal using the supplied resolved settings.
- ZIP byte/CRC checks, executable freshness, DLL loading, matching tracker
  version and cumulative patch forward/reverse applicability checked.

No connected in-game playthrough was performed. This is not a certification
of every setting combination or every physical check in the game.
