"""Compile the real native SmallKeys helper for all ten small-key scenes."""
from pathlib import Path
from run_native_tests import function
import argparse, json, subprocess
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
r=Path(__file__).resolve().parents[1]
s=(r/'soh/Enhancements/randomizer/logic.cpp').read_text()
code=r'''
#include <cassert>
#include <cstdint>
#include <iostream>
#include "soh/Enhancements/randomizer/randomizerEnums.h"
using SceneID=int;
struct Logic {bool skeleton=false;int keyCount=0;
 bool HasItem(RandomizerGet item){assert(item==RG_SKELETON_KEY);return skeleton;}
 int GetSmallKeyCount(SceneID){return keyCount;}
 bool SmallKeys(SceneID scene,uint8_t requiredAmount);
};
''' + function(s,'bool Logic::SmallKeys(') + r'''
int main(){int tests=0;Logic l;
for(int scene=0;scene<10;++scene)for(int held=0;held<12;++held)
for(int needed=0;needed<12;++needed)for(int skeleton=0;skeleton<2;++skeleton){
 l.keyCount=held;l.skeleton=skeleton;
 assert(l.SmallKeys(scene,needed)==(skeleton || held>=needed));++tests;
}
std::cout<<"PASS "<<tests<<" native Skeleton Key assertions\n";}
'''
src=out/'skeleton_native.cpp';exe=out/'skeleton_native.exe';src.write_text(code)
build=subprocess.run(['cl','/nologo','/std:c++20','/Zc:preprocessor','/EHsc','/MD','/I',str(r),
    str(src),'/Fo'+str(out/'skeleton_native.obj'),'/Fe'+str(exe)],capture_output=True,text=True)
run=subprocess.run([str(exe)],capture_output=True,text=True) if build.returncode==0 else None
log=build.stdout+build.stderr+(run.stdout+run.stderr if run else '')
passed=build.returncode==0 and run.returncode==0
(out/'skeleton-native.json').write_text(json.dumps(dict(passed=passed,assertions=2880,log=log),indent=2))
print(log);raise SystemExit(not passed)
