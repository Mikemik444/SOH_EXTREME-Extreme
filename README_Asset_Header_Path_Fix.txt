SOH-EXTREME - Asset Header Include Path Fix
===========================================

For the reported build log where CMake already prints:
  SOH-EXTREME packer source: E:/test/bb/soh/assets/tools/soh-o2r-packer
but C++ compilation cannot find:
  soh_assets.h
  textures/icon_item_static/icon_item_static.h

Install
-------
1. Finish/stop any active build and close the game.
2. Keep a copy of your current tools/cmake/SohExtremeAssets.cmake as a backup.
3. Extract this ZIP directly into E:/test/bb. Merge tools/cmake and replace
   SohExtremeAssets.cmake when prompted.
4. Run your existing build.cmd from E:/test/bb.

No patch installer needs to be run. Do not rerun earlier all-in-one installers.
Do not delete build-vs. Keep your restored build.cmd.

Scope
-----
One existing build configuration file is replaced:
  tools/cmake/SohExtremeAssets.cmake

It retains the previous packer/staging configuration and appends the game
asset-header include paths. It keeps root assets/ overrides ahead of the nested
soh/assets/ headers and does not replace the target's other include directories.
The headers themselves are not regenerated, copied, or changed.

This ZIP contains no build.cmd, CMakeLists.txt, PowerShell installer, APWorld,
arvhipelago files, C++ gameplay changes, textures, save changes or DLLs.
It does not call or install any Archipelago packaging scripts.

This replacement matches the SohExtremeAssets.cmake module explicitly named in
your latest build log. On reconfiguration, look for:
  SOH-EXTREME game asset header paths: .../assets;.../soh/assets

The module reports a specific configure-time error if either required header is
actually absent from both supported asset roots. It does not create empty headers
or suppress a missing-file failure.

Validation
----------
12 isolated CMake/GCC/Clang test scenarios passed (six for each compiler):
- Reproduced the original missing-header compile failure with the old module.
- Built and ran a probe using the real asset resource-name headers in the nested
  layout, the legacy root layout, and a mixed root-override/nested layout.
- Verified existing compile definitions and include-directory ordering remain.
- Reconfigured the existing fixture build directories without adding duplicates.
- Confirmed clear errors when all headers or the texture header are absent.

The two tested asset headers exactly match the Git blobs read from your repository:
  soh_assets.h: 3f8d44db050b193143c0fa6fb4bd1018f49d3458
  textures/icon_item_static/icon_item_static.h:
    c323058597581ad21742d19e3e60c1b495ffe664

Other engine/packer dependencies in the test project were stubs. This is not a
full game build, Windows/MSVC validation, production asset-pack test or in-game
visual test. The earlier asset packer/staging commands were left unchanged.
