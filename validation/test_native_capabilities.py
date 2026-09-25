"""Compile production capability helpers/conditions with actual native enums.
Controlled inventory/context services, NOT a complete game build/physics test.
"""
import argparse,subprocess,json,shutil
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path,required=True);p.add_argument('--overlay',type=Path,required=True);p.add_argument('--report',type=Path,required=True);p.add_argument('--compiler',default='clang++');a=p.parse_args()
r=a.source_root.resolve();o=a.overlay.resolve();build=a.report.parent/'native-capabilities';build.mkdir(parents=True,exist_ok=True)
def read(n):return (o/n if (o/n).exists() else r/n).read_text()
def function(s,sig):
 start=s.index(sig);i=s.index('{',start);depth=0;mode='code'
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
   if not depth:return s[start:i+1]
  i+=1
 raise ValueError(sig)
opt=read('soh/Enhancements/randomizer/option.h');opt=opt[opt.index('class OptionValue {'):opt.index('/**\n * @brief A class describing')]
impl=read('soh/Enhancements/randomizer/option.cpp');impl=impl[impl.index('OptionValue::OptionValue('):impl.index('size_t Option::GetOptionCount')]
logic=read('soh/Enhancements/randomizer/logic.cpp');loc=read('soh/Enhancements/randomizer/location_access.cpp');hooks=read('soh/Enhancements/randomizer/hook_handlers.cpp');talk=read('soh/Enhancements/randomizer/ShuffleSpeak.cpp')
strength=logic[logic.index('        case RG_GORONS_BRACELET:'):logic.index('        case RG_PROGRESSIVE_BOMB_BAG:')]
boots=logic[logic.index('        case RG_IRON_BOOTS:',logic.index('bool Logic::CanUse(')):logic.index('        case RG_HOVER_BOOTS:',logic.index('bool Logic::CanUse('))]
water_start=hooks.index('    if (',hooks.index('void RandomizerOnPlayerUpdateHandler()'))
water=hooks[water_start+len('    if ('):hooks.index(') {',water_start)]
# Entire actual business-scrub callback body (not a reimplementation).
start=talk.index('    COND_VB_SHOULD(VB_BUSINESS_SCRUB_SPEAK,');body=function(talk,talk[start:talk.index('{',start)+1]);body=body[body.index('{')+1:-1]
source=r'''
#include <algorithm>
#include <array>
#include <cstdio>
#include <memory>
#include <set>
#include <string>
#include <vector>
#include "z64.h"
#include "macros.h"
#include "soh/Enhancements/randomizer/randomizerEnums.h"
namespace Rando {
'''+opt+impl+r'''
class Context { public:
 std::array<OptionValue,RSK_MAX> options{};std::array<OptionValue,RT_MAX> tricks{};
 static std::shared_ptr<Context> GetInstance(){static auto p=std::make_shared<Context>();return p;}
 OptionValue& GetOption(RandomizerSettingKey k){return options[k];}
 OptionValue& GetTrickOption(RandomizerTrick k){return tricks[k];}
};
class Location {public:
 RandomizerCheck check=RC_UNKNOWN_CHECK; ActorID actor=ACTOR_ID_MAX;int type=RCTYPE_MERCHANT;std::string name;
 RandomizerCheck GetRandomizerCheck()const{return check;} ActorID GetActorID()const{return actor;}
 int GetRCType()const{return type;} const std::string& GetName()const{return name;}
};
class Logic { public:
 std::shared_ptr<Context> ctx=Context::GetInstance();std::set<RandomizerGet> items;bool IsAdult=false;int strength=0;
 int CurrentUpgrade(int)const{return strength;}
 bool HasItem(RandomizerGet itemName){switch(itemName){
'''+strength+r'''
 default:return items.count(itemName)!=0;}}
 bool CanUse(RandomizerGet item){if(!HasItem(item))return false;switch(item){
'''+boots+r'''
 case RG_KOKIRI_SWORD:case RG_BOOMERANG:case RG_FAIRY_SLINGSHOT:case RG_STICKS:return !IsAdult;
 case RG_MEGATON_HAMMER:case RG_MASTER_SWORD:case RG_BIGGORON_SWORD:case RG_GIANTS_KNIFE:case RG_HOOKSHOT:case RG_LONGSHOT:case RG_FAIRY_BOW:case RG_ZORA_TUNIC:return IsAdult;
 default:return true;}}
 int Health()const{return 48;}
 bool CanJumpslash(){return CanUse(RG_KOKIRI_SWORD)||CanUse(RG_MASTER_SWORD)||CanUse(RG_STICKS)||CanUse(RG_MEGATON_HAMMER);}
 bool HasExplosives();bool CanBreakPots(EnemyDistance=ED_CLOSE,bool=true,bool=false);
 bool CanBreakCrates();bool CanBreakSmallCrates();bool CanBreakRocks();bool CanBonkTrees();
 bool HasAnimalSoul(RandomizerGet);uint16_t WaterTimer();
};
'''+ '\n'.join(function(logic,sig) for sig in ['bool Logic::HasExplosives()','bool Logic::CanBreakPots(','bool Logic::CanBreakCrates()','bool Logic::CanBreakSmallCrates()','bool Logic::CanBreakRocks()','bool Logic::CanBonkTrees()','bool Logic::HasAnimalSoul(','uint16_t Logic::WaterTimer()'])+r'''
}
'''+function(loc,'static RandomizerGet MegaSpeakItemForLocation(')+r'''
static int checks=0,failures=0;
static void ck(bool b,const char* label){++checks;if(!b){++failures;if(failures<10)std::printf("FAIL %s\n",label);}}
static bool swimFlag=false,npcFlag=false,speakFlag=false;
extern "C" s32 Flags_GetRandomizerInf(RandomizerInf flag){return flag==RAND_INF_CAN_SWIM?swimFlag:flag==RAND_INF_NPC_SOUL?npcFlag:flag==RAND_INF_CAN_SPEAK_DEKU?speakFlag:false;}
static PlayState play{};static Player player{};PlayState* gPlayState=&play;
static bool WaterVoids(){return '''+water+r''';}
static void ScrubSpeak(bool* should){'''+body+r'''}
int main(){
 auto ctx=Rando::Context::GetInstance();Rando::Logic l;
 const RandomizerGet items[]={RG_POWER_BRACELET,RG_ROLL,RG_KOKIRI_SWORD,RG_BOMB_BAG,RG_MEGATON_HAMMER};
 for(int shuffled=0;shuffled<2;++shuffled)for(int soul=0;soul<2;++soul)for(int mask=0;mask<32;++mask)for(int age=0;age<2;++age){
  l.items.clear();l.IsAdult=age;ctx->GetOption(RSK_SHUFFLE_ROLL).Set(shuffled);
  for(auto option:{RSK_SHUFFLE_POT_SOUL,RSK_SHUFFLE_CRATE_SOUL,RSK_SHUFFLE_ROCK_SOUL,RSK_SHUFFLE_TREE_SOUL})ctx->GetOption(option).Set(shuffled);
  if(soul)for(auto item:{RG_POT_SOUL,RG_CRATE_SOUL,RG_ROCK_SOUL,RG_TREE_SOUL})l.items.insert(item);
  for(int i=0;i<5;++i)if(mask&(1<<i))l.items.insert(items[i]);
  bool exists=!shuffled||soul,grab=mask&1,roll=!shuffled||(mask&2),sword=!age&&(mask&4),bomb=mask&8,hammer=age&&(mask&16);
  ck(l.CanBreakPots()==(exists&&(grab||sword||bomb||hammer)),"pot method and existence");
  ck(l.CanBreakCrates()==(exists&&(roll||bomb||hammer)),"fixed crate method and existence");
  ck(l.CanBreakSmallCrates()==(exists&&(roll||grab||sword||bomb||hammer)),"small crate method and existence");
  ck(l.CanBreakRocks()==(exists&&(bomb||grab)),"rock method and existence");
  ck(l.CanBonkTrees()==(exists&&roll),"tree needs Roll");
 }
 for(int mode=0;mode<3;++mode)for(int mask=0;mask<4;++mask){
  ctx->GetOption(RSK_SHUFFLE_ANIMAL_SOUL).Set(mode);l.items.clear();
  if(mask&1)l.items.insert(RG_ANIMAL_SOUL);if(mask&2)l.items.insert(RG_ANIMAL_SOUL_CUCCO);
  ck(l.HasAnimalSoul(RG_ANIMAL_SOUL_CUCCO)==(mode==0||(mode==1?bool(mask&1):bool(mask&2))),"Cucco exact soul mode");
 }
 for(int grab=0;grab<2;++grab)for(int level=0;level<4;++level){
  l.items.clear();if(grab)l.items.insert(RG_POWER_BRACELET);l.strength=level;
  ck(l.HasItem(RG_GORONS_BRACELET)==bool(grab&&level>=1),"Goron strength still needs Grab");
  ck(l.HasItem(RG_SILVER_GAUNTLETS)==bool(grab&&level>=2),"Silver strength still needs Grab");
  ck(l.HasItem(RG_GOLDEN_GAUNTLETS)==bool(grab&&level>=3),"Golden strength still needs Grab");
 }
 for(int swim=0;swim<2;++swim)for(int adult=0;adult<2;++adult){
  l.items={RG_IRON_BOOTS,RG_ZORA_TUNIC};l.IsAdult=adult;if(swim)l.items.insert(RG_BRONZE_SCALE);
  ck(l.CanUse(RG_IRON_BOOTS)==bool(swim&&adult),"Irons do not replace Swim");
  ck(l.WaterTimer()==(swim&&adult?UINT16_MAX:0),"water timer needs Swim");
 }
 play.actorCtx.actorLists[ACTORCAT_PLAYER].head=&player.actor;
 for(int swim=0;swim<2;++swim)for(int water=0;water<2;++water)for(int transition=0;transition<2;++transition)for(int boots=0;boots<3;++boots){
  swimFlag=swim;player.stateFlags1=water?PLAYER_STATE1_IN_WATER:0;player.currentBoots=boots;
  play.transitionTrigger=transition?TRANS_TRIGGER_START:TRANS_TRIGGER_OFF;
  ck(WaterVoids()==bool(water&&!swim&&!transition),"water contact void regardless boots");
 }
 for(int npcSetting=0;npcSetting<2;++npcSetting)for(int speakSetting=0;speakSetting<3;++speakSetting)for(int flags=0;flags<4;++flags){
  ctx->GetOption(RSK_SHUFFLE_NPC_SOUL).Set(npcSetting);ctx->GetOption(RSK_SHUFFLE_SPEAK).Set(speakSetting);
  npcFlag=flags&1;speakFlag=flags&2;bool should=true;ScrubSpeak(&should);
  ck(should==bool((!npcSetting||npcFlag)&&(!speakSetting||speakFlag)),"scrub trade NPC and speech prerequisites");
  should=false;ScrubSpeak(&should);ck(!should,"scrub guard must not override another denial");
 }
 Rando::Location location;
 for(auto rc:{RC_ZR_MAGIC_BEAN_SALESMAN,RC_WASTELAND_BOMBCHU_SALESMAN,RC_KAK_GRANNYS_SHOP}){
  location.check=rc;location.name="ZR Gerudo Goron misleading area";ck(MegaSpeakItemForLocation(&location)==RG_SPEAK_HYLIAN,"merchant identity before area fallback");
 }
 location.check=RC_GC_MEDIGORON;ck(MegaSpeakItemForLocation(&location)==RG_SPEAK_GORON,"Medigoron language");
 location.check=RC_UNKNOWN_CHECK;location.type=RCTYPE_SCRUB;ck(MegaSpeakItemForLocation(&location)==RG_SPEAK_DEKU,"business scrub language before area fallback");
 std::printf("checks=%d failures=%d\n",checks,failures);return failures?1:0;
}
'''
path=build/'capabilities.cpp';path.write_text(source);exe=build/'capabilities'
cmd=[shutil.which(a.compiler) or a.compiler,'-std=c++20','-fms-extensions','-O1']
for d in [o,r,r/'include',r/'src',r/'soh',r/'assets',r/'libultraship/include']:cmd+=['-I',str(d)]
cmd +=[str(path),'-o',str(exe)]
c=subprocess.run(cmd,capture_output=True,text=True,timeout=45);result={'compile_command':cmd,'compile_exit':c.returncode,'compile_stderr':c.stderr}
x=subprocess.run([str(exe)],capture_output=True,text=True,timeout=20) if not c.returncode else None
result.update(passed=c.returncode==0 and x.returncode==0,run_exit=x.returncode if x else None,stdout=x.stdout if x else '',stderr=x.stderr if x else '',scope=__doc__)
a.report.write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2));raise SystemExit(not result['passed'])
