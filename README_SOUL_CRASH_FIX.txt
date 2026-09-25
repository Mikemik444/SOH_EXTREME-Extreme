SOH-EXTREME Soul Runtime Crash Fix

Purpose
-------
Fixes the recent Fast3D GfxDpLoadTlut access-violation crash by removing the
128x128 tiled enemy-soul texture upload path.

What changes
------------
- Enemy soul portraits always use the normal 32x32 RGBA32 resource.
- The billboard itself is enlarged so enemy portraits are still easier to see.
- Texture LUT is explicitly disabled before and after portrait rendering.
- Boss souls, bean souls, category souls, APWorld logic, build.cmd, CMake and
  APCpp are not changed.

Install
-------
Extract this ZIP directly into:
    E:\test\bb

Replace:
    soh\Enhancements\randomizer\EnemySoulDraw.cpp

Then run your existing:
    build.cmd

After BUILD COMPLETE, run the newly built game from:
    E:\test\bb\x64\Release\soh.exe

Do not delete build-vs and do not rerun older all-in-one patch installers.
