SOH-EXTREME 0.11.36 - Ability pickups, progress counts and encounter logic
Repository: https://github.com/Mikemik444/SOH_EXTREME-Extreme

WINDOWS DRAG-AND-DROP
Close SOH and the Archipelago/Universal Tracker clients.
Extract the Windows ZIP into the folder containing soh.exe, replacing soh.exe
and APCpp.dll. Keep your existing game assets, soh.o2r, configuration and saves.
Install the included soh_extreme.apworld through Archipelago's APWorld installer
or replace its existing copy in custom_worlds. Restart the AP/UT clients.
Use matching 0.11.36 runtime and APWorld so the tracker loads the updated rules.

SOURCE DRAG-AND-DROP
Extract the Source-Patch ZIP into your SOH_EXTREME-Extreme source root, the
folder containing build.cmd. Replace the included files, open a fresh Command
Prompt and run build.cmd. Wait for BUILD SUCCESS. This package is cumulative
against repository commit 9bc10e7191b546754a50da6463e074276d33862f and retains
previous fixes. Back up/merge any independent edits to the same source files.

CHANGES
- Every shuffled ability uses the major overhead pickup presentation, including
  Open Chest and Flow of Time. Both progressive Open Chest copies animate and
  grant exactly one tier each. Existing Roll, Grab, Swim, Climb, Crawl, language,
  Shovel, Fishing Pole, Roc's Feather, button and soul presentations are retained.
- Flow of Time has its own named item entry and does not grant Sun's Song.
- Sun's Song can change day to night or night to day before Flow of Time is
  collected. The clock then stays at the new time. Normal progression resumes
  after Flow of Time. The starting phase is applied only when creating a save;
  loading, reconnecting and the AP update loop do not reset it every frame.
  Logic requires the ocarina, the song, enabled buttons and all enabled notes.
- Song notes are held overhead. The pickup names the song and shows its note
  count including the pickup, such as Bolero of Fire: 3/8. A complete song says
  Song complete. Each of the 74 notes keeps its individual persistent identity.
- Silver Rupees show the specific puzzle name and collected/required count,
  including the current pickup. Pouch mode displays the completed group count.
- Open Chest, song-note and Silver Rupee receipts stay pending until the engine
  executes the grant. Failed starts retry; interrupted ungranted presentations
  do not consume the receive. Reconnect receipts retain normal deduplication.
- Historical item reconstruction on a newly recreated save remains immediate;
  old receipts do not replay a long chain of pickup animations.
- KF Wonder Crawl Grass 1/2 and LW Wonder Back Skull Kids Grass 1/2 are proximity
  triggers, not cuttable grass. No sword or Grass/Bush Soul is required for them.
  Child access, Crawl for the Kokiri tunnel, and the route into Lost Woods still
  apply. Real grass checks retain their cutting/lifting and soul requirements.
- Hyrule Field's seven parent Peahats require daytime availability. Their
  presence underground at night does not make them defeatable. When time is
  shuffled and frozen at night, they require Flow of Time or playable Sun's Song.
  Lon Lon Ranch Guays still require night, with the same time-change alternatives.
  Child access,
  enabled soul requirements and suitable weapons remain required.
- All 84 soul types retain a major overhead pickup, including boss, enemy,
  animal, NPC, business scrub, bean and object souls.

EXISTING SEEDS
These changes do not move placed items or clear collected checks. The tracker
can use the updated requirements in an existing seed, but a circular item
placement in an old seed is not repaired by updating the tracker. Generate new
seeds with this APWorld for the corrected Peahat requirements. This release
does not newly certify the three earlier multiworlds.

VALIDATION
See VALIDATION-ABILITY-WONDER-FIX.json for the exact tests and build results.
Tests cover real AP/UT reachability, receipt state transitions with controlled
engine services, pickup text/counts, compiled clock/Sun's Song behavior, and
generated seed progression.
No rendered in-game or connected-server playthrough was performed.
