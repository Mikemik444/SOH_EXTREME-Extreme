"""Apply the renderer patch to a baseline, then reject ambiguous/altered inputs atomically."""
from pathlib import Path
import argparse
import json
import subprocess

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--baseline', type=Path, required=True)
p.add_argument('--cmake', required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
out = a.output.resolve()
source = out / 'fixture'
(source / 'src/fast').mkdir(parents=True, exist_ok=True)
patch = Path(__file__).resolve().parents[1] / 'Cmake/SohExtremeVertexSafety.cmake'
(source / 'src/CMakeLists.txt').write_text('add_library(libultraship INTERFACE)\n')
(source / 'CMakeLists.txt').write_text('cmake_minimum_required(VERSION 3.20)\nproject(Test NONE)\n'
                                    'add_subdirectory(src)\ninclude("' + patch.as_posix() + '")\n')
cpp = source / 'src/fast/interpreter.cpp'
baseline = a.baseline.read_text(encoding='utf-8')
cpp.write_text(baseline, encoding='utf-8')

def configure():
    return subprocess.run([a.cmake, '--fresh', '-G', 'Ninja', '-S', str(source), '-B', str(out / 'build')],
                          capture_output=True, text=True)

first = configure()
assert first.returncode == 0, first.stdout + first.stderr
fixed = cpp.read_bytes()
second = configure()
assert second.returncode == 0 and cpp.read_bytes() == fixed, second.stdout + second.stderr
cases = ['reviewed baseline', 'idempotent repeat']
for name, bad in [
    ('missing late anchor', baseline.replace('        gfx_step();\n    }\n\n    Flush();', '        changed_step();')),
    ('duplicate anchor', baseline + '\nvoid Interpreter::SpReset() {\n}\n'),
    ('altered installed guard', fixed.decode().replace('start > capacity', 'start >= capacity')),
]:
    cpp.write_text(bad, encoding='utf-8')
    before = cpp.read_bytes()
    result = configure()
    assert result.returncode != 0 and cpp.read_bytes() == before, name
    cases.append(name + ' rejected unchanged')
cpp.write_bytes(fixed)
(out / 'interpreter-fixed.cpp').write_bytes(fixed)
report = dict(passed=True, cases=cases)
(out / 'patch.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
