SOH-EXTREME 1.6.0 - generation state-isolation hotfix (2026-10-09)

Install
Close Archipelago Generator and any automatic tracker worker. Replace
Archipelago/custom_worlds/soh_extreme.apworld with the included file of that exact
name, then reopen Archipelago and generate again. Keep only one installed copy
of SOH-EXTREME. The regular oot_soh.apworld may stay installed.
No YAML changes, new game executable, or version bump are required for this fix.
For the in-game tracker, restart AP Tracker after installing the APWorld.
Existing successfully generated seeds and saves do not need regeneration.
The previous client update is still needed to remove its old version display gate.

Cause and fix
Archipelago loads both installed world packages, even for a solo EXTREME seed.
The regular SoH world overwrote shared age/reachability and health dictionaries
after EXTREME initialized them. This raised KeyError: 1 during event/plando sweeps.
EXTREME now owns separate fields throughout its region, location, enemy, item
and health logic. Both packages can coexist regardless of hook registration order.
Rules, item/location IDs, saved slot data and tracker wire format are unchanged.
Both public release labels remain 1.6.0.

Source update
Copy the source ZIP's matching directories/files into your source checkout.
It includes the complete canonical archipelago tree, the cumulative 1.6.0
About/Check Finder source changes, and updated/new regression tests.
Run tools/build_standalone_apworld.ps1 -SkipInstall to rebuild the APWorld.
No GitHub push or installed-APWorld replacement was performed automatically.

Validation
Reproduced KeyError: 1 using the user's installed stock and EXTREME APWorlds.
Fixed archive: 36 assertions using the real stock/EXTREME state hooks, both
registration orders, the reported plando-sweep entry point, copied reachability,
and a room containing one slot from each game with independent health changes.
680 AP/Universal Tracker child/adult and day/night Peahat assertions passed.
A full 3311-check seed generated, filled, met its goal and replayed every check
under the current logic. These checks use the AP 0.6.7 source core; they do not
claim live gameplay or prove every possible seed/configuration.
Archive/source parity and package integrity were verified.
