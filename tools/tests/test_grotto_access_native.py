"""Compile native bomb-grotto rules and the actual DoorAna opening functions.

The real item-use, Bombchu, attack-mask, collider-registration, Soul and Shovel
predicates are extracted from source. Inventory/options, contact geometry,
allocation, scene loading, camera and audiovisual engine IO are controlled.
The retained original helper is regression evidence, never production code.
Requires Python 3 and g++ with C++20, AddressSanitizer and UBSan; no ROM needed.
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
ACTORS = SOURCE / 'src/overlays/actors'
TEMPLATE = Path(__file__).with_name('grotto_access_native_tests.cpp.in')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    started = time.monotonic()
    paths = {
        'logic': SOURCE / 'soh/Enhancements/randomizer/logic.cpp',
        'door': ACTORS / 'ovl_Door_Ana/z_door_ana.c',
        'grotto': SOURCE / 'soh/Enhancements/randomizer/randomizer_grotto.c',
        'grotto_header': SOURCE / 'soh/Enhancements/randomizer/randomizer_grotto.h',
        'souls': SOURCE / 'soh/Enhancements/randomizer/MegaSouls.cpp',
        'collision': SOURCE / 'src/code/z_collision_check.c',
        'bomb': ACTORS / 'ovl_En_Bom/z_en_bom.c',
        'bombchu': ACTORS / 'ovl_En_Bom_Chu/z_en_bom_chu.c',
        'player': ACTORS / 'ovl_player_actor/z_player.c',
        'field': SOURCE / 'soh/Enhancements/randomizer/location_access/overworld/hyrule_field.cpp',
        'kak': SOURCE / 'soh/Enhancements/randomizer/location_access/overworld/kakariko.cpp',
        'sfm': SOURCE / 'soh/Enhancements/randomizer/location_access/overworld/sacred_forest_meadow.cpp',
        'catalog': SOURCE / 'archipelago/soh_extreme/SceneTransitionCatalog.json',
    }
    tests = (Path(__file__), TEMPLATE, Path(__file__).with_name('grotto_legacy_opening.inc'),
             Path(__file__).with_name('test_soul_logic_native.py'))
    digest = lambda path: sha256(path.read_bytes()).hexdigest()
    hashes = {str(path.relative_to(SOURCE)): digest(path) for path in paths.values()}
    texts = {key: path.read_text() for key, path in paths.items()}
    groups = {
        'LOGIC': ('logic', ['Logic::CanUse', 'Logic::BombchusEnabled', 'Logic::BombchuRefill',
                           'Logic::HasExplosives', 'Logic::BlastOrSmash', 'Logic::CanBreakRocks',
                           'Logic::CanOpenBombGrotto']),
        'DOOR': ('door', ['DoorAna_SetupAction', 'DoorAna_ShovelMissing', 'DoorAna_Init',
                         'DoorAna_Destroy', 'DoorAna_WaitClosed', 'DoorAna_WaitOpen',
                         'DoorAna_GrabPlayer', 'DoorAna_Update']),
        'SHOVEL': ('grotto', ['Grotto_ActorRequiresShovel']),
        'SOULS': ('souls', ['MegaHas', 'MegaSoul_CanUseRock', 'MegaSoul_CanUseCrate',
                           'IsMegaAnimalActor', 'IsMegaCrateActor', 'IsMegaRockActor',
                           'IsMegaScrubActor', 'IsMegaNpcSoulActor',
                           'MegaSoul_IsNpcSoulLocked', 'MegaSoul_CanInteractWithActor']),
        'COLLISION': ('collision', ['Collider_ResetACBase', 'Collider_ResetACInfo',
                                  'Collider_ResetCylinderAC', 'CollisionCheck_SetAC',
                                  'CollisionCheck_NoSharedFlags']),
        'BOMBCHU': ('bombchu', ['EnBomChu_Explode']),
    }
    functions = {name: function(texts[key], name)
                 for key, names in groups.values() for name in names}
    fragments = {token: '\n\n'.join(functions[name] for name in names)
                 for token, (_, names) in groups.items()}
    legacy_text = tests[2].read_text()
    fragments['LEGACY'] = function(legacy_text, 'Logic::CanOpenBombGrotto').replace(
        'Logic::CanOpenBombGrotto', 'Logic::LegacyCanOpenBombGrotto', 1)
    fragments['COLLIDER_DATA'] = re.search(
        r'static ColliderCylinderInit sCylinderInit = \{.*?\n\};', texts['door'], re.S)[0]
    fragments['GROTTO_ENTRANCES'] = re.search(
        r'static s16 sGrottoEntrances\[\] = \{.*?\n\};', texts['door'], re.S)[0]
    fragments['GROTTO_LOAD_TYPE'] = re.search(
        r'typedef struct \{.*?\} GrottoLoadInfo;', texts['grotto_header'], re.S)[0]
    fragments['GROTTO_LOAD_DATA'] = re.search(
        r'static const GrottoLoadInfo grottoLoadTable\[NUM_GROTTOS\] = \{.*?\n\};',
        texts['grotto'], re.S)[0]
    fragments['NUM_GROTTOS'] = str(fragments['GROTTO_LOAD_DATA'].count('.entranceIndex ='))
    fragments['MELEE_FLAGS'] = re.search(
        r'static u32 D_80854488\[\]\[2\] = \{.*?\n\};', texts['player'], re.S)[0]
    bomb_data = re.search(
        r'static ColliderJntSphElementInit sJntSphElementsInit\[1\] = \{.*?\n\};',
        texts['bomb'], re.S)[0]
    fragments['BOMB_MASK'] = re.search(r'ELEMTYPE_UNK0,\s*\{ (0x[0-9A-Fa-f]+),', bomb_data)[1]
    caller_rules = []
    for key in ('field', 'kak', 'sfm'):
        for target, rule in re.findall(r'^\s*ENTRANCE\((RR_\w+),\s*(.+)\),\s*$', texts[key], re.M):
            if 'logic->CanOpenBombGrotto()' in rule:
                caller_rules.append((str(paths[key].relative_to(SOURCE)), target, rule))
    assert {row[1] for row in caller_rules} == {
        'RR_HF_INSIDE_FENCE_GROTTO', 'RR_HF_COW_GROTTO', 'RR_HF_NEAR_KAK_GROTTO',
        'RR_HF_TEKTITE_GROTTO', 'RR_KAK_REDEAD_GROTTO', 'RR_SFM_WOLFOS_GROTTO'}
    assert len(caller_rules) == 6
    fragments['SOURCE_RULES'] = '\n'.join(
        '    {' + target + ', [](Rando::Logic* logic) { return ' + rule + '; }},'
        for _, target, rule in caller_rules)
    rows = [row for row in json.loads(texts['catalog']) if row['id'] == 11001806]
    assert len(rows) == 1
    assert (rows[0]['source_scene'], rows[0]['target_scene'], rows[0]['grotto'], rows[0]['content']) == (81, 62, 14, 229)
    fixture = TEMPLATE.read_text()
    all_text = fixture + '\n'.join(fragments.values())
    # Engine enum tags are isolated IO. Keep scene tags in the native signed
    # byte range used by GrottoLoadInfo; actual table identities are retained.
    scene_tags = sorted(set(re.findall(r'\bSCENE_[A-Z0-9_]+\b', all_text)))
    fragments['SCENES'] = 'enum { ' + ', '.join(scene_tags) + ' };'
    constants = set(re.findall(r'\b(?:ACTOR|RAND_INF|RG|RR|RT|RSK|RO|LOGIC|ITEM|UPG|ENTR)_[A-Z0-9_]+\b', all_text))
    constants = {key for key in constants if not key.startswith(('ACTOR_FLAG_', 'ACTORCAT_'))}
    fragments['CONSTANTS'] = 'enum { ' + ', '.join(sorted(constants)) + ', CONSTANT_COUNT };'
    for token, text in fragments.items():
        fixture = fixture.replace('@' + token + '@', text)
    assert not re.search(r'@[A-Z_]+@', fixture)
    with tempfile.TemporaryDirectory(prefix='soh-grotto-access-') as tmp:
        build = Path(tmp)
        cpp = build / 'grotto.cpp'
        cpp.write_text(fixture)
        binary = build / 'grotto'
        command = ['g++', '-std=c++20', '-Wall', '-Wextra', '-Werror',
                   '-Wno-unused-parameter', '-Wno-missing-field-initializers', '-Wno-narrowing',
                   '-g', '-O1', '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                   str(cpp), '-o', str(binary)]
        result = subprocess.run(command, text=True, capture_output=True)
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)
        env = dict(os.environ, ASAN_OPTIONS='detect_leaks=0:halt_on_error=1',
                   UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
        result = subprocess.run([str(binary)], text=True, capture_output=True, env=env)
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)
        counts = json.loads(result.stdout)
    assert hashes == {str(path.relative_to(SOURCE)): digest(path) for path in paths.values()}, \
        'Production source changed during validation'
    report = {
        'status': 'passed', **counts,
        'source_sha256': hashes,
        'test_sha256': {str(path.relative_to(SOURCE)): digest(path) for path in tests},
        'source_unchanged_during_tests': True,
        'captured_functions': list(functions),
        'captured_function_sha256': {name: sha256(text.encode()).hexdigest()
                                     for name, text in functions.items()},
        'captured_data_sha256': {token: sha256(fragments[token].encode()).hexdigest()
                                 for token in ('COLLIDER_DATA', 'GROTTO_LOAD_DATA', 'MELEE_FLAGS',
                                               'BOMB_MASK', 'SOURCE_RULES', 'LEGACY')},
        'physical_source_caller_rules': caller_rules,
        'native_attack_mask': '0x00000048',
        'accepted_attacks': ['explosives: 0x00000008', 'ordinary Hammer swing: 0x00000040'],
        'excluded_hammer_jumpslash': '0x40000000',
        'policy_retained': ['Shovel when shuffled', 'Rock/Boulder Soul when shuffled',
                            'Stone of Agony discovery', 'individual source-route blockers'],
        'legacy_source_sha256': re.search(r'Original logic.cpp SHA256: ([a-f0-9]{64})', legacy_text)[1],
        'sanitizers': ['AddressSanitizer', 'UndefinedBehaviorSanitizer'],
        'native_game_build': False, 'in_game_playthrough': False,
        'scope': 'Actual native CanOpenBombGrotto, CanBreakRocks, BlastOrSmash, HasExplosives, '
                 'CanUse, Bombchu enabled/refill and six physical source predicates; actual DoorAna '
                 'init/update/closed/open/entry actions, Shovel load-table lookup, Soul actor '
                 'classification, AC reset/registration and damage mask, and Bombchu bomb handoff. '
                 'Inventory and item-use permission storage, engine enum tags, camera, allocation, '
                 'contact geometry, scene transitions, audio and effects are isolated IO. The '
                 'original helper is used only to reproduce Grab-only false-positive logic. '
                 'No AP mapping/pool changes or native routing changes; no scene-asset geometry proof. '
                 'DoorAna itself lacks a Rock Soul gate; the existing broader logical Soul policy '
                 'is deliberately retained pending a separate complete physical blocker audit.',
        'elapsed_seconds': round(time.monotonic() - started, 3),
        'replay_command': 'python source/tools/tests/test_grotto_access_native.py '
                          '--report tests/grotto_access_1811_native.json',
        'external_dependencies': ['Python 3', 'g++ with C++20, AddressSanitizer and UndefinedBehaviorSanitizer'],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'status': report['status'], **counts, 'report': str(args.report)}))


if __name__ == '__main__':
    main()
