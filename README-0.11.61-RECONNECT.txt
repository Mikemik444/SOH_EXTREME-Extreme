SOH-EXTREME 0.11.61 - saved AP connection and tracker reconnect fix
SOURCE UPDATE ONLY. No new game executable is included in this package.

Base: Mikemik444/SOH_EXTREME-Extreme commit 11f45cf3340959e999064d4811cea61b1e188bad.
The touched existing source files matched that updated GitHub revision before
editing. This package contains only this update's 20 changed/new files.
It does not replace the rest of your repository with an older cumulative copy.

What changes
- The save identifies its AP game by seed name, team, slot ID and player name.
  The same game may move to a new server address/port without losing receipts.
- Edit the Network menu connection fields, then click Reconnect with updated
  settings. The game connection and automatic tracker use the updated details.
  Merely editing text does not redirect an already connected tracker.
- Loading a save restores that save's cached AP settings before scene actors
  initialize, including offline loads. Unverified live settings cannot replace
  the saved snapshot. Save progress and received-item counts are preserved.
- Pre-0.11.61 saves lack a seed ID. At their existing endpoint they retain the
  previous compatibility behavior and learn the ID. If the address changed,
  Check Tracker asks once to confirm it is the same generated game and player.
  Confirm only for the same game. After a normal save stores the ID, future
  address changes are automatic. A known wrong seed/team/slot is blocked.
- Existing generated seeds are supported. Item/location IDs are unchanged.

Apply to source
Back up your working source. Either copy the matching folder structure from
this ZIP into the repository, or apply the included patch (choose one method):
  git apply --check fixes-0.11.61-against-11f45cf.patch
  git apply fixes-0.11.61-against-11f45cf.patch
Both forward application and reverse validation were checked on copies of
the touched GitHub files. Reconfigure and rebuild the project normally; CMake
applies the new APCpp callback patch automatically to its fetched dependency.
Build the matching APWorld with tools/build_standalone_apworld.ps1.

Runtime installation, AFTER a successful game build
Install the rebuilt soh.exe, its matching rebuilt APCpp.dll, and the matching
soh_extreme.apworld together. Keep tracker.apworld installed in the Archipelago
runtime. Keep existing saves/configuration. Do not install the 0.11.61 APWorld
with the old 0.11.60 executable: the tracker requires matching versions.

Validation
- 47 assertions exercise production save-loading/reconnect functions with
  controlled engine/network adapters, including offline settings restoration,
  changed endpoints, rejected wrong identities, legacy confirmation and cursor
  preservation.
- Five delivery/save integration groups pass, including immutable identity
  snapshots for queued background saves after switching files.
- Five CMake patch cases pass, including idempotence and atomic failure checks.
- The actual patched APCpp DLL compiles and passes the packet-parser test for
  authentication gating, callback order, stable names, team/slot, reserved-key
  exclusion and repeated Connected packets. This test opens no network socket.
- APWorld builds with all 104 archive files matching canonical source.
- Python syntax and git diff whitespace checks pass.

Reproduce relevant tests in an x64 Visual Studio developer shell
  python validation/test_save_reconnect.py --include-dir <vcpkg-include> --output <test-output>/reconnect
  python validation/test_ap_delivery_audit.py --include-dir <vcpkg-include> --output <test-output>/delivery
  python validation/test_ap_connection_protocol.py --apcpp-source <fetched-apcpp-source> --apcpp-build <directory-containing-APCpp.lib-and-APCpp.dll> --output <test-output>/protocol
  python validation/test_ap_identity_patch.py --baseline <APCpp-Archipelago.cpp-before-this-identity-patch> --cmake <cmake-executable> --output <test-output>/patch

Current limitation
The full game executable has not been rebuilt or playtested for this update.
Windows still denies this session access to E:\test\vcpkg after permissions
were granted and the drive was reconnected. The standalone network DLL test
uses existing workspace libraries; it does not substitute for the full game
build. No 0.11.61 Windows runtime release is claimed or included here.
