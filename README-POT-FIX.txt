SOH-EXTREME 0.11.38 - Dodongo's Cavern doorway pots
Repository: https://github.com/Mikemik444/SOH_EXTREME-Extreme

WINDOWS REPLACEMENT
Close SOH. Extract the Windows ZIP into the folder containing the soh.exe you
actually launch, replacing soh.exe and APCpp.dll. For a source build, this may
be x64\Release. Keep your existing assets, configuration and saves.
Install the included soh_extreme.apworld using the AP installer, or replace
the existing copy in custom_worlds. Restart AP/Universal Tracker clients.

SOURCE REPLACEMENT
Extract the Source-Patch ZIP into your SOH_EXTREME-Extreme source root, beside
build.cmd, and replace the included files. Run build.cmd from a fresh Command
Prompt and wait for BUILD SUCCESS. Install the resulting 0.11.38 APWorld.
This patch is cumulative against Git commit
9bc10e7191b546754a50da6463e074276d33862f. Merge independent edits to these files.

FIX
The two pots outside the lower Lizalfos doorway were absent from the AP
catalog and runtime map, although native pot shuffle tried to replace their
contents. All 341 non-MQ native pots were compared against the AP catalog;
these were the only two omissions.

New seeds now include these checks when dungeon/all pots are shuffled:
- Dodongos Cavern Near Lizalfos Room Pot 1 (943)
- Dodongos Cavern Near Lizalfos Room Pot 2 (944)
Their region, Pot Soul requirement and usable break/lift action are enforced.
AP-inactive pots retain ordinary drops. Failed collectible allocation leaves
the check pending instead of dereferencing a missing actor.

EXISTING SEEDS
Your old server has no AP items assigned to these two pots. Updating the EXE
fixes their ordinary drop behavior but cannot add server-side rewards.
Generate a NEW SEED with APWorld 0.11.38 to make them AP checks. Old-seed UT
reconstruction will not add phantom checks. These omissions did not hide
assigned progression items from your existing seed.

The patch also includes the 0.11.37 important-item hold-up fixes and courtyard
window retirement, plus all earlier fixes. New seeds exclude the two windows;
old seeds retain their server-owned window placements. Previously received
items are not granted again solely to replay their animation.

VALIDATION
739 catalog/AP logic/UT assertions; 134 compiled production pot assertions;
AP presentation and five delivery regression groups; Windows Release build;
104-file APWorld/source parity; source patch apply checks and ZIP checksums.
Fresh seed 1138 passed generation and independent progression replay: all
3319 network checks reachable and the goal met. This tests that generated
seed and modeled requirements, not every possible seed or in-game physics.
No rendered or connected in-game playthrough was performed.
See VALIDATION-POT-FIX.json, CHECK-AUDIT-POT-FIX.json and SOH_AP_FIX_HISTORY.txt.
