"""Compile the complete production Fishing C translation unit to an object.

Needs the complete native checkout, generated asset headers, and libultraship
headers. This is not a complete game link, MSVC build or live-engine test.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source-root', type=Path, required=True)
parser.add_argument('--compiler', default='clang')
parser.add_argument('--ship-root', type=Path)
parser.add_argument('--report', type=Path, required=True)
args = parser.parse_args()
root = args.source_root.resolve()
ship = args.ship_root.resolve() if args.ship_root else root / 'libultraship'
compiler = shutil.which(args.compiler)
if compiler is None:
    parser.error(f'Compiler not found: {args.compiler}')
source = root / 'src/overlays/actors/ovl_Fishing/z_fishing.c'
if not source.is_file():
    parser.error(f'Production source not found: {source}')
report = args.report.resolve()
report.parent.mkdir(parents=True, exist_ok=True)
obj = report.with_suffix('.o')
log = report.with_suffix('.compiler.log')
cmd = [compiler, '-std=c11', '-fms-extensions',
       '-Werror=implicit-function-declaration', '-Werror=implicit-int',
       '-Wno-error=incompatible-pointer-types', '-Wno-error=int-conversion',
       '-DLOG_LEVEL_GAME_PRINTS=6', '-DCVAR_PREFIX_ENHANCEMENT="gEnhancements"']
for directory in (root, root/'include', root/'src', root/'soh', root/'assets',
                  ship/'include', ship/'include/ship/utils/binarytools'):
    cmd.extend(['-I', str(directory)])
cmd.extend(['-c', str(source), '-o', str(obj)])
completed = subprocess.run(cmd, cwd=root, text=True, capture_output=True, timeout=60)
log.write_text(completed.stdout + completed.stderr)
result = {
    'scope': __doc__,
    'compiler': subprocess.run([compiler, '--version'], text=True, capture_output=True).stdout.splitlines()[0],
    'command': cmd,
    'returncode': completed.returncode,
    'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
    'object_size': obj.stat().st_size if obj.exists() else 0,
    'diagnostic_log': log.name,
    'passed': completed.returncode == 0 and obj.is_file() and obj.stat().st_size > 0,
}
report.write_text(json.dumps(result, indent=2))
print(json.dumps(result, indent=2))
raise SystemExit(0 if result['passed'] else 1)
