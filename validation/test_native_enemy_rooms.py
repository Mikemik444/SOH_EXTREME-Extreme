"""Compile complete production finder functions, real enums and OptionValue,
with controlled engine/logic services. This is not a complete game build.
"""
import argparse,json,subprocess,shutil
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path,required=True);p.add_argument('--report',type=Path,required=True);p.add_argument('--compiler',default='clang++');a=p.parse_args()
root=a.source_root.resolve();out=a.report.resolve().parent/('native-enemy-rooms-'+a.compiler.replace('+','p'));out.mkdir(parents=True,exist_ok=True)
def function(s,sig):
 start=s.index(sig);pos=s.index('{',start);depth=0;mode='code';i=pos
 while i<len(s):
  c=s[i];n=s[i:i+2]
  if mode=='line':
   if c=='\n':mode='code'
  elif mode=='block':
   if n=='*/':mode='code';i+=1
  elif mode in ('"',"'"):
   if c=='\\':i+=1
   elif c==mode:mode='code'
  elif n=='//':mode='line';i+=1
  elif n=='/*':mode='block';i+=1
  elif c in ('"',"'"):mode=c
  elif c=='{':depth+=1
  elif c=='}':
   depth-=1
   if depth==0:return s[start:i+1]
  i+=1
 raise ValueError(sig)
s=(root/'soh/Enhancements/randomizer/randomizer_check_tracker.cpp').read_text()
enums=s[s.index('enum EnemyFinderCombat'):s.index('// NPC Speech checks are separate AP locations.')]
opt=(root/'soh/Enhancements/randomizer/option.h').read_text();opt=opt[opt.index('class OptionValue {'):opt.index('/**\n * @brief A class describing')]
impl=(root/'soh/Enhancements/randomizer/option.cpp').read_text();impl=impl[impl.index('OptionValue::OptionValue('):impl.index('size_t Option::GetOptionCount')]
functions='\n'.join(function(s,sig) for sig in ('static bool EnemyFinderMelee(', 'static bool EnemyFinderRanged(', 'static bool EnemyFinderCombatReachable(', 'static bool EnemyFinderRoomCondition(', 'static bool EnemyFinderEncounterGate(', 'static bool IsEnemyDefeatReachable('))
cpp=r'''
#include <algorithm>
#include <array>
#include <cstdint>
#include <cstdio>
#include <map>
#include <memory>
#include <set>
#include <string>
#include <vector>
#include "soh/Enhancements/randomizer/randomizerEnums.h"
#include "soh/Enhancements/randomizer/CheckFinderState.h"
// Only these actor/scene identifiers occur in the extracted finder functions.
constexpr int ACTOR_EN_TUBO_TRAP=0x11D;
struct SaveContext{};SaveContext gSaveContext;
namespace Rando {
'''+opt+impl+r'''
struct Logic {
 SaveContext* mSaveContext=nullptr;bool CalculatingAvailableChecks=false;
 bool IsAdult=false,IsChild=true,AtDay=true,AtNight=false;
 RandomizerRegion CurrentRegionKey=RR_ROOT;RandomizerCheck CurrentCheckKey=RC_UNKNOWN_CHECK;
 std::map<RandomizerGet,unsigned> useMask;
 bool has=true,localFlags=true,sunlight=true;int fire=100;
 void SetSaveContext(SaveContext* p){mSaveContext=p;}
 bool CanUse(RandomizerGet i)const {auto it=useMask.find(i);return (it==useMask.end()?15u:it->second)&(IsAdult?(AtNight?8u:4u):(AtNight?2u:1u));}
 bool HasItem(RandomizerGet)const{return has;}
 bool Get(RandomizerLogicFlag)const{return localFlags;}
 bool HasExplosives()const{return CanUse(RG_BOMB_BAG)||CanUse(RG_BOMBCHU_5);}
 bool CanReflectNuts()const{return CanUse(IsAdult?RG_HYLIAN_SHIELD:RG_DEKU_SHIELD);}
 bool HasFireSourceWithTorch()const{return CanUse(RG_DINS_FIRE)||CanUse(RG_FIRE_ARROWS)||CanUse(RG_STICKS);}
 int FireTimer()const{return fire;}
 bool SunlightArrows()const{return sunlight;}
};
class Context {
 public:
 std::map<RandomizerTrick,OptionValue> tricks;
 std::map<RandomizerSettingKey,OptionValue> opts;
 std::shared_ptr<Logic> logic=std::make_shared<Logic>();
 static std::shared_ptr<Context> GetInstance(){static auto ptr=std::make_shared<Context>();return ptr;}
 OptionValue& GetTrickOption(RandomizerTrick t){return tricks[t];}
 OptionValue& GetOption(RandomizerSettingKey t){return opts[t];}
 std::shared_ptr<Logic> GetLogic(){return logic;}
};
}
struct Region {bool childDay=false,childNight=false,adultDay=false,adultNight=false;bool HasAccess()const{return childDay||childNight||adultDay||adultNight;}};
std::map<RandomizerRegion,Region> regions;
Region* RegionTable(RandomizerRegion rr){return &regions[rr];}
bool soul=true;bool MegaSoul_HasEnemyDefeatSoul(int){return soul;}
'''+enums+functions+r'''
static int checks=0,failures=0;
void ck(bool ok,const char* name){++checks;if(!ok){++failures;if(failures<10)std::printf("FAIL %s\n",name);}}
int main(){
 auto ctx=Rando::Context::GetInstance();auto logic=ctx->logic;
 std::set<int64_t> ids;
 for (const auto& entry:kEnemyDefeatFinderEntries){
  ck(ids.insert(entry.locationId).second,"unique network identity");
  ck(entry.locationId<9800765LL||entry.locationId>=9800786LL,"offspring remain excluded");
  for(unsigned access=0;access<16;++access){
   *RegionTable(entry.region)={bool(access&1),bool(access&2),bool(access&4),bool(access&8)};
   logic->IsChild=false;logic->IsAdult=true;logic->AtDay=false;logic->AtNight=true;
   logic->CurrentRegionKey=RR_ROOT;logic->CurrentCheckKey=RC_UNKNOWN_CHECK;
   bool expected=bool(access&entry.spawnMask);
   // Night-gated actors only activate at night (their normal masks are night-only).
   if(entry.gate==EFG_NIGHT)expected=bool(access&entry.spawnMask&10u);
   // Forest block-top is an explicitly adult-only ledge.
   if(entry.gate==EFG_FOREST_BLOCK_TOP)expected=bool(access&entry.spawnMask&12u);
   ck(IsEnemyDefeatReachable(entry)==expected,"same reachable age/time + local condition");
   ck(logic->IsAdult&&!logic->IsChild&&!logic->AtDay&&logic->AtNight&&logic->CurrentRegionKey==RR_ROOT,"scope restores previous age/time/region");
   ck(!logic->CalculatingAvailableChecks&&logic->mSaveContext==nullptr,"scope restores save mode");
  }
  *RegionTable(entry.region)={true,true,true,true};soul=false;
  ck(!IsEnemyDefeatReachable(entry),"missing soul blocks each entry");soul=true;
 }
 // The complete production room-condition switch against an independent truth table.
 for(unsigned mask=0;mask<32;++mask)for(unsigned tricks=0;tricks<4;++tricks)for(int timer:{0,15,16,23,24}){
  logic->useMask[RG_LENS_OF_TRUTH]=(mask&1)?15:0;
  logic->useMask[RG_ZELDAS_LULLABY]=(mask&2)?15:0;
  logic->useMask[RG_FAIRY_BOW]=(mask&4)?15:0;
  logic->useMask[RG_MIRROR_SHIELD]=(mask&8)?15:0;
  logic->sunlight=mask&16;logic->fire=timer;
  ctx->GetTrickOption(RT_LENS_SHADOW).Set(tricks&1);ctx->GetTrickOption(RT_LENS_GANON).Set((tricks>>1)&1);
  for(const auto& entry:kEnemyDefeatFinderEntries){
   bool expected=true;
   switch(entry.locationId){
    case 9800364:expected=(mask&1)||(tricks&1);break;
    case 9800370:case 9800371:expected=mask&2;break;
    case 9800462:case 9800463:case 9800464:case 9800465:expected=(mask&1)||(tricks&2);break;
    case 9800469:case 9800470:case 9800471:expected=timer>=16;break;
    case 9800472:case 9800473:expected=timer>=24;break;
    case 9800481:case 9800482:case 9800483:expected=(mask&4)&&((mask&8)||(mask&16));break;
   }
   ck(EnemyFinderRoomCondition(logic.get(),entry)==expected,"local-room switch truth table");
  }
 }
 std::printf("entries=%zu checks=%d failures=%d\n",ids.size(),checks,failures);
 return failures?1:0;
}
'''
cpp=cpp.replace('RandomizerLogicFlag','LogicVal')
source=out/'enemy_rooms.cpp';source.write_text(cpp);exe=out/'enemy_rooms'
cmd=[shutil.which(a.compiler) or a.compiler,'-std=c++20','-O1','-Werror=return-type','-I',str(root),str(source),'-o',str(exe)]
c=subprocess.run(cmd,text=True,capture_output=True,timeout=45)
r=subprocess.run([str(exe)],text=True,capture_output=True,timeout=30) if c.returncode==0 else None
report={'scope':__doc__,'compiler':a.compiler,'command':cmd,'compile_exit':c.returncode,'compile_stdout':c.stdout,'compile_stderr':c.stderr,'run_exit':None if r is None else r.returncode,'stdout':'' if r is None else r.stdout,'stderr':'' if r is None else r.stderr,'passed':c.returncode==0 and r.returncode==0}
a.report.write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2));raise SystemExit(0 if report['passed'] else 1)
