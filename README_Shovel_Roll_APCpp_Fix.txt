SOH-EXTREME -- SHOVEL / ROLL GRAPHICS + APCpp REQUEST SAFETY
Patch revision: 1
Source reviewed: Mikemik444/SOH_EXTREME-Extreme
Main commit: 5851e0c273ae53632d03688898d0e85a1933fed0
APCpp Archipelago.cpp blob reviewed: f515de56c3246af750a1aefbe69fa834682ef206

INSTALL
=======
1. Close Ship of Harkinian and stop any currently running build.
2. Extract ALL contents of this ZIP directly into E:\test\bb.
   Merge the CMake, assets, soh and tools folders. Do not replace entire folders.
3. Run APPLY_SHOVEL_ROLL_CRASH_FIX.cmd.
   It validates/backs up the affected existing files, installs the integration,
   and calls your current build.cmd. No manual source edits are required.
4. Wait for BUILD COMPLETE. Launch E:\test\bb\soh.exe.

Do NOT delete build-vs. The changed CMake configuration regenerates normally.
Keep the previous all-souls and soul-linker fixes installed.
Future ordinary rebuilds can use your existing build.cmd as before.

IMPORTANT RUNTIME DIRECTORY
===========================
The attached crash log names E:\test\bb\x64\Release2\APCpp.dll.
This is a different runtime directory from the source-root output deployed by
our earlier build.cmd. After this build, launch the SOURCE-ROOT soh.exe above
so it uses the freshly copied APCpp.dll and soh.o2r. This patch does not copy
files into Release2, move saves, remove mods, or delete an old runtime folder.
The changed dependency prints this runtime confirmation when initialized:
    AP: SOH-EXTREME request safety patch 1 active
CMake also prints:
    SOH-EXTREME: APCpp request safety patch 1 enabled ...

GRAPHICS
========
* Shovel: a dedicated three-dimensional shovel with wood-grain and metal
  materials, plus a matching transparent 32x32 RGBA32 icon.
* Roll: a three-dimensional green circular-arrow emblem with a gold center,
  plus a matching transparent 32x32 RGBA32 icon.
* Both native item entries now use their dedicated get-item/world draw callback
  and message/UI icon. The existing Archipelago item mapping is unchanged.
* The tracker no longer forces boots for Roll or a hammer for Shovel. Both
  regular and faded GUI texture registrations use their dedicated icons.
* Vertex storage is static, vertex batches stay within the engine's cache,
  draw state is explicitly configured, and frame interpolation uses the proper
  native header/linkage. Missing optional material textures leave visible
  shaded geometry instead of attempting to dereference a missing resource.

CRASH INVESTIGATION AND PATCH
=============================
The latest exception in the supplied log is 0xc0000005. Its recorded stack
names APCpp.dll and the map of AP_GetServerDataRequest pointers. It occurred
in SCENE_HYRULE_CASTLE shortly after authentication/scouting. The log does not
establish that the HC Moat torch checks or the soul renderer caused it.

The reviewed APCpp socket error/close callback erases map entries inside a
range-for loop over that same map. Erasing the current entry invalidates the
loop's iterator. This patch marks pending requests failed, then clears the map
AFTER traversal. It also synchronizes the pending-request structures, clears
queued requests on disconnect, protects the message deque, and removes shared
mutable JSON Reader/FastWriter instances from the reviewed active call sites.

Offline request commitment now removes a queue entry BEFORE resolving it, so
callbacks that re-enter the API cannot process the same front entry again.
These changes address confirmed unsafe paths in the implicated library. They
are not a claim that every possible game crash has been eliminated.

The CMake module builds patched COPIES of the three APCpp source files in:
    build-vs\soh-extreme-apcpp-safe
It does not edit FetchContent's checkout, change the dependency's public ABI,
replace APCpp with a downloaded binary, or disable Universal Tracker. The
existing APCpp target still produces and deploys APCpp.dll normally.
An incompatible dependency source layout produces a clear configure error
rather than silently generating a partially patched DLL.

EXISTING FILES UPDATED BY THE INSTALLER
======================================
    CMakeLists.txt
    soh\Enhancements\randomizer\item_list.cpp
    soh\Enhancements\randomizer\randomizer_item_tracker.cpp
    soh\SohGui\ImGuiUtils.cpp

The installer uses narrow, validated edits because the repository does not
contain every previously delivered local patch. It preserves other content
in those files, including the soul registration loop and the previous build
configuration fixes. Originals are copied to:
    patch-backups\shovel-roll-apcpp-<timestamp>
If writing/copying during installation fails, those four originals are restored.
Running the installer again does not duplicate its entries or include lines.

NEW FILES
=========
    CMake\SoHExtremeAPCppSafety.cmake
    CMake\SoHExtremeAPCpp\Safety.inc
    soh\Enhancements\randomizer\ProgressionItemVisuals.h
    soh\Enhancements\randomizer\ProgressionItemVisuals.cpp
    soh\Enhancements\randomizer\ProgressionItemMeshes.inc
    assets\custom\textures\parameter_static\gExtremeShovelIcon.rgba32.png
    assets\custom\textures\parameter_static\gExtremeRollIcon.rgba32.png
    assets\custom\textures\parameter_static\gExtremeShovelWood.rgba32.png
    assets\custom\textures\parameter_static\gExtremeAbilityMetal.rgba32.png
    tools\install_shovel_roll_crash_fix.ps1
    APPLY_SHOVEL_ROLL_CRASH_FIX.cmd

The four textures are additionally mirrored to soh/assets/custom by the
installer, supporting the repository layout without changing the active packer.
The mesh include is data consumed by ProgressionItemVisuals.cpp; it is not a
separate compilation unit.

UNCHANGED
=========
EnemySoulDraw.cpp, EnemySoulIcons.h, build.cmd, the existing /FS /MP1 fixes,
item IDs, advancement/ownership effects, save schema, AP settings/mappings,
Check Finder access rules, Universal Tracker, and the AP world package.
No new seed or save is required by these changes.

VALIDATION
==========
See VALIDATION_Shovel_Roll_APCpp_Fix.txt for the tests actually performed.
This package was not built as a complete Windows game and was not tested in
an in-game rendering session. The installer was statically checked and its
source-edit patterns were exercised, but Windows PowerShell itself was not
available in the validation environment.

Source attribution:
    https://github.com/Mikemik444/SOH_EXTREME-Extreme
    https://github.com/N00byKing/APCpp
The existing APCpp source and its upstream license remain in the dependency
checkout. New graphics are original geometry and generated material textures.
