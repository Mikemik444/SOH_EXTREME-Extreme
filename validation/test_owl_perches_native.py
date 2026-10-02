"""Compile actual native perch/ride predicates and the owl speech switch arm."""
from pathlib import Path
import argparse, json, re, subprocess
p = argparse.ArgumentParser(); p.add_argument('--output', type=Path, required=True)
a = p.parse_args(); r = Path(__file__).resolve().parent.parent
o = a.output.resolve(); o.mkdir(parents=True, exist_ok=True)
root = r/'soh/Enhancements/randomizer'
lh = (root/'location_access/overworld/lake_hylia.cpp').read_text()
dmt = (root/'location_access/overworld/death_mountain_trail.cpp').read_text()
speak = (root/'ShuffleSpeak.cpp').read_text()
logic = (root/'logic.cpp').read_text()
expressions = [re.search(r'ENTRANCE\(RR_LH_GROTTO,\s*(.*)\),', lh)[1],
    re.search(r'ENTRANCE\(RR_LH_OWL_FLIGHT,\s*(.*)\),', lh)[1],
    re.search(r'ENTRANCE\(RR_DMT_OWL_FLIGHT,\s*(.*)\),', dmt)[1],
    re.search(r'LOCATION\(RC_DMT_UPPER_EXIT_ARROW_SIGN,\s*(.*)\),', dmt)[1]]
arm = re.search(r'case ACTOR_EN_OWL:(.*?)\n            }', speak, re.S)[1]
speech = re.search(r'case RG_SPEAK_ZORA:\s*(.*?)\s*// Ocarina Buttons', logic, re.S)[1]
code = r'''
#include <iostream>
#include <map>
#include "soh/Enhancements/randomizer/randomizerEnums.h"
bool npcOwned; int mode, mask;
struct Context {
 bool npcShuffle;
 int GetOption(int opt){return opt==RSK_SHUFFLE_NPC_SOUL?npcShuffle:mode;}
} context;
Context* ctx=&context;
RandomizerInf languages[]={RAND_INF_CAN_SPEAK_DEKU,RAND_INF_CAN_SPEAK_GERUDO,
 RAND_INF_CAN_SPEAK_GORON,RAND_INF_CAN_SPEAK_HYLIAN,RAND_INF_CAN_SPEAK_KOKIRI,RAND_INF_CAN_SPEAK_ZORA};
bool Flags_GetRandomizerInf(int inf){
 if(inf==RAND_INF_NPC_SOUL)return npcOwned;
 for(int i=0;i<6;++i)if(inf==languages[i])return mode==0||(mode==1?bool(mask&1):bool(mask&(1<<i)));
 return false;
}
bool CheckRandoInf(int inf){return Flags_GetRandomizerInf(inf);}
namespace StaticData {std::map<RandomizerGet,int> RandoGetToRandInf={
 {RG_SPEAK_DEKU,RAND_INF_CAN_SPEAK_DEKU},{RG_SPEAK_GERUDO,RAND_INF_CAN_SPEAK_GERUDO},
 {RG_SPEAK_GORON,RAND_INF_CAN_SPEAK_GORON},{RG_SPEAK_HYLIAN,RAND_INF_CAN_SPEAK_HYLIAN},
 {RG_SPEAK_KOKIRI,RAND_INF_CAN_SPEAK_KOKIRI},{RG_SPEAK_ZORA,RAND_INF_CAN_SPEAK_ZORA}};}
bool nativeSpeech(RandomizerGet itemName){
'''+speech+r'''
}
struct Logic {
 bool IsChild,IsAdult,grab,sign;
 bool HasItem(RandomizerGet item){
  if(item==RG_NPC_SOUL)return npcOwned;
  if(item==RG_POWER_BRACELET)return grab;
  return nativeSpeech(item);
 }
 bool CanRead(){return sign;}
 bool CanBreakRocks(){return true;}
} value;
Logic* logic=&value;
bool owlSpeech(){
 bool result=true;bool*should=&result;RandomizerInf inf=RAND_INF_MAX;
 if(mode==0)return true;
 auto hook=[&](){ switch(333){case 333:
'''+arm+r'''
 }
 if(inf!=RAND_INF_MAX&&!Flags_GetRandomizerInf(inf))*should=false;
 };
 hook();return result;
}
'''
for name, expression in zip(('grave', 'lakeRide', 'mountainRide', 'sign'), expressions):
    code += f'bool {name}(){{return {expression};}}\n'
code += r'''
int main(){int checks=0;
 for(mode=0;mode<3;++mode)for(int bits=0;bits<32;++bits)for(mask=0;mask<64;++mask){
  ctx->npcShuffle=bits&1;npcOwned=bits&2;logic->IsAdult=bits&4;logic->IsChild=!logic->IsAdult;
  logic->grab=bits&8;logic->sign=bits&16;
  bool speech=mode==0||(mode==1?bool(mask&1):bool(mask&8));
  bool talk=(!ctx->npcShuffle||npcOwned)&&speech;
  bool ride=logic->IsChild&&talk;
  bool perch=logic->IsAdult||talk;
  checks+=5;
  if(grave()!=(logic->grab&&perch)||lakeRide()!=ride||mountainRide()!=ride||
     sign()!=(logic->sign&&perch)||owlSpeech()!=speech){
   std::cerr<<"FAIL mode="<<mode<<" bits="<<bits<<" languages="<<mask;return 1;
  }
 }
 std::cout<<checks<<" native owl assertions passed\n";
}
'''
src = o/'owl.cpp'; exe = o/'owl.exe'; src.write_text(code)
c = subprocess.run(['cl', '/nologo', '/std:c++20', '/Zc:preprocessor', '/EHsc', '/MD', '/I'+str(r),
    str(src), '/Fo'+str(o/'owl.obj'), '/Fe'+str(exe)], capture_output=True, text=True)
t = subprocess.run([str(exe)], capture_output=True, text=True) if c.returncode == 0 else None
log = c.stdout+c.stderr+(t.stdout+t.stderr if t else '')
report = dict(passed=c.returncode == 0 and t.returncode == 0, checks=30720, output=log)
(o/'native.json').write_text(json.dumps(report, indent=2)); print(log)
raise SystemExit(not report['passed'])
