"""Compile production CanUse, animal-soul helpers, NPC classifier and bush/grass
interaction branches against the supplied native enums and OptionValue type.
Inventory/context and engine flag reads are controlled test services.
This is NOT an engine playthrough or complete MSVC executable build.
"""
from pathlib import Path
import argparse,json,re,shutil,subprocess
p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path,required=True);p.add_argument('--report',type=Path,required=True);p.add_argument('--compiler',default='clang++');a=p.parse_args();root=a.source_root.resolve();out=a.report.parent/('native-fishing-'+a.compiler.replace('+','p'));out.mkdir(parents=True,exist_ok=True)
def text(path):return (root/path).read_text()
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
opt=text('soh/Enhancements/randomizer/option.h');opt=opt[opt.index('class OptionValue {'):opt.index('/**\n * @brief A class describing')]
impl=text('soh/Enhancements/randomizer/option.cpp');impl=impl[impl.index('OptionValue::OptionValue('):impl.index('size_t Option::GetOptionCount')]
lg=text('soh/Enhancements/randomizer/logic.cpp');ms=text('soh/Enhancements/randomizer/MegaSouls.cpp');la=text('soh/Enhancements/randomizer/location_access.cpp')
source=r'''
#include <algorithm>
#include <array>
#include <cstdio>
#include <memory>
#include <set>
#include <string>
#include "z64.h"
#include "macros.h"
#include "soh/Enhancements/randomizer/FishingSoulAccess.h"
#include "soh/Enhancements/randomizer/randomizerEnums.h"
#define SPDLOG_INFO(...) do {} while(0)
namespace Rando {
'''+opt+impl+r'''
class Context {public:
 std::array<OptionValue,RSK_MAX> options{};
 OptionValue& GetOption(RandomizerSettingKey k){return options[k];}
};
}
static auto ctx=std::make_shared<Rando::Context>();
static bool testRando=true;
#undef IS_RANDO
#define IS_RANDO testRando
#define RAND_GET_OPTION(k) ctx->GetOption(k)
static std::set<RandomizerInf> flags;
extern "C" s32 Flags_GetRandomizerInf(RandomizerInf f){return flags.contains(f);}
'''+ '\n'.join(function(ms,sig) for sig in [
 'static bool MegaHas(', 'extern "C" bool MegaSoul_IsFishingOwnerPresent(',
 'extern "C" bool MegaSoul_ArePondFishPresent(', 'extern "C" bool MegaSoul_CanTalkToFishingOwner(',
 'static bool IsMegaAnimalActor(', 'static bool IsMegaScrubActor(', 'static bool IsMegaNpcSoulActor(']) +r'''
namespace Rando {
class Logic {public:
 bool IsChild=true,IsAdult=false;
 std::set<RandomizerGet> items;
 bool HasItem(RandomizerGet r) {
  // Native non-shuffled defaults are granted when the save/logic state is
  // initialized. Supply those defaults without inventing extra received items.
  if(r==RG_FISHING_POLE&&!ctx->GetOption(RSK_SHUFFLE_FISHING_POLE))return true;
  if(r==RG_CHILD_WALLET&&!ctx->GetOption(RSK_SHUFFLE_CHILD_WALLET))return true;
  if(r==RG_SPEAK_HYLIAN&&!ctx->GetOption(RSK_SHUFFLE_SPEAK))return true;
  return items.contains(r);
 }
 bool Get(LogicVal){return false;}
 bool ItemUseAllowed(RandomizerGet){return true;}
 bool BombchuRefill(){return false;}
 bool BombchusEnabled(){return false;}
 bool HasExplosives(){return CanUse(RG_BOMB_BAG);}
 bool CanUse(RandomizerGet);
 bool HasAnimalSoul(RandomizerGet);
 bool CanCutShrubs();bool CanPickUpGrass();
};
'''+ '\n'.join(function(lg,sig) for sig in ['bool Logic::CanUse(', 'bool Logic::HasAnimalSoul(', 'bool Logic::CanCutShrubs(', 'bool Logic::CanPickUpGrass(']) +r'''
}
static auto logic=std::make_shared<Rando::Logic>();
static bool objectInteraction(int kind) {switch(kind) {
'''+la[la.index('        case RCTYPE_GRASS:'):la.index('        case RCTYPE_ROCK:',la.index('        case RCTYPE_GRASS:'))]+r'''
 default:return false;
}}
static int cases=0,failures=0;
static void ck(bool got,bool expected,const char* what){++cases;if(got!=expected){++failures;if(failures<10)std::printf("FAIL %s\n",what);}}
int main(){
 // Verify the overloaded actor ID is classified by role, before category.
 for(int category:{ACTORCAT_NPC,ACTORCAT_PROP,ACTORCAT_ENEMY}) {
  for(int param:{1,99,100,114,115,116,200}) {
   Actor a{};a.id=ACTOR_FISHING;a.category=category;a.params=param;
   ck(IsMegaNpcSoulActor(&a),param<100,"fishing owner/fish NPC classification");
  }
 }
 ck(IsMegaNpcSoulActor(nullptr),false,"null actor");
 // Actual runtime soul predicates: NPC visibility, speech, fish presence
 // are three independent facts. A generic soul cannot replace Fish in mode 2.
 for(int rando=0;rando<2;++rando)for(int npcShuffle=0;npcShuffle<2;++npcShuffle)
 for(int speakMode=0;speakMode<3;++speakMode)for(int animalMode=0;animalMode<3;++animalMode)
 for(int mask=0;mask<16;++mask) {
  testRando=rando;ctx->GetOption(RSK_SHUFFLE_NPC_SOUL).Set(npcShuffle);
  ctx->GetOption(RSK_SHUFFLE_SPEAK).Set(speakMode);ctx->GetOption(RSK_SHUFFLE_ANIMAL_SOUL).Set(animalMode);
  flags.clear();if(mask&1)flags.insert(RAND_INF_NPC_SOUL);if(mask&2)flags.insert(RAND_INF_CAN_SPEAK_HYLIAN);
  if(mask&4)flags.insert(RAND_INF_ANIMAL_SOUL);if(mask&8)flags.insert(RAND_INF_ANIMAL_SOUL_FISH);
  const bool owner=!rando||!npcShuffle||(mask&1);
  const bool talk=owner&&(!rando||!speakMode||(mask&2));
  const bool fish=!rando||!animalMode||(animalMode==1?(mask&4):(mask&8));
  ck(MegaSoul_IsFishingOwnerPresent(),owner,"owner presence");
  ck(MegaSoul_CanTalkToFishingOwner(),talk,"owner talk prerequisite");
  ck(MegaSoul_ArePondFishPresent(),fish,"independent fish visibility");
 }
 testRando=true;
 // Repeated in-room receive/remove: callbacks must not need a re-entry.
 flags.clear();ctx->GetOption(RSK_SHUFFLE_NPC_SOUL).Set(1);ctx->GetOption(RSK_SHUFFLE_SPEAK).Set(2);ctx->GetOption(RSK_SHUFFLE_ANIMAL_SOUL).Set(2);
 ck(MegaSoul_ArePondFishPresent(),false,"fish absent initially");flags.insert(RAND_INF_ANIMAL_SOUL_FISH);
 ck(MegaSoul_ArePondFishPresent(),true,"fish receipt reveals fish");ck(MegaSoul_IsFishingOwnerPresent(),false,"fish receipt does not reveal owner");
 flags.insert(RAND_INF_NPC_SOUL);ck(MegaSoul_CanTalkToFishingOwner(),false,"NPC receipt alone cannot speak");
 flags.insert(RAND_INF_CAN_SPEAK_HYLIAN);ck(MegaSoul_CanTalkToFishingOwner(),true,"speak completes owner access");
 flags.erase(RAND_INF_ANIMAL_SOUL_FISH);ck(MegaSoul_ArePondFishPresent(),false,"fish removal hides fish again");
 // Native pond action (complete production CanUse), both ages and modes.
 for(int age=0;age<2;++age)for(int npcShuffle=0;npcShuffle<2;++npcShuffle)
 for(int speakMode=0;speakMode<3;++speakMode)for(int animalMode=0;animalMode<3;++animalMode)
 for(int rodShuffle=0;rodShuffle<2;++rodShuffle)for(int walletShuffle=0;walletShuffle<2;++walletShuffle)
 for(int mask=0;mask<64;++mask) {
  logic->IsAdult=age;logic->IsChild=!age;logic->items.clear();
  ctx->GetOption(RSK_SHUFFLE_NPC_SOUL).Set(npcShuffle);ctx->GetOption(RSK_SHUFFLE_SPEAK).Set(speakMode);
  ctx->GetOption(RSK_SHUFFLE_ANIMAL_SOUL).Set(animalMode);ctx->GetOption(RSK_SHUFFLE_FISHING_POLE).Set(rodShuffle);ctx->GetOption(RSK_SHUFFLE_CHILD_WALLET).Set(walletShuffle);
  if(mask&1)logic->items.insert(RG_NPC_SOUL);if(mask&2)logic->items.insert(RG_SPEAK_HYLIAN);
  if(mask&4)logic->items.insert(RG_ANIMAL_SOUL_FISH);if(mask&8)logic->items.insert(RG_ANIMAL_SOUL);
  if(mask&16)logic->items.insert(RG_FISHING_POLE);if(mask&32)logic->items.insert(RG_CHILD_WALLET);
  bool expected=(!npcShuffle||(mask&1))&&(!speakMode||(mask&2))&&(!animalMode||(animalMode==1?(mask&8):(mask&4)))&&(!rodShuffle||(mask&16))&&(!walletShuffle||(mask&32));
  ck(logic->CanUse(RG_FISHING_POLE),expected,"native pond action");
 }
 // Actual bush/grass switch branches and grass helper bodies. No change to
 // cutting semantics is permitted just to make walk-through bushes available.
 for(int soulShuffle=0;soulShuffle<2;++soulShuffle)for(int mask=0;mask<8;++mask){
  ctx->GetOption(RSK_SHUFFLE_GRASS_SOUL).Set(soulShuffle);logic->IsAdult=false;logic->IsChild=true;logic->items.clear();
  if(mask&1)logic->items.insert(RG_GRASS_SOUL);if(mask&2)logic->items.insert(RG_POWER_BRACELET);if(mask&4)logic->items.insert(RG_KOKIRI_SWORD);
  const bool exists=!soulShuffle||(mask&1);
  ck(objectInteraction(RCTYPE_BUSH),exists,"walk-through bush needs no method");
  ck(objectInteraction(RCTYPE_GRASS),exists&&((mask&2)||(mask&4)),"grass still needs grab or cutting");
 }
 std::printf("cases=%d failures=%d\n",cases,failures);return failures?1:0;
}
'''
# Preserve the real fishing-role constants without pulling C++ UI dependencies
# into the isolated service fixture; z_fishing.c itself is compiled separately.
constants='\n'.join(line for line in text('src/overlays/actors/ovl_Fishing/z_fishing.h').splitlines() if line.startswith('#define EN_FISH_'))
source=source.replace('#define SPDLOG_INFO',constants+'\n#define SPDLOG_INFO')
f=out/'test.cpp';f.write_text(source);exe=out/'test';cmd=[shutil.which(a.compiler) or a.compiler,'-std=c++20','-fms-extensions','-O1']
for d in [root,root/'include',root/'src',root/'soh',root/'assets',root/'libultraship/include',root/'libultraship/include/ship/utils/binarytools']:cmd+=['-I',str(d)]
cmd +=[str(f),'-o',str(exe)]
c=subprocess.run(cmd,capture_output=True,text=True,timeout=45);run=subprocess.run([str(exe)],capture_output=True,text=True,timeout=15) if c.returncode==0 else None
report=dict(passed=c.returncode==0 and run is not None and run.returncode==0,command=cmd,compile_exit=c.returncode,compile_stderr=c.stderr,stdout=run.stdout if run else '',stderr=run.stderr if run else '',scope=__doc__)
a.report.write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2));raise SystemExit(not report['passed'])
