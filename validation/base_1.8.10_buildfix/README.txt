SOH-EXTREME 1.8.10 - Complete source files, compile fix
=====================================================

This cumulative ZIP fixes the Windows compiler error:
  logic.cpp(1633): C3861: 'CVarGetInteger': identifier not found

logic.cpp now directly includes the existing project header:
  <libultraship/bridge/consolevariablebridge.h>

This is the same header used by neighboring randomizer source files. It makes
the console-variable declaration available to WaterTempleDoorsShuffled().
No function body or gameplay rule changed. The version remains 1.8.10, and
the APWorld and YAML are byte-identical to the original 1.8.10 release.

CONTENTS
--------
All 175 complete replacement source files are included, with all prior fixes,
the matching APWorld, YAML, and clean-build helpers. SOURCE_FILES.json has the
updated logic.cpp hash so the helper accepts the corrected complete file.

INSTALL AND BUILD
-----------------
1. Merge soh\, src\, archipelago\ and tools\ into your complete checkout,
   replacing the corresponding files. Replace SOURCE_FILES.json in the root
   as well, and copy BUILD_RELEASE.cmd and BUILD_RELEASE.ps1 there.
2. For your E:\test\bb checkout, run:

   cd /d E:\test\bb
   BUILD_RELEASE.cmd -RepositoryPath "E:\test\bb" -BuildDirectory "build-vs"

   The helper verifies the sources, performs the clean Release build, and
   prints the executable path. Use your actual paths if different.
3. If your APWorld is already 1.8.10, this compile-only repair needs no APWorld
   change or new seed. For an older installation, the included APWorld goes
   in C:\ProgramData\Archipelago\custom_worlds\soh_extreme.apworld.

The previously audited 1.8.9 seed still needs regeneration with 1.8.10 because
of its invalid progression route. This compile fix does not change that audit.

VALIDATION
----------
Current declaration/compiler and source-package reports are in validation/.
Original 1.8.10 rule/runtime/seed evidence and detailed release notes are kept
under validation/base_1.8.10/. Those reports retain their original source
hashes; they are historical execution evidence, not newly rerun tests.
The source comparison proves this correction adds only the declaration-header
include and preserves every original logic.cpp byte following it.

The earlier Water fixture supplied CVarGetInteger as test I/O before compiling
extracted function bodies. That tested behavior but missed the production
translation unit's absent include. The targeted declaration check covers this
specific omission against the real dependency header.

The partial checkout still cannot support a complete Windows game build in
this environment. The scoped compiler check and source preflight do not claim
an MSBuild run or an in-game playthrough.
