"""Compile the complete Castle Grounds region initializer with controlled services.
Uses actual game/enum/OptionValue declarations; test graph traversal is not the
whole game's reachability engine or a physics simulation.
"""
import argparse, subprocess, json, re, shutil
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path,required=True);p.add_argument('--overlay',type=Path);p.add_argument('--report',type=Path,required=True);p.add_argument('--compiler',default='clang++');a=p.parse_args()
root=a.source_root.resolve();overlay=a.overlay.resolve() if a.overlay else root
build=a.report.resolve().parent/('native-castle-'+('after' if a.overlay else 'before')+'-'+a.compiler.replace('+','p'));build.mkdir(parents=True,exist_ok=True)
def read(rel):
 q=overlay/rel;return (q if q.exists() else root/rel).read_text()
option=read('soh/Enhancements/randomizer/option.h');option=option[option.index('class OptionValue {'):option.index('/**\n * @brief A class describing')]
impl=read('soh/Enhancements/randomizer/option.cpp');impl=impl[impl.index('OptionValue::OptionValue('):impl.index('size_t Option::GetOptionCount')]
s=read('soh/Enhancements/randomizer/location_access/overworld/castle_grounds.cpp')
services=r'''
#pragma once
#include <array>
#include <cstdio>
#include <functional>
#include <memory>
#include <set>
#include <string>
#include <vector>
#include "z64.h"
#include "soh/Enhancements/randomizer/randomizerEnums.h"
namespace Rando {
'''+option+impl+r'''
struct Context {
 std::array<OptionValue,RSK_MAX> options{}; std::array<OptionValue,RT_MAX> tricks{};
 OptionValue& GetOption(RandomizerSettingKey k){return options[k];}
 OptionValue& GetTrickOption(RandomizerTrick k){return tricks[k];}
};
}
static auto ctx=std::make_shared<Rando::Context>();
namespace Rando {
struct Logic {
 bool IsChild=true,IsAdult=false,AtNight=false,extra=false; int hearts=3;
 std::set<LogicVal> events;
 std::set<RandomizerGet> items;
 bool HasItem(RandomizerGet item){return items.contains(item);}
 bool HasAnimalSoul(RandomizerGet item);
 bool CanUse(RandomizerGet item){
   if ((item==RG_LONGSHOT||item==RG_HOOKSHOT||item==RG_IRON_BOOTS||item==RG_HOVER_BOOTS||item==RG_MEGATON_HAMMER)&&!IsAdult) return false;
   return HasItem(item);
 }
 int Health(){return hearts*16;}
 bool BeanPlanted(LogicVal){return extra;}
 bool Get(LogicVal id){return events.contains(id);}
 template<typename... Args> bool CanKillEnemy(Args...){return false;}
 bool CanSpawnSoilSkull(RandomizerGet){return false;}
 bool CanRecoilHover(RecoilRequirements){return false;}
 bool CanRecoilHoverFromObject(TorchRecoilRequirements){return false;}
'''
methods=re.findall(r'logic->(\w+)\(\)',s)
returns={'CanJumpslash':'extra','CallGossipFairy':'false','CanUse':'false'}
for method in sorted(set(methods)-{'Health'}):
 services+=f' bool {method}(){{return {returns.get(method,"false")};}}\n'
services+='};\n'
logic_source=read('soh/Enhancements/randomizer/logic.cpp');start=logic_source.index('bool Logic::HasAnimalSoul(');end=logic_source.index('\n}\n',start)+2
services+=logic_source[start:end]+'\n}\n'
services+=r'''
static auto logic=std::make_shared<Rando::Logic>();
struct EventAccess{LogicVal id;std::function<bool()> predicate;};
struct LocationAccess{RandomizerCheck id;std::function<bool()> predicate;};
struct Entrance{RandomizerRegion to;std::function<bool()> predicate;};
struct Region {
 std::string name;SceneID scene=SCENE_ID_MAX;std::vector<EventAccess> events;std::vector<LocationAccess> locations;std::vector<Entrance> exits;
 Region()=default;
 Region(std::string n,SceneID scene_,bool,std::vector<RandomizerArea>,std::vector<EventAccess> e,std::vector<LocationAccess> l,std::vector<Entrance> x):name(n),scene(scene_),events(e),locations(l),exits(x){}
 Region(std::string name_,SceneID scene_,std::vector<EventAccess> e,std::vector<LocationAccess> l,std::vector<Entrance> x):name(name_),scene(scene_),events(e),locations(l),exits(x){}
};
static std::array<Region,RR_MAX> areaTable;
static constexpr bool TIME_DOESNT_PASS=false;
static bool CanPlantBean(RandomizerGet){return false;}
static int GetCheckPrice(){return 0;}static int GetWalletCapacity(){return 999;}
#define EVENT_ACCESS(id,...) EventAccess{id,[]{return __VA_ARGS__;}}
#define LOCATION(id,...) LocationAccess{id,[]{return __VA_ARGS__;}}
#define ENTRANCE(id,...) Entrance{id,[]{return __VA_ARGS__;}}
'''
fake=build/'services/soh/Enhancements/randomizer';fake.mkdir(parents=True,exist_ok=True);(fake/'location_access.h').write_text(services);(fake/'entrance.h').write_text('#pragma once\n')
program=s+r'''
static int cases=0,failures=0;
static void check(bool value,const char* name){++cases;if(!value){++failures;if(failures<12)std::printf("FAIL %s\n",name);}}
static bool gate(RandomizerRegion from,RandomizerRegion to){
 for(const auto& e:areaTable[from].exits)if(e.to==to)return e.predicate();
 check(false,"missing entrance");return false;
}
static bool event(RandomizerRegion from,LogicVal id){
 for(const auto& e:areaTable[from].events)if(e.id==id)return e.predicate();
 check(false,"missing event");return false;
}
int main(){
 RegionTable_Init_CastleGrounds();
 for(int shuffled=0;shuffled<2;++shuffled)for(int mask=0;mask<32;++mask){
  const bool npc=mask&1,speak=mask&2,wallet=mask&4,climb=mask&8,egg=mask&16;
  const bool exists=npc||!shuffled;
  ctx->GetOption(RSK_SHUFFLE_NPC_SOUL).Set(shuffled);
  logic->items.clear();logic->events.clear();logic->IsChild=true;logic->IsAdult=false;
  if(npc)logic->items.insert(RG_NPC_SOUL);if(speak)logic->items.insert(RG_SPEAK_HYLIAN);
  if(wallet)logic->items.insert(RG_CHILD_WALLET);if(climb)logic->items.insert(RG_CLIMB);
  if(egg)logic->items.insert(RG_WEIRD_EGG);
  check(gate(RR_HC_GATE,RR_HC_PAST_GATE)==(exists&&speak&&wallet),"guard bribe needs real NPC speech wallet");
  check(gate(RR_HC_GATE,RR_HC_ABOVE_VINE)==climb,"climb route independent of guard soul/speech");
  check(event(RR_HC_MOAT,LOGIC_TALON_RETURNED_FROM_CASTLE)==(exists&&speak&&egg),"Talon needs real NPC speech and egg");
  check(event(RR_HC_GARDEN,LOGIC_MET_ZELDA)==(exists&&speak),"Zelda interaction needs real NPC speech");
  logic->events.insert(LOGIC_TALON_RETURNED_FROM_CASTLE);
  check(event(RR_HC_GATE,LOGIC_MALON_RETURNED_FROM_CASTLE)==(exists&&speak),"Malon needs actual NPC speech");
 }
 std::printf("cases=%d failures=%d\n",cases,failures);return failures?1:0;
}
'''
src=build/'gv.cpp';src.write_text(program);exe=build/'gv'
cmd=[shutil.which(a.compiler) or a.compiler,'-std=c++20','-fms-extensions','-O1']
for path in [build/'services',root,root/'include',root/'src',root/'soh',root/'assets',root/'libultraship/include']:cmd+=['-I',str(path)]
cmd += [str(src),'-o',str(exe)]
c=subprocess.run(cmd,capture_output=True,text=True,timeout=45);x=subprocess.run([str(exe)],capture_output=True,text=True,timeout=30) if c.returncode==0 else None
report={'passed':c.returncode==0 and x.returncode==0,'compile_command':cmd,'compile_exit':c.returncode,'compile_stdout':c.stdout,'compile_stderr':c.stderr,'run_exit':x.returncode if x else None,'stdout':x.stdout if x else '', 'stderr':x.stderr if x else '', 'scope':'Whole Castle Grounds initializer and production HasAnimalSoul/OptionValue with actual enum and save headers; controlled item/engine services and local graph traversal; not game physics.'}
a.report.write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2));raise SystemExit(not report['passed'])
