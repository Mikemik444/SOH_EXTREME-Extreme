SOH-EXTREME 0.11.13 - enemy origin and lifetime correction

This cumulative source package contains the 0.11.12 native changes plus the
0.11.13 corrections, and one matching ready-to-install soh_extreme.apworld.
There are 38 complete native files; this is NOT a complete source repository.
Do not delete your existing soh or src directory.

INSTALL
1. Merge this archive into E:\test\bb. Overwrite the included files.
2. Rebuild:
   cd /d E:\test\bb
   cmake --build build-vs --config Release --parallel 8
   Keep using your existing resource/OTR/O2R copy steps.
3. Close Archipelago and Universal Tracker. Replace the installed
   C:\ProgramData\Archipelago\custom_worlds\soh_extreme.apworld
   with the file at this archive's root. Keep one installed SOH-EXTREME world.
   Use the same world version in every installation running Universal Tracker.
4. Restart the applications and generate a NEW seed. Your YAML settings need
   no edits. Old seeds still expecting the 21 removed offspring checks are not
   compatible with the new location set. Stable receipt indices do not make
   those old servers compatible. Do not continue such a seed with this patch.

RULE
Scene-placed enemies and explicitly mapped non-enemy room/puzzle controllers
can own checks. Monster/boss-created offspring, fragments, clones, projectiles
and descendants of enemy-created helpers cannot own checks. Ordinary enemy
loot remains available according to the existing drop/soul settings.

CHANGES
- Capture immutable spawn provenance and hostile-at-spawn classification before
  actor initialization. Cover raw spawns, SpawnAsChild, nested init/update/draw/
  destroy callbacks, and actor hooks. Preserve authentic parent/child linking.
- Remove the old fallback re-identification that could give a rejected spawn
  an unrelated actor-list/param identity. Failed allocations consume one-shot
  spawn context; they cannot leak a scene index or a prepared encounter ID.
- Retire the 21 Peahat larval checks (9800765..9800785) from AP and Check Finder.
  Keep all 786 receipt slots unchanged; reject retired bindings, pickups,
  pending-state queries and reconnect receipt replay even with stale slot data.
- Keep all three Bow-room Stalfos and all four real Poe Sisters. Paintings and
  cubes use explicit non-enemy encounter spawning. Meg decoys do not count.
- Floormaster: one placed check after the entire split group is defeated, not
  when an early small hand dies. The original identity survives the circular
  parent/child links; the pickup appears at the last fragment's position.
- Guay and authored Dead Hand hand actors reset per-life drop/death flags only
  when a confirmed new life begins. Saved collection and source identity stay.
- Initialize vetoed Actor_SpawnEntry results and restore nested map-load state.

CONTENTS
soh/, src/                  Complete changed/native files, merge into project.
soh_extreme.apworld         Ready-to-install standalone world, version 0.11.13.
source/soh_extreme-source.zip  Matching AP source, no test adapters inside.
validation/                Reproduction scripts, bounded fixtures, actual logs.
VALIDATION.md              Test scope and exact reproduction instructions.
ENEMY_COVERAGE.md          Coverage and remaining incomplete work.
FILE_MANIFEST.json         Paths, sizes and SHA-256 digests.

Not a whole Windows build or proof that every physical encounter/seed is
correct. See ENEMY_COVERAGE.md before treating this as a completed logic audit.
