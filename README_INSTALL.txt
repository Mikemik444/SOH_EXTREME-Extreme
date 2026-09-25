SOH-EXTREME 0.11.22 - ASSET BUILD + CANONICAL ARVHIPELAGO SOURCE HOTFIX

INSTALL (keep the already-applied Soul Clarity/Grab 0.11.22 patch)
1. Close the game and Universal Tracker. Do not run another build concurrently.
2. Extract this COMPLETE ZIP into E:\test\bb; keep patch-data intact.
3. Double-click APPLY_BUILD_SOURCE_FIX.cmd.

The installer backs up affected files, repairs the asset target in your actual
CMakeLists.txt, synchronizes the complete 0.11.22 arvhipelago source tree, updates
the obsolete APWorld build entry points, and runs your existing build.cmd.
If ProgramData permissions are denied, run the CMD as administrator.
After BUILD COMPLETE, use E:\test\bb\soh.exe. Restart Universal Tracker.
Do NOT delete build-vs. Do NOT rerun the older 0.11.22 installer: it has already
installed its gameplay/visual changes and this hotfix does not remove them.

NORMAL BUILDS AFTER INSTALLING
Run build.cmd as usual. It now builds/verifies the world directly from:
  arvhipelago\archipelago.json
  arvhipelago\soh_extreme\...
The output is soh_extreme.apworld beside build.cmd, then the SAME archive is
installed into the detected Archipelago\custom_worlds directory. No Python
installation is needed for this PowerShell packaging operation.
APWORLD_SOURCE_SYNC_REPORT.json records the version, file count, archive hash
and successful source/ZIP parity checks. Every archived entry is SHA-256 checked
against its source, and Python/C++ tracker versions must agree with the manifest.
No gameplay/version bump is introduced: world and tracker stay at 0.11.22.

WHAT WAS WRONG
- CMake used assets/tools/soh-o2r-packer/main.cpp even though the repository stores
  the tool in soh/assets/tools/soh-o2r-packer. A partial assets/custom folder
  created by a patch is not proof that the root tools folder exists.
- The old build_standalone_apworld.ps1 started from apworld/*.apworld, downloaded
  stock helpers again, deleted/replaced the modified private vendor folder, and
  forced version 0.11.2. The older install script similarly forced 0.11.9.
- BUILD_FIXED_APWORLD.py searched older archives and edited their contents instead
  of packaging the current source. These legacy entry points now delegate to the
  same canonical arvhipelago builder; they never re-download stock helper rules.

SOURCE AUDIT
At reviewed GitHub commit 473e6c69d146fb426fd83f9d1278c3c717fa865d, the ENTIRE
arvhipelago tree matches the 0.11.21d APWorld source (Git tree hash
 a19193300a57f3572180e8a8a9ce037c1c3b403d).
The repository's root APWorld also matches that same 0.11.21d artifact.
This does not mean all earlier updates were absent. The prior 0.11.22 installer
already targeted six source files in arvhipelago, as well as the installed ZIP.
This hotfix includes all 102 files of the matching 0.11.22 source rather than
relying on a partial overlay. The full source is entry-for-entry identical to
that delivered 0.11.22 APWorld, including the modified vendored helpers.
Future edits must be made to arvhipelago, not only inside a binary .apworld.
This installer modifies your LOCAL checkout. Commit and push the resulting
changes to publish them on GitHub; it does not write to GitHub automatically.

ASSET BUILD
Tool discovery checks for all three actual packer source files, nested layout
first and legacy root layout second. A recovery copy of these unchanged source
files is included and copied only when a nested file is missing. Build-time
tools are excluded from soh's recursive source glob to avoid the earlier
TorchExtract.h / extra-main error.

The new GenerateSohOtr command stages the full soh/assets/custom base plus the
legacy assets/custom overlay under build-vs, then stages the selected
LibUltraShip shaders. On conflicts, root/assets/custom wins, matching the
previous root-based packer's inputs; keep legacy overlays synchronized with
intentional future edits to the same nested resource. Original source assets
are not removed. The build holds a staging/packing lock and replaces soh.o2r
only after the packer exits successfully with a nonempty archive.

BUILD SETTINGS
Your CMake dependency/toolchain paths and unrelated configuration are retained.
Your existing build.cmd asset setup and runtime-copy steps are retained.
The inserted pre-build section appends /FS /MP1 through _CL_ and limits an old
soh --parallel value above three to three (existing lower values remain lower).
These are the low-memory/compiler-PDB controls used during troubleshooting;
they are not a guarantee against all machine-specific build failures.
The old build.cmd-only version banner is removed to avoid mistaking it for the
APWorld version. An older number printed by the AP-model installer describes
that script, not a downgrade of the gameplay world.

SAFETY
Unknown local edits to protected payload files stop installation before copying.
Source baselines accept LF/CRLF checkout differences. Existing files are backed
up under patch-backups/build-source-fix-<timestamp>, with a restore manifest.
File-write failures attempt rollback. A later build failure leaves the installed
source fix in place so the first build error can be addressed without reapplying
or deleting your build directory. Save files, seeds, item IDs, receipt history,
Shovel/Roll models, soul visuals, and APCpp networking fixes are not rewritten.
Newer/incompatible installed APWorld versions are not silently downgraded.
Renamed duplicate SOH-EXTREME APWorlds or an unpacked development world are not
silently deleted. Existing seed item placements are unchanged.

CUSTOM INSTALLATION / DEVELOPER SWITCHES
The default search matches the user's C:\ProgramData\Archipelago setup.
For a different installation, set SOH_EXTREME_AP_ROOT in your own environment
or supply -ArchipelagoRoot to Apply-BuildSourceFix.ps1 / the canonical builder.
The builder also supports -SkipInstall and -CheckOnly; the installer supports
-SkipBuild. None of these switches are needed for the normal instructions above.

VALIDATION AND LIMITS
31 isolated checks passed. The original missing-source configuration error was
reproduced with the repository's target layout, then the corrected CMake modules
configured/generated successfully for both folder layouts. A dummy game target
built without pulling in the packer/torch-cli sources. The real staging script
passed base/overlay/shader, alias-deduplication, and failed/empty-output retention
tests using a MOCK packer; this is not a codec or in-game rendering test.
All 75 Python modules in the source bundle parse, JSON data parses, the 102
source files match the previous 0.11.22 archive, and all tracker versions agree.
The complete old source tree and root APWorld match the reviewed GitHub hashes.
Windows PowerShell execution, a full MSVC/Windows game build, full Archipelago
seed generation and in-game visual testing were NOT performed here.
See validation/ for the actual reports. No new rendering/logic test claims are
made for the unchanged 0.11.22 implementation.
