"""Build/run the real APCpp parser regression without connecting to a server.

Run from an x64 Visual Studio developer shell. --apcpp-build is the directory
containing the freshly built matching APCpp.lib and APCpp.dll (usually Release).
"""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--apcpp-source', type=Path, required=True)
p.add_argument('--apcpp-build', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
out = a.output.resolve()
out.mkdir(parents=True, exist_ok=True)
source = Path(__file__).with_suffix('.cpp')
library = a.apcpp_build.resolve()
dll = library / 'APCpp.dll'
exe = out / 'connection_protocol.exe'
build = subprocess.run([
    'cl', '/nologo', '/std:c++17', '/EHsc', '/MD', '/UNDEBUG',
    '/I', str(a.apcpp_source.resolve()), str(source), str(library / 'APCpp.lib'),
    '/Fo' + str(out / 'connection_protocol.obj'), '/Fe' + str(exe),
], capture_output=True, text=True)
run = None
if build.returncode == 0:
    if dll != out / dll.name:
        shutil.copy2(dll, out / dll.name)
    run = subprocess.run([str(exe)], cwd=out, capture_output=True, text=True)
log = build.stdout + build.stderr + (run.stdout + run.stderr if run else '')
(out / 'protocol.log').write_text(log, encoding='utf-8')
passed = build.returncode == 0 and run is not None and run.returncode == 0
report = {
    'passed': passed,
    'build_exit': build.returncode,
    'test_exit': run.returncode if run else None,
    'output': run.stdout if run else '',
    'apcpp_sha256': hashlib.sha256(dll.read_bytes()).hexdigest(),
    'parser_sha256': hashlib.sha256((a.apcpp_source / 'Archipelago.cpp').read_bytes()).hexdigest(),
    'scope': 'Real APCpp packet parser; no socket, server, or live game connection.',
}
(out / 'protocol.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(log)
raise SystemExit(0 if passed else 1)
