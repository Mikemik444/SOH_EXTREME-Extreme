SOH-EXTREME APWORLD SYNC FIX
=============================

Extract this ZIP directly over your SOH-EXTREME source root:

    E:\test\bb

Overwrite the included files.

WHY THIS PATCH EXISTS
---------------------
The canonical APWorld source folder was renamed from:

    arvhipelago\

to:

    archipelago\

but the APWorld packaging script still used the old misspelled path.

The current build.cmd also stopped invoking the APWorld packager, which allowed
the installed custom_worlds\soh_extreme.apworld to remain stale while the source
and C++ client changed.

FILES
-----
build.cmd
tools\build_standalone_apworld.ps1
REBUILD_APWORLD_ONLY.cmd

WHAT TO DO
----------
Fast APWorld-only repair:

    REBUILD_APWORLD_ONLY.cmd

Then completely close/reopen Archipelago and generate a NEW seed.

Or run the normal:

    build.cmd

The updated build.cmd now:
1. rebuilds soh_extreme.apworld from archipelago\
2. installs that exact APWorld into Archipelago custom_worlds
3. builds the game as usual
4. validates APWorld/source parity at the end

IMPORTANT
---------
Do not continue an old room/seed when testing this fix. The active location
manifest and slot data are generated into the room, so use a newly generated seed.

V2 POWERSHELL COMPATIBILITY FIX
-----------------------------
Explicitly loads both System.IO.Compression and System.IO.Compression.FileSystem
so Windows PowerShell can resolve ZipArchiveMode.
