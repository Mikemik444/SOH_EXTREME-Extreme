# SOH-EXTREME 0.11.21d hotfix

Apply this over **0.11.21c**.

This hotfix addresses two issues reported during live testing:

1. **Enemy Soul held/get-item visuals**
   - The enemy-specific soul texture resource name was being passed directly to `gDPLoadTextureBlock` as though it were decoded RGBA data.
   - That produced the large garbled/grass-like square above Link's head.
   - `EnemySoulDraw.cpp` now resolves the OTR texture resource with `ResourceMgr_LoadTexOrDListByName()` before sending the actual RGBA32 bytes to Fast3D.
   - The same fix applies to the enemy-soul world/get-item draw path. The existing 47 textures do not need to be rebuilt.

2. **Residential indoor pot logic**
   - Generic pot logic allowed Bombs/Bombchus to count even in house interiors where explosives cannot be used.
   - The native rules and AP/Universal Tracker rules now require a *usable indoor* method for these pots.
   - Affected families: Link's House, House of Twins, Know-It-All House, Market Guard House, Market Back Alley House, and Talon's House.
   - Pot Soul is still required whenever Pot Soul shuffle is enabled.
   - Valid non-explosive methods remain: Grab/lift, sword/stick/hammer jumpslash, Giant's Knife, Boomerang, Hookshot/Longshot, Slingshot, or Bow when usable by the current age/inventory.

The AP manifest/tracker protocol remains **0.11.21**. `0.11.21d` is the native/AP logic hotfix revision, so the existing automatic tracker handshake remains compatible.

## Install

1. Close Ship of Harkinian and Archipelago/Universal Tracker.
2. Extract this ZIP directly into your `E:\test\bb` folder and overwrite the included file.
3. Run:

   ```bat
   cd /d E:\test\bb
   APPLY-0.11.21d.cmd
   cmake --build build-vs --config Release --parallel 8
   ```

4. Replace the installed AP world with the included `soh_extreme.apworld`:

   `C:\ProgramData\Archipelago\custom_worlds\soh_extreme.apworld`

5. Restart the game/Archipelago.

The source patcher makes `.pre-0.11.21d.bak` backups of the three location-access files it changes. It refuses to modify them if the expected house-pot source layout does not match.

## Seed note

The held soul visual fix and Check Finder/UT reachability correction work without generating a new seed. For placement guarantees, generate a new seed: an older seed may already have placed progression based on the old overly-permissive house-pot rule.

## Validation performed

- Python syntax compilation of the packaged AP world.
- 66 native residential pot rules identified and transformation-tested: 5 Kokiri house pots, 58 Market house pots, and 3 Talon house pots.
- AP final-rule branch statically verified to exclude Bomb/Bombchu routes for the same residential families.
- Enemy Soul draw source verified to resolve the OTR resource token to decoded texture data before `gDPLoadTextureBlock`.

A complete Windows/MSVC build and live in-game visual test were not performed here.
