SOH-EXTREME 0.11.40 - Graveyard/Windmill logic, song colors and runtime fixes
Repository: https://github.com/Mikemik444/SOH_EXTREME-Extreme

WINDOWS DRAG-AND-DROP
Close SOH. Extract the Windows ZIP into the folder containing the soh.exe you
actually launch (often x64\Release), replacing BOTH soh.exe and APCpp.dll.
Keep your existing soh.o2r/assets, saves and configuration. The EXE/DLL pair
must stay together because the earlier AP model fix changed their callback ABI.
Install the included soh_extreme.apworld through Archipelago's installer or
replace its existing copy in custom_worlds. Restart Archipelago and Universal
Tracker, then restart/refresh the in-game AP tracker.

SOURCE DRAG-AND-DROP
Extract the Source-Patch ZIP into your SOH_EXTREME-Extreme source root beside
build.cmd. Replace the included files, then run build.cmd in a fresh Command
Prompt. Wait for BUILD SUCCESS and install the resulting 0.11.40 APWorld.
CMake applies the APCpp and libultraship renderer dependency fixes and rebuilds
them. Unrecognized renderer revisions stop with an explicit error.
This cumulative overlay targets Git commit
9bc10e7191b546754a50da6463e074276d33862f. Merge any independent local edits.

LOGIC CHANGES
- Graveyard heart piece and its crate share the same physical route: an adult
  planted bean platform, adult Roc's Feather jump, or usable Longshot, plus
  Crate Soul and a crate-breaking action when their shuffles are enabled.
  The separately enabled child Boomerang trick remains available.
- All ten bean-planting events require the correct area's Bean Soul when
  shuffled. Owning a soul alone does not replace beans or child planting access.
- Song from Windmill requires adult access, Ocarina, NPC Soul and Hylian speech
  as configured. The front door requires Windmill Key or Skeleton Key when
  locked. The alternate route through Dampe's grave requires his interaction
  and playable Song of Time before it can bypass the door.
- The screenshot's Graveyard Room 1 Keese and Skullwalltulas are outdoor
  actors; they do not require Zelda's Lullaby. Royal Family's Tomb is a
  separate scene, whose checks require a complete playable Lullaby, including
  Ocarina and shuffled buttons/notes. Negative controls verified that gate.

RUNTIME CHANGES
- All 74 song notes use their own song's existing native model/color and keep
  the important-item hold-up and note-count text. A note does not grant the
  full song before all its notes have actually been received.
- Pending hold-ups are re-offered at each safe player update. Interrupted
  one-frame offers no longer wait for repeated 90-frame timeouts. Scene,
  cutscene, water, death and unrelated item safety gates remain in effect.
  This removes the confirmed local delay; network latency can still occur.
- Two matching user scene-transition crashes were traced to the second half
  of a texture palette copy in libultraship. The previous guard validated only
  its first half. The Windows fix validates and stages the complete bounded
  copy before publishing it. A protected-page test reproduced the original
  access violation and verified the fix. Other crash causes remain possible.

EXISTING SEEDS
No item/location IDs change in .40. Runtime fixes and corrected tracker advice
work with existing seeds. Generate a NEW seed with the .40 APWorld to have the
stricter logic govern placement; an update cannot move old seed items or prove
an existing seed is physically beatable. Earlier cumulative catalog changes
also retain their documented new-seed requirements (Dodongo doorway pots and
retired Hyrule Castle courtyard windows).

VALIDATION
Windows Release build, 104-file APWorld/source parity, source-patch apply and
archive checks passed. Tests include 189 AP/UT route assertions, 3072 native
route predicates, 189 color assertions, 1798 receipt/re-offer assertions,
897 enemy-model assertions, 66058 protected-memory/bounds assertions, CMake
patch fixtures, item presentation and five delivery regression groups.
Fresh generation and replay using the user's current YAML reached the goal
and all 3319 checks without a source-interaction rejection. These checks are
automated evidence, not a complete rendered or connected game playthrough.
See VALIDATION-0.11.40-FIXES.json, TEST-EVIDENCE-0.11.40-FIXES.json and
SOH_AP_FIX_HISTORY.txt for the cumulative history and limits.
