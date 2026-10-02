SOH-EXTREME 0.11.55 - Bean-fairy requirements and Lost Woods diving

All eight child Lost Woods underwater shortcut rupees now need Silver Scale
rather than Golden Scale, in both native and AP logic. With Swim shuffled,
that means two Progressive Scales total: one for Swim and one for deeper diving.

Reaching Lost Woods is still required. Climb provides the direct Kokiri route;
an accessible outside route through Goron City or the Zora River diving shortcut
can substitute. The rupees do not get an extra blanket Climb requirement, and
two scales alone do not assume an escape from a closed forest without Climb
or another reachable route. Adult-only access does not collect child rupees.

Bean fairies require child access to the plot, beans to plant, the matching
soil/Bean Soul when shuffled, and playable Song of Storms. Playing the song
requires an ocarina and A, C-Up and C-Down buttons when buttons are shuffled.
Individual-notes mode also requires all six notes of Song of Storms.

The three Lost Woods bean fairies near Deku Theater previously checked bean
possession without checking whether that exact soil plot was available.
They now use the same plant-use rule as the other sites and require Lost
Woods Bean Soul. Lost Woods Bridge Bean Soul does not substitute for it.

All 30 checks across the ten plots were audited. Existing child/area access,
beans, song, instrument and button requirements are retained. Disabling the
soul or button shuffle makes that capability innate. Flow of Time is not
required to explicitly play the song and water the planted bean.

Close SOH, then copy the Windows package contents into the game directory.
Install soh_extreme.apworld into Archipelago/custom_worlds and restart the
AP client/tracker. Use matching .55 game and APWorld versions. Existing saves,
check IDs and item placements are preserved. Tracker reachability updates
for existing seeds; this does not rearrange previously generated placements.

Includes all prior fixes through .54 and ROM extractor assets. No ROM or
oot.o2r is included. The separate Source Patch ZIP includes the cumulative
source overlay and a verified patch against repository commit
9bc10e7191b546754a50da6463e074276d33862f.

Validation: 8,364 AP/Universal Tracker assertions for all 30 fairies, each
missing prerequisite and song note, wrong-plot souls, both ages, individual
notes/full-song mode, shuffle-off settings, and restored tracker slots.
Old .54 fails 24 assertions; the corrected version passes all of them.
Another 3,040 AP/UT assertions cover diving depth, both ages, Climb versus
outside routes, closed-forest access and restored slot settings. 128 compiled
native assertions cover all eight rupee predicates and scale upgrade tiers.
Windows Release build verified. No live gameplay test was performed.
