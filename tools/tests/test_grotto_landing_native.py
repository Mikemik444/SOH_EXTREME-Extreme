"""Compile exterior grotto landing geometry, ownership, and native motion.

Actual production grotto tables, landing helpers, Force/void/FW routines, and
native movement fragments run against controlled collision-query IO. This is a
regression fixture, not a scene-asset or complete game-build validation.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time

from test_soul_logic_native import function


SOURCE = Path(__file__).resolve().parents[2]
TEMPLATE = Path(__file__).with_name('grotto_landing_native_tests.cpp.in')
LEGACY = Path(__file__).with_name('grotto_landing_legacy_return.inc')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dependencies', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    started = time.monotonic()
    paths = {
        'grotto': SOURCE / 'soh/Enhancements/randomizer/randomizer_grotto.c',
        'header': SOURCE / 'soh/Enhancements/randomizer/randomizer_grotto.h',
        'player': SOURCE / 'src/overlays/actors/ovl_player_actor/z_player.c',
        'actor': SOURCE / 'src/code/z_actor.c',
        'door': SOURCE / 'src/overlays/actors/ovl_Door_Ana/z_door_ana.c',
        'bgcheck': SOURCE / 'src/code/z_bgcheck.c',
        'collision': SOURCE / 'src/code/z_collision_check.c',
        'bombiwa': SOURCE / 'src/overlays/actors/ovl_Obj_Bombiwa/z_obj_bombiwa.c',
        'ishi': SOURCE / 'src/overlays/actors/ovl_En_Ishi/z_en_ishi.c',
        'runtime': SOURCE / 'soh/Network/Archipelago/EntranceRuntime.inc',
        'ap_header': SOURCE / 'soh/Network/Archipelago/ArchipelagoC.h',
        'catalog': SOURCE / 'archipelago/soh_extreme/SceneTransitionCatalog.json',
    }
    texts = {name: path.read_text() for name, path in paths.items()}
    digest = lambda path: sha256(path.read_bytes()).hexdigest()
    hashes = {str(path.relative_to(SOURCE)): digest(path) for path in paths.values()}
    tests = (Path(__file__), TEMPLATE, LEGACY, Path(__file__).with_name('test_soul_logic_native.py'))
    test_hashes = {str(path.relative_to(SOURCE)): digest(path) for path in tests}
    dependencies = {name: args.dependencies / name for name in ('scene_table.h', 'entrance_table.h')}
    dependency_hashes = {name: digest(path) for name, path in dependencies.items()}
    grotto = texts['grotto']
    fragments = {
        'TYPES': texts['header'][texts['header'].index('typedef struct {'):texts['header'].index('#ifdef __cplusplus')],
        'DATA': grotto[grotto.index('// Information necessary for entering each grotto'):
                       grotto.index('// SOH-EXTREME Shovel semantics.')],
        'HELPERS': grotto[grotto.index('// SOH-EXTREME exterior grotto landing ownership and geometry.'):],
    }
    names = ['Grotto_InitExitAndLoadLists', 'Grotto_ShouldSetLastEntrance', 'Grotto_SetupReturnInfo',
             'Grotto_OverrideSpecialEntrance', 'Grotto_ForceGrottoReturnOnSpecialEntrance',
             'Grotto_ForceGrottoReturn', 'Grotto_ForceRegularVoidOut',
             'Grotto_SetupReturnInfoOnFWReturn', 'Grotto_SanitizeEntranceType']
    captured = {name: function(grotto, name) for name in names}
    fragments['ROUTING'] = '\n\n'.join(captured.values())
    for name in ('Actor_UpdateVelocityXZGravity', 'Actor_UpdatePos', 'Actor_MoveXZGravity'):
        captured[name] = function(texts['actor'], name)
    fragments['NATIVE_PHYSICS'] = '\n\n'.join(captured[name] for name in
        ('Actor_UpdateVelocityXZGravity', 'Actor_UpdatePos', 'Actor_MoveXZGravity'))
    captured['Player_Action_8084F9C0'] = function(texts['player'], 'Player_Action_8084F9C0')
    captured['func_8083DFE0'] = function(texts['player'], 'func_8083DFE0')
    fragments['NATIVE_ACTIONS'] = re.sub(r'\bthis\b', 'link',
        captured['Player_Action_8084F9C0'] + '\n\n' + captured['func_8083DFE0'])
    init = texts['player'][texts['player'].index('void Player_Init('):]
    start = init.index('    respawnFlag = gSaveContext.respawnFlag;')
    end = init.index('    if ((respawnFlag == 0) || (respawnFlag < -1))', start)
    fragments['PLAYER_RESPAWN_OVERRIDE'] = re.sub(r'\bthis\b', 'link', init[start:end])
    fragments['LEGACY_FORCE_RETURN'] = function(LEGACY.read_text(), 'Grotto_ForceGrottoReturn').replace(
        'Grotto_ForceGrottoReturn', 'Legacy_Grotto_ForceGrottoReturn', 1)
    fragments['SCENES'] = 'enum {\n' + '\n'.join(
        f'    {name} = {value},' for value, name in re.findall(
            r'/\* (0x[0-9A-Fa-f]+) \*/ DEFINE_SCENE\([^,]+,[^,]+,\s*(SCENE_\w+),',
            dependencies['scene_table.h'].read_text())) + '\n};'
    fragments['ENTRANCES'] = 'enum {\n' + '\n'.join(
        f'    {name} = {value},' for value, name in re.findall(
            r'/\* (0x[0-9A-Fa-f]+) \*/ DEFINE_ENTRANCE\((ENTR_\w+),',
            dependencies['entrance_table.h'].read_text())) + '\n};'
    row = next(row for row in json.loads(texts['catalog']) if row['id'] == 11001806)
    assert (row['source_scene'], row['target_scene'], row['grotto'], row['content']) == (81, 62, 14, 229)
    # The real trigger proves why a static floor ray alone is insufficient.
    door_open = function(texts['door'], 'DoorAna_WaitOpen')
    assert '15.0f' in door_open and 'PLAYER_STATE1_FLOOR_DISABLED' in door_open
    assert texts['player'].index('const s32 grottoLandingResult') < texts['player'].index(
        '    sControlInput = input;', texts['player'].index('void Player_UpdateCommon('))
    assert texts['player'].index('Grotto_UpdateReturnLanding(&this->actor);') < texts['player'].index(
        'GameInteractor_ExecuteOnPlayerUpdate();')
    fixture = TEMPLATE.read_text()
    for token, value in fragments.items():
        fixture = fixture.replace('@' + token + '@', value)
    assert not re.search(r'@[A-Z_]+@', fixture)
    with tempfile.TemporaryDirectory(prefix='soh-grotto-landing-') as tmp:
        build = Path(tmp)
        cpp, binary = build / 'grotto.cpp', build / 'grotto'
        cpp.write_text(fixture)
        command = ['g++', '-std=c++20', '-Wall', '-Wextra', '-Werror',
                   '-Wno-unused-parameter', '-Wno-unused-function', '-Wno-missing-field-initializers',
                   '-Wno-narrowing', '-Wno-parentheses', '-g', '-O1',
                   '-fsanitize=address,undefined', '-fno-omit-frame-pointer', str(cpp), '-o', str(binary)]
        result = subprocess.run(command, text=True, capture_output=True)
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)
        env = dict(os.environ, ASAN_OPTIONS='detect_leaks=0:halt_on_error=1',
                   UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
        result = subprocess.run([str(binary)], text=True, capture_output=True, env=env)
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)
        counts = json.loads(result.stdout)
    assert hashes == {str(path.relative_to(SOURCE)): digest(path) for path in paths.values()}
    assert test_hashes == {str(path.relative_to(SOURCE)): digest(path) for path in tests}
    report = {
        'status': 'passed', **counts,
        'source_sha256': hashes, 'test_sha256': test_hashes,
        'dependency_sha256': dependency_hashes,
        'source_unchanged_during_tests': True,
        'captured_function_sha256': {name: sha256(value.encode()).hexdigest() for name, value in captured.items()},
        'captured_fragment_sha256': {name: sha256(value.encode()).hexdigest() for name, value in fragments.items()},
        'legacy_source_sha256': re.search(r'Original randomizer_grotto.c SHA256: ([a-f0-9]{64})', LEGACY.read_text())[1],
        'sanitizers': ['AddressSanitizer', 'UndefinedBehaviorSanitizer'],
        'native_game_build': False, 'scene_asset_geometry': False, 'in_game_playthrough': False,
        'scope': 'Production landing geometry/ownership/cache/Force/FW functions and all 33 authored '
                 'grotto return rows; actual native velocity/position and emergence/neutral-fall action '
                 'fragments. Engine floor/wall/ceiling/water/OC and actor-Soul queries use explicit '
                 'controlled geometry IO. Actual Player_Init positive-respawn override reproduces '
                 'the old Force helper replacing an off-hole ActorEntry with the hole origin in idle '
                 'mode. Real scene and entrance enum values are retained. No ROM assets are available; '
                 'real destinations are validated at runtime and unproven geometry keeps native emergence.',
        'elapsed_seconds': round(time.monotonic() - started, 3),
        'replay_command': 'python source/tools/tests/test_grotto_landing_native.py '
                          '--dependencies tests/entrance_184_native_dependencies '
                          '--report tests/grotto_landing_1812_native.json',
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'status': 'passed', **counts, 'report': str(args.report)}))


if __name__ == '__main__':
    main()
