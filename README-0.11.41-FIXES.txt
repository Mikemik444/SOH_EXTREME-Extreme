SOH-EXTREME 0.11.41 - Unused enemy checks and existing-seed compatibility
Repository: https://github.com/Mikemik444/SOH_EXTREME-Extreme

CORRECTION
My earlier explanation and map of live outdoor Graveyard Keese were wrong.
The raw room data contains five Keese and two Skullwalltulas, but their object
dependencies are missing, so normal gameplay never spawns them. Enemy
Randomizer also deliberately discards them. A Lost Woods Octorok has the same
problem. These eight checks are excluded from NEW seed generation in .41.
Real Keese inside the Royal Family's Tomb remain gated by a playable Zelda's
Lullaby, including the configured Ocarina/button/note requirements.

KEEPING YOUR EXISTING SEED
Keep your current server/multidata and save. Do not regenerate to apply this
compatibility fix; using the same seed number with changed code can produce a
different world. No item or location IDs have been renumbered.

For an old server that explicitly includes these eight locations, the game
restores only the exact uncollected enemy placements. The Graveyard enemies
appear as adult Link, at their original authored positions. The original
enemy is preserved even with Enemy Randomizer enabled. Normal soul, combat,
pickup, receipt, save and server-reporting requirements still apply. Items are
not auto-awarded. Leave and re-enter the area after loading/connecting so its
actors can spawn. Once the locations are checked, the compatibility spawns
are no longer needed. New seeds do not receive these extra actors/checks.

Both the runtime and APWorld/Universal Tracker must be updated. Installing an
APWorld alone does not change an old server's placements or fix actor spawning.

WINDOWS DRAG-AND-DROP
1. Close SOH. Extract the Windows ZIP into the folder containing the soh.exe
   you actually launch: E:\test\bb\x64\Release in the inspected installation.
   Replace BOTH soh.exe and APCpp.dll. Keep the existing assets, saves/config.
2. Install the included soh_extreme.apworld through Archipelago's installer
   or replace its existing copy in custom_worlds. Restart Archipelago/UT and
   the in-game AP tracker. Keep the existing seed and save for this repair.
3. Launch that soh.exe, reconnect, and re-enter Graveyard as adult Link.
   Your earlier session logged repeated AP connection failures; if those
   continue, delivery to/from the server cannot complete until connected.

SOURCE DRAG-AND-DROP
Extract the Source-Patch ZIP into the source root beside build.cmd and replace
the included files. Run build.cmd in a fresh Command Prompt. Wait for BUILD
SUCCESS, then install the generated .41 APWorld. CMake applies the dependency
patches as part of the build. This cumulative overlay targets Git commit
9bc10e7191b546754a50da6463e074276d33862f; preserve unrelated local edits.

CRATER CRASH
The available log contains one Crater crash at 09:54:18 on September 30, in
the session started at 09:23. Its fault offset matches the previously traced
Fast::Interpreter::GfxDpLoadTlut second palette-copy access violation. The
subsequently inspected installed EXE/DLL matched .40, but that does not prove
which code the earlier process had loaded. No later Crater crash was present
in that log when inspected; this is not proof that every crash is fixed.

This package retains the .40 full-transfer TLUT memory guard. It also logs
runtime 0.11.41 and the build timestamp at startup, before connecting, so a
future failure can be tied to the loaded version. Please keep a crash log
from a new session if a transition still fails. No live Crater transition was
performed here, and unrelated crash causes remain possible.

VALIDATION
Windows Release build; 227 missing-object restoration/rejection cases through
the production C spawn code and Enemy Randomizer hook; 812 actor identities
and 41658 offspring-rejection cases; 142 AP/UT manifest/soul/age assertions;
182 Graveyard/Windmill route assertions; resource object-list audit; rebuilt
APCpp callback ABI test; 104-file APWorld/source parity; source-patch and ZIP
verification. Fresh generation/replay with the supplied YAML reaches the goal
and all 3311 modeled checks. This is automated evidence, not a complete
rendered playthrough or a guarantee that every physical route is correct.

The package includes prior .40 fixes for song colors, item presentation,
receipt delays, bean-soul routes, Windmill access and the known palette fault.
See VALIDATION-0.11.41-FIXES.json, TEST-EVIDENCE-0.11.41-FIXES.json and
SOH_AP_FIX_HISTORY.txt for details and earlier compatibility limits.
