SOH-EXTREME HQ Safe Soul Portrait Patch

Why this exists
---------------
The old 32x32 portrait is visibly blurry when enlarged.
The previous single 128x128 runtime path was unsafe and produced a Fast3D
GfxDpLoadTlut access-violation crash.

This patch uses FOUR independent 32x32 RGBA32 textures for each portrait.
Together they render as one effective 64x64-detail enemy portrait.

Important
---------
- The enemy artwork is regenerated from source/portraits when available.
- The giant skull composite is NOT used for the new in-world portrait.
- Each GPU/Fast3D upload remains only 32x32 RGBA32.
- No 64x64/128x128 RGBA32 texture is loaded as one block.
- APWorld, build.cmd, CMake and APCpp are untouched.

Install
-------
Extract the ZIP into E:\test\bb.
Run APPLY_HQ_SAFE_SOUL_PORTRAITS.cmd.

It generates the tile PNGs, then calls your existing build.cmd.
After BUILD COMPLETE, launch:
E:\test\bb\x64\Release\soh.exe
