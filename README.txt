SOH-EXTREME 1.8.9 - Complete replacement source files
====================================================

This cumulative ZIP contains 159 complete replacement source files and the
matching soh_extreme.apworld. All previous 1.8.8 replacement files are retained.
Merge the root directories soh\, src\, archipelago\ and tools\ into your
existing complete checkout. 65 files changed or were added since 1.8.8.

INVISIBLE NPCS AND OBJECT COLLISION
----------------------------------
NPCs without NPC Soul cannot talk, auto-talk, exchange or give items, be
carried, be targeted, or accept the Lost Woods Mido ocarina interaction.
Two precise placements retain hidden blocking movement and solid collision:
  - The Kokiri Forest exit boy (En_Ko, type 3, in Kokiri Forest).
  - Adult Mido in Lost Woods, where he blocks the route to the meadow.
Mido in Kokiri Forest and all other missing-soul NPC placements are non-solid.
Acquiring the appropriate Soul restores the existing actors' normal behavior.

Missing Crate Soul: small and large crates are invisible and non-solid.
Missing Rock / Boulder Soul: regular small rocks are invisible and non-solid.
Large silver rocks, brown/bronze boulders, and ceiling boulders stay solid.
All missing-soul crates, rocks and boulders remain unusable and unbreakable.

When NPC Soul is shuffled, AP and Finder require it for every conversation,
including path blockers. Adult Mido's ordinary Lost Woods passage requires
usable Saria's Song in both directions, plus NPC Soul and Kokiri speech when
their respective shuffle options are enabled. Child passage and the existing
enabled backflip alternative keep
their original requirements. Other temporary passages opened by absent NPCs
remain conservatively out of logic where receiving Soul could close them.

DUNGEON POOLS AND RETURN ACTIONS
-------------------------------
Unmixed dungeon room doors shuffle within each individual dungeon. This also
covers forward-only dungeon shutters. Normal two-way doors retain a paired
return, and the six Jabu carried-Ruto door pairs retain native connections.

Go to Dungeon Spawn returns to the physical dungeon entrance. This is the
default dungeon action with no entrance shuffle, separate dungeon/room-door
shuffle, separate boss shuffle, or a mixed pool containing only dungeon
categories. A shuffled boss uses the dungeon from which Link entered it.
The resolved dungeon entrance is not shuffled a second time.

Return to Previous Scene is used when enabled dungeon_doors is in the actual
mixed pool with an enabled outside category. All includes enabled categories
only. Mixing unrelated pools, listing a disabled category, or selecting only
dungeon_doors does not activate this mode. Dungeon categories are dungeons,
bosses and dungeon_doors; the remaining categories count as outside.

Previous Scene restores the last distinct playable scene and its recorded
entry context. Same-scene room changes do not overwrite that scene history.
It does not copy temporary switches between scenes. A fresh randomized spawn
with no prior scene offers Continue and Return to Spawn until history exists.
Game-over follows the available dungeon/history return with safe spawn fallback.

Return to Spawn remains a separate action using the seed's assigned spawn for
the chosen age. It clears a queued scene return. Same-save reloads retain the
entrance map and tracker context; changing save, age or map invalidates unsafe
pending returns. Reconnecting does not reroll saved entrance mappings.

SELECT WHICH SONGS USE INDIVIDUAL NOTES
--------------------------------------
The new Song Note Songs option chooses which songs become Progressive items.
Unselected songs remain complete songs and follow Shuffle Songs: anywhere,
song locations, dungeon rewards, or their vanilla locations when off.

The included SOH-EXTREME.yaml preserves every original setting value and weight
and adds the following default, which keeps the previous all-song behavior:

  song_note_shuffle: individual_notes
  song_note_songs:
    - all

To split only two songs, replace the song_note_songs list with:

  song_note_songs:
    - zeldas_lullaby
    - bolero_of_fire

Accepted song keys:
  zeldas_lullaby       eponas_song          sarias_song
  suns_song           song_of_time        song_of_storms
  minuet_of_forest     bolero_of_fire      serenade_of_water
  requiem_of_spirit    nocturne_of_shadow  prelude_of_light

Full names such as Zelda's Lullaby also work. All overrides other listed songs.
An empty list splits none. With Song Note Shuffle off, the list is ignored.
Most songs need 6 copies; Bolero needs 8, Serenade 5, and Nocturne 7.
All uses the existing 74 copies and existing item/save identities. The native
tracker shows only selected songs in the note-progress section and sums their
required copies. Starting with a selected song grants its complete note group;
starting with an unselected song grants its ordinary whole-song item. Ocarina
and shuffled button requirements still apply. Older saved note seeds default
to all when they do not contain the new selection field.
New seeds convert numbered legacy notes in selected starting-song requests
to matching Progressive copies. Selected-song plando must also use Progressive
copies; overlapping numbered and progressive receipts are rejected. Existing
UT saves retain their original receipt identities.

CUMULATIVE FEATURES RETAINED
---------------------------
Paired entrance returns, overworld shuffle, all-enabled mixed pools, assigned
child/adult spawns, reviewed age-safe destinations, trial medallion and Jabu
tentacle barriers, room-switch logic, Finder names/collapse preferences,
paged hints, AP progressive item hints, Way of the Hero/barren hints, and
tracker continuity remain included. Entrance randomizer settings remain
Experimental. The current NPC/collision rules above replace earlier behavior.

INSTALL AND BUILD
-----------------
1. Close the game and finish any active build.
2. Extract into E:\test\bb\, merging directories and replacing included files.
   Keep your full checkout, root CMakeLists.txt and configured build-vs folder.
3. From E:\test\bb, run:
     BUILD_RELEASE.cmd -RepositoryPath "E:\test\bb" -BuildDirectory "build-vs"
   The helper reports version 1.8.9, revision 4, and verifies all 159 source
   files before the configured clean build:
     cmake --build build-vs --config Release --parallel 8 --clean-first
   Wait for success, then launch the exact executable path printed by the helper.
4. Install the top-level soh_extreme.apworld at:
     C:\ProgramData\Archipelago\custom_worlds\soh_extreme.apworld
   Update generation and tracker installations if separate, then restart them.
5. Generate a fresh seed and create its matching AP save/server slot. Updated
   source cannot relocate progression in an already generated server.
6. Confirm version 1.8.9 under Network -> Archipelago and inspect the applied
   entrance map plus child/adult spawn destinations.

VALIDATION AND PRACTICAL LIMITS
-------------------------------
Current reports include actual AP pools/prefill/song rules, NPC interaction
rules, both Mido directions, room/trial/Jabu regressions, native actor and
collision functions, native save/scene return routing, song receipt/tracker
functions, the built APWorld loader, and the shipped build helper preflight.

Two complete official Archipelago 0.6.8 fills reached every network check and
the goal: the original all-song configuration as adult, and a clearly labeled
child variant selecting Zelda's Lullaby and Bolero only. Both retained initial
physical checks and Hyrule Field access. Final hints did not change placements
or RNG state. Exact seeds, counts, source hashes, and report scopes are in
VALIDATION.txt and validation\souls_restart_189_release_validation.json.

The supplied source snapshot is incomplete for a full Windows game build or
playthrough. Native fixtures isolate engine I/O and lack extracted ROM
collision assets. Rebuild the complete checkout for in-game verification.
The passing fills validate these seeds under the AP model, not every possible
seed or physical route. Reports under previous_1.8.8 are historical evidence.
