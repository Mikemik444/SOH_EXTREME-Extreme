"""Compile source-derived native predicates with real enums/OptionValue.
Other scene/engine services are controlled. Not a Windows game build."""
import argparse,json,subprocess
from pathlib import Path
from source_index import native_sources,mask_comments,body_at
p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path,required=True);p.add_argument('--apworld-source',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--compiler',default='clang++');a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
n,regions=native_sources(a.source_root)
sheiks=('RC_SHEIK_IN_ICE_CAVERN','RC_SHEIK_IN_CRATER','RC_SHEIK_AT_COLOSSUS','RC_SHEIK_IN_KAKARIKO','RC_SHEIK_IN_FOREST','RC_SHEIK_AT_TEMPLE')
conditions=[r['condition'] for key in sheiks for r in n[key]]
def edge(s,t):return next(e['condition'] for e in regions[s]['exits'] if e['target']==t)
rock=edge('RR_DEATH_MOUNTAIN_TRAIL','RR_DEATH_MOUNTAIN_ROCKFALL')
summit=edge('RR_DEATH_MOUNTAIN_ROCKFALL','RR_DEATH_MOUNTAIN_SUMMIT')
goron=next(e['condition'] for e in regions['RR_GORON_CITY']['events'] if e['event']=='LOGIC_GORON_CITY_STOP_ROLLING_GORON_AS_ADULT')
shadow=edge('RR_GRAVEYARD_WARP_PAD_REGION','RR_SHADOW_TEMPLE_ENTRYWAY')
raw=(a.source_root/'soh/Enhancements/randomizer/option.h').read_text();opt=raw[raw.index('class OptionValue {'):raw.index('/**\n * @brief A class describing')]
raw=(a.source_root/'soh/Enhancements/randomizer/option.cpp').read_text();opt+=raw[raw.index('OptionValue::OptionValue('):raw.index('size_t Option::GetOptionCount')]
raw=(a.source_root/'soh/Enhancements/randomizer/logic.cpp').read_text();i=raw.index('bool Logic::CanBreakRocks()');j=raw.index('\n}',i)+2;rock_helper=raw[i:j]
code=r'''
#include <algorithm>
#include <array>
#include <cstdint>
#include <cstdio>
#include <set>
#include <map>
#include <functional>
#include <string>
#include <vector>
#include "soh/Enhancements/randomizer/randomizerEnums.h"
namespace Rando {
''' +opt+r'''
struct Context {
 std::map<RandomizerSettingKey,OptionValue> options;
 OptionValue& GetOption(RandomizerSettingKey k){return options[k];}
 OptionValue GetTrickOption(RandomizerTrick){return OptionValue(0);}
};
Context c;Context* ctx=&c;
struct Logic {
 bool IsAdult=true,IsChild=false,explosives=true;
 std::set<RandomizerGet> missing;
 bool HasItem(RandomizerGet k){return !missing.count(k);}
 bool CanUse(RandomizerGet k){return !missing.count(k);}
 bool HasExplosives(){return explosives;}
 bool BeanPlanted(LogicVal){return false;}
 bool CanKillEnemy(RandomizerEnemy){return true;}
 bool CanBreakRocks();
};
''' +rock_helper+r'''
Logic l;Logic* logic=&l;
bool AnyAgeTime(const std::function<bool()>& condition){return condition();}
}
using namespace Rando;
int checks=0;void ck(bool v,const char* msg){++checks;if(!v){std::printf("FAIL %s\n",msg);std::exit(1);}}
int main(){
 std::vector<std::function<bool()>> sheiks={
''' + ',\n'.join('[]{return '+e+';}' for e in conditions)+r'''
 };
 for(int npcMode=0;npcMode<2;++npcMode)for(int speechMode=0;speechMode<3;++speechMode)
 for(int npc=0;npc<2;++npc)for(int speech=0;speech<2;++speech){
  ctx->options[RSK_SHUFFLE_NPC_SOUL]=npcMode;ctx->options[RSK_SHUFFLE_SPEAK]=speechMode;
  logic->missing.clear();if(!npc)logic->missing.insert(RG_NPC_SOUL);
  if(!speech){logic->missing.insert(RG_SPEAK_HYLIAN);logic->missing.insert(RG_SPEAK_GORON);}
  bool expected=(!npcMode||npc)&&(!speechMode||speech);
  for(const auto& f:sheiks)ck(f()==expected,"Sheik soul/language combination");
  ck(('''+goron+r''')==expected,"Goron door event soul/language");
 }
 ctx->options[RSK_SHUFFLE_ROCK_SOUL]=1;
 logic->missing={RG_ROCK_SOUL};logic->explosives=true;
 ck(!logic->CanBreakRocks(),"Bombchus without soul cannot remove mountain rocks");
 ck(!('''+rock+r'''),"native route blocks missing rock soul");
 logic->missing.clear();ck(logic->CanBreakRocks(),"soul and explosives allow rocks");
 ck(('''+rock+r'''),"native mountain rocks restored");
 logic->missing={RG_POWER_BRACELET};logic->explosives=false;
 ck(!logic->CanBreakRocks(),"soul without method cannot break rocks");
 logic->missing.clear();ck(logic->CanBreakRocks(),"Grab is valid rock method");
 logic->missing={RG_CLIMB};ck(!('''+summit+r'''),"summit requires climb");
 logic->missing.clear();ck(('''+summit+r'''),"adult summit climb restored");
 logic->missing={RG_DINS_FIRE};ck(!('''+shadow+r'''),"Shadow door no Dins Fire and no fire-arrow trick");
 logic->missing.clear();ck(('''+shadow+r'''),"Shadow door with usable Dins Fire");
 std::printf("CHECKS %d PASS\n",checks);
}
'''
(a.out/'native_reported.cpp').write_text(code)
cmd=[a.compiler,'-std=c++20','-O1','-I'+str(a.source_root.resolve()),str(a.out/'native_reported.cpp'),'-o',str(a.out/'native_reported')]
r=subprocess.run(cmd,capture_output=True,text=True);(a.out/'compile.log').write_text(r.stdout+r.stderr)
if r.returncode:print(r.stderr);raise SystemExit(r.returncode)
r=subprocess.run([str(a.out/'native_reported')],capture_output=True,text=True);(a.out/'run.log').write_text(r.stdout+r.stderr)
print(r.stdout+r.stderr)
if r.returncode:raise SystemExit(r.returncode)
silver=json.loads((a.apworld_source/'SilverRoomRoutes.json').read_text())
for rc,rows in silver.items():
 expected={(r['region'],r['condition']) for r in n[rc] if r['region'] in json.loads((a.apworld_source/'EnemyRoomGraph.json').read_text())}
 assert {(r['region'],r['condition']) for r in rows}==expected,rc
(a.out/'result.json').write_text(json.dumps({'passed':True,'native_predicate_assertions':int(r.stdout.split()[1]),'source_silver_checks':len(silver),'native_sheik_definitions':len(conditions),'compiler':a.compiler,'scope':'compiled production expressions and CanBreakRocks with real enums and OptionValue; controlled engine services'},indent=2))
