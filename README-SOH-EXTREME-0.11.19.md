# SOH-EXTREME 0.11.19 — tracker result mirror and reported route corrections

Apply over 0.11.18. This archive contains 11 complete native replacement/new files,
the ready-to-install soh_extreme.apworld, and the complete AP source bundle.
No src files, game assets, enemy IDs, or enemy receipt slots are changed.

## Installation

1. Merge the included soh folder into E:\test\bb and overwrite the supplied files.
   Do not delete the existing soh or src directories. In your working Command Prompt:

   ```bat
   cd /d E:\test\bb
   cmake --build build-vs --config Release --parallel 8
   ```

2. Close Archipelago Launcher and all tracker instances. Replace:

   ```text
   C:\ProgramData\Archipelago\custom_worlds\soh_extreme.apworld
   ```

   Keep exactly one installed SOH-EXTREME world. Keep your existing tracker.apworld
   installed too: the new component uses Universal Tracker, it does not replace it.
   Restart Archipelago Launcher.

3. Launch **SOH-EXTREME Universal Tracker**, the new Launcher entry provided by this
   world. Connect it and the game to the same AP slot. Keep this tracker open.
   Use Check Finder / available-check tracking in the game (EnableAvailableChecks
   or OnlyShowAvailable). Its AP availability view now displays the tracker result.

   The generic **Universal Tracker** entry does not publish the mirror. You must use
   the SOH-EXTREME entry for this view. It is a subclass of the installed UT client,
   with the upstream evaluator and normal UT window, not an independent rules engine.
   Close extra tracker instances for this slot.

4. Generate a NEW SEED for the corrected Sheik, mountain, and silver-location
   placement rules. The uploaded YAML settings do not need changing. No asset
   regeneration is needed. Existing IDs are unchanged, but an old seed may already
   have placed progression behind a route that was incorrectly considered open.

## Tracker matching: what changed

The prior C++ Check Finder and the AP/Universal Tracker graph were separate
calculations. Reconstructing the AP graph did not verify C++ parity.

For an AP save with available-check tracking enabled, the game now requests a
read-only snapshot of the paired UT client's actual updateTracker result. The
snapshot contains active IDs, checked IDs, received-item count, and the exact
normal/glitched location IDs and labels returned by UT. The new UI renders these
rows directly. It does not AND or OR them with the older native answer, infer
locations from item names, or substitute another graph if UT is unavailable.

The transport checks slot, per-save/per-connection nonce, protocol version,
request/revision ordering, producer, active/checked ID sets, and receipt count.
A snapshot expires after 10 seconds; requests are sent about every 2 seconds while
the view is open. Missing, stale, or inconsistent data shows a waiting/sync message
instead of a guessed list. Normal and glitched results remain distinct.

The mirror follows UT's AP receipt inventory, including any manually added UT items
and ignored locations. The game shows an override notice, and warns when AP has
received more items than this save has finished applying. UT manual items do not
grant items to the game. Game debug-inventory edits do not become AP receipts.

Ordinary standalone randomizer tracking is unchanged. The ordinary check-history
view is still used when available-check tracking is off. This read-only feature
does not change pickups, server check reports, item delivery, DeathLink, or TrapLink.
A deliberate disable of the entire AP integration leaves AP mode; this patch does
not implement an independent offline copy of the UT engine.

## Reproduced and corrected logic

### Sheik

All six Sheik song-reward locations in 0.11.18 remained reachable without NPC Soul
or Speak Hylian in the test inventory. The AP rules now require NPC availability
and the configured Hylian speech capability as well as each location's existing
age, region and quest prerequisites. Combined speech mode uses Speak; disabled
shuffles retain innate capabilities. Native conditions are corrected too, including
both Ice Cavern layout definitions (seven native occurrences for six checks).

### Death Mountain / crater

The AP Trail-to-Summit edge used BlastOrSmash, allowing Bombchus to bypass missing
Rock / Boulder Soul. The corrected edge uses the native rock interaction, climbing,
and rockfall-safety requirements, preserving the specific supported adult routes.
The global BlastOrSmash helper is NOT changed: it is also used by non-rock walls.

The Goron unlock EVENT now requires NPC Soul and Goron speech, not just the reward
location. The Darunia-to-crater route also keeps Grab for moving the block. Bolero
is a separate valid route and does not need unrelated Goron or rock items: it needs
the complete song/note group, Ocarina and required buttons.

The same fresh physical inventory, with Bombchus present but all three approaches
incomplete, reached four summit/crater regions under 0.11.18 and reaches none under
0.11.19. Starting from fresh physical items is important: removing a virtual song
while retaining all its notes is not a valid missing-song test.

### Silver rupees

All 80 existing silver checks now use room-specific route proxies. Each native
alternative stays coupled as (reachable room AND local method). All routes use
native room conditions and the compiler introduced with 0.11.18. Missing mappings
raise errors; there is no dungeon-entry or Menu fallback. No network checks or IDs
are added.

The Shadow front torch door was already gated in 0.11.18 for the tested settings.
It is tested again: without usable Din's Fire the normal approach stays closed,
and a Fire Arrow alternative requires the corresponding enabled trick and usable
weapon. The recent unidentified door screenshot was unavailable for inspection;
this report does not claim to identify or physically test that particular door.

## Scope and remaining verification

Read VALIDATION.md for exact test scope and commands. This is not a certification
of every physical check. No complete Windows/MSVC game build, in-game playthrough,
live Universal Tracker GUI session, or live AP server/Bounce session was performed.
The new launcher wrapper is tested with a controlled UT host and verified against
upstream interfaces; end-to-end installed-UT/network behavior still needs runtime
verification. The C++ tests compile the production parser, client/view functions,
and native conditions with controlled engine/UI/network services.

Using one evaluated result prevents the two AP availability displays from running
contradictory solvers. It does not make any remaining incorrect AP route physically
correct. Master Quest coverage, quest-state/lifecycle edge cases, and broader
physical checks are not claimed complete by this patch. The 0.11.18 enemy-room
assignments and the no-enemy-offspring rule are retained, not newly re-certified.
