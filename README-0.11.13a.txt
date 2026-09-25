SOH-EXTREME 0.11.13a - Dead Hand arm build hotfix
================================================
Apply over the 0.11.13 enemy-origin patch.

Only one production source file is replaced:
  src/overlays/actors/ovl_En_Dha/z_en_dha.c

INSTALL
1. Extract this ZIP into E:\test\bb and overwrite the included source file.
   Merge folders. Do not delete your existing src or soh folders.
2. Rebuild using your existing configuration:
     cd /d E:\test\bb
     cmake --build build-vs --config Release --parallel 8

You do NOT need to rebuild assets, change build flags, edit libultraship,
replace your AP world, change the YAML, or generate a new seed for this fix.
Keep soh_extreme.apworld version 0.11.13 from the previous package.

CAUSE AND CHANGES
The previous patch included GameInteractor_Hooks.h before z_en_dha.h had
loaded the native game types. This left bool undefined when CVarExists was
parsed, and Player undefined in the hook declarations. The supplied Windows
log contains 11 compiler errors from this one translation unit.

The source now loads its native actor/global headers before the hook header.
It also explicitly includes EnemyDropBridge.h for the declaration of
MegaSoul_ResetEnemyDefeatLife, fixing the C4013 warning in the same log.

Every non-include line is unchanged from 0.11.13. No functions, enemy IDs,
spawn-origin rules, drop handling, save data, or AP logic are changed.
Enemies spawned by enemies or bosses remain excluded from separate checks
by the existing 0.11.13 policy. This hotfix adds no further enemy coverage.

VALIDATION
- Reproduced the original bool/Player and missing-reset-prototype errors
  by compiling the complete original C translation unit.
- Compiled the complete corrected C translation unit to an object with
  Clang 17 and GCC 14.2 using the supplied production headers, not stubs.
- Compared original and corrected files: all non-include lines identical.
- Re-ran the three isolated lifecycle tests (Floormaster group completion,
  Guay respawn, Dead Hand arm regrowth); all passed. These lifecycle tests
  use controlled substitutes for engine services.

Three pre-existing animation-resource pointer-type warnings remain in
both compiler outputs. GCC's initial attempt treated these as errors;
the final before/after comparison used -Wno-error=incompatible-pointer-types
for both versions, matching their warning status in the supplied MSVC log.
Unknown types and implicit declarations were still errors. This is a test
harness setting; no changes to your Windows build flags are needed.

Full Windows/MSVC build, executable linking, and in-game testing were NOT
performed. No seed simulations were run for this include-only repair.

The logs, source diff, checksums, and test reports are under:
  validation/0.11.13a/
