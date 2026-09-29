"""Compile actual native enemy finder routing with controlled region/inventory services."""
from pathlib import Path
from run_native_tests import function
import argparse,json,subprocess
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--source-root',type=Path,default=Path(__file__).resolve().parent.parent)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args();root=a.source_root.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
tracker=(root/'soh/Enhancements/randomizer/randomizer_check_tracker.cpp').read_text(encoding='utf-8')
enums=tracker[tracker.index('enum EnemyFinderCombat'):tracker.index('// NPC Speech checks are separate AP locations.')]
functions='\n'.join(function(tracker,s) for s in ('static bool EnemyFinderMelee(',
    'static bool EnemyFinderRanged(','static bool EnemyFinderCombatReachable(',
    'static bool EnemyFinderEncounterGate(','static bool IsEnemyDefeatReachable('))
code=r'''
#include <cassert>
#include <cstdint>
#include <iostream>
#include <memory>
#include <set>
#include "soh/Enhancements/randomizer/randomizerEnums.h"
struct SaveContext{};SaveContext gSaveContext;
namespace SohExtreme {template<class T,class S>struct ScopedCheckFinderLogic {ScopedCheckFinderLogic(T&,S&){};};}
namespace Rando {
struct Logic {
 bool IsAdult=false,IsChild=true,AtDay=true,AtNight=false;
 RandomizerRegion CurrentRegionKey=RR_KOKIRI_FOREST;
 RandomizerCheck CurrentCheckKey=RC_UNKNOWN_CHECK;
 std::set<RandomizerGet> inventory;
 bool CanUse(RandomizerGet i){return inventory.count(i)!=0;}
 bool HasItem(RandomizerGet i){return CanUse(i);}
 bool HasExplosives(){return CanUse(RG_BOMB_BAG);}
 bool CanReflectNuts(){return CanUse(RG_DEKU_SHIELD);}
 bool HasFireSourceWithTorch(){return false;}
 bool Get(int){return false;}
};
struct Context {
 std::shared_ptr<Logic> logic=std::make_shared<Logic>();
 static Context* GetInstance(){static Context c;return &c;}
 std::shared_ptr<Logic> GetLogic(){return logic;}
 bool GetOption(int){return false;}
};}
struct Region {
 bool childDay=false,childNight=false,adultDay=false,adultNight=false;
 bool HasAccess(){return childDay||childNight||adultDay||adultNight;}
};
Region forest,outside;
Region* RegionTable(RandomizerRegion r){return r==RR_KOKIRI_FOREST?&forest:r==RR_KF_OUTSIDE_DEKU_TREE?&outside:nullptr;}
bool soul=true;
bool MegaSoul_HasEnemyDefeatSoul(int){return soul;}
constexpr int ACTOR_EN_TUBO_TRAP=0x11D;
'''+enums+r'''
bool EnemyFinderRoomCondition(Rando::Logic*,const EnemyDefeatFinderEntry&){return true;}
'''+functions+r'''
int main(){
 auto l=Rando::Context::GetInstance()->GetLogic();int tests=0,count=0;
 forest.childDay=forest.childNight=true;
 for(const auto&e:kEnemyDefeatFinderEntries){
  if(e.scene==85&&e.room==1){assert(e.region==RR_KF_OUTSIDE_DEKU_TREE);++tests;}
  if(e.locationId<9800531||e.locationId>9800535)continue;
  ++count;assert(e.region==RR_KF_OUTSIDE_DEKU_TREE);assert(e.exactRegion);assert(e.spawnMask==3);tests+=3;
  for(bool gateOpen:{false,true})for(bool ownsSoul:{false,true})for(auto weapon:{RG_KOKIRI_SWORD,RG_BOOMERANG,RG_STICKS}){
   outside={gateOpen,gateOpen,false,false};soul=ownsSoul;l->inventory={weapon};
   assert(IsEnemyDefeatReachable(e)==(gateOpen&&ownsSoul&&weapon!=RG_STICKS));++tests;
  }
  // Adult access to the path cannot expose child-only placements.
  outside={false,false,true,true};soul=true;l->inventory={RG_MASTER_SWORD};
  assert(!IsEnemyDefeatReachable(e));++tests;
 }
 assert(count==5);std::cout<<"PASS "<<tests<<" native Mido region/combat assertions\n";
}
'''
src=out/'mido_native.cpp';exe=out/'mido_native.exe';src.write_text(code,encoding='utf-8')
build=subprocess.run(['cl','/nologo','/std:c++20','/Zc:preprocessor','/EHsc','/MD','/I',str(root),str(src),
    '/Fo'+str(out/'mido_native.obj'),'/Fe'+str(exe)],capture_output=True,text=True)
run=subprocess.run([str(exe)],capture_output=True,text=True) if build.returncode==0 else None
log=build.stdout+build.stderr+(run.stdout+run.stderr if run else '')
passed=build.returncode==0 and run.returncode==0
(out/'native.json').write_text(json.dumps(dict(passed=passed,log=log),indent=2),encoding='utf-8')
print(log);raise SystemExit(0 if passed else 1)
