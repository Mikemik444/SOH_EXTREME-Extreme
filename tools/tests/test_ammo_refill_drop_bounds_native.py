"""Exercise the real repeat-enemy drop selector at every native table cell.

Table data, ordinary drop conversion and the complete production drop function
are compiled. RNG, inventory, flags, actor allocation and audiovisual IO are
controlled. The retained legacy selector calculates invalid indices safely.
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
TEMPLATE = Path(__file__).with_name('ammo_refill_drop_bounds_native_tests.cpp.in')
LEGACY = Path(__file__).with_name('ammo_refill_drop_bounds_legacy.inc')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    start = time.monotonic()
    paths = {
        'drop': SOURCE / 'src/code/z_en_item00.c',
        'policy': SOURCE / 'soh/Enhancements/randomizer/BombchuRefillPolicy.h',
        'rng': SOURCE / 'src/code/code_800FD970.c',
    }
    texts = {name: path.read_text() for name, path in paths.items()}
    digest = lambda path: sha256(path.read_bytes()).hexdigest()
    hashes = {str(path.relative_to(SOURCE)): digest(path) for path in paths.values()}
    tests = (Path(__file__), TEMPLATE, LEGACY, Path(__file__).with_name('test_soul_logic_native.py'))
    test_hashes = {str(path.relative_to(SOURCE)): digest(path) for path in tests}
    captured = {name: function(texts['drop'], name) for name in
        ('EnItem00_ConvertBombDropToBombchu', 'EnItem00_ConvertOrdinaryBombDrop',
         'func_8001F404', 'Item_DropCollectibleRandom')}
    data = {}
    lengths = {}
    for name in ('sItemDropIds', 'sDropQuantities'):
        data[name] = re.search(r'static u8 ' + name + r'\[\] = \{.*?\n\};', texts['drop'], re.S)[0]
        body = data[name][data[name].index('{') + 1:data[name].rindex('}')]
        lengths[name] = len([entry for entry in body.split(',') if entry.strip()])
    assert lengths == {'sItemDropIds': 240, 'sDropQuantities': 244}
    assert lengths['sItemDropIds'] // 16 == lengths['sDropQuantities'] // 16 == 15
    assert lengths['sItemDropIds'] % 16 == 0
    legacy = '\n'.join(line for line in LEGACY.read_text().splitlines() if not line.startswith('//'))
    assert 'Rand_ZeroOne() * 16.0f' in legacy
    native_rng = function(texts['rng'], 'Rand_ZeroOne').replace('Rand_ZeroOne', 'Native_Rand_ZeroOne', 1)
    # Invert the actual engine LCG so its next value is 0xFFFFFFFF, producing
    # the maximum native 23-bit mantissa through the actual Rand_ZeroOne body.
    seed = ((0xFFFFFFFF - 1013904223) * pow(1664525, -1, 1 << 32)) % (1 << 32)
    fragments = {
        'DATA': '\n\n'.join(data.values()),
        'CONVERSIONS': '\n\n'.join(value for name, value in captured.items() if name != 'Item_DropCollectibleRandom'),
        'DROP': captured['Item_DropCollectibleRandom'],
        'POLICY': texts['policy'].replace('#pragma once', ''),
        'LEGACY_SELECTOR': legacy,
        'NATIVE_RNG': native_rng,
        'RNG_MAX_SEED': str(seed) + 'u',
    }
    template = TEMPLATE.read_text()
    constants = sorted(set(re.findall(r'\b(?:ITEM00|ITEM|UPG|ACTOR|RSK|RO)_[A-Z0-9_]+\b',
                                     template + '\n'.join(fragments.values()))) -
                       {'ACTOR_FLAG_UPDATE_CULLING_DISABLED', 'ITEM_NONE'})
    fragments['CONSTANTS'] = '\n'.join(f'constexpr int {name}={i};' for i, name in enumerate(constants))
    fragments['CONSTANTS'] += f'\nconstexpr int CONSTANT_COUNT={len(constants)};'
    for name, value in fragments.items():
        template = template.replace('@' + name + '@', value)
    assert not re.search(r'@[A-Z_]+@', template)
    with tempfile.TemporaryDirectory(prefix='soh-ammo-drop-bounds-') as tmp:
        cpp, binary = Path(tmp) / 'drops.cpp', Path(tmp) / 'drops'
        cpp.write_text(template)
        result = subprocess.run(['g++', '-std=c++20', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
            '-Wno-unused-parameter', '-Wno-unused-variable', '-Wno-missing-field-initializers',
            '-fno-strict-aliasing', '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
            str(cpp), '-o', str(binary)], text=True, capture_output=True)
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
        'source_unchanged_during_tests': True,
        'table_entries': lengths, 'complete_rows_in_each_table': 15,
        'quantity_trailing_bytes': 4,
        'captured_function_sha256': {name: sha256(value.encode()).hexdigest() for name, value in captured.items()},
        'captured_table_sha256': {name: sha256(value.encode()).hexdigest() for name, value in data.items()},
        'legacy_source_sha256': re.search(r'Original z_en_item00.c SHA256: ([a-f0-9]{64})', LEGACY.read_text())[1],
        'sanitizers': ['AddressSanitizer', 'UndefinedBehaviorSanitizer'],
        'native_game_build': False, 'in_game_playthrough': False,
        'scope': 'Actual complete Item_DropCollectibleRandom, native ID/quantity tables, ordinary '
                 'drop and Bombchu conversion functions, Bombchu ownership policy and Rand_ZeroOne '
                 'endpoint generation. All240 valid cells run through ordinary and direct-pickup '
                 'repeat-enemy branches for both ages. Native inventory/options, geometry-free '
                 'actor allocation and audiovisual IO are controlled. Legacy indices240..255 '
                 'are demonstrated by executing the retained selector without unsafe reads.',
        'elapsed_seconds': round(time.monotonic() - start, 3),
        'replay_command': 'python source/tools/tests/test_ammo_refill_drop_bounds_native.py '
                          '--report tests/ammo_refill_drop_bounds_1812_native.json',
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'status': 'passed', **counts, 'report': str(args.report)}))


if __name__ == '__main__':
    main()
