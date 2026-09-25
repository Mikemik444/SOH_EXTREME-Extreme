SOH-EXTREME - ALL SOULS RENDERING PATCH
====================================
Source reviewed: Mikemik444/SOH_EXTREME-Extreme
Base commit: 5851e0c273ae53632d03688898d0e85a1933fed0

INSTALL
-------
1. Close the game and finish/stop any running build.
2. Extract this ZIP's CONTENTS directly into E:\test\bb.
   Merge the soh and tools folders and replace the two existing source files.
   Do not put a second SOH_EXTREME_All_Souls_Render_Fix folder inside bb.
3. Run your existing E:\test\bb\build.cmd and wait for BUILD COMPLETE.
4. Launch E:\test\bb\soh.exe, then load your existing save.

No CMake, build.cmd, save, mod, seed, YAML or apworld files are replaced.
Keep your previously installed Torch/PDB build patch. Do not delete build-vs.
The existing build.cmd regenerates/copies soh.o2r and copies the freshly built
executable/APCpp.dll. No new seed or AP world install is required for this visual change.

FULL REPLACEMENT SOURCE FILES
-----------------------------
soh/Enhancements/randomizer/EnemySoulDraw.cpp
soh/Enhancements/randomizer/EnemySoulIcons.h

WHAT CHANGES
------------
The 47 individual enemy/Skulltula/Scrub portraits keep their resource names and
recognizable existing artwork. Their in-world drawing now uses the aligned
__OTR__ texture name, preserving the PNG/format/dimension metadata needed by the
renderer. The previous code decoded the resource into a raw pointer first.

A dedicated one-cycle texture-alpha material is established after the native
flame is drawn; it does not inherit the flame's combiner. Geometry, grayscale
and translucent material state are reset afterward, and matrix pushes/pops are
balanced. Optional portraits missing from loaded archives fall back to the
native skull rather than dereferencing a missing resource or disappearing.

All 84 soul item IDs present in the reviewed RandomizerGet enum are explicitly
mapped, including the enemy souls appended after unrelated items. No numeric
range guesses or changes to enum values are used.

PRESENTATION
------------
47 individual enemy/Skulltula/Scrub souls:
  Existing horned-base enemy portrait with the native animated soul flame.
18 category/animal souls:
  The native 3D boss-soul skull with a category-colored animated soul flame.
  This includes combined Enemy/NPC/Animal souls, Pot/Crate/Grass/Rock/Tree/
  Beehive/Sign souls, and all eight individual animal souls.
10 bean souls:
  Their native sprout model with the animated soul flame.
9 boss souls:
  Their original boss renderer and original Simpler Boss Soul Models setting.
  No replacement of the existing boss animations or boss palette.

These are not 45 newly animated enemy skeleton models: the existing individual
enemy portraits are retained intentionally. Generic/animal souls use the native
3D skull rather than an inventory-icon billboard. The item-tracker window layout
is not modified by this patch.

HOW NATIVE AND ARCHIPELAGO USE IT
--------------------------------
StaticData::InitItemTable already calls SohExtreme_GetEnemySoulIcon for every
item and assigns Randomizer_DrawEnemySoul for each non-null result. The extended
lookup makes that existing loop register every soul. The wrapper delegates
verified boss IDs to the original boss renderer and beans to the original sprout.

Archipelago's ProcessItem copies that same native item's GetItemEntry. Scouted
same-player placements also select native RandomizerGet items. The patch therefore
updates those existing render routes without modifying networking/receipt logic.
Cross-world items keep their AP-logo route; foreign item IDs are not treated as souls.

Item IDs, receipt identity, ownership flags, progression logic and long get-item
animations are unchanged. An ice-trap disguise can select a soul visual without
changing the underlying trap's identity. Only a local copy is normalized for the
original boss renderer, which indexes a nine-entry palette.

VALIDATION
----------
The included coverage JSON enumerates all 84 mappings.
The modified renderer and header were compiled in a C++20 test harness with GCC
and Clang using warnings-as-errors, AddressSanitizer and UndefinedBehaviorSanitizer.
Each compiler's test run passed 1,248 mocked renderer cases: every soul across
four item origins with/without a trap disguise, missing and alternate portraits,
resource-name/alpha-material checks, rejected foreign/non-soul IDs, matrix and
live-entry preservation, null arguments, and the maximum frame-counter value.

Those tests replace graphics/resource APIs and native boss/sprout functions with
mocks. They are NOT a full SoH/MSVC build and do NOT verify actual pixels or mod
compatibility in the Windows game. In-game visual verification is still needed.

Optional checkout audit (read-only, Python standard library only):
  python tools\verify_soul_render_patch.py
This compares the mapping to your actual native enum and checks the registration
loop and portrait source paths. It is not required to install the patch.

Source references for the implementation:
  soh/Enhancements/randomizer/draw.cpp -- Randomizer_DrawBossSoul / DrawBeanSprout
  soh/Enhancements/randomizer/item_list.cpp -- final soul registration loop
  soh/GbiWrap.cpp -- metadata requirement for resource-backed textures
  soh/ResourceManagerHelpers.cpp -- resource lookup/existence behavior
  soh/Network/Archipelago/ArchipelagoClient.cpp -- native Item/GetItemEntry route

Rollback: restore just the two replaced source files from your own backup, then
rebuild. Do not restore old build.cmd/CMakeLists.txt files over your build fixes.
