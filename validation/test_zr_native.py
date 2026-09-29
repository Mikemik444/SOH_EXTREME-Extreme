"""Compile production ZR location predicates with controlled engine services.

Exercises child/adult, Swim, Grab, Cucco, Climb and rock interaction separately.
Region traversal and settings-to-inventory conversion are covered by AP/UT tests.
"""
from pathlib import Path
from run_native_tests import function
import argparse, json, re, subprocess
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--source-root', type=Path, default=Path(__file__).resolve().parent.parent)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args(); root = a.source_root.resolve(); out = a.output.resolve()
out.mkdir(parents=True, exist_ok=True)
source = (root/'soh/Enhancements/randomizer/location_access/overworld/zoras_river.cpp').read_text(encoding='utf-8')
predicates = {}
for line in source.splitlines():
    match = re.search(r'LOCATION\((RC_ZR_(?:UPPER_CIRCLE_\w+|WONDER_NEAR_CUCCO_\d)),\s*(.*)\),', line)
    if match: predicates[match[1]] = match[2]
assert len(predicates) == 12
code = r'''
#include <cassert>
#include <iostream>
#include "soh/Enhancements/randomizer/randomizerEnums.h"
struct Logic {
 bool IsAdult=false,IsChild=true,swim=false,grab=false,cucco=false,climb=false,rocks=false;
 bool CanClimbLadder(){return climb;}
 bool HasAnimalSoul(RandomizerGet){return cucco;}
 bool HasItem(RandomizerGet i){return i==RG_BRONZE_SCALE?swim:i==RG_POWER_BRACELET?grab:false;}
 bool BlastOrSmash(){return rocks;}
 bool CanBreakRocks(){return rocks;}
};
Logic value;Logic* logic=&value;
''' + function(source, 'static bool CanReachZrUpperCircle(') + '\n'
for name, expression in predicates.items(): code += f'bool check_{name}(){{return {expression};}}\n'
code += 'int main(){int tests=0; for(int mask=0;mask<64;++mask){\n'
code += 'logic->IsAdult=mask&1;logic->IsChild=!logic->IsAdult;logic->swim=mask&2;logic->grab=mask&4;logic->cucco=mask&8;logic->climb=mask&16;logic->rocks=mask&32;\n'
# The parent is assumed reachable; no route into it can bypass these local gates.
for name in predicates:
    expected = ('logic->IsChild && logic->swim' if 'WONDER' in name else
                'logic->climb && (logic->IsAdult || (logic->grab && logic->cucco)) && logic->rocks')
    code += f'assert(check_{name}()==({expected}));++tests;\n'
code += '} std::cout<<"PASS "<<tests<<" native ZR assertions\\n"; }\n'
src = out/'zr_native.cpp'; exe = out/'zr_native.exe'; src.write_text(code, encoding='utf-8')
build = subprocess.run(['cl','/nologo','/std:c++20','/Zc:preprocessor','/EHsc','/MD','/I',str(root),str(src),
    '/Fo'+str(out/'zr_native.obj'),'/Fe'+str(exe)], capture_output=True, text=True)
run = subprocess.run([str(exe)], capture_output=True, text=True) if build.returncode == 0 else None
log = build.stdout + build.stderr + (run.stdout + run.stderr if run else '')
passed = build.returncode == 0 and run.returncode == 0
(out/'native.json').write_text(json.dumps(dict(passed=passed, checks=768, log=log,
    scope=__doc__), indent=2), encoding='utf-8')
print(log); raise SystemExit(0 if passed else 1)
