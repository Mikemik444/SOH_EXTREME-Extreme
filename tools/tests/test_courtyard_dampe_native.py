"""Compile real courtyard guard Init/lifecycle, hut SetupType and arrival policy.

Complete production EnHeishi1_Init and EnDoor_SetupType execute with minimal
engine I/O and actual actor layouts/tables/constants. Rendering, scene geometry
and full actor Update are not simulated. Guard Update integration is checked
for an early refresh before AI/timers. Historical production excerpts reproduce
the guard selection, child-evening hut bug and original type-5 table overrun.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import zipfile

from test_zora_river_native import function, enum_containing, between


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dependencies', type=Path, required=True)
    parser.add_argument('--original-archive', type=Path)
    parser.add_argument('--baseline', type=Path)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    cc, cxx = shutil.which('gcc'), shutil.which('g++')
    if not cc or not cxx:
        raise SystemExit('GCC C11 and C++20 compilers are required.')
    native_guard = 'src/overlays/actors/ovl_En_Heishi1/z_en_heishi1.c'
    native_door = 'src/overlays/actors/ovl_En_Door/z_en_door.c'
    sources = (
        native_guard, native_door,
        'src/overlays/actors/ovl_En_Heishi1/z_en_heishi1.h',
        'src/overlays/actors/ovl_En_Door/z_en_door.h',
        'soh/Network/Archipelago/ArchipelagoC.h',
        'soh/Network/Archipelago/EntranceDestinationPolicy.h',
        'soh/Network/Archipelago/EntranceDestinationData.inc',
        'archipelago/soh_extreme/EntranceDestinationPolicy.json',
        'soh/Enhancements/randomizer/ShuffleWonderItems.cpp',
        'soh/Enhancements/randomizer/LockOverworldDoors.cpp',
    )
    tests = (
        'tools/tests/test_courtyard_dampe_native.py',
        'tools/tests/test_zora_river_native.py',
        'tools/tests/courtyard_dampe_native_io.h',
        'tools/tests/courtyard_dampe_native_tests.c.in',
        'tools/tests/courtyard_dampe_policy_tests.cpp.in',
        'tools/tests/courtyard_dampe_legacy_sources.json',
        'tools/tests/courtyard_dampe_legacy_guard.inc',
        'tools/tests/courtyard_dampe_legacy_full_guard_init.inc',
        'tools/tests/courtyard_dampe_legacy_door.inc',
    )
    dependencies = ('scene_table.h', 'z64save.h', 'z64scene.h')
    source_before = {name: digest(root / name) for name in sources}
    test_before = {name: digest(root / name) for name in tests}
    dependency_before = {name: digest(args.dependencies / name) for name in dependencies}
    read = lambda name: (root / name).read_text(encoding='utf-8-sig')
    guard, door = read(native_guard), read(native_door)
    guard_header = read(sources[2])
    door_header = read(sources[3])
    provenance = json.loads(read('tools/tests/courtyard_dampe_legacy_sources.json'))
    for kind, archive_path, signature in (
            ('guard', args.original_archive, 'void EnHeishi1_Init(Actor* thisx, PlayState* play) {'),
            ('door', args.baseline, 'void EnDoor_SetupType(EnDoor* this, PlayState* play) {')):
        meta = provenance[kind]
        assert digest(root / meta['retained_excerpt']) == meta['retained_excerpt_sha256']
        if kind == 'guard':
            assert digest(root / meta['retained_full_init']) == meta['retained_full_init_sha256']
        if archive_path:
            assert digest(archive_path) == meta['archive_sha256']
            with zipfile.ZipFile(archive_path) as archive:
                original = archive.read(meta['member'])
            assert hashlib.sha256(original).hexdigest() == meta['full_source_sha256']
            full = function(original.decode('utf-8-sig').replace('\r\n', '\n'), signature)
            if kind == 'guard':
                expected = ('// Original guard-selection tail; intentionally excludes animation and actor spawning.\n'
                            'void Baseline_InitializeCourtyardAccess(EnHeishi1* this) {\n' +
                            full[full.index("    // eventChkInf[4]"):] + '\n')
                assert read(meta['retained_full_init']) == full.replace(
                    'void EnHeishi1_Init(', 'void Baseline_EnHeishi1_Init(', 1) + '\n'
            else:
                expected = full.replace('void EnDoor_SetupType(', 'void Baseline_EnDoor_SetupType(', 1) + '\n'
            assert read(meta['retained_excerpt']) == expected

    # Bind complete production Init and exact original table, including its four
    # rows. The fixed type-5 path uses existing defaults; no fixture table growth.
    guard_data = between(guard, 'static f32 sAnimParamsInit', 'static s32 sCamDataIdxs')
    guard_data = re.sub(r'static s16 sBaseHeadTimers\[\].*?;\n\n', '', guard_data, flags=re.S)
    assert guard_data.count('1000.0f, 200.0f') == 2
    guard_structs = between(guard_header, 'struct EnHeishi1;', '#endif')
    door_structs = between(door_header, 'struct EnDoor;', '#ifdef __cplusplus')
    save_header = (args.dependencies / 'z64save.h').read_text()
    constants = '\n'.join(re.findall(
        r'^#define EVENTCHKINF_(?:40_INDEX|40_SHIFT|OBTAINED_ZELDAS_LETTER|LEARNED_ZELDAS_LULLABY|ZELDA_FLED_HYRULE_CASTLE|TALON_RETURNED_FROM_CASTLE) [^\r\n]+',
        save_header, re.M))
    scene_header = (args.dependencies / 'z64scene.h').read_text()
    constants += '\n' + between(scene_header, '#define DEFINE_SCENE', '// this define exists')
    constants += '\n#undef DEFINE_SCENE\n'
    constants += '\n' + enum_containing(door_header, 'DOOR_EVENING,')
    constants += '\n' + re.search(r'^#define DOOR_AJAR_SLAM_RANGE[^\r\n]+', door, re.M).group(0)
    helper_signatures = (
        'static bool EnHeishi1_HasPendingCourtyardTransition(void) {',
        'static bool EnHeishi1_ShouldBeActive(EnHeishi1* this, bool preserveChecks) {',
        'static void EnHeishi1_WaitForCourtyardAccess(EnHeishi1* this, PlayState* play) {',
        'static void EnHeishi1_InitializeCourtyardAccess(EnHeishi1* this) {',
        'static bool EnHeishi1_RefreshCourtyardAccess(EnHeishi1* this) {',
    )
    guard_init = function(guard, 'void EnHeishi1_Init(Actor* thisx, PlayState* play) {')
    guard_update = function(guard, 'void EnHeishi1_Update(Actor* thisx, PlayState* play) {')
    assert guard_init.count('EnHeishi1_InitializeCourtyardAccess(this);') == 1
    refresh = guard_update.index('if (EnHeishi1_RefreshCourtyardAccess(this)) {\n        return;\n    }')
    assert refresh < guard_update.index('this->activeTimer++') < guard_update.index('this->actionFunc(this, play)')
    captures = {
        'captured_native_constants.h': constants,
        'captured_actor_structs.h': guard_structs + '\n' + door_structs,
        'captured_guard_data.inc': guard_data,
        'captured_guard_helpers.inc': '\n'.join(function(guard, sig) for sig in helper_signatures),
        'captured_guard_init.inc': guard_init,
        'captured_dampe_door.inc': function(door, 'static bool EnDoor_IsChildDampeHutDoor(') + '\n' +
            function(door, 'void EnDoor_SetupType(EnDoor* this, PlayState* play) {'),
    }
    env = dict(os.environ, ASAN_OPTIONS='detect_leaks=0', UBSAN_OPTIONS='halt_on_error=1')
    outputs = {}
    commands = []
    with tempfile.TemporaryDirectory(prefix='courtyard-dampe-native-') as directory:
        temp = Path(directory)
        (temp / 'tables').mkdir()
        shutil.copyfile(args.dependencies / 'scene_table.h', temp / 'tables/scene_table.h')
        for name, contents in captures.items():
            (temp / name).write_text(contents + '\n')
        for name in tests:
            if name.endswith(('.h', '.inc')):
                shutil.copyfile(root / name, temp / Path(name).name)
        shutil.copyfile(root / 'tools/tests/courtyard_dampe_native_tests.c.in', temp / 'native_tests.c')
        shutil.copyfile(root / 'tools/tests/courtyard_dampe_policy_tests.cpp.in', temp / 'policy_tests.cpp')
        flags = ['-g', '-O1', '-fno-omit-frame-pointer', '-fsanitize=address,undefined',
                 '-fno-sanitize-recover=all', '-no-pie', '-Wall', '-Wextra', '-Werror',
                 '-Wno-unused-parameter', '-Wno-unused-variable', '-Wno-sign-compare',
                 '-I', str(root), '-I', str(temp)]
        for name, compiler, standard, extension in (
                ('native', cc, '-std=c11', 'c'), ('policy', cxx, '-std=c++20', 'cpp')):
            command = [compiler, standard, *flags, str(temp / (name + '_tests.' + extension)), '-o', str(temp / name)]
            commands.append(command)
            build = subprocess.run(command, text=True, capture_output=True)
            if build.returncode:
                raise SystemExit(build.stdout + build.stderr)
            run = subprocess.run([str(temp / name)], text=True, capture_output=True, env=env)
            if run.returncode:
                raise SystemExit(run.stdout + run.stderr)
            outputs[name] = json.loads(run.stdout)
        # The unchanged full original Init is deliberately run only in its own
        # failing subprocess; its table has four rows and type 5 indexes row 5.
        original = subprocess.run([str(temp / 'native'), 'baseline-type5-oob'], text=True,
                                  capture_output=True, env=env)
        assert original.returncode != 0, 'Original full Init unexpectedly accepted type 5'
        assert 'index 5 out of bounds' in original.stderr, original.stderr
        outputs['original_type5_init'] = {
            'expected_failure_reproduced': True, 'exit_code': original.returncode,
            'sanitizer_diagnostic': original.stderr.strip(),
        }
    stable = (source_before == {name: digest(root / name) for name in sources} and
              test_before == {name: digest(root / name) for name in tests} and
              dependency_before == {name: digest(args.dependencies / name) for name in dependencies})
    assert stable, 'Fixture/source changed during test execution'
    report = {
        'status': 'passed', 'source_sha256': source_before, 'test_sha256': test_before,
        'source_unchanged_during_run': stable,
        'dependency_root': str(args.dependencies.resolve()),
        'dependency_sha256': dependency_before,
        'baseline': provenance,
        'evidence': {path.name: {'path': str(path.resolve()), 'sha256': digest(path)}
                     for path in (args.original_archive, args.baseline) if path is not None},
        'captures_sha256': {name: hashlib.sha256((content + '\n').encode()).hexdigest()
                           for name, content in captures.items()},
        'compiler': {'c': subprocess.check_output([cc, '--version'], text=True).splitlines()[0],
                     'cpp': subprocess.check_output([cxx, '--version'], text=True).splitlines()[0]},
        'sanitizers': ['AddressSanitizer', 'UndefinedBehaviorSanitizer'],
        'results': outputs, 'scope': __doc__,
    }
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'status': 'passed', 'results': outputs}, indent=2))


if __name__ == '__main__':
    main()
