"""Compile actual DC room predicates, shutter setup and temporary switch flags.

Inventory/options, actor storage and engine callbacks are isolated IO. The
captured production functions and region blocks are compiled without edits.
This is not a full native build or a collision-geometry gameplay simulation.
"""
from hashlib import sha256
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time

from test_soul_logic_native import function
from test_water_native import assignment


SOURCE = Path(__file__).resolve().parents[2]
TEMPLATE = Path(__file__).with_name('dodongo_armos_native_tests.cpp.in')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    started = time.monotonic()
    paths = {
        'logic': SOURCE / 'soh/Enhancements/randomizer/logic.cpp',
        'dc': SOURCE / 'soh/Enhancements/randomizer/location_access/dungeons/dodongos_cavern.cpp',
        'shutter': SOURCE / 'src/overlays/actors/ovl_Door_Shutter/z_door_shutter.c',
        'shutter_header': SOURCE / 'src/overlays/actors/ovl_Door_Shutter/z_door_shutter.h',
        'flags': SOURCE / 'src/code/z_actor.c',
        'catalog': SOURCE / 'archipelago/soh_extreme/DungeonDoorCatalog.json',
    }
    texts = {name: path.read_text() for name, path in paths.items()}
    digest = lambda path: sha256(path.read_bytes()).hexdigest()
    hashes = {str(path.relative_to(SOURCE)): digest(path) for path in paths.values()}
    capture = {
        'CAN_USE': ('logic', 'Logic::CanUse'),
        'CAN_CLIMB_LADDER': ('logic', 'Logic::CanClimbLadder'),
        'SHUTTER_SETUP_ACTION': ('shutter', 'DoorShutter_SetupAction'),
        'SHUTTER_SETUP_DOOR': ('shutter', 'DoorShutter_SetupDoor'),
        'FLAGS_GET': ('flags', 'Flags_GetSwitch'),
        'FLAGS_SET': ('flags', 'Flags_SetSwitch'),
        'FLAGS_UNSET': ('flags', 'Flags_UnsetSwitch'),
    }
    fragments = {token: function(texts[key], name) for token, (key, name) in capture.items()}
    regions = ['RR_DODONGOS_CAVERN_' + name for name in
               ('ARMOS_ROOM', 'STAIRS_UPPER', 'ENTRANCE_SIDE_BRIDGE', 'BOMB_ROOM_LOWER')]
    fragments['REGIONS'] = '\n'.join(assignment(texts['dc'], region) for region in regions)
    fragments['SHUTTER_TYPES'] = re.search(r'typedef enum \{.*?\} DoorShutterType;',
                                          texts['shutter_header'], re.S)[0]
    doors = [row for row in json.loads(texts['catalog']) if row['id'] in (11201058, 11201060)]
    assert len(doors) == 2
    for row in doors:
        assert (row['source_scene'], row['room_to'], row['side'], row['actor'], row['params']) == (1, 5, 0, 46, 162)
    fragments['DOOR_FACTS'] = '\n'.join(
        '    {' + ', '.join(str(row[key]) for key in ('door', 'room_from', 'room_to', 'params')) + '},'
        for row in doors)
    fixture = TEMPLATE.read_text()
    all_text = fixture + '\n'.join(fragments.values())
    constants = set(re.findall(r'\b(?:RG|RC|RR|RT|RSK|LOGIC|ITEM|UPG|RE|ED|SCENE)_[A-Z0-9_]+\b', all_text))
    constants.discard('CONSTANT_COUNT')
    fragments['CONSTANTS'] = 'enum { ' + ', '.join(sorted(constants)) + ', CONSTANT_COUNT };'
    defined = set(re.findall(r'\b(\w+)\s*\([^;{}]*\)\s*(?:const\s*)?[;{]', fixture))
    called = set(re.findall(r'logic->(\w+)\s*\(', all_text))
    stubbed = sorted(called - defined - {'CanUse', 'CanClimbLadder'})
    fragments['OTHER_LOGIC_METHODS'] = '\n'.join(
        '    template<class... Args> bool ' + name + '(Args...) { return capabilities["' + name + '"]; }'
        for name in stubbed)
    for token, text in fragments.items():
        fixture = fixture.replace('@' + token + '@', text)
    assert not re.search(r'@[A-Z_]+@', fixture)
    with tempfile.TemporaryDirectory(prefix='soh-dc-armos-') as tmp:
        build = Path(tmp)
        source = build / 'dodongo_armos.cpp'
        source.write_text(fixture)
        binary = build / 'dodongo_armos'
        command = ['g++', '-std=c++20', '-Wall', '-Wextra', '-Werror', '-Wno-parentheses',
                   '-g', '-O1', '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                   str(source), '-o', str(binary)]
        compiled = subprocess.run(command, capture_output=True, text=True)
        if compiled.returncode:
            raise RuntimeError(compiled.stdout + compiled.stderr)
        env = dict(os.environ, ASAN_OPTIONS='detect_leaks=0:halt_on_error=1',
                   UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
        result = subprocess.run([str(binary)], capture_output=True, text=True, env=env)
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)
        counts = json.loads(result.stdout)
    assert hashes == {str(path.relative_to(SOURCE)): digest(path) for path in paths.values()}, \
        'Production source changed during native fixture'
    test_paths = (Path(__file__), TEMPLATE, Path(__file__).with_name('test_soul_logic_native.py'),
                  Path(__file__).with_name('test_water_native.py'))
    report = {
        'status': 'passed', **counts, 'source_sha256': hashes,
        'test_sha256': {str(path.relative_to(SOURCE)): digest(path) for path in test_paths},
        'captured_functions': [name for _, name in capture.values()],
        'captured_region_blocks': regions,
        'captured_fragment_sha256': {key: sha256(text.encode()).hexdigest() for key, text in fragments.items()},
        'sanitizers': ['AddressSanitizer', 'UndefinedBehaviorSanitizer'],
        'engine_io_isolated': True, 'native_game_build': False, 'in_game_playthrough': False,
        'elapsed_seconds': round(time.monotonic() - started, 3),
        'scope': 'Actual native Armos/adjacent region predicates, CanUse, CanClimbLadder, '
                 'DoorShutter_SetupDoor and temporary Flags_Get/Set/UnsetSwitch functions. '
                 'Source actor data supplies both switch0x22 door sides. No geometry measurement.',
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'status': report['status'], **counts, 'report': str(args.report)}))


if __name__ == '__main__':
    main()
