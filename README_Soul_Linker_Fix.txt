SOH-EXTREME - SOUL RENDERER LINKER HOTFIX
======================================

Install this ON TOP of the All Souls Rendering Patch already installed.

1. Close the game and let any current build stop.
2. Extract this ZIP's CONTENTS directly into E:\test\bb.
   Merge the soh folder and replace:
   soh\Enhancements\randomizer\EnemySoulDraw.cpp
3. Run E:\test\bb\build.cmd.
4. After BUILD COMPLETE, launch E:\test\bb\soh.exe.

Do not delete build-vs, regenerate your seed, or change compiler settings.
No APPLY_PATCH.cmd step is needed. This contains a complete replacement source
file, not a script that edits your source.

Only EnemySoulDraw.cpp is replaced. Keep EnemySoulIcons.h from the previous
All Souls Rendering Patch. The existing build.cmd and CMake fixes are untouched.

FIX
---
The native OPEN_DISPS/CLOSE_DISPS macros declare frame-interpolation hooks at
block scope. The previous renderer omitted the native interpolation header and
placed its drawing helpers inside an anonymous namespace. The resulting C++
function references did not match the native C-linkage exports.

The corrected renderer includes soh/frame_interpolation.h outside extern "C"
and uses global-scope static helpers rather than an anonymous namespace. This
keeps the helper functions file-local while allowing the macro declarations to
match the engine's existing FrameInterpolation_RecordOpenChild and
FrameInterpolation_RecordCloseChild exports.

No stub implementations are added to the game. Interpolation stays enabled.
All seven function bodies are unchanged, so this hotfix preserves the previous
soul drawing behavior, mappings, ownership rules and save compatibility.

VALIDATION
----------
A focused reproducer used the native interpolation header (Git blob verified)
and the native OPEN_DISPS/CLOSE_DISPS macro definitions. The original arrangement
reproduced unresolved interpolation symbols. The corrected arrangement passed
GCC and Clang compile/link/run checks in Release and Debug configurations, plus
clang-cl/lld-link Windows-COFF compile/link checks for both configurations.

These are isolated linkage tests with stub game types and implementations, not
a full Microsoft MSVC build of SoH or an in-game graphics test. The Windows test
executables were linked but not run. The full game must still be built locally.

Basis: SOH_EXTREME_All_Souls_Render_Fix.zip supplied in this conversation.
Native declarations checked in Mikemik444/SOH_EXTREME-Extreme:
  soh/frame_interpolation.h
  include/macros.h
