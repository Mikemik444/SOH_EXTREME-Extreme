SOH-EXTREME 1.6.0 - matching client/APWorld release and updated About panel

Install
Close SoH and extract the entire Windows package into your game folder, replacing
the matching files. Keep the included assets folder. Install the included
soh_extreme.apworld in the Archipelago runtime used by the automatic tracker.
Keep tracker.apworld installed. Both the client and APWorld now use 1.6.0.
Existing saves, generated AP seeds, and compatible oot.o2r files are retained.

About
Settings > General > About now identifies SOH-EXTREME, shows Client version
1.6.0 and Matching APWorld 1.6.0, and offers an Open SOH-EXTREME GitHub button:
https://github.com/Mikemik444/SOH_EXTREME-Extreme
It credits Ship of Harkinian, shows the actual build's branch/commit, and labels
the ROM revision as ROM assets (for example NTSC 1.0). Missing Git metadata in
source archives uses explicit fallback labels. Matching APWorld states which
version to install; it does not claim to detect the installed package offline.

The public release number is separate from the upstream 9.2.3 save/asset format.
That format has not changed, so this version change does not require new assets
or new AP saves. Includes all 0.11.63 fixes and retail/debug MQ conversion data.

Source update
The source ZIP contains 13 updated/new files against GitHub commit 374b8d3b9bafb63aa8aa2704809ef4302b4f7316.
Copy its matching source folders into that checkout, or apply its patch:
  git apply --check fixes-1.6.0-against-374b8d3.patch
  git apply fixes-1.6.0-against-374b8d3.patch
Then reconfigure CMake and rebuild. The generated src/boot/build.c is recreated
automatically. Build APWorld with tools/build_standalone_apworld.ps1. The source
patch was applied forward and checked in reverse on private baseline copies.
No GitHub push or release publication was performed.

Validation
Windows x64 Release build completed. The real Python serializer and C++ tracker
agree on 1.6.0; older tracker data receives a matching-version error. Both
APWorld manifests, client release header, and packaged APWorld agree. The
generated build information retains numeric save/archive format 9.2.3. Source
archives do not inherit Git metadata from an unrelated parent repository.
The rebuilt APCpp DLL passed its packet-parser/reconnection regression.
ZIP contents and checksums were verified. No live UI/gameplay test was performed.
