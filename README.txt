SOH-EXTREME 1.6.1 - entrances, room debug, and logic fixes

Already applied on this computer:
  Source: E:\test\bb
  Game: E:\test\bb\x64\Release\soh.exe
  APWorld: C:\ProgramData\Archipelago\custom_worlds\soh_extreme.apworld
  Backup: E:\test\bb\codex-backups\entrance-room-20261014-180935

Restart SOH and use Restart AP tracker in Check Tracker.
Click Room debug beside Refresh AP checks to show the scene, engine room,
logical region(s), and destination labels beside nearby physical doors.
Rooms containing several logical regions show all their region names.

FIXES
- Normal FLOOR_EFFECT_2 scene crossings report checks, including entering the
  Lon Lon Ranch house, stable, and tower. Return crossings remain separate.
- Both lower Dodongo's Cavern Lizalfos exits require their soul and a defeat
  method. Moving the statue at the corridor switch requires Grab, even as adult.
- The Kakariko tree drop no longer wrongly requires Skulltula Soul because its
  old name contains GS. New seeds have independent child and adult tree checks;
  each requires Roll, Tree Soul, and access at the matching age.
- Existing AP seeds keep the original shared tree ID and can collect it at
  either age. They do not gain a new adult-tree placement. Generate a new seed
  with Shuffle Trees enabled for the separate adult check.
- Dampe's first six pots, first three rupees, and first five wonder items are
  before the first barrier and do not require starting the race. Their physical
  interactions still apply. Later tunnel checks retain the Dampe speech gate.

INSTALL ON ANOTHER COMPUTER
Close SOH. Copy x64/Release/soh.exe and APCpp.dll into the existing game folder.
Keep the existing game assets, mods, saves, configuration and other DLLs.
Install soh_extreme.apworld into Archipelago/custom_worlds, replacing the old
SOH-EXTREME APWorld, then restart the tracker. This is an incremental update.
No save reset or new seed is needed for fixes to already-existing checks.

SOURCE / GITHUB
The archipelago/, soh/, and tools/ files are the source update. The patch is an
alternative against the previous source revision. Do not add the executable,
DLL, validation output or patch scratch files to Git just because they ship here.
All 107 APWorld entries exactly match the included and local AP source bytes.
After Git changes line endings, rebuild with tools/build_standalone_apworld.ps1
before running its -CheckOnly parity verification.

VALIDATION
Windows Release x64 compiled and linked. 746 crossing identities, 624 physical
scene-exit cases, 473 door-label directions, 262 soul/combat/Grab assertions,
295 AP/Universal Tracker/finder logic assertions, and native tree identities
passed. A complete seed generated and replayed all 4,037 network checks.
648 exit-surface records across playable age/time layouts were audited;
dynamic returns and sealed boss-room returns were classified separately.
No interactive gameplay test was performed. See VALIDATION.json for details.
