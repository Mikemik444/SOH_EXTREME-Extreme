SOH-EXTREME 1.8.8 - Complete replacement source files
====================================================

This cumulative ZIP contains 136 complete replacement source files and the
matching soh_extreme.apworld. All prior 1.8.7 replacement files are retained.
Merge it into your existing full checkout. The directories are at the ZIP
root: soh\, src\, archipelago\ and tools\.

JABU'S LIVE TENTACLE BARRIERS
---------------------------
The uploaded spoiler was reproduced using official Archipelago 0.6.8 and the
previous 1.8.7 APWorld: all 4,036 network item placements matched. Its internal
generation seed is 75502037396837836795; the filename contains another number.

In that map, the Temple of Time courtyard gossip-stone exit sends Link to the
northwest Jabu doorway beside the live tentacle. The old graph treated
TakeDamage as proof that Link could escape into the central corridor, exposing
the route to Open Chest on the lower-ledge/water-switch door. Surviving damage
does not prove that this arrival can pass the physical barrier.

All three vanilla To Fork -> Forked Corridor routes now require the matching
permanent tentacle-clear event. North West and North East require West;
North requires East. The generic damage escape is removed in both native
room logic and the AP graph. Legitimate direct arrivals into other rooms keep
their own local requirements. This does not apply a blanket adult Jabu ban.

Defeating a tentacle still requires its Soul and an age-usable Boomerang.
Merely owning a child-only item does not make adult combat possible.
The north room's return also now requires clearing all four Biri, whose
Soul is separate from the tentacle Soul. Killing the tentacle still records
its own permanent switch immediately; it does not falsely clear the room.

TRIAL MEDALLIONS
---------------
The physical source doorway keeps its requirements after shuffling, including
when scene-transition checks are disabled. Forest, Fire, Light and Spirit
trial returns require their own medallions when Medallion Locked Trials is on.
The reported Spirit Beamos Room -> Main check therefore requires the Spirit
Medallion even when its destination is Water Temple's Boss Key Room.

Water and Shadow returns preserve the actual native alternatives. Water
permits its Water Medallion or clearing the two Freezards. Shadow permits
its Shadow Medallion or clearing the Green Bubble and Like Like with access
to their actual platforms. Required Souls, usable combat and age rules still
apply to those clear actions. Forward medallion gates are retained.

Items already physically reachable through an alternate room arrival retain
their local collection requirements. A legacy whole-trial item overlay no
longer reattaches the original entrance medallion to exact ER collection routes.

SWITCHES AND SHORTCUTS
---------------------
Water Temple's 3 Jets No Switch -> Canal Alcove exit now needs access to the
actual switch side as the age using the door. Arriving at the far side no
longer treats the timed shutter as free. Walking over from the switch side,
or using a valid local return method to reach it, remains supported.

The age search now retries a blocked dependent exit when its required region
becomes reachable later in the search. A temporary switch is not converted
into a permanently collected AP event.

Native validation covers all 24 catalog temporary-switch shutters in both
directions, source/destination scene flags, ordinary room cleanup, respawn
flags, timers and existing recorded-switch replay. Permanent scene state
remains scoped to its physical scene. Existing authored recorded actions are
retained; arbitrary flags are not granted or copied into another dungeon.

The overworld pool includes Lost Woods <-> Goron City, Lost Woods <-> Zora's
River, and Lake Hylia <-> Zora's Domain. Internal Fire, Shadow and Spirit
shortcuts retain their physical switch/item/age logic. Crawlholes, open room
passages and movement within a room remain traversal paths; they are not
separate shuffled door endpoints. There is no dungeon/boss-shortcut setting
in the supplied fork or YAML.

CUMULATIVE FEATURES
-------------------
Paired entrances and returns; optional overworld entrances; mixed pool all
meaning every enabled pool; randomized child/adult spawns and save-to-spawn;
reviewed playable destinations and age restrictions; descriptive Finder/AP
names; optional room/door numbers; singleton header suppression; automatic
zone dropdowns with manual choices; A-to-continue hints; progression-item AP
hints and in-game Way of the Hero/barren hints; tracker continuity; solid
soul-gated objects and interactable path-blocking NPCs; Lost Woods access
corrections. All entrance-randomizer settings remain Experimental.

INSTALL AND BUILD
-----------------
1. Close the game and finish any active build.
2. Extract this ZIP directly into E:\test\bb\, merging its directories and
   replacing the included files. Keep the rest of your full checkout,
   including CMakeLists.txt and your configured build-vs directory.
3. From E:\test\bb, run:
     BUILD_RELEASE.cmd -RepositoryPath "E:\test\bb" -BuildDirectory "build-vs"
   The helper must report version 1.8.8 and revision 4. It verifies all
   136 delivered source files, then performs the configured clean build:
     cmake --build build-vs --config Release --parallel 8 --clean-first
   Wait for success and launch the exact Game executable path it prints.
4. Install the top-level soh_extreme.apworld at:
     C:\ProgramData\Archipelago\custom_worlds\soh_extreme.apworld
   Update both generation and tracker installations if they are separate,
   then restart them. Both APWorld copies in this ZIP are identical.
5. Generate a fresh seed and create its matching AP save/server slot.
   The supplied SOH-EXTREME.yaml is your unchanged YAML. Correcting rules
   cannot relocate progression items in a previously generated server.
6. Confirm version 1.8.8 under Network -> Archipelago, then verify the
   entrance-map status and displayed child/adult spawn destinations.

VALIDATION
----------
The reported old seed was reproduced with 4,036/4,036 matching placements.
The new source passed 13 medallion AP test methods, 22 focused Jabu/switch/
shortcut tests, 40 retained start/pool/restore tests, and the retained
Jabu carried-Ruto suite. Native ASan/UBSan fixtures passed 1,152 directional
medallion cases plus 4 registration/unrelated-actor cases and 382 scene-flag
lifecycle cases. Reports distinguish executed tests from source-only review.

Both complete official AP 0.6.8 fills reached all 4,036 network checks and
the goal. The child-start run used seed 18801; the adult-start run
used the reported seed number 75502037396837836795 with corrected source.
Initial child: 62 network / 60 physical checks.
Initial adult: 31 network / 29 physical checks.
Both had initial Hyrule Field access. Final hints preserved item placements
and RNG state and retained item, Way of the Hero and barren hints.

The full Windows game could not be built or played from the supplied partial
source snapshot. Native fixtures isolate engine I/O, and extracted ROM
collision assets were unavailable. These results are not a proof of every
seed or every physical path. Rebuild your full checkout for live validation.
See VALIDATION.txt and validation\ for the exact evidence and limits.
