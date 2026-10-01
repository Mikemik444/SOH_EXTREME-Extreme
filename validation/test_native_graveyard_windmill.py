"""Compile the real native Graveyard and Windmill predicates with controlled inventory."""
from pathlib import Path
from run_native_tests import function
from source_index import native_sources
import argparse, json, subprocess
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
r=Path(__file__).resolve().parent.parent;o=a.output.resolve();o.mkdir(parents=True,exist_ok=True)
gy=(r/'soh/Enhancements/randomizer/location_access/overworld/graveyard.cpp').read_text()
sources,regions=native_sources(r)
wind=sources['RC_SONG_FROM_WINDMILL'][0]['condition']
passage=next(e['condition'] for e in regions['RR_GRAVEYARD_DAMPES_GRAVE']['exits'] if e['target']=='RR_KAK_WINDMILL_UPPER')
code=r'''
#include <cassert>
#include <cstdio>
#include <set>
#include "soh/Enhancements/randomizer/randomizerEnums.h"
struct Context {std::set<int> enabled;bool GetOption(int i){return enabled.count(i);}} context;auto*ctx=&context;
struct Logic {bool IsAdult=false,IsChild=true,bean=false,crate=false;std::set<int> items;
 bool HasItem(int i){return items.count(i);}
 bool CanUse(int i){return HasItem(i)&&(i!=RG_LONGSHOT||IsAdult);}
 bool BeanPlanted(int){return bean;} bool CanBreakCrates(){return crate;} bool CanGroundJump(){return false;}
} value;auto*logic=&value;
'''
code+=function(gy,'static bool CanTalkToDampe(')+'\n'+function(gy,'static bool CanReachGraveyardCrate(')
code+='\nbool windmill(){return '+wind+';}\nbool passage(){return '+passage+';}\n'
code+=r'''
int main(){int assertions=0;auto ck=[&](bool x){assert(x);++assertions;};
 for(int m=0;m<1024;++m){
  value=Logic{};context.enabled.clear();
  bool adult=m&1,bean=m&2,feather=m&4,longshot=m&8,crate=m&16,npc=m&32,speak=m&64,ocarina=m&128,npcShuffle=m&256,speakShuffle=m&512;
  value.IsAdult=adult;value.IsChild=!adult;value.bean=bean;value.crate=crate;
  if(feather)value.items.insert(RG_ROCS_FEATHER);if(longshot)value.items.insert(RG_LONGSHOT);
  if(npc)value.items.insert(RG_NPC_SOUL);if(speak)value.items.insert(RG_SPEAK_HYLIAN);
  if(ocarina){value.items.insert(RG_FAIRY_OCARINA);value.items.insert(RG_SONG_OF_TIME);}
  if(npcShuffle)context.enabled.insert(RSK_SHUFFLE_NPC_SOUL);
  if(speakShuffle)context.enabled.insert(RSK_SHUFFLE_SPEAK);
  ck(CanReachGraveyardCrate()==(adult&&(bean||feather||longshot)&&crate));
  bool interact=(!npcShuffle||npc)&&(!speakShuffle||speak);
  ck(windmill()==(adult&&ocarina&&interact));ck(passage()==(adult&&ocarina&&interact));
 }
 std::printf("%d assertions passed\n",assertions);
}
'''
src=o/'routes.cpp';exe=o/'routes.exe';src.write_text(code)
c=subprocess.run(['cl','/nologo','/std:c++20','/Zc:preprocessor','/EHsc','/MD','/I'+str(r),str(src),'/Fo'+str(o/'routes.obj'),'/Fe'+str(exe)],capture_output=True,text=True)
t=subprocess.run([str(exe)],capture_output=True,text=True) if c.returncode==0 else None
report=dict(passed=c.returncode==0 and t.returncode==0,assertions=3072,compile_output=c.stdout+c.stderr,output=t.stdout+t.stderr if t else '',scope=__doc__)
(o/'native.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2));raise SystemExit(not report['passed'])
