SOH-EXTREME 1.8.10 - Complete replacement source files
====================================================

This single cumulative ZIP contains 175 complete replacement source files,
the matching soh_extreme.apworld, YAML and revision 4 clean-build helpers.
All previous 1.8.9 replacement source files are retained. 40 files changed
or were added since 1.8.9. Merge soh\, src\, archipelago\ and tools\ into your
existing complete checkout. These are complete files, with no patch to apply.

UPLOADED SEED 90569625277056890789: REGENERATION REQUIRED
------------------------------------------------------
The original 1.8.9 seed was exactly reproduced: all 4,036 item placements,
719 entrance connections and all 36 original progression sphere sizes match.
The audit also restored original item classifications and all 104 shop prices.

With those same placements/map under the corrected 1.8.10 access rules,
progression stops after 355/4,036 checks and 3/20 required Triforce Pieces.
The remaining 3,681 checks and the goal are inaccessible under these rules.
The dry Water Low Emblem Open Chest doorway and the first Swim/Scale pickup
remain reachable; the lock happens later, before access to Pot Soul.

The old solver admitted two flooded middle-floor Water Temple arrivals and
assumed water-control capability that this inventory had not established.
After the first Scale, those assumptions opened a route through Water's
upper exit, Death Mountain Trail and Spirit Temple's statue platform into
the GTG Lobby. That made the GTG Lobby -> Sand Room doorway's Pot Soul appear
reachable in the original sphere 11. The corrected rules reject the flooded
approach; they do not impose the destination's hazard on a source-door check.

Installing the client update cannot relocate the old server's placed items.
Generate a fresh seed using the enclosed APWorld.

WATER, AGE AND DOOR LOGIC
-------------------------
Reviewed flooded Water Temple room arrivals require usable Iron Boots.
Usable boots include the actual age requirement and Swim. Dry upper ledges,
the dry 3F Iron Boots pickup and proven dry-floor drops retain their routes.

A mixed doorway applies both its physical source rule and its landing hazard
to graph traversal. The source crossing check still uses its own physical
requirements: a later water recovery does not erase an already crossed check.

With room doors shuffled, reaching the real Low/Middle control action is
required to establish those levels. Middle cannot be played while submerged.
High retains the native capability proved at the actual High Emblem.
Vanilla aggregate paths can no longer bypass shuffled pillar doorways.
Legitimate local pillar swimming/floating routes remain represented.

Nine submerged enemy checks receive local water/combat requirements:
four GTG underwater Shell Blades and five Water Temple Shell Blades.
Dry doors and other checks in those rooms do not inherit an unrelated enemy's
underwater condition. GTG underwater checks include Song of Time, usable
Iron Boots/Hookshot and the required water timer.

GERUDO GUARDS AND VINES
-----------------------
Both Gerudo vine ascents require Climb or a usable Hookshot in AP, matching
the native rules. Child Link cannot substitute an unusable adult Hookshot.

Loaded Gerudo guards now apply a received membership card before their next
hostile sensing/capture action, including the first NPC Soul restored update.
Automatic capture cancellation only releases that guard's own message and
cutscene. KO/stuns, friendly roles and voluntary jail travel are preserved.

In the uploaded map the Zora's Domain exit lands directly above GTG. The two
screenshot door checks therefore do not imply a ground-patrol approach.
They do not get a blanket membership-card requirement. The absence of NPC
Soul does not grant permanent logical permission to cross guarded routes.

RICHARD'S DELIVERY ROUTE
------------------------
Market at night -> Back Alley -> Dog Lady's House stays connected.
The house entrance and return remain checks but are excluded from entrance
shuffle; the Market/Back Alley connection remains fixed as well.

Delivery requires child/night access, the configured Dog/Animal Soul,
NPC Soul and Hylian speech requirements, plus the house key/Skeleton Key
when locks are enabled. Native tests confirm Richard's identity survives
the normal delivery route and the correct turn-in grants the check.
An unrelated scene without the dog object can lose the follower, which is
why the local carrier route is preserved. Normal following distance applies.

ROOM RETURN AND DEATH
----------------------
Return to Previous Scene restores the immediate prior room's departure
point at the doorway. This includes two rooms within the same dungeon scene
and actual same-room transitions through different shuffled doorways.

Death with entrance shuffle active reloads the current room at its recorded
arrival checkpoint and preserves the previous-room destination. It does not
replace that destination with the death/reload. A -> B, death in B, return
still goes to the source doorway in A. Reloads and canceled room preloads are not
successful crossings.

The menu selection policy is preserved: Go to Dungeon Spawn remains the
manual action for ordinary dungeons and dungeon-only/unmixed pools.
Return to Previous Scene is used when room doors are mixed with an enabled
outside category. Return to Spawn still uses the seed's resolved age spawn.
Recovery/return reloads do not award extra transition checks or rerandomize
an already resolved destination.

PREVIOUS FEATURES RETAINED
--------------------------
Coupled entrances, overworld options, enabled-only mixed All, random child
and adult spawns, experimental entrance labels, dungeon-only pool partitions,
individual-song note selection, descriptive Finder names, scene grouping and
dropdown behavior, optional room/door numbers, paged hints and AP progression
hint sharing remain included. Earlier invisible NPC/object, Lost Woods Mido,
Jabu tentacle/carried-Ruto, trial-medallion and scene-switch fixes are retained.

INSTALL AND BUILD
-----------------
1. Close the game. Merge this ZIP's root folders into the complete checkout,
   replacing the corresponding files. Put BUILD_RELEASE.cmd/.ps1 and
   SOURCE_FILES.json in that checkout's root as well.
2. From Command Prompt run:

   cd /d E:\test\bb
   BUILD_RELEASE.cmd -RepositoryPath "E:\test\bb" -BuildDirectory "build-vs"

   Use your actual checkout/build paths if different. The helper verifies
   every replacement source and performs:
   cmake --build build-vs --config Release --parallel 8 --clean-first
   Launch the executable whose path the helper prints.
3. Install the enclosed soh_extreme.apworld into:
   C:\ProgramData\Archipelago\custom_worlds\soh_extreme.apworld
   Update the generator and tracker installations if they are separate,
   then restart them. Generator, tracker and native client must be 1.8.10.
4. Generate a fresh seed. The original YAML setting values/weights are kept;
   the bundled YAML includes the explicit song_note_songs: [all] selector.

VALIDATION AND LIMITS
---------------------
Fresh child seed 181001 and adult seed 181002 both passed complete official
Archipelago 0.6.8 generation, the goal and 4,036/4,036 checks under current rules.
These are generation regression results, not new playable seed output files.
The official APWorld ZIP loader verified all 120 package files and all release
version markers. Current native/AP test reports and source hashes are included
under validation/. See VALIDATION.txt for the executed suite counts and scope.

This environment cannot build the complete Windows game from the partial
uploaded checkout. Native tests compile production function bodies with
documented engine I/O shims. Full scene collision/actor assets, a live game
playthrough and visual confirmation of doorway positioning are not available.
