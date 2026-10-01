SOH-EXTREME 0.11.46 - Uncollected NPC Speech glow

READY-TO-RUN UPDATE
1. Close SOH. Extract soh.exe, APCpp.dll and soh.o2r from the Windows ZIP into
   the folder containing the soh.exe you launch (your recent folder was
   E:\test\bb\x64\Release), replacing those three files together.
2. Replace the SOH-EXTREME APWorld in Archipelago's custom_worlds with the
   included soh_extreme.apworld, then restart the AP client / Universal Tracker.
3. Keep your saves, configuration and ROM archives. No new seed is needed
   for this visual feature. Prior fixes, including .45 pot logic, are included.

SOURCE BUILD ALTERNATIVE
Extract the Source-Patch ZIP over your SOH_EXTREME-Extreme source folder
(the folder containing build.cmd), then run build.cmd in a new command prompt.
The overlay is cumulative from commit 9bc10e7191b546754a50da6463e074276d33862f.
The included binary-capable Git patch is an alternative to the source overlay;
do not apply both methods.

BEHAVIOR
- Visible NPCs with an uncollected Speech Sanity check have a soft cyan glow.
- If NPC Soul is shuffled and missing, the glow stays off.
- Talking to the NPC turns the glow off immediately when the check enters
  the saved local outbox, including offline or during a slow server reply.
- Collected checks stay off after reconnect/load. Moving NPCs retain the
  same identity instead of gaining a new glow every time they change areas.
- Speech Sanity off, inactive checks and hidden/destroyed actors have no glow.
- The glow marks an uncollected conversation, not a guarantee that every
  interaction requirement is currently met. Existing speech/ability rules apply.
- An NPC who also has an enemy-drop check uses cyan while its speech check
  remains. Afterward, its normal gold enemy-drop indicator can still appear.

VALIDATION AND SCOPE
14,520 compiled glow assertions cover all 162 identity rows, NPC Soul,
pending/confirmed/save states, legacy speech identities, and render bounds.
The existing 215 speech and 2,027 enemy-glow assertions also passed.
The Release build, APWorld/source parity and cumulative patch are verified.
Render calls were checked with controlled engine/GPU services; a live in-game
visual playtest was not performed.

This feature does not change AP placements or generation logic and adds no
new crash fix. It uses the existing actor draw pass, retains no actor pointers
across scenes, and preserves prior crash safeguards. The original .44 callback
corrupting write remains unidentified.
