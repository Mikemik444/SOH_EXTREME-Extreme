SOH-EXTREME 0.11.62 - normal OoT from PAL Master Quest, plus AP reconnection

Install
Close SoH, then extract the complete Windows ZIP into your SoH folder, replacing
the matching files. Keep your saves and configuration. The assets folder is
required. Install the included soh_extreme.apworld in your Archipelago runtime
and keep tracker.apworld installed. Game and APWorld must both be 0.11.62.
Existing generated AP seeds do not need regeneration; item/location IDs did
not change.

Using either ROM
If you already have compatible normal oot.o2r, it continues to work.
If you only have oot-mq.o2r, launch soh.exe and select your ROM when asked.
The verified PAL GameCube Master Quest (E) ROM now creates NORMAL oot.o2r.
Regular supported OoT ROMs also create normal oot.o2r through the usual path.
AP saves use normal dungeon layouts in either case, rather than treating MQ
rooms as normal rooms. Non-AP saves retain their own dungeon selection.
The input ROM is never changed. Temporary converted data is removed after
extraction. No ROM or extracted Nintendo asset archive is included here.

Supported MQ reference
PAL GameCube MQ, SHA-1 f46239439f59a2a594ef83cf68ef65043b1bffe2.
The converted result matches normal NTSC 1.0, SHA-1
ad69c91157f6705e8ab06c79fe08aad47bb57ba7, byte for byte.
Byte-swapped inputs are normalized. Other MQ regional/debug revisions require
separate verified conversion data and report an explicit error.

Saved AP connection changes (included from 0.11.61)
Edit the Network connection fields, then choose Reconnect with updated settings.
The game and automatic tracker use the actual updated connection. Loading a
save still restores its cached AP configuration before scene actors initialize.
Seed name, team and slot identify the saved game independently of host/port.
An older save changing endpoints may ask once to confirm it is the same game;
after the identity is saved, subsequent endpoint changes are automatic.
Known wrong seed/team/slot identities are blocked. Received-item counts and
pending checks are preserved.

Source update
The source ZIP contains 31 changed/new files against GitHub commit
11f45cf3340959e999064d4811cea61b1e188bad. Copy its matching folders into that repository, OR apply its included
binary patch (choose one method):
  git apply --check fixes-0.11.62-against-11f45cf.patch
  git apply fixes-0.11.62-against-11f45cf.patch
Forward and reverse application, including the conversion BPS data, were checked
on copies of the matching GitHub source. Reconfigure and build normally; CMake
patches the APCpp dependency. Rebuild APWorld with
tools/build_standalone_apworld.ps1. The source package includes the deterministic
conversion-data generator, which accepts the two private reference ROMs.

Validation
- Full Windows x64 Release game and matching APCpp DLL build completed.
- 31 native BPS/conversion cases pass: byte-for-byte reference match, byte order,
  all BPS operations, overlap, malformed lengths/offsets, checksums and failures
  that leave output unchanged. Original reference files remain unchanged.
- The actual CallTorch entry point passes handoff and temporary-cleanup checks
  with a controlled Torch service, including missing patches, failed extraction,
  exceptions and rejection of an unexpected MQ archive name.
- 47 production reconnect assertions and delivery/save regression groups pass.
- Eight APCpp patch tests pass, including the cached 0.11.61 layout upgrade;
  repeated full CMake configuration succeeds.
- Actual rebuilt APCpp packet-parser regression passes without a network socket.
- All 104 APWorld archive files match canonical source; both versions are 0.11.62.
- Source patch and release archive integrity checks pass.

Testing limit
No live gameplay test was performed. An actual Torch extraction comparison was
attempted but Windows denied its weakly_canonical path-metadata lookup in this
execution environment, even with explicit directory permission. The converted
ROM itself is verified identical to the normal reference; a complete in-game
first-run extraction still needs a player smoke test. Torch now restores its
logging level so extraction failures are visible in the log.

Reproduce conversion checks in an x64 Visual Studio developer shell:
  python validation/test_normal_oot.py --mq <PAL-MQ-ROM> --normal <NTSC-1.0-ROM> --output <test-directory>
Optional full asset comparison: supply --torch-harness pointing to the same
test_normal_oot.cpp compiled with TEST_TORCH, TorchExtract.cpp and the built Torch
libraries. See the other validation scripts for reconnect/parser regression use.
