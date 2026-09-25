SOH-EXTREME HQ Soul __gfxCtx Linker Fix

Fixes:
EnemySoulDraw.obj : error LNK2001: unresolved external symbol __gfxCtx

Cause:
The HQ soul patch used POLY_XLU_DISP inside helper functions that were outside
the lexical OPEN_DISPS block. POLY_XLU_DISP therefore resolved to the global
extern __gfxCtx instead of the local graphics context created by OPEN_DISPS.

Fix:
The helpers now receive the active Gfx* display-list pointer by reference from
inside DrawSoulPortrait's OPEN_DISPS scope.

Install:
1. Extract this ZIP directly into E:\test\bb
2. Replace soh\Enhancements\randomizer\EnemySoulDraw.cpp
3. Run your existing build.cmd
4. After BUILD COMPLETE run E:\test\bb\x64\Release\soh.exe

This patch does not modify build.cmd, CMake, APWorld, assets, or APCpp.
