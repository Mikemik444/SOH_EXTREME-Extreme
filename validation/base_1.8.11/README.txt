SOH-EXTREME 1.8.11 - Complete source files
==========================================

DODONGO'S CAVERN STARTING SOFTLOCK
--------------------------------
Both exits from Armos Room, room 5, are barred by temporary switch 0x22 on the
central pillar. The stairs-side exit was incorrectly considered free by the
native/AP rules. Both exits now require the current age's switch-access action.
The normal child route needs Grab / Power Bracelet and Climb. The structural
statue has no Armos Soul or Rock / Boulder Soul requirement. The adult ledge
route and genuinely usable alternate actions retain their authored behavior.

The switch is temporary scene state, so an earlier adult visit cannot permanently
unlock it for an unequipped child. The Armos Room -> Bomb Room shortcut now passes
through the physical Entrance Side Bridge doorway and cannot bypass its mapping.

Your AP_98530958489753355589 seed was exactly reproduced: all 4,036 items and 719
entrance connections match. Its child spawn enters Armos Room 5. With the corrected
rules, the unchanged seed reaches only Link's Pocket and Song from Impa: 2 of 4,036,
then stops. It requires regeneration with the included 1.8.11 APWorld and a new save.
Updating the native executable cannot move that seed's fixed items or entrance map.

BOMBABLE WALLS
--------------
The small mud walls now register their receiving collider during the actor update
instead of Draw. Their solid barrier can receive explosive and ordinary Hammer
hits when the model is not drawn. The attack mask, normal switch, break effects,
King Dodongo floor and lava-cover behavior are retained. No new Soul is required.

ROOM DESTINATION LABELS
----------------------
The opt-in world destination labels put a descriptive arrival first, for example:

  Door to Deku Tree: Basement Torch Room
  Room 6

The number is the actual destination room for a mapped room door. Raw native
boss-return names such as RR_FOREST_TEMPLE_BOSS_ENTRYWAY are now readable names.
Real scene-exit handle identities distinguish front/back exits sharing a scene.
Preloading a room does not reverse a label while Link remains on the source side.
Native passages show their physical destinations, including vertical/drop types.
Unknown destination-room numbers are left unspecified; spawn indices are not rooms.

In Check Finder, Show room and door numbers remains optional and off by default.
When enabled, the destination room and source door details are below the descriptive
check name. Existing age suffixes and player aliases are preserved. AP check names,
location IDs, entrance catalogs and destination policy are unchanged.

INSTALL AND BUILD
-----------------
1. Merge soh, src, archipelago and tools into your complete checkout, replacing
   the corresponding files. Replace SOURCE_FILES.json in the checkout root too,
   and copy BUILD_RELEASE.cmd and BUILD_RELEASE.ps1 there.
2. For your E:\test\bb checkout, run:

   cd /d E:\test\bb
   BUILD_RELEASE.cmd -RepositoryPath "E:\test\bb" -BuildDirectory "build-vs"

   The helper verifies the complete sources, performs a clean Release build and
   prints the executable path. Use your actual paths if different.
3. Install the ROOT soh_extreme.apworld from this ZIP to:
   C:\ProgramData\Archipelago\custom_worlds\soh_extreme.apworld
4. Generate a new seed with 1.8.11 and start its new save. Your reported Armos-room
   seed is blocked; do not resume that save expecting the placement to change.

All prior source fixes are included, including logic.cpp's direct console-variable
declaration-header include for the C3861 error. A local EnHoll pointer/fixture
signature now matches the native coordinate API; its routing behavior is unchanged.

VALIDATION
----------
Fresh evidence is under validation/dodongo_1811/. It includes the exact original
seed reproduction and corrected replay, focused native/AP regressions, separate
child/adult full fills, current APWorld/source verification and the actual build
helper's source preflight. The child test uses your reported settings. The adult
test explicitly changes Closed Forest to Off because On forces Child, and both
tests assert the age actually generated. Native fixtures execute production functions with
explicit engine I/O shims. No full Windows game build or controller playthrough
was performed in this partial-source environment.

Historical reports elsewhere in validation retain their original source hashes.
The old APWorld under validation/dodongo_1811/inputs is ONLY for reproducing the
failed original seed; install the 1.8.11 APWorld in this ZIP's root.

CONTENTS: 190 complete replacement source files, matching APWorld, YAML and build helpers.
