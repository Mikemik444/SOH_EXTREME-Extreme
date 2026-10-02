"""Compile the native Kak silver-boulder ledge predicate with controlled capabilities."""
from pathlib import Path
import argparse,json,re,subprocess,zipfile
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--baseline-source-zip',type=Path);a=p.parse_args()
r=Path(__file__).resolve().parent.parent;o=a.output.resolve();o.mkdir(parents=True,exist_ok=True)
path='soh/Enhancements/randomizer/location_access/overworld/kakariko.cpp'
if a.baseline_source_zip:
    with zipfile.ZipFile(a.baseline_source_zip) as z:s=z.read(path).decode()
else:s=(r/path).read_text()
expr=re.search(r'LOCATION\(RC_KAK_SILVER_BOULDER,\s*(.*?)\),\s*\n',s,re.S)[1]
code=r'''
#include <iostream>
#include "soh/Enhancements/randomizer/randomizerEnums.h"
struct Logic {
 bool IsAdult,climb,hover,longshot,AtDay,grab,cucco,trick,slash,damage,silver;
 bool HasItem(RandomizerGet i){return (i==RG_CLIMB&&climb)||(i==RG_LONGSHOT&&longshot)||(i==RG_POWER_BRACELET&&grab);}
 bool CanUse(RandomizerGet i){return (i==RG_HOVER_BOOTS&&hover)||(i==RG_SILVER_GAUNTLETS&&silver);}
 bool HasAnimalSoul(RandomizerGet){return cucco;}
 bool CanJumpslash(){return slash;}
 bool TakeDamage(){return damage;}
 bool GetTrickOption(int){return trick;}
} value;
Logic*logic=&value;Logic*ctx=&value;
'''+f'bool check(){{return {expr};}}\n'+r'''
int main(){
 for(int mask=0;mask<2048;++mask){
  logic->IsAdult=mask&1;logic->climb=mask&2;logic->hover=mask&4;logic->longshot=mask&8;
  logic->AtDay=mask&16;logic->grab=mask&32;logic->cucco=mask&64;logic->trick=mask&128;
  logic->slash=mask&256;logic->damage=mask&512;logic->silver=mask&1024;
  bool expected=logic->IsAdult&&logic->silver&&(logic->climb||logic->hover||
      (logic->longshot&&((logic->AtDay&&logic->grab&&logic->cucco)||(logic->trick&&logic->slash&&logic->damage))));
  if(check()!=expected){std::cerr<<"FAIL mask="<<mask;return 1;}
 }
 std::cout<<"2048 native Kak boulder assertions passed\n";
}
'''
src=o/'kak.cpp';exe=o/'kak.exe';src.write_text(code)
c=subprocess.run(['cl','/nologo','/std:c++20','/Zc:preprocessor','/EHsc','/MD','/I'+str(r),str(src),'/Fo'+str(o/'kak.obj'),'/Fe'+str(exe)],capture_output=True,text=True)
t=subprocess.run([str(exe)],capture_output=True,text=True) if c.returncode==0 else None
log=c.stdout+c.stderr+(t.stdout+t.stderr if t else '')
report=dict(passed=c.returncode==0 and t.returncode==0,checks=2048,output=log)
(o/'native.json').write_text(json.dumps(report,indent=2));print(log);raise SystemExit(not report['passed'])
