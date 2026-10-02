"""Compile every native rule for ZR pillar grass against route capability cases."""
from pathlib import Path
from run_native_tests import function
import argparse, json, re, subprocess
p=argparse.ArgumentParser(description=__doc__); p.add_argument('--output', type=Path, required=True)
a=p.parse_args(); r=Path(__file__).resolve().parent.parent; o=a.output.resolve(); o.mkdir(parents=True,exist_ok=True)
s=(r/'soh/Enhancements/randomizer/location_access/overworld/zoras_river.cpp').read_text()
rules=re.findall(r'LOCATION\(RC_ZR_NEAR_FREESTANDING_POH_GRASS,\s*(.*)\),',s)
assert len(rules)==2
helper=function(s,'static bool CanCollectZrPillarGrass(') if 'static bool CanCollectZrPillarGrass(' in s else ''
code=r'''
#include <iostream>
#include "soh/Enhancements/randomizer/randomizerEnums.h"
struct Logic {
 bool IsChild=true,grab=false,cucco=false,swim=false,cut=false;
 bool HasAnimalSoul(RandomizerGet){return cucco;}
 bool HasItem(RandomizerGet i){return i==RG_POWER_BRACELET?grab:i==RG_BRONZE_SCALE?swim:false;}
 bool CanCollectGrass(){return cut;}
 bool CanCutShrubs(){return cut;}
 bool CanUse(RandomizerGet i){return i==RG_BOOMERANG&&cut;}
};
Logic value;Logic*logic=&value;
'''+helper+'\n'
for i,rule in enumerate(rules): code+=f'bool check{i}(){{return {rule};}}\n'
code+='int main(){int checks=0;for(int m=0;m<32;++m){logic->IsChild=m&1;logic->grab=m&2;logic->cucco=m&4;logic->swim=m&8;logic->cut=m&16;\n'
for i in range(len(rules)):
    code+=f'++checks;if(check{i}()!=(logic->IsChild&&logic->grab&&logic->cucco&&logic->swim&&logic->cut)){{std::cerr<<"FAIL route {i}, mask "<<m;return 1;}}\n'
code+='}std::cout<<checks<<" native pillar grass assertions passed\\n";}\n'
src=o/'zr_grass.cpp';exe=o/'zr_grass.exe';src.write_text(code)
c=subprocess.run(['cl','/nologo','/std:c++20','/Zc:preprocessor','/EHsc','/MD','/I'+str(r),str(src),'/Fo'+str(o/'zr_grass.obj'),'/Fe'+str(exe)],capture_output=True,text=True)
t=subprocess.run([str(exe)],capture_output=True,text=True) if c.returncode==0 else None
log=c.stdout+c.stderr+(t.stdout+t.stderr if t else '')
report=dict(passed=c.returncode==0 and t.returncode==0,checks=64,output=log,scope=__doc__)
(o/'native.json').write_text(json.dumps(report,indent=2));print(log);raise SystemExit(not report['passed'])
