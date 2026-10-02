"""Compile all native routes to the raised ZR Skulltula and gossip stone."""
from pathlib import Path
from run_native_tests import function
import argparse,json,re,subprocess,zipfile
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--baseline-source-zip',type=Path);a=p.parse_args()
r=Path(__file__).resolve().parent.parent;o=a.output.resolve();o.mkdir(parents=True,exist_ok=True)
path='soh/Enhancements/randomizer/location_access/overworld/zoras_river.cpp'
if a.baseline_source_zip:
    with zipfile.ZipFile(a.baseline_source_zip) as z:s=z.read(path).decode()
else:s=(r/path).read_text()
names=['RC_ZR_GS_NEAR_RAISED_GROTTOS','RC_ZR_NEAR_GROTTOS_GOSSIP_STONE_FAIRY','RC_ZR_NEAR_GROTTOS_GOSSIP_STONE_FAIRY_BIG']
rules={n:re.findall(r'LOCATION\('+n+r',\s*(.*)\),',s) for n in names}
assert [len(rules[n]) for n in names]==[2,1,1]
code=r'''
#include <iostream>
#include "soh/Enhancements/randomizer/randomizerEnums.h"
struct Logic {
 bool IsAdult=false,IsChild=true,climb=false,grab=false,cucco=false,night=false,soul=false,song=false,storms=false;
 int hook=0;
 bool CanClimbLadder(){return climb;}
 bool HasAnimalSoul(RandomizerGet){return cucco;}
 bool HasItem(RandomizerGet i){return i==RG_POWER_BRACELET&&grab;}
 bool CanUse(RandomizerGet i){return i==RG_SONG_OF_STORMS&&storms;}
 bool CanGetEnemyDrop(int,int distance){return soul&&IsAdult&&hook>=(distance==ED_LONGSHOT?2:1);}
 bool CanGetNightTimeGS(){return night;}
 bool CallGossipFairy(){return song;}
};
Logic value;Logic*logic=&value;
'''+function(s,'static bool CanReachZrUpperCircle(')+'\n'
predicates=[]
for name,expressions in rules.items():
    for i,expr in enumerate(expressions):
        key=f'{name}_{i}';predicates.append(key);code+=f'bool check_{key}(){{return {expr};}}\n'
code+='int main(){int checks=0;for(int mask=0;mask<256;++mask)for(int hook=0;hook<3;++hook){\n'
code+='logic->IsAdult=mask&1;logic->IsChild=!logic->IsAdult;logic->climb=mask&2;logic->grab=mask&4;logic->cucco=mask&8;logic->night=mask&16;logic->soul=mask&32;logic->song=mask&64;logic->storms=mask&128;logic->hook=hook;\n'
code+='bool ledge=logic->climb&&(logic->IsAdult||(logic->grab&&logic->cucco));\n'
expected=['logic->IsAdult&&hook==2&&logic->night&&logic->soul',
          'logic->IsAdult&&hook>0&&ledge&&logic->night&&logic->soul',
          'ledge&&logic->song','ledge&&logic->storms']
for key,expr in zip(predicates,expected):
    code+=f'++checks;if(check_{key}()!=({expr})){{std::cerr<<"FAIL {key} mask="<<mask<<" hook="<<hook;return 1;}}\n'
code+='}std::cout<<checks<<" native raised ZR assertions passed\\n";}\n'
src=o/'raised.cpp';exe=o/'raised.exe';src.write_text(code)
c=subprocess.run(['cl','/nologo','/std:c++20','/Zc:preprocessor','/EHsc','/MD','/I'+str(r),str(src),'/Fo'+str(o/'raised.obj'),'/Fe'+str(exe)],capture_output=True,text=True)
t=subprocess.run([str(exe)],capture_output=True,text=True) if c.returncode==0 else None
log=c.stdout+c.stderr+(t.stdout+t.stderr if t else '')
report=dict(passed=c.returncode==0 and t.returncode==0,checks=3072,output=log)
(o/'native.json').write_text(json.dumps(report,indent=2));print(log);raise SystemExit(not report['passed'])
