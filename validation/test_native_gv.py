"""Compile the complete Gerudo Valley region initializer with controlled services.
Uses actual game/enum/OptionValue declarations; test graph traversal is not the
whole game's reachability engine or a physics simulation.
"""
import argparse, subprocess, json, re, shutil
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path,required=True);p.add_argument('--overlay',type=Path);p.add_argument('--report',type=Path,required=True);p.add_argument('--compiler',default='clang++');a=p.parse_args()
root=a.source_root.resolve();overlay=a.overlay.resolve() if a.overlay else root
build=a.report.resolve().parent/('native-gv-'+('after' if a.overlay else 'before')+'-'+a.compiler.replace('+','p'));build.mkdir(parents=True,exist_ok=True)
def read(rel):
 q=overlay/rel;return (q if q.exists() else root/rel).read_text()
option=read('soh/Enhancements/randomizer/option.h');option=option[option.index('class OptionValue {'):option.index('/**\n * @brief A class describing')]
impl=read('soh/Enhancements/randomizer/option.cpp');impl=impl[impl.index('OptionValue::OptionValue('):impl.index('size_t Option::GetOptionCount')]
s=read('soh/Enhancements/randomizer/location_access/overworld/gerudo_valley.cpp')
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
 bool IsChild=true,IsAdult=false,extra=false; int hearts=3;
 std::set<RandomizerGet> items;
 bool HasItem(RandomizerGet item){return items.contains(item);}
 bool HasAnimalSoul(RandomizerGet item);
 bool CanUse(RandomizerGet item){
   if ((item==RG_LONGSHOT||item==RG_HOOKSHOT||item==RG_IRON_BOOTS||item==RG_HOVER_BOOTS||item==RG_MEGATON_HAMMER)&&!IsAdult) return false;
   return HasItem(item);
 }
 int Health(){return hearts*16;}
 bool BeanPlanted(LogicVal){return extra;}
 bool Get(LogicVal){return false;}
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
 Region(std::string name_,SceneID scene_,std::vector<EventAccess> e,std::vector<LocationAccess> l,std::vector<Entrance> x):name(name_),scene(scene_),events(e),locations(l),exits(x){}
};
static std::array<Region,RR_MAX> areaTable;
static bool CanPlantBean(RandomizerGet){return false;}
static int GetCheckPrice(){return 0;}static int GetWalletCapacity(){return 999;}
#define EVENT_ACCESS(id,...) EventAccess{id,[]{return __VA_ARGS__;}}
#define LOCATION(id,...) LocationAccess{id,[]{return __VA_ARGS__;}}
#define ENTRANCE(id,...) Entrance{id,[]{return __VA_ARGS__;}}
'''
fake=build/'services/soh/Enhancements/randomizer';fake.mkdir(parents=True,exist_ok=True);(fake/'location_access.h').write_text(services);(fake/'entrance.h').write_text('#pragma once\n')
program=s+r'''
static bool reachable(RandomizerCheck id,RandomizerRegion start){
 std::set<RandomizerRegion> found{start};bool changed;
 do{changed=false;auto old=found;for(const auto region:old){for(const auto& exit:areaTable[region].exits)if(exit.predicate()) changed=found.insert(exit.to).second||changed;}}while(changed);
 for(const auto region:found)for(const auto& check:areaTable[region].locations)if(check.id==id&&check.predicate())return true;
 return false;
}
int main(){
 RegionTable_Init_GerudoValley();int cases=0,failures=0;
 // Route entry is Gerudo Valley itself. External Root->Valley access is an AP
 // graph regression, not assumed to be validated by this local graph harness.
 for(int mode=0;mode<3;++mode)for(int shuffled=0;shuffled<8;++shuffled)
 for(int adult=0;adult<2;++adult)for(int mask=0;mask<16;++mask)
 for(int hearts=1;hearts<=2;++hearts)for(int extra=0;extra<2;++extra){
   const bool grab=(mask&1)||!(shuffled&1),climb=(mask&4)||!(shuffled&2),swim=(mask&8)||!(shuffled&4);
   const bool cucco=(mask&2)||mode==0;
   ctx->GetOption(RSK_SHUFFLE_ANIMAL_SOUL).Set(mode);ctx->GetOption(RSK_SHUFFLE_GRAB).Set(bool(shuffled&1));
   ctx->GetOption(RSK_SHUFFLE_CLIMB).Set(bool(shuffled&2));ctx->GetOption(RSK_SHUFFLE_SWIM).Set(bool(shuffled&4));
   logic->items.clear();logic->IsAdult=adult;logic->IsChild=!adult;logic->hearts=hearts;logic->extra=extra;
   if(grab)logic->items.insert(RG_POWER_BRACELET);if(climb)logic->items.insert(RG_CLIMB);if(swim)logic->items.insert(RG_BRONZE_SCALE);
   if(mask&2)logic->items.insert(mode==1?RG_ANIMAL_SOUL:RG_ANIMAL_SOUL_CUCCO);
   if(extra){logic->items.insert(RG_LONGSHOT);logic->items.insert(RG_HOOKSHOT);logic->items.insert(RG_IRON_BOOTS);logic->items.insert(RG_HOVER_BOOTS);}
   bool expected=(!adult&&cucco&&grab)||(climb&&swim);
   bool actual=reachable(RC_GV_WATERFALL_FREESTANDING_POH,RR_GERUDO_VALLEY);++cases;
   if(actual!=expected){++failures;if(failures<=8)std::printf("FAIL soulmode=%d shuffled=%d adult=%d items=%d hearts=%d otherRoutes=%d actual=%d expected=%d\n",mode,shuffled,adult,mask,hearts,extra,actual,expected);}
 }
 // The cow route must require Cow Soul, never Cucco Soul or generic Animal
 // Soul when individual animal souls are selected.
 logic->IsChild=true;logic->IsAdult=false;logic->hearts=3;logic->extra=false;logic->items={RG_EPONAS_SONG};
 ctx->GetOption(RSK_SHUFFLE_ANIMAL_SOUL).Set(2);
 for(int m=0;m<4;++m){logic->items={RG_EPONAS_SONG};if(m&1)logic->items.insert(RG_ANIMAL_SOUL_COW);if(m&2)logic->items.insert(RG_ANIMAL_SOUL);
  ++cases; if(reachable(RC_GV_COW,RR_GERUDO_VALLEY)!=bool(m&1))++failures;
 }
 std::printf("cases=%d failures=%d\n",cases,failures);return failures?1:0;
}
'''
src=build/'gv.cpp';src.write_text(program);exe=build/'gv'
cmd=[shutil.which(a.compiler) or a.compiler,'-std=c++20','-fms-extensions','-O1']
for path in [build/'services',root,root/'include',root/'src',root/'soh',root/'assets',root/'libultraship/include']:cmd+=['-I',str(path)]
cmd += [str(src),'-o',str(exe)]
c=subprocess.run(cmd,capture_output=True,text=True,timeout=45);x=subprocess.run([str(exe)],capture_output=True,text=True,timeout=30) if c.returncode==0 else None
report={'passed':c.returncode==0 and x.returncode==0,'compile_command':cmd,'compile_exit':c.returncode,'compile_stdout':c.stdout,'compile_stderr':c.stderr,'run_exit':x.returncode if x else None,'stdout':x.stdout if x else '', 'stderr':x.stderr if x else '', 'scope':'Whole GV initializer and production HasAnimalSoul/OptionValue with actual enum and save headers; controlled item/engine services and local graph traversal; not game physics.'}
a.report.write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2));raise SystemExit(not report['passed'])
