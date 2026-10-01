"""Configure the TLUT patch against reviewed, repeated and incompatible sources."""
from pathlib import Path
import argparse, json, subprocess, re
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--previous-function', type=Path, required=True)
p.add_argument('--cmake', required=True); p.add_argument('--output', type=Path, required=True)
a=p.parse_args(); out=a.output.resolve(); out.mkdir(parents=True, exist_ok=True)
patch=Path(__file__).resolve().parent.parent/'Cmake/SohExtremeTlutSafety.cmake'
source=out/'fixture'; (source/'src/fast').mkdir(parents=True,exist_ok=True)
(source/'src/CMakeLists.txt').write_text('add_library(libultraship INTERFACE)\n')
(source/'CMakeLists.txt').write_text('cmake_minimum_required(VERSION 3.20)\nproject(Test NONE)\nadd_subdirectory(src)\ninclude("'+patch.as_posix()+'")\n')
cpp=source/'src/fast/interpreter.cpp'
original=a.previous_function.read_text()+'void Interpreter::GfxDpLoadBlock() {}\n'
cpp.write_text(original)
def run(): return subprocess.run([a.cmake,'--fresh','-G','Ninja','-S',str(source),'-B',str(out/'build')],capture_output=True,text=True)
first=run(); assert first.returncode==0,first.stdout+first.stderr
fixed=cpp.read_bytes(); assert b'SOH_EXTREME_TLUT_COMPLETE_GUARD' in fixed
second=run(); assert second.returncode==0 and cpp.read_bytes()==fixed
cpp.write_text(re.sub(r'#ifdef _WIN32.*?#endif', '', original, flags=re.S))
clean=run(); assert clean.returncode==0,clean.stdout+clean.stderr
assert cpp.read_bytes()==fixed
cpp.write_text(original.replace('void Interpreter::GfxDpLoadTlut(', 'void Interpreter::Changed('))
before=cpp.read_bytes(); bad=run(); assert bad.returncode!=0 and cpp.read_bytes()==before
report=dict(passed=True,cases=['actual target source-directory layout','reviewed partial-guard source',
    'idempotent repeat','reviewed source before partial guard','incompatible source rejected unchanged'])
(out/'patch.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
