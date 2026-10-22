"""Package the include-only 1.8.10 correction as complete source files."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

from prepare_seed_safety_1810_delivery import inventory
from prepare_source_delivery import write_source_archive

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'source'
BASE = ROOT / 'delivery/SOH-EXTREME-1.8.10-source-files.zip'
BASE_SHA = '26dfe91e02b7d494d7f54fac01afb9bf18fc5beb836fcff398a369594cb0660a'
PACKAGE = ROOT / 'delivery/SOH-EXTREME-1.8.10-buildfix-source-files'
ARCHIVE = PACKAGE.parent / (PACKAGE.name + '.zip')
LOGIC = 'soh/Enhancements/randomizer/logic.cpp'
INCLUDE = b'#include <libultraship/bridge/consolevariablebridge.h>\r\n'


def sha(value: bytes):
    return hashlib.sha256(value).hexdigest()


def read(path: Path):
    return json.loads(path.read_bytes())


def prepare():
    assert sha(BASE.read_bytes()) == BASE_SHA
    changed, _, _, _ = inventory()
    with zipfile.ZipFile(BASE) as base:
        old_manifest = json.loads(base.read('SOURCE_FILES.json'))
        assert len(old_manifest['files']) == 175
        assert set(changed) == {row['path'] for row in old_manifest['files']}
        assert (SOURCE / LOGIC).read_bytes() == INCLUDE + base.read(LOGIC)
        contents = {}
        for name in base.namelist():
            assert not name.endswith('/')
            target = name
            if name.startswith('validation/'):
                target = 'validation/base_1.8.10/' + name[len('validation/'):]
            elif name in ('README.txt', 'VALIDATION.txt', 'SOURCE_FILES.json'):
                target = 'validation/base_1.8.10/' + name
            contents[target] = base.read(name)
        manifest = json.loads(base.read('SOURCE_FILES.json'))
        manifest['build_fix'] = 'Direct console-variable bridge include for logic.cpp C3861.'
        for row in manifest['files']:
            name = row['path']
            current = (SOURCE / name).read_bytes()
            if name != LOGIC:
                assert current == base.read(name), ('unexpected source change', name)
            else:
                row['size_bytes'] = len(current)
                row['sha256'] = sha(current)
                contents[name] = current
        assert contents['soh_extreme.apworld'] == (SOURCE / 'archipelago/soh_extreme.apworld').read_bytes()
        assert contents['soh_extreme.apworld'] == contents['archipelago/soh_extreme.apworld']
        contents['SOURCE_FILES.json'] = (json.dumps(manifest, indent=2) + '\n').encode()
        old_logic_sha = sha(base.read(LOGIC))
    for name, data in contents.items():
        target = PACKAGE / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    scope = (
        'These reports and documents are retained from the original 1.8.10 release.\n'
        'Their source hashes describe that earlier snapshot; they have not been rewritten.\n'
        'This build fix adds one declaration-header include to logic.cpp and changes no function body.\n'
        'Every other replacement source file and both APWorld copies are byte-identical.\n'
        'Current compile-fix validation is in the parent validation directory.\n'
        'The original 1.8.9 uploaded seed still fails the corrected rules as documented in inputs/.\n'
    )
    (PACKAGE / 'validation/base_1.8.10/SCOPE.txt').write_text(scope)
    report = {
        'status': 'passed', 'version': '1.8.10', 'build_fix': 'console-variable-header',
        'base_archive_sha256': BASE_SHA, 'complete_source_files': len(manifest['files']),
        'only_production_change': LOGIC, 'only_prepend_include_changed': True,
        'function_bodies_unchanged': True, 'original_crlf_bytes_preserved': True,
        'previous_logic_sha256': old_logic_sha, 'current_logic_sha256': sha((SOURCE / LOGIC).read_bytes()),
        'source_sha256': {row['path']: row['sha256'] for row in manifest['files']},
        'manifest_sha256': sha((PACKAGE / 'SOURCE_FILES.json').read_bytes()),
        'apworld_sha256': sha((PACKAGE / 'soh_extreme.apworld').read_bytes()),
        'apworld_unchanged_from_1_8_10': True, 'all_previous_source_files_retained': True,
        'yaml_unchanged_from_1_8_10': True,
    }
    (ROOT / 'tests/compile_fix_1810_source_completeness.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'status': 'prepared', 'source_files': len(manifest['files']), 'source_changes': 1,
                      'apworld_unchanged': True, 'package': str(PACKAGE)}))


def finalize():
    manifest = read(PACKAGE / 'SOURCE_FILES.json')
    completeness = read(ROOT / 'tests/compile_fix_1810_source_completeness.json')
    build = read(ROOT / 'tests/compile_fix_1810_source_build_validation.json')
    probe_path = ROOT / 'tests/compile_fix_1810_cvar_declaration.json'
    probe = read(probe_path)
    assert completeness['status'] == build['status'] == probe['status'] == 'passed'
    assert probe['cases']['without_bridge_include']['returncode'] != 0
    assert 'CVarGetInteger' in probe['cases']['without_bridge_include']['stderr']
    assert probe['cases']['with_production_bridge_include']['returncode'] == 0
    assert probe['source_unchanged_during_tests']
    assert probe['current_water_helper_sha256'] == probe['retained_water_helper_sha256']
    assert sha((PACKAGE / 'validation/base_1.8.10/water_1810_native.json').read_bytes()) == probe['retained_water_report_sha256']
    assert completeness['manifest_sha256'] == build['manifest_sha256'] == sha((PACKAGE / 'SOURCE_FILES.json').read_bytes())
    assert completeness['apworld_sha256'] == build['apworld_sha256'] == sha((PACKAGE / 'soh_extreme.apworld').read_bytes())
    for row in manifest['files']:
        name = row['path']
        assert row['sha256'] == sha((SOURCE / name).read_bytes()) == sha((PACKAGE / name).read_bytes()), name
    for name, digest in build['helper_sha256'].items():
        assert sha((PACKAGE / name).read_bytes()) == digest
    # The probe owns the real-header compilation and reproduces the missing
    # declaration separately. It binds its actual source, fixtures and headers.
    for name, digest in probe['source_sha256'].items():
        assert sha((ROOT / name).read_bytes()) == digest, name
    for name, digest in probe['fixture_sha256'].items():
        assert sha((ROOT / name).read_bytes()) == digest, name
    validation = PACKAGE / 'validation'
    evidence_names = ('compile_fix_1810_source_completeness.json',
                      'compile_fix_1810_source_build_validation.json',
                      'compile_fix_1810_cvar_declaration.json',
                      'compile_fix_1810_source_build_check.py',
                      'compile_fix_1810_cvar_declaration.py',
                      'entrance_184_source_build_probe.ps1')
    for name in evidence_names:
        shutil.copyfile(ROOT / 'tests' / name, validation / name)
    for name in probe['fixture_sha256']:
        path = ROOT / name
        if path.name == 'compile_fix_1810_cvar_declaration.py':
            continue
        relative = Path(name)
        assert not relative.is_absolute() and '..' not in relative.parts
        if relative.parts[0] == 'tests':
            relative = relative.relative_to('tests')
        destination = validation / 'compile_probe_inputs' / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
    shutil.copyfile(Path(__file__), validation / Path(__file__).name)
    summary = {
        'status': 'passed', 'version': '1.8.10', 'build_fix': 'console-variable-header',
        'utc': datetime.now(timezone.utc).isoformat(),
        'source_sha256': completeness['source_sha256'],
        'manifest_sha256': completeness['manifest_sha256'],
        'apworld_sha256': completeness['apworld_sha256'],
        'base_archive_sha256': BASE_SHA,
        'only_production_change': LOGIC, 'function_bodies_unchanged': True,
        'current_reports': {name: sha((ROOT / 'tests' / name).read_bytes()) for name in evidence_names[:3]},
        'native_game_build': False,
        'scope': 'Include-only source repair, real bridge-header declaration probe, and actual build-helper source preflight. Prior rule/runtime test evidence is retained separately and was not rerun.',
    }
    (validation / 'compile_fix_1810_release_validation.json').write_text(json.dumps(summary, indent=2) + '\n')
    (PACKAGE / 'README.txt').write_text(r'''SOH-EXTREME 1.8.10 - Complete source files, compile fix
=====================================================

This cumulative ZIP fixes the Windows compiler error:
  logic.cpp(1633): C3861: 'CVarGetInteger': identifier not found

logic.cpp now directly includes the existing project header:
  <libultraship/bridge/consolevariablebridge.h>

This is the same header used by neighboring randomizer source files. It makes
the console-variable declaration available to WaterTempleDoorsShuffled().
No function body or gameplay rule changed. The version remains 1.8.10, and
the APWorld and YAML are byte-identical to the original 1.8.10 release.

CONTENTS
--------
All 175 complete replacement source files are included, with all prior fixes,
the matching APWorld, YAML, and clean-build helpers. SOURCE_FILES.json has the
updated logic.cpp hash so the helper accepts the corrected complete file.

INSTALL AND BUILD
-----------------
1. Merge soh\, src\, archipelago\ and tools\ into your complete checkout,
   replacing the corresponding files. Replace SOURCE_FILES.json in the root
   as well, and copy BUILD_RELEASE.cmd and BUILD_RELEASE.ps1 there.
2. For your E:\test\bb checkout, run:

   cd /d E:\test\bb
   BUILD_RELEASE.cmd -RepositoryPath "E:\test\bb" -BuildDirectory "build-vs"

   The helper verifies the sources, performs the clean Release build, and
   prints the executable path. Use your actual paths if different.
3. If your APWorld is already 1.8.10, this compile-only repair needs no APWorld
   change or new seed. For an older installation, the included APWorld goes
   in C:\ProgramData\Archipelago\custom_worlds\soh_extreme.apworld.

The previously audited 1.8.9 seed still needs regeneration with 1.8.10 because
of its invalid progression route. This compile fix does not change that audit.

VALIDATION
----------
Current declaration/compiler and source-package reports are in validation/.
Original 1.8.10 rule/runtime/seed evidence and detailed release notes are kept
under validation/base_1.8.10/. Those reports retain their original source
hashes; they are historical execution evidence, not newly rerun tests.
The source comparison proves this correction adds only the declaration-header
include and preserves every original logic.cpp byte following it.

The earlier Water fixture supplied CVarGetInteger as test I/O before compiling
extracted function bodies. That tested behavior but missed the production
translation unit's absent include. The targeted declaration check covers this
specific omission against the real dependency header.

The partial checkout still cannot support a complete Windows game build in
this environment. The scoped compiler check and source preflight do not claim
an MSBuild run or an in-game playthrough.
''')
    (PACKAGE / 'VALIDATION.txt').write_text(
        'SOH-EXTREME 1.8.10 compile-fix validation: PASSED\n'
        '175 complete source files; one production include added; function bodies unchanged.\n'
        'Actual console-variable declaration probe and build-helper source preflight passed.\n'
        'The original APWorld, YAML and all other source files are byte-identical.\n'
        'Prior 1.8.10 test reports are under validation/base_1.8.10/.\n'
        'No full native Windows build or gameplay test was performed.\n')
    contents = {p.relative_to(PACKAGE).as_posix(): p.read_bytes() for p in PACKAGE.rglob('*') if p.is_file()}
    assert not any(name.startswith('payload/') or name.endswith(('.patch', '.diff')) for name in contents)
    write_source_archive(ARCHIVE, contents, datetime.now(timezone.utc))
    result = {'status': 'passed', 'archive': str(ARCHIVE), 'sha256': sha(ARCHIVE.read_bytes()),
              'size_bytes': ARCHIVE.stat().st_size, 'source_files': 175, 'archive_files': len(contents),
              'zip_crc_and_inventory_verified': True, 'patch_files': 0}
    (ROOT / 'tests/compile_fix_1810_source_zip_validation.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('prepare', 'finalize'))
    args = parser.parse_args()
    {'prepare': prepare, 'finalize': finalize}[args.action]()
