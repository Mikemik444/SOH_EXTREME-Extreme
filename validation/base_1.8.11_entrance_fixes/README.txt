SOH-EXTREME 1.8.11 - Complete source files, entrance fixes
=========================================================

YELLOW AND CYAN ENTRANCE LABELS
------------------------------
A physical doorway now gets one yellow label, including double doors. If that
doorway also owns a scene-exit trigger, its overlapping cyan label is suppressed
while the yellow label is visible. Independent exits keep their cyan labels,
including separate exits that share a destination. Invisible or distant door
actors leave the scene-exit fallback available. Existing descriptive names and
destination room numbers are retained.

CHECK FINDER AUTOMATIC EXPANSION
-------------------------------
The current physical scene opens automatically until you explicitly choose its
dropdown state. Untouched sections collapse again when you leave. A deliberate
open or close remains your choice. The current area is determined from the live
scene identity, independent of the tracker worker's inventory-refresh timing.
Day/night/adult variants of the same area match the same Finder section. Shared
interiors use their physical spawn identity, and the Dampe's Grave-to-Windmill
passage follows Link's current room instead of the original entrance. Manual
scene choices remain stable when the region grouping or visible check counts change.

BOMBABLE GROTTOS AND RANDOMIZED SPAWN
-----------------------------------
The hidden hole's native opening rule now requires usable explosives or Hammer,
matching the existing Archipelago rule. Grab / Power Bracelet alone cannot open
it. Existing Shovel, Rock / Boulder Soul and Stone of Agony logic policy and
separate source-specific blockers are retained; this is not a change to which
physical obstacles are governed by Souls.

Opening the hole from outside and arriving inside are separate routes. A grotto
used as the randomized spawn can have reachable checks without explosives.
Returning to that spawn restores access to its inside. The checks still apply
their own applicable item, Soul and combat requirements. No explosives condition
has been added to every check in a grotto merely because its outside hole is shut.

UPLOADED SEED CHECK
-------------------
AP_66154502437901277321 was reconstructed from generator seed
28991991854046421672. All 4,036 placements match the uploaded spoiler exactly.
Its child spawn targets HF Stone Bridge Tree Grotto, and that grotto's physical
field entrance retains its vanilla destination. AP validation reaches all 4,036
checks and the goal across 44 validation spheres. The exact reconstruction and
source-versus-spawn regression are included in this update's validation folder.
This is verification of the AP model, not a full in-game route/collision proof.

COMPATIBILITY
-------------
The APWorld and every AP source file are byte-identical to the delivered 1.8.11.
No entrance map, item placement, location ID, option or release marker changed.
An existing 1.8.11 seed/save does not need regeneration for this source update.
The previously diagnosed Armos-room seed AP_98530958489753355589 remains blocked;
these label/grotto changes do not repair that older seed's fixed placements.

INSTALL AND BUILD
-----------------
1. Merge soh, src, archipelago and tools into your complete checkout, replacing
   the corresponding files. Copy SOURCE_FILES.json, BUILD_RELEASE.cmd and
   BUILD_RELEASE.ps1 into the checkout root as well.
2. For E:\test\bb, run:

   cd /d E:\test\bb
   BUILD_RELEASE.cmd -RepositoryPath "E:\test\bb" -BuildDirectory "build-vs"

   The helper verifies the complete replacement sources and performs a clean
   Release build. Use the executable path printed by that successful build.
3. The root soh_extreme.apworld is the same 1.8.11 file previously supplied.
   If you still need to update an older APWorld, install it at:
   C:\ProgramData\Archipelago\custom_worlds\soh_extreme.apworld
   Keep your current 1.8.11 seed/save for this update.

All earlier complete replacement sources are included, including the Dodongo
wall/switch fixes and logic.cpp's direct declaration include for CVarGetInteger.
There is no payload folder and no patch application step.

VALIDATION
----------
Fresh evidence and reproducible source tests are under
validation/entrance_fixes_1811/ and tools/tests/. Source hashes bind each current
report to its actual inputs. The shipped build helper's source preflight checks
every replacement file in a disposable fixture. Historical reports retain their
original bytes and dates; they are not presented as fresh runs of changed source.
To replay the tests, also copy validation into the checkout and follow REPLAY.txt.
Native fixtures execute production code with explicit engine I/O shims. This
partial-source environment does not perform a full Windows game build or an
in-game controller playthrough. Source-graph seed validation is not a guarantee
that every modeled physical route has been tested in the game.

The old APWorld under validation/dodongo_1811/inputs is audit-only. Use the
current APWorld in the ZIP root if installation is needed.
