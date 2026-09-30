SOH-EXTREME 0.11.39 - Native models for enemy AP drops
Repository: https://github.com/Mikemik444/SOH_EXTREME-Extreme

WINDOWS DRAG-AND-DROP
Close SOH. Extract the Windows ZIP into the folder containing the soh.exe you
actually launch (often x64\Release), replacing BOTH soh.exe and APCpp.dll.
The pair must stay together: the AP scout callback now includes game identity.
Keep your existing soh.o2r/assets, saves and configuration.
Install the included soh_extreme.apworld through Archipelago's installer, or
replace the existing copy in custom_worlds. Restart AP/Universal Tracker.

SOURCE DRAG-AND-DROP
Extract the Source-Patch ZIP into the SOH_EXTREME-Extreme source root beside
build.cmd and replace the included files. Run build.cmd in a fresh Command
Prompt and wait for BUILD SUCCESS. Its CMake step patches and rebuilds APCpp.
Install the resulting 0.11.39 APWorld. The overlay is cumulative against Git
commit 9bc10e7191b546754a50da6463e074276d33862f; merge independent local edits.

BEHAVIOR
Enemy first-defeat AP pickups now show the native item model for rewards
belonging to SOH-EXTREME, whether for you or another SOH-EXTREME player.
Other games retain the AP logo, colored for progression/useful items and gray
for filler. Unknown/missing scout data uses a logo until it can be resolved.
An already spawned pickup updates when scout data arrives. Progressive items
use the normal native model resolver; Ice Traps retain their disguise and the
Mysterious Shuffle setting still conceals models.

This is a visual change to the physical enemy reward. It does not grant the
shown item locally or bypass Archipelago. Important-item hold-up delivery,
location identity, saved collection and server reporting remain in place.
An enemy pickup stays pending if its check cannot enter the send queue yet.

EXISTING SEEDS
This enemy-model fix works with existing seeds; no regeneration is needed.
APWorld .39 has the same item/location/logic data as .38, only a new version.
The package includes all earlier fixes. Earlier catalog changes still require
a new seed for their effects: adding the two Dodongo's Cavern doorway AP pot
rewards and removing the two Hyrule Castle courtyard window checks. Updating
the client does not relocate or add server-assigned rewards in an old seed.

VALIDATION
897 compiled assertions covering native mappings, same-game and foreign
recipients, colliding names/IDs, unknown data, late scouts, mailbox ownership,
spawn failure, deferred collection and single collection. Actual rebuilt
APCpp DLL parser/callback tests passed without a socket. Existing important
item presentation and delivery regressions passed, as did the Windows Release
build, 104-file APWorld/source parity, source patch and archive checks.
No rendered or connected in-game playthrough was performed.
See VALIDATION-ENEMY-MODEL-FIX.json and SOH_AP_FIX_HISTORY.txt.
