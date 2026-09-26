SOH-EXTREME TLUT crash guard

1. Keep EnemySoulDraw.cpp using the required call:
   gSPVertex(polyXluDisp++, reinterpret_cast<uintptr_t>(quad), 4, 0);

2. Run APPLY_TLUT_CRASH_FIX.cmd.
   It patches E:\test\libultraship\src\fast\interpreter.cpp and makes a backup.

3. Rebuild:
   cd /d E:\test\bb
   cmake --build build-vs --config Release --parallel 8

The patch is revision-tolerant: it locates GfxDpLoadTlut and its memcpy instead
of relying on a fixed line number. If the expected function/memcpy is not found,
it stops without modifying the file.
