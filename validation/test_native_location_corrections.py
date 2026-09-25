"""Compile production correction bodies against production enums and OptionValue.

Engine/save inventory services are controlled; no game executable, MSVC or live
physics validation. The shared LACS policy is compared between both real callers.
"""
from pathlib import Path
import argparse,json,re,shutil,subprocess
p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path,required=True);p.add_argument('--report',type=Path,required=True);p.add_argument('--compiler',default='clang++');a=p.parse_args()
r=a.source_root;build=a.report.parent/('native-locations-'+a.compiler.replace('+','p'));build.mkdir(parents=True,exist_ok=True)
def function(text,sig):
 start=text.index(sig);i=text.index('{',start);level=0;mode='code'
 while i<len(text):
  c=text[i];d=text[i:i+2]
  if mode=='line':
   if c=='\n':mode='code'
  elif mode=='block':
   if d=='*/':mode='code';i+=1
  elif mode in ('"',"'"):
   if c=='\\':i+=1
   elif c==mode:mode='code'
  elif d=='//':mode='line';i+=1
  elif d=='/*':mode='block';i+=1
  elif c in ('"',"'"):mode=c
  elif c=='{':level+=1
  elif c=='}':
   level-=1
   if level==0:return text[start:i+1]
  i+=1
 raise ValueError(sig)
base=r/'soh/Enhancements/randomizer';lg=(base/'logic.cpp').read_text();hk=(base/'hook_handlers.cpp').read_text();la=(base/'location_access.cpp').read_text()
opt=(base/'option.h').read_text();opt=opt[opt.index('class OptionValue {'):opt.index('/**\n * @brief A class describing')]
impl=(base/'option.cpp').read_text();impl=impl[impl.index('OptionValue::OptionValue('):impl.index('size_t Option::GetOptionCount')]
common='''#include <array>
#include <algorithm>
#include <string>
#include <memory>
#include <set>
#include <cstdio>
#include "soh/Enhancements/randomizer/randomizerEnums.h"
#include "soh/Enhancements/randomizer/LacsRequirements.h"
#include "soh/Network/Archipelago/ArchipelagoC.h"
namespace Rando {
'''+opt+impl+'''
class Context {public:
 std::array<OptionValue,RSK_MAX> values{};
 OptionValue& GetOption(RandomizerSettingKey k){return values[k];}
};
}
static auto ctx=std::make_shared<Rando::Context>();
static bool apSave=false;
extern "C" bool Archipelago_IsCurrentSaveFile(void){return apSave;}
static unsigned tests=0,failures=0;
void check(bool v,const char* l){++tests;if(!v){++failures;if(failures<12)std::printf("FAIL %s\\n",l);}}
int finish(){std::printf("assertions=%u failures=%u\\n",tests,failures);return failures?1:0;}
'''
results=[]
def run(name,source):
 path=build/(name+'.cpp');exe=build/name;path.write_text(source)
 cmd=[shutil.which(a.compiler) or a.compiler,'-std=c++20','-fms-extensions','-Wall','-Wextra','-I',str(r),str(path),'-o',str(exe)]
 c=subprocess.run(cmd,capture_output=True,text=True,timeout=45);z=subprocess.run([str(exe)],capture_output=True,text=True,timeout=30) if c.returncode==0 else None
 result=dict(name=name,passed=c.returncode==0 and z.returncode==0,compile_exit=c.returncode,run_exit=z.returncode if z else None,command=cmd,compile_stdout=c.stdout,compile_stderr=c.stderr,stdout=z.stdout if z else '',stderr=z.stderr if z else '')
 results.append(result);print(name,result['passed'],result['stdout'],result['compile_stderr'][:3000],flush=True)

source=common+'''
namespace Rando { class Logic {public:
 std::set<RandomizerGet> items;bool child=true;
 bool HasItem(RandomizerGet k){
  if(k==RG_POWER_BRACELET&&!ctx->GetOption(RSK_SHUFFLE_GRAB))return true;
  return items.contains(k);
 }
 bool CanUse(RandomizerGet k){
  if((k==RG_MASTER_SWORD||k==RG_MEGATON_HAMMER||k==RG_BIGGORON_SWORD||k==RG_GIANTS_KNIFE)&&child)return false;
  if((k==RG_KOKIRI_SWORD||k==RG_BOOMERANG)&&!child)return false;
  return items.contains(k);
 }
 bool HasExplosives(){return items.contains(RG_BOMB_BAG)||items.contains(RG_BOMBCHU_5);}
 bool CanCutShrubs();bool CanPickUpGrass();bool CanCollectGrass();
};
'''+ '\n'.join(function(lg,s) for s in ('bool Logic::CanCutShrubs(','bool Logic::CanPickUpGrass(','bool Logic::CanCollectGrass('))+'''
}
static auto logic=std::make_shared<Rando::Logic>();
static bool boulderGate(int t) {switch(t){
'''+la[la.index('        case RCTYPE_BOULDER:'):la.index('        case RCTYPE_TREE:')]+'''
 default:return false;}}
int main(){
 const RandomizerGet tools[]={RG_KOKIRI_SWORD,RG_BOOMERANG,RG_BOMB_BAG,RG_BOMBCHU_5,RG_MASTER_SWORD,RG_MEGATON_HAMMER,RG_BIGGORON_SWORD,RG_GIANTS_KNIFE};
 for(int soulShuffle=0;soulShuffle<2;++soulShuffle)for(int grabShuffle=0;grabShuffle<2;++grabShuffle)
 for(int soul=0;soul<2;++soul)for(int grab=0;grab<2;++grab)for(int child=0;child<2;++child)for(unsigned mask=0;mask<256;++mask){
  ctx->GetOption(RSK_SHUFFLE_GRASS_SOUL).Set(soulShuffle);ctx->GetOption(RSK_SHUFFLE_GRAB).Set(grabShuffle);
  logic->items.clear();logic->child=child;
  if(soul)logic->items.insert(RG_GRASS_SOUL);if(grab)logic->items.insert(RG_POWER_BRACELET);
  bool cut=false;
  for(unsigned i=0;i<8;++i)if(mask&(1u<<i)){
   logic->items.insert(tools[i]);
   // Independent age/tool truth table, not a call to the implementation.
   if((i<2&&child)||(i>=2&&i<4)||(i>=4&&!child))cut=true;
  }
  bool exists=!soulShuffle||soul;
  check(logic->CanCollectGrass()==(exists&&(cut||!grabShuffle||grab)),"grass collection OR alternatives");
  check(logic->CanCutShrubs()==(exists&&cut),"resource cutting remains separate");
 }
 for(int shuffle=0;shuffle<2;++shuffle)for(int soul=0;soul<2;++soul){
  ctx->GetOption(RSK_SHUFFLE_ROCK_SOUL).Set(shuffle);logic->items.clear();if(soul)logic->items.insert(RG_ROCK_SOUL);
  check(boulderGate(RCTYPE_BOULDER)==(!shuffle||soul),"boulder material rule not overwritten by generic method");
 }
 return finish();}
'''
run('grass_alternatives_and_boulder_gate',source)

source=common+'''
struct Inventory {unsigned stones=0,medallions=0,dungeons=0;struct{unsigned gsTokens=0;}inventory;std::set<RandomizerGet>items;};
static Inventory gSaveContext;
#define RAND_GET_OPTION(k) ctx->GetOption(k)
#define CHECK_QUEST_ITEM(q) gSaveContext.items.contains((q)==0?RG_SHADOW_MEDALLION:RG_SPIRIT_MEDALLION)
#define QUEST_MEDALLION_SHADOW 0
#define QUEST_MEDALLION_SPIRIT 1
unsigned CheckStoneCount(){return gSaveContext.stones;}
unsigned CheckMedallionCount(){return gSaveContext.medallions;}
unsigned CheckDungeonCount(){return gSaveContext.dungeons;}
bool Flags_GetRandomizerInf(RandomizerInf k){return k==RAND_INF_GREG_FOUND&&gSaveContext.items.contains(RG_GREG_RUPEE);}
namespace Rando {class Logic {public:
 bool HasItem(RandomizerGet k){return gSaveContext.items.contains(k);}
 unsigned StoneCount(){return gSaveContext.stones;}unsigned MedallionCount(){return gSaveContext.medallions;}
 unsigned DungeonCount(){return gSaveContext.dungeons;}unsigned GetGSCount(){return gSaveContext.inventory.gsTokens;}
 bool CanTriggerLacs();
};
'''+function(lg,'bool Logic::CanTriggerLacs()')+'''\n}\n'''+function(hk,'static bool MeetsLacsRequirementsForSave()')+'''
int main(){
 Rando::Logic logic;
 unsigned modes[]={RO_GANON_BOSS_KEY_VANILLA,RO_GANON_BOSS_KEY_ANYWHERE,RO_GANON_BOSS_KEY_STONES,RO_GANON_BOSS_KEY_MEDALLIONS,RO_GANON_BOSS_KEY_REWARDS,RO_GANON_BOSS_KEY_DUNGEONS,RO_GANON_BOSS_KEY_TOKENS};
 for(auto k:{RSK_GBK_STONE_COUNT,RSK_GBK_MEDALLION_COUNT,RSK_GBK_REWARD_COUNT,RSK_GBK_DUNGEON_COUNT,RSK_GBK_TOKEN_COUNT})ctx->GetOption(k).Set(3);
 for(int ap=0;ap<2;++ap)for(int hunt=0;hunt<2;++hunt)for(auto mode:modes)for(unsigned n=0;n<4;++n)
 for(int shadow=0;shadow<2;++shadow)for(int spirit=0;spirit<2;++spirit)for(int greg=0;greg<2;++greg){
  apSave=ap;ctx->GetOption(RSK_TRIFORCE_HUNT_PIECES_TOTAL).Set(hunt?60:0);ctx->GetOption(RSK_GANONS_BOSS_KEY).Set(mode);ctx->GetOption(RSK_GBK_OPTIONS).Set(RO_CHECK_TRIGGER_GREG_REWARD);
  gSaveContext.items.clear();if(shadow)gSaveContext.items.insert(RG_SHADOW_MEDALLION);if(spirit)gSaveContext.items.insert(RG_SPIRIT_MEDALLION);if(greg)gSaveContext.items.insert(RG_GREG_RUPEE);
  gSaveContext.stones=n;gSaveContext.medallions=n;gSaveContext.dungeons=n;gSaveContext.inventory.gsTokens=n;
  bool expected=shadow&&spirit;
  if(ap&&!hunt){
   if(mode==RO_GANON_BOSS_KEY_STONES||mode==RO_GANON_BOSS_KEY_MEDALLIONS||mode==RO_GANON_BOSS_KEY_DUNGEONS)expected=n+greg>=3;
   if(mode==RO_GANON_BOSS_KEY_REWARDS)expected=2*n+greg>=3;
   if(mode==RO_GANON_BOSS_KEY_TOKENS)expected=n>=3;
  }
  check(logic.CanTriggerLacs()==expected,"native LACS logic policy");
  check(MeetsLacsRequirementsForSave()==expected,"actual save LACS trigger policy");
 }
 // Explicitly preserve the intended wildcard difference: an out-of-logic bonus
 // may trigger in-game, but must not be relied upon by item placement/tracking.
 apSave=true;ctx->GetOption(RSK_TRIFORCE_HUNT_PIECES_TOTAL).Set(0);ctx->GetOption(RSK_GANONS_BOSS_KEY).Set(RO_GANON_BOSS_KEY_STONES);ctx->GetOption(RSK_GBK_OPTIONS).Set(RO_CHECK_TRIGGER_WILDCARD_REWARD);
 gSaveContext.stones=2;gSaveContext.items={RG_GREG_RUPEE};
 check(!logic.CanTriggerLacs(),"wildcard not in logic");check(MeetsLacsRequirementsForSave(),"wildcard still works in game");
 return finish();}
'''
run('lacs_runtime_and_logic_callers',source)
# Compile every generated native RC binding against the production enum list.
source=common+'''
#include <unordered_set>
#include <utility>
static const std::pair<int,long long> bindings[] = {
#include "soh/Network/Archipelago/ArchipelagoLocationMap.inc"
};
int main(){std::unordered_set<int>rcs;std::unordered_set<long long>ids;
for(auto p:bindings){check(rcs.insert(p.first).second,"unique native RC");check(ids.insert(p.second).second,"unique AP ID");check(p.second!=943&&p.second!=944,"retired nonexistent pot IDs");}
return finish();}
'''
run('native_explicit_location_bindings',source)
report=dict(scope=__doc__,compiler=a.compiler,tests=results,all_passed=all(x['passed'] for x in results));a.report.write_text(json.dumps(report,indent=2));raise SystemExit(not report['all_passed'])
