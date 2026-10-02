"""Compile native guard events and speech ownership logic; services are controlled."""
from pathlib import Path
from run_native_tests import function
import argparse,json,re,subprocess
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
r=Path(__file__).resolve().parent.parent;o=a.output.resolve();o.mkdir(parents=True,exist_ok=True)
s=(r/'soh/Enhancements/randomizer/location_access/overworld/gerudo_fortress.cpp').read_text()
logic=(r/'soh/Enhancements/randomizer/logic.cpp').read_text()
gtg=re.findall(r'EVENT_ACCESS\(LOGIC_GTG_GATE_OPEN,\s*(.*)\),',s)
gate=re.findall(r'EVENT_ACCESS\(LOGIC_GF_GATE_OPEN,\s*(.*)\),',s)
assert len(gtg)==1 and len(gate)==2
entry=re.search(r'ENTRANCE\(RR_GF_TOWER,\s*(.*?)\),\s*\n',s,re.S)[1]
speech=re.search(r'case RG_SPEAK_ZORA:\s*(.*?)\s*// Ocarina Buttons',logic,re.S)[1]
code=r'''
#include <iostream>
#include <map>
#include "soh/Enhancements/randomizer/randomizerEnums.h"
bool npcShuffle,npcOwned,languageFlag;
struct Context {
 bool hookLadderTrick;
 bool GetOption(int){return npcShuffle;}
 bool GetTrickOption(int){return hookLadderTrick;}
} context;
Context*ctx=&context;
namespace StaticData {std::map<RandomizerGet,int> RandoGetToRandInf={{RG_SPEAK_GERUDO,RAND_INF_CAN_SPEAK_GERUDO}};}
bool CheckRandoInf(int inf){return inf==RAND_INF_NPC_SOUL?npcOwned:languageFlag;}
bool nativeSpeech(RandomizerGet itemName){
'''+speech+r'''
}
struct Logic {
 bool IsAdult,IsChild,card,wallet,climb;int hook;
 bool HasItem(RandomizerGet item){
  if(item==RG_SPEAK_GERUDO)return nativeSpeech(item);
  if(item==RG_GERUDO_MEMBERSHIP_CARD)return card;
  if(item==RG_CHILD_WALLET)return wallet;
  return item==RG_CLIMB&&climb;
 }
 bool CanUse(RandomizerGet item){return IsAdult&&item==RG_LONGSHOT&&hook==2;}
 bool CanClimbHighLadder();
} value;
Logic*logic=&value;
'''+function(logic,'bool Logic::CanClimbHighLadder()')+'\n'
for name,expr in zip(('gtg','tower','outside','towerEntry'),[*gtg,*gate,entry]):code+=f'bool {name}(){{return {expr};}}\n'
code+=r'''
int main(){int checks=0;
 for(int bits=0;bits<256;++bits)for(int hook=0;hook<3;++hook){
  logic->IsAdult=bits&1;logic->IsChild=!logic->IsAdult;logic->card=bits&2;logic->wallet=bits&4;
  logic->climb=bits&8;npcShuffle=bits&16;npcOwned=bits&32;languageFlag=bits&64;
  ctx->hookLadderTrick=bits&128;logic->hook=hook;
  bool talk=languageFlag&&(!npcShuffle||npcOwned);
  bool expectGtg=logic->IsAdult&&logic->card&&logic->wallet&&talk;
  bool expectTower=logic->IsAdult&&talk;
  bool expectOutside=logic->IsAdult&&logic->card&&talk;
  bool expectFront=expectOutside&&(logic->climb||(ctx->hookLadderTrick&&hook==2));
  checks+=4;
  if(gtg()!=expectGtg||tower()!=expectTower||outside()!=expectOutside||(towerEntry()&&tower())!=expectFront){
   std::cerr<<"FAIL mask="<<bits<<" hook="<<hook;return 1;
  }
 }
 std::cout<<checks<<" native Gerudo gate assertions passed\n";
}
'''
src=o/'gerudo.cpp';exe=o/'gerudo.exe';src.write_text(code)
c=subprocess.run(['cl','/nologo','/std:c++20','/Zc:preprocessor','/EHsc','/MD','/I'+str(r),str(src),'/Fo'+str(o/'gerudo.obj'),'/Fe'+str(exe)],capture_output=True,text=True)
t=subprocess.run([str(exe)],capture_output=True,text=True) if c.returncode==0 else None
log=c.stdout+c.stderr+(t.stdout+t.stderr if t else '')
report=dict(passed=c.returncode==0 and t.returncode==0,checks=3072,output=log)
(o/'native.json').write_text(json.dumps(report,indent=2));print(log);raise SystemExit(not report['passed'])
