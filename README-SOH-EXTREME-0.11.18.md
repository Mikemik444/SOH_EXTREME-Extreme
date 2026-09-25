# SOH-EXTREME 0.11.18 — enemy room routes

Apply this incremental source patch over **0.11.17**. It is not a full game checkout.

## Install

1. Close the game, Archipelago and Universal Tracker.
2. Merge the included `soh` folder into your existing project root, for example
   `E:\test\bb`. Overwrite the included files; **do not delete your existing
   folders**. There are four complete native replacement/new files. No `src`
   or asset changes are required.
3. Rebuild with your working Command Prompt:

   ```bat
   cd /d E:\test\bb
   cmake --build build-vs --config Release --parallel 8
   ```

4. Replace `C:\ProgramData\Archipelago\custom_worlds\soh_extreme.apworld` with the
   included file. Keep exactly one installed SOH-EXTREME world. Install the same
   file wherever Universal Tracker runs, and restart the applications.
5. **Generate a new seed.** Existing placements were made using the old routes.
   No edits to your uploaded YAML are needed. Saved enemy receipt indices and
   network IDs have not changed, but this does not migrate old seed placements.

`source/soh_extreme/` is the complete matching AP-world source, provided for
reference/building. It is not an additional world to install beside the `.apworld`.

## Changes

- Replaces **all 413 enemy assignments that previously used a dungeon-entry
  parent**. In total, **535 existing dungeon enemy checks** now use explicit
  native room/floor assignments; the 218 other existing checks retain their
  previous overworld/grotto/hideout assignments.
- Exports **429 vanilla native regions** and their connections/events into an
  enemy-only AP route graph. Its connections are compiled from the C++
  `ENTRANCE` / `EVENT_ACCESS` expressions used by native reachability. Entry
  bindings are at the corresponding dungeon entrances, not at every enemy.
- Uses one room crosswalk for the AP location parents and native Check Finder
  table. An additional local-condition table handles encounter activation or
  obstacles inside a shared region, including the Shadow boat song, invisible
  encounters, fire-trial survival, and wrong-sun Wallmasters.
- Removes native Check Finder's previous whole-dungeon equipment/key shortcut.
  Parent reachability, local activation, soul and combat are evaluated in the
  same available age/time branch.
- Keeps early encounters before their rewards: the Bow-room Stalfos do not
  require the Bow, Jabu's Boomerang-room Stingers do not require Boomerang, the
  first Ice Cavern Freezards do not require later Blue Fire, and GTG's Wolves
  are before the heavy block. Earlier dungeon doors and puzzles still apply.
- Corrects the Dodongo room crosswalk: the first corridor, first slingshot
  room, lower/upper Lizalfos floors and boss maze are not interchangeable.
  The old room-number Slingshot/Grab overlay has been removed from those checks.
- Jabu's native water-switch crossing no longer uses adult age as a substitute
  for Swim. A supported Hover Boots crossing is separate from carrying Ruto
  through the water, which requires Swim.
- Compiles trial-dependent routes **after** randomized trials and authoritative
  UT slot settings are restored. Required trials block tower access; legitimately
  skipped trials do not add an invented Light Arrow requirement to tower enemies.
- Also corrects stale unconditional Climb requirements on castle trees/fairies,
  moat wonders and the upper waterfall wonder when Climb shuffle is disabled.
  Climb remains required when its shuffle is enabled.

## What did not change

No new network checks were added or removed. The active enemy catalogue remains
**753 checks**. Enemy/boss-created offspring remain excluded, and the 21 retired
Peahat-offspring IDs remain reserved. The finite scripted room-controller
encounters remain valid checks. The append-only native placement/receipt list,
spawn aliases, creator classification and MegaSouls runtime code are unchanged.

The build dependencies, assets, CMake configuration and your settings are unchanged.

## Scope

This is a tested **room-logic correction**, not a complete Windows/MSVC build or
physical playthrough. Source room assignments and simulated reachability do not
prove collision, all attack branches, irreversible quest states, pickup recovery
or every native helper is physically correct. The exported layout is the supplied
vanilla layout; this release does not implement a complete Master Quest or
entrance-randomized enemy catalogue. Existing unimplemented encounters are not
silently added.

Read `ENEMY_ROOM_COVERAGE.md` and `VALIDATION.md` for exact scope and results.
