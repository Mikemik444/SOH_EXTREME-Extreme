"""Compile the actual Water helper against the official CVar declaration header.

This intentionally does not link the game or replace the existing Water behavior
fixture. The negative variant omits only the CVar bridge include; the positive
variant uses the direct include present in production logic.cpp. Neither variant
declares or defines CVarGetInteger itself.
"""

from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / 'source')
    parser.add_argument('--dependencies', type=Path,
                        default=ROOT / 'tests/water_cvar_bridge_1810_dependencies')
    parser.add_argument('--retained-report', type=Path,
                        default=ROOT / 'tests/water_1810_native.json')
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    source = args.source.resolve()
    dependencies = args.dependencies.resolve()
    sys.path.insert(0, str(source / 'tools/tests'))
    from test_soul_logic_native import function

    production = source / 'soh/Enhancements/randomizer/logic.cpp'
    production_header = source / 'soh/Enhancements/randomizer/logic.h'
    archipelago_header = source / 'soh/Network/Archipelago/ArchipelagoC.h'
    cvar_prefixes = source / 'soh/cvar_prefixes.h'
    before = production.read_bytes()
    text = before.decode('utf-8-sig').replace('\r\n', '\n')
    include = '#include <libultraship/bridge/consolevariablebridge.h>'
    assert text.count(include) == 1, 'Production must include its CVar declaration directly'
    assert before.startswith((include + '\r\n').encode()), 'Unexpected build-fix edit shape'

    helper = function(text, 'Logic::WaterTempleDoorsShuffled')
    member = re.search(r'^\s*bool WaterTempleDoorsShuffled\(\);',
                       production_header.read_text(), re.M).group().strip()
    helper_hash = hashlib.sha256(helper.encode()).hexdigest()
    retained = json.loads(args.retained_report.read_text())
    retained_hash = retained['captured_fragment_sha256']['WATER_MODE']
    assert helper_hash == retained_hash, 'Previously tested Water helper changed'
    without_include_hash = hashlib.sha256(before[len((include + '\r\n').encode()):]).hexdigest()
    assert without_include_hash == retained['source_sha256'][
        'soh/Enhancements/randomizer/logic.cpp'], 'Change exceeds one added include line'

    provenance_path = dependencies / 'provenance.json'
    provenance = json.loads(provenance_path.read_text())
    for relative, evidence in provenance['files'].items():
        path = dependencies / relative
        assert digest(path) == evidence['sha256'], f'Dependency checksum differs: {relative}'
        data = path.read_bytes()
        git_hash = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\x00' + data).hexdigest()
        assert git_hash == evidence['git_blob_sha1'], f'Dependency blob differs: {relative}'

    # The project normally supplies CVAR_PREFIX_RANDOMIZER_SETTING from build
    # configuration. Its value is immaterial to declaration checking. The real
    # project macro and the real AP/CVar headers supply all called API declarations.
    prefix = '\n'.join([
        '#define CVAR_PREFIX_RANDOMIZER_SETTING "declaration_probe"',
        '#include "soh/cvar_prefixes.h"',
        '#include "soh/Network/Archipelago/ArchipelagoC.h"',
    ]) + '\n'
    wrapper = 'namespace Rando {\nclass Logic { public: ' + member + ' };\n'
    line_number = text[:text.index(helper)].count('\n') + 1
    body = wrapper + f'#line {line_number} "soh/Enhancements/randomizer/logic.cpp"\n' + helper + '\n}\n'
    variants = {
        'without_bridge_include': prefix + body,
        'with_production_bridge_include': include + '\n' + prefix + body,
    }
    results = {}
    with tempfile.TemporaryDirectory(prefix='soh-water-cvar-declaration-') as temp:
        build = Path(temp)
        for name, unit in variants.items():
            path = build / (name + '.cpp')
            path.write_text(unit)
            command = ['g++', '-std=c++20', '-Wall', '-Wextra', '-Werror', '-fsyntax-only',
                       '-I', str(source), '-I', str(dependencies / 'include'), str(path)]
            run = subprocess.run(command, capture_output=True, text=True)
            results[name] = {
                'returncode': run.returncode,
                'stdout': run.stdout.replace(temp, '$PROBE'),
                'stderr': run.stderr.replace(temp, '$PROBE'),
                'translation_unit_sha256': hashlib.sha256(unit.encode()).hexdigest(),
                'command': [part.replace(temp, '$PROBE') for part in command],
            }
    negative = results['without_bridge_include']
    assert negative['returncode'] != 0, 'Negative missing-include probe unexpectedly compiled'
    assert 'CVarGetInteger' in negative['stderr'] and 'not declared' in negative['stderr'], \
        'Negative probe failed for something other than the missing CVar declaration'
    positive = results['with_production_bridge_include']
    assert positive['returncode'] == 0, positive['stdout'] + positive['stderr']
    assert production.read_bytes() == before, 'Production changed during compile verification'
    report = {
        'status': 'passed',
        'scope': 'Compile-only declaration regression for the actual production '
                 'Logic::WaterTempleDoorsShuffled function with real official CVar '
                 'and current Archipelago declaration headers. No fake CVar declaration '
                 'or implementation is supplied.',
        'cases': results,
        'source_sha256': {str(path.relative_to(ROOT)): digest(path) for path in (
            production, production_header, archipelago_header, cvar_prefixes)},
        'fixture_sha256': {str(path.relative_to(ROOT)): digest(path) for path in (
            Path(__file__), provenance_path, source / 'tools/tests/test_soul_logic_native.py',
            *(dependencies / relative for relative in provenance['files']))},
        'dependency_provenance': provenance,
        'dependency_provenance_sha256': digest(provenance_path),
        'retained_water_report_sha256': digest(args.retained_report),
        'retained_water_helper_sha256': retained_hash,
        'current_water_helper_sha256': helper_hash,
        'previous_full_logic_sha256': without_include_hash,
        'exact_change': 'One added CRLF include line; all pre-existing logic.cpp bytes unchanged.',
        'source_unchanged_during_tests': True,
        'compiler': subprocess.run(['g++', '--version'], capture_output=True,
                                   text=True, check=True).stdout.splitlines()[0],
        'native_windows_build': False,
        'linked_game': False,
        'gameplay_tests_rerun': False,
        'limitations': [
            'The surrounding Logic class is a minimal shell using its production member declaration.',
            'The CVar prefix value is a string supplied for compile checking; runtime settings are not evaluated.',
            'The official header commit is pinned for this probe; the partial upload does not contain the user dependency lock.',
            'This validates the reported missing declaration and fixed call, not the full logic.cpp translation unit or a Windows build.',
        ],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'status': report['status'], 'report': str(args.report),
                      'negative_missing_declaration': negative['returncode'] != 0,
                      'fixed_real_header_compiles': positive['returncode'] == 0,
                      'helper_unchanged': helper_hash == retained_hash}))


if __name__ == '__main__':
    main()
