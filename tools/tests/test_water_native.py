"""Compile native Water Temple rules and the local GTG underwater Finder gate.

Production region initializers, CanUse, WaterLevel and Finder gate functions
are compiled unchanged. Inventory, options and region storage are test IO;
this is not a collision simulation or a complete game build.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
import time

from test_soul_logic_native import function


SOURCE = Path(__file__).resolve().parents[2]
RANDO = SOURCE / 'soh/Enhancements/randomizer'
TEMPLATE = Path(__file__).with_name('water_native_tests.cpp.in')


def assignment(text, region):
    start = text.index('    areaTable[' + region + '] = Region(')
    end = text.index('\n    });', start) + len('\n    });')
    return text[start:end]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    started = time.monotonic()
    paths = {
        'logic': RANDO / 'logic.cpp', 'logic_header': RANDO / 'logic.h',
        'water': RANDO / 'location_access/dungeons/water_temple.cpp',
        'gtg': RANDO / 'location_access/dungeons/gerudo_training_ground.cpp',
        'finder': RANDO / 'randomizer_check_tracker.cpp',
        'finder_map': SOURCE / 'soh/Network/Archipelago/ArchipelagoEnemyFinderMap.inc',
        'enemy_map': SOURCE / 'archipelago/soh_extreme/EnemyRoomMap.json',
        'catalog': SOURCE / 'archipelago/soh_extreme/EntranceCatalog.json',
    }
    read = lambda path: path.read_text(encoding='utf-8-sig')
    texts = {name: read(path) for name, path in paths.items()}
    digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    hashes = {str(path.relative_to(SOURCE)): digest(path) for path in paths.values()}
    fragments = {
        'CAN_USE': function(texts['logic'], 'Logic::CanUse'),
        'WATER_MODE': function(texts['logic'], 'Logic::WaterTempleDoorsShuffled'),
        'WATER_LEVEL': function(texts['logic'], 'Logic::WaterLevel'),
        'WATER_REGIONS': function(texts['water'], 'RegionTable_Init_WaterTemple'),
        'GTG_REGION': assignment(texts['gtg'], 'RR_GERUDO_TRAINING_GROUND_UNDERWATER'),
        'FINDER_MELEE': function(texts['finder'], 'EnemyFinderMelee'),
        'FINDER_GATE': function(texts['finder'], 'EnemyFinderEncounterGate'),
        'FINDER_TYPES': texts['finder'].split('enum EnemyFinderCombat', 1)[1].split(
            '// Generated from the finite per-placement', 1)[0],
        'FINDER_MAP': texts['finder_map'],
    }
    fragments['FINDER_TYPES'] = 'enum EnemyFinderCombat' + fragments['FINDER_TYPES']
    fixture = TEMPLATE.read_text()
    all_text = fixture + '\n'.join(fragments.values())
    constants = set(re.findall(
        r'\b(?:RG|RC|RCAREA|RR|RT|RSK|RO|RAND_INF|ACTOR|SCENE|RE|ED|WL|LOGIC|ITEM|UPG|RECOIL)_[A-Z0-9_]+\b',
        all_text))
    constants.update({'WATER_TEMPLE'})
    constants.discard('CONSTANT_COUNT')
    fragments['CONSTANTS'] = 'enum { ' + ', '.join(sorted(constants)) + ', CONSTANT_COUNT };'
    defined = set(re.findall(r'\b(\w+)\s*\([^;{}]*\)\s*(?:const\s*)?[;{]', fixture))
    called = set(re.findall(r'(?:logic|enemyLogic)->(\w+)\s*\(', all_text))
    stubbed = sorted(called - defined - {'WaterTempleDoorsShuffled', 'WaterLevel', 'CanUse'})
    fragments['OTHER_LOGIC_METHODS'] = '\n'.join(
        '    template<class... Args> bool ' + name + '(Args...) { return capabilities["' + name + '"]; }'
        for name in stubbed)
    for token, text in fragments.items():
        fixture = fixture.replace('@' + token + '@', text)
    assert not re.search(r'@[A-Z_]+@', fixture)

    # Bind the exact physical placements independently of the generated Finder
    # condition. The pool floor and dry doorway must never share one gate.
    enemies = json.loads(texts['enemy_map'])
    for location in range(9800443, 9800447):
        enemy = enemies[str(location)]
        assert enemy['scene'] == 11 and enemy['room'] == 9
        assert enemy['spawn_position'][1] in (-960, -961)
    arrival = next(row for row in json.loads(texts['catalog']) if row['id'] == 9621)
    assert arrival['scene'] == 11 and arrival['room'] == 9 and arrival['position'][1] == -240

    with tempfile.TemporaryDirectory(prefix='soh-water-native-') as tmp:
        build = Path(tmp)
        source = build / 'water_native.cpp'
        source.write_text(fixture)
        binary = build / 'water_native'
        command = ['g++', '-std=c++20', '-Wall', '-Wextra', '-Werror',
                   '-Wno-unknown-pragmas', '-Wno-parentheses', '-g', '-O1',
                   '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                   str(source), '-o', str(binary)]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)
        env = dict(os.environ, ASAN_OPTIONS='detect_leaks=0:halt_on_error=1',
                   UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
        result = subprocess.run([str(binary)], capture_output=True, text=True, env=env)
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)
        counts = json.loads(result.stdout)
    assert hashes == {str(path.relative_to(SOURCE)): digest(path) for path in paths.values()}, \
        'Production source changed during validation'
    report = {
        'status': 'passed', **counts,
        'source_sha256': hashes,
        'test_sha256': {str(path.relative_to(SOURCE)): digest(path) for path in (
            Path(__file__), TEMPLATE, Path(__file__).with_name('test_soul_logic_native.py'))},
        'captured_fragment_sha256': {key: hashlib.sha256(value.encode()).hexdigest()
                                    for key, value in fragments.items()},
        'sanitizers': ['AddressSanitizer', 'UndefinedBehaviorSanitizer'],
        'captured_functions': ['Logic::CanUse', 'Logic::WaterTempleDoorsShuffled', 'Logic::WaterLevel',
                               'RegionTable_Init_WaterTemple', 'EnemyFinderMelee',
                               'EnemyFinderEncounterGate'],
        'captured_region_blocks': ['RR_GERUDO_TRAINING_GROUND_UNDERWATER'],
        'engine_io_isolated': True, 'native_game_build': False, 'in_game_playthrough': False,
        'scope': 'Actual native Water Temple region initializer, item usability, water-control '
                 'helper and local GTG Finder encounter gate; complete generated enemy gate table. '
                 'Inventory/options/region storage are isolated. No collision geometry simulation.',
        'elapsed_seconds': round(time.monotonic() - started, 3),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'status': report['status'], **counts, 'report': str(args.report)}))


if __name__ == '__main__':
    main()
