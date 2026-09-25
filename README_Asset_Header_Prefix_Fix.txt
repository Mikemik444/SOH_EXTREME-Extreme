SOH-EXTREME - Asset Header Prefix Fix (v2)
=========================================

Fixes:
  ImGuiUtils.cpp: Cannot open include file: 'assets/soh_assets.h'

The previous helper added the assets directories but omitted their parents.
  #include "soh_assets.h"        needs <repo>/soh/assets
  #include "assets/soh_assets.h" needs <repo>/soh
This replacement supports both the root and nested asset layouts. It retains
existing include directories and adds only target-private include paths.

INSTALL
1. Stop any running build.
2. Back up tools/cmake/SohExtremeAssets.cmake outside the source tree.
3. Extract this ZIP directly into E:\test\bb, merge folders, and replace:
     tools\cmake\SohExtremeAssets.cmake
4. Run your existing build.cmd from E:\test\bb.

No installer is included or required. Do not delete build-vs. Do not reapply
old all-in-one installers. This ZIP does not change build.cmd, the root
CMakeLists.txt, arvhipelago, any APWorld, gameplay C++, APCpp or textures.
The existing PackSohExtremeAssets.cmake must remain installed.

On regeneration, the helper prints:
  SOH-EXTREME game asset header paths (v2): ...
For a nested checkout the list includes BOTH E:/test/bb/soh/assets and
E:/test/bb/soh. Existing root-layout include directories are retained too.

SCOPE
Only one existing file is replaced. The packer, shader discovery and asset
staging sections are byte-identical to the previous asset-header patch.
No APWorld packaging, installation, version change or game rebuild is
performed merely by extracting this ZIP.

VALIDATION
Reproduced the old prefixed-include failure. Built and ran isolated header
probes with GCC and Clang for nested-only, root-only, root-overlay/nested-header,
and both-root layouts. Compiled those probes as Windows-targeted objects with
clang-cl. Tests used the three actual asset headers from the user's bb_assets.zip
with their alignment macro, not the full game or dependency tree.
Verified bare and assets/-prefixed includes resolve, prior include paths remain,
and include paths do not propagate to the stub dependency target.

This was NOT a complete Windows/MSVC game build, an in-game test, or a test
of the full ImGuiUtils.cpp translation unit. No new seed is needed for an
include-path-only change.
