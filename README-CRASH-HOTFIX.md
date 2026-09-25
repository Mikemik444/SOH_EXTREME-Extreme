# SOH-EXTREME 0.11.21a -- APCpp crash hotfix

Apply over the installed 0.11.21 Bombchu/soul patch. This is a native/network
hotfix, not a new AP gameplay-rule version. Keep soh_extreme.apworld 0.11.21,
tracker.apworld, your existing assets, and your current save/seed.

## What the log actually shows

The final exception is 0xc0000005. Its traceback names the std::map erase code
for AP_GetServerDataRequest pointers in APCpp.dll. The DLL was loaded from
E:\test\bb\x64\Release2\APCpp.dll, not necessarily the build output directory.
The automatic UT host was started at 08:59:40.844 and 08:59:40.870, 26 ms apart.

The trace does not contain an exact APCpp source line or establish why the
connection closed. This repair addresses a reproduced defect in that same
request cleanup code, a concurrent JSON-codec hazard, and the independently
reproduced duplicate tracker startup. A complete Windows run is still required
to confirm that this resolves this particular crash.

## Changes

1. The reviewed APCpp disconnect/error handler erased the current std::map node
   inside a range-for, then incremented that invalid iterator. The new loop
   uses the iterator returned by erase and completes each outstanding request
   once. It also tolerates a null request pointer.
2. APCpp's mutable Json::Reader and Json::FastWriter instances become
   thread_local. Matching extern declarations in its gifting/offline helper
   files are updated together. Game-thread Bounce serialization no longer uses
   the websocket thread's codec objects. This is not a blanket claim that every
   other APCpp public API is now thread-safe.
3. ServiceFinderWorker waits for both save-runtime reconciliation and the
   game's first-authentication reset. Previously Update started the worker,
   stopped/reset it later in that same Update, then started a second worker on
   the next frame. The game still manages its tracker automatically. Region
   grouping and normal-save/native tracking are unchanged.

No Bombchu pool/refill, item receipt, soul texture, enemy identity, or location
rule is removed or changed by this hotfix.

## Install and build

Close the game (including its crash dialog), and close other build jobs.
Merge this ZIP into E:\test\bb, overwriting the included native source file.
Do not delete your soh, src, assets, build-vs, or save folders.

Run in your working Command Prompt:

```bat
cd /d E:\test\bb
BUILD-AP-CRASH-HOTFIX.cmd
```

Use that helper for this first installation, not just a plain EXE rebuild.
The crash is in APCpp.dll, which must be repaired and rebuilt too.

The helper:
- Adds one guarded include after your existing FetchContent_MakeAvailable(apcpp)
  without replacing the rest of your CMakeLists.txt/toolchain configuration.
- Repairs the locally fetched APCpp source at configure time. It verifies the
  reviewed block before writing, saves originals with .before-soh-0.11.21a,
  and reapplies after future dependency refreshes. An unrecognized revision
  stops with an error instead of receiving a guessed edit.
- Reconfigures the existing build, then builds APCpp and soh with one worker.
- Uses the actual target paths emitted by CMake, not modification-time guesses.
- Verifies the new DLL's marker and deploys the matched EXE/DLL to bb, the
  configured EXE output directory, and x64\Release2 if it contains soh.exe.
  Old runtime files are backed up, and deployed hashes are checked.

No asset rebuild or AP-world replacement is needed. The helper does not delete
or modify assets, saves, YAMLs, or seeds. It does not kill running processes.
A failed build/deployment is reported as failure, not success.

After starting the game, the log should include:

```text
AP: SOH-EXTREME APCpp safety hotfix 0.11.21a active
```

AP-CRASH-HOTFIX-DEPLOYMENT.txt records exactly which EXE and DLL were deployed.
Use the rebuilt EXE in one of those directories, not another older runtime copy.

## Contents

- One complete replacement native file:
  soh/Network/Archipelago/ArchipelagoClient.cpp
- CMake/SohExtremeAPCppSafety.cmake
- tools/build_ap_crash_hotfix.ps1
- BUILD-AP-CRASH-HOTFIX.cmd
- Focused regression sources/results, validation scope, and native source diff.

## Limitations

No full Windows/MSVC game or APCpp build, Windows PowerShell helper execution,
live AP/UT connection, or in-game visual playtest was possible in this Linux
runtime. The supplied helper performs the real Windows rebuild and verification.
See VALIDATION.md for what was reproduced and executed here.
