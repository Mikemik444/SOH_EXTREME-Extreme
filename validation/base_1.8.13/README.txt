SOH-EXTREME 1.8.13 - Complete replacement source files
=====================================================

This is a cumulative source delivery. It includes the prior 1.8.12 ammo,
grotto-landing, river-path, Check Finder, hint, Soul and dungeon-return changes.
Merge the supplied complete files into your existing full checkout.

CASTLE COURTYARD ACCESS
----------------------
The castle drain, guard maze and Zelda-side courtyard now have distinct logic
regions. Entering the guard maze no longer makes the far-side Zelda exit appear
reachable. The four existing directed scene-transition check IDs are retained
and inherit the appropriate source-side traversal rules.

The guard route requires child access and the actual patrol window. The native
guards begin blocking at clock 0xB889, before the engine's normal night phase;
the passable window is 0x4555 <= clock < 0xB889 while the day phase is active.
Frozen-time logic and tracker cache invalidation use that same boundary.
The normal Flow of Time and usable Sun's Song routes can still establish access
to the appropriate time, subject to their existing requirements.

After the Zelda visit is completed or skipped, the guards retain their normal
patrol access while an active courtyard transition check remains outstanding.
This preserves the route needed to finish the visit's checks. The existing
wonder-check preservation behavior is retained for older seeds.
Guard variants also respond when the server's active-check list arrives after
scene initialization. The update reuses the original actors without a scene
reload, repeated rupee spawns, or resetting a running alert/caught sequence.
Completing the checks does not close the path in the middle of the visit.

WARP-SONG TRANSITION CHECKS
--------------------------
The six existing warp-song checks keep their original IDs. Song travel now
records its actual source song and awards that song's check after a successful
arrival. Native song travel uses a special respawn flag that the old generic
scene matcher rejected. The corrected path distinguishes a real song departure
from an unrelated load at the same destination entrance.

Normal animations, skipped animations, the actor-allocation fallback and direct
pause-menu song travel are covered by focused regressions. This includes all
six songs, both ages and same-scene arrivals. Randomized warps retain the
original song's check identity for ordinary, grotto and room destinations.
Cancelled travel, death/save returns, inactive locations and repeated arrivals
do not create a new song check. The scene-transition setting and the seed's
active check list still determine whether a song transition is a check.

DAMPÉ'S HUT: ADULT ONLY
-----------------------
The exterior hut doorway is adult-only in AP gameplay, including the old child
evening opening. Owning the hut key does not grant child access. Adults still
need the key when the configured overworld-door setting requires it.

The AP ingress rule and randomized arrival policy match that restriction.
New child routes and spawns cannot use the hut as a destination. The reverse
hut exit remains usable for a character already inside, including an existing
child save or legacy arrival, so the correction does not trap them there.

EXISTING SEEDS
---------------
Install both the native source update and the matching APWorld. The current
courtyard and song check IDs are unchanged; the native fixes can apply to the
corresponding existing checks without changing their item assignments.

The adult-only hut rule changes reachability. The older supplied 719-route map
has entrance 1190 (GF Top of Lower Vines Near) leading to hut arrival 781. That
source is child reachable under the production rules, so the exact unchanged
map is rejected by corrected AP age validation and requires a new seed. Other
old maps with a child-reachable hut arrival can have the same incompatibility.
No saved entrance targets are silently rerolled. Even when a map loads, an old
item placement has not been revalidated as a complete 1.8.13 seed merely
because the tracker now uses the corrected rules.

Independent Zora's River land/water shuffling still requires a seed generated
with the revised river catalog. Last-unit ammo protection remains automatic
and needs no new YAML option. The current YAML is retained from 1.8.12.

INSTALL AND BUILD
-----------------
1. Merge soh, src, archipelago and tools into your complete checkout, replacing
   the corresponding files. Copy SOURCE_FILES.json, BUILD_RELEASE.cmd and
   BUILD_RELEASE.ps1 into the checkout root as well.
2. For E:\test\bb, run in Command Prompt:

   cd /d E:\test\bb
   BUILD_RELEASE.cmd -RepositoryPath "E:\test\bb" -BuildDirectory "build-vs"

   The helper verifies the replacement source files and performs a clean
   Release build. Run the executable path printed by the successful build.
3. Install the root soh_extreme.apworld at:
   C:\ProgramData\Archipelago\custom_worlds\soh_extreme.apworld
   Restart the Archipelago client/generator to load the updated world.

VALIDATION
-----------
Passed: 8 AP tests / 542 evaluated decisions; 14,084 native guard/door
assertions; 19 native age-policy assertions; 995 warp cases / 7,166 assertions;
938 shared room-return cases; 97 protocol vectors, 145 native worker cases and
49 Python handler cases. Destination-policy generation passed 17 cases covering
721 endpoints and 2,884 native age/time layers. The official AP 0.6.8 loader verified
the current 1.8.13 APWorld, and the PowerShell source preflight verified all
253 complete replacement source files. See VALIDATION.txt for scope.

The detailed current reports, source/test hashes, native fixture inputs and
replay instructions are in validation/transition_fixes_1813. Earlier reports
remain unchanged under validation as historical evidence. Use the current
APWorld at the ZIP root for installation, not older historical copies.

A complete Windows game build, controller playthrough and full new 1.8.13
item fill were not performed here. Native tests
compile production function bodies with explicit engine I/O shims. The AP
tests evaluate actual rules and topology with controlled state and ingress.
