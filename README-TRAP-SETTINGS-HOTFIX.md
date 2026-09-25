# SOH-EXTREME 0.11.21b — Additional Traps preferences hotfix

Apply over 0.11.21a (the APCpp crash hotfix). This is a native source hotfix,
not a new AP-world version. Keep soh_extreme.apworld 0.11.21 and tracker.apworld.

## Fixed

ArchipelagoClient::ApplySlotSettings previously overwrote all 13 persistent
`gEnhancements.ExtraTraps.*` configuration values every time AP settings were
applied. It then requested that console variables be saved. When the AP
`ExtremeTrapPool` value was Off, the local Additional Traps master toggle was
written to zero and the menu hid its child controls. Shock, Knockback, Bomb,
Void, Ammo, Kill and Teleport were always written to zero by this AP path.
That affected save creation, save loading and reconnect/settings reapplication.
The global changes also affected subsequent normal saves.

This hotfix removes those writes. Local Additional Traps preferences stay in
exactly the same configuration keys used by the existing menu. The master
toggle, selected trap variants, and Simple/Advanced Teleport mode are not
replaced by AP settings anymore.

AP trap effects continue to use the AP seed's authoritative options, read from
the live randomizer Context instead of by modifying the enhancement preferences.
The menu displays two AP-only explanatory lines. It still lets you edit the
saved local preferences, which are used for non-AP saves. This patch does not
make local trap selections override an AP seed.

The effects supported by the existing AP policy remain:

- Off: do not remix received Ice Traps; apply the ordinary freeze effect.
- Ice Only: freeze.
- Expanded: select only the seed's enabled Ice, Fire, Slow, Magic Suck and Health
  Drain variants. If no variant is enabled, retain the existing freeze fallback.

`extreme_trap_pool` is distinct from the standard Ice Trap item count/filler
replacement options: Off does not remove Ice Trap items already in a seed.
No AP pool, receipt, item, location, save format or connection protocol changes
are made by this hotfix.

Delayed effect updates no longer depend on the local master toggle. AP slowdown
can finish even if the local toggle is off, and disabling the local toggle while
already slowed no longer strands the multiplier. Save-load/exit hooks clear
only transient effect timers; they do not delete queued Ice Traps or saved
preferences.

## Install

1. Close the game. Merge the `soh` folder from this ZIP into `E:\test\bb`,
   overwriting the three supplied files. Do not delete your existing folders.
2. In the working Command Prompt, run:

```bat
cd /d E:\test\bb
cmake --build build-vs --config Release --parallel 8
```

3. Start the newly rebuilt executable. If you normally play from a copied
   runtime folder such as `x64\Release2`, deploy the new executable there using
   your existing copy/deployment procedure; do not run the old copy.
4. If an older build already saved the erased configuration, enable Additional
   Traps and select your preferred variants/Teleport mode once after installing.
   The old choices cannot be reconstructed from values already overwritten on
   disk. Do not delete your configuration or save files.

No new seed, YAML changes, AP-world replacement, asset regeneration, or new
APCpp dependency/DLL change is needed for this hotfix. Keep the previously
installed 0.11.21a APCpp safety repair in place.

## Complete replacement source files

- `soh/Network/Archipelago/ArchipelagoClient.cpp`
- `soh/Enhancements/ExtraTraps.cpp`
- `soh/SohGui/SohMenuEnhancements.cpp`

The client replacement includes the previous 0.11.21a startup-order correction;
this increment changes only the trap-preference overwrite block in that file.
Bombchu pool/refill behavior, soul portraits, automatic tracker startup, and
region grouping are otherwise untouched.

## Validation

See VALIDATION.md and validation/results/. No complete Windows/MSVC game build
or in-game menu test was performed here.
