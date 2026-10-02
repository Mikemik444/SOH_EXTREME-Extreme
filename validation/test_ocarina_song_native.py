"""Compile real moat actor, flag dispatch and AP collection functions.

Engine services use test adapters. This is not a live game playtest.
The player-update recovery prefix is extracted separately from unrelated
swim/credits logic; production actor and flag functions are compiled in full.
"""
from pathlib import Path
import argparse, json, re, subprocess, zipfile
from run_native_tests import function

p = argparse.ArgumentParser()
p.add_argument('--output', type=Path, required=True)
p.add_argument('--source-root', type=Path)
p.add_argument('--baseline-zip', type=Path)
a = p.parse_args()
r = (a.source_root or Path(__file__).resolve().parent.parent).resolve()
o = a.output.resolve(); o.mkdir(parents=True, exist_ok=True)
def source(name):
    if a.baseline_zip:
        with zipfile.ZipFile(a.baseline_zip) as archive:
            try:
                return archive.read(name).decode('utf-8')
            except KeyError:
                return subprocess.check_output(['git', 'show', 'HEAD:'+name], cwd=r).decode('utf-8')
    return (r/name).read_text(encoding='utf-8')
hooks = source('soh/Enhancements/randomizer/hook_handlers.cpp')
actor = source('src/overlays/actors/ovl_Item_Ocarina/z_item_ocarina.c')
flags = source('src/code/z_actor.c')
helper = 'static void CompleteArchipelagoOcarinaSong()'
helper_body = function(hooks, helper) if helper in hooks else helper+' {}'
update = function(hooks, 'void RandomizerOnPlayerUpdateHandler() {')
recovery_prefix = update.split('// Swim is required', 1)[0]+'}'
assert '// Swim is required' in update
code = r'''
#include <iostream>
#include <map>
#include <queue>
#include <cmath>
#include <cstdint>
#include "soh/Enhancements/randomizer/randomizerEnums.h"
using s32=int;
constexpr int EVENTCHKINF_OBTAINED_OCARINA_OF_TIME=0x43, EVENTCHKINF_LEARNED_SONG_OF_TIME=0xa9;
constexpr int EVENTCHKINF_TALON_WOKEN_IN_CASTLE=0x11, EVENTCHKINF_TALON_RETURNED_FROM_CASTLE=0x12,
 EVENTCHKINF_OBTAINED_POCKET_EGG=0x13;
constexpr int FLAG_EVENT_CHECK_INF=1, FLAG_RANDOMIZER_INF=2, FLAG_GS_TOKEN=3,
 ITEM_SWORD_BROKEN=1, ITEM_EYEDROPS=2, PLAYER_STATE2_DIVING=1,
 VB_GIVE_ITEM_OCARINA_OF_TIME=1, GI_OCARINA_OOT=1;
#define LUSLOG_INFO(...)
#define SPDLOG_INFO(...)
#define SEGMENTED_TO_VIRTUAL(x) (x)
bool rando, apSave, identityMatches, songActive, itemActive, closing, parent, giveVanilla;
#define IS_RANDO rando
struct Vec3f {float x,y,z;};
struct Actor {float xzDistToPlayer,yDistToPlayer; void* draw; struct {Vec3f pos;} world;};
struct PlayState {struct {void* segment;} csCtx; int gameplayFrames;};
struct ItemOcarina {Actor actor; void (*actionFunc)(ItemOcarina*,PlayState*);};
struct Player {int stateFlags2;} player;
#define GET_PLAYER(play) (&player)
struct Save {uint16_t eventChkInf[32];int cutsceneTrigger;} gSaveContext;
PlayState play;PlayState* gPlayState=&play;
void* gHyruleFieldZeldaSongOfTimeCs=(void*)1;
int switchCount, offerCount, eventDispatches, checks, failures;
std::queue<RandomizerCheck> randomizerQueuedChecks;
struct Loc {
 bool obtained=false; int reports=0;
 bool HasObtained(){return obtained;}
 RandomizerGet GetPlacedRandomizerGet(){return RG_KOKIRI_SWORD;}
 void SetCheckStatus(int){obtained=true;}
};
std::map<RandomizerCheck,Loc> locations;
struct Option {int Get(){return 0;} bool Is(int){return false;}};
namespace Rando {struct Context {
 static Context* GetInstance(){static Context ctx;return &ctx;}
 Option GetOption(int){return {};}
 Loc* GetItemLocation(RandomizerCheck rc){return &locations[rc];}
};}
#define RAND_GET_OPTION(x) Option{}
namespace CheckTracker {
 void SpoilAreaFromCheck(RandomizerCheck){}
 void SetCheckCollected(RandomizerCheck rc){auto& loc=locations[rc];loc.obtained=true;++loc.reports;}
}
bool Archipelago_ShouldHandleCheck(int rc){return rando&&apSave&&identityMatches&&
 (rc==RC_SONG_FROM_OCARINA_OF_TIME?songActive:rc==RC_HF_OCARINA_OF_TIME_ITEM&&itemActive);}
RandomizerCheck GetRandomizerCheckFromFlag(int type,int flag){
 if(type!=FLAG_EVENT_CHECK_INF)return RC_UNKNOWN_CHECK;
 if(flag==EVENTCHKINF_OBTAINED_OCARINA_OF_TIME)return RC_HF_OCARINA_OF_TIME_ITEM;
 if(flag==EVENTCHKINF_LEARNED_SONG_OF_TIME)return RC_SONG_FROM_OCARINA_OF_TIME;
 return RC_UNKNOWN_CHECK;
}
void Flags_UnsetRandomizerInf(int){}
void Flags_SetRandomizerInf(int){}
void Inventory_ReplaceItem(PlayState*,int,int){}
int Randomizer_GetNextAdultTradeItem(){return 0;}
void RandomizerOnFlagSetHandler(int16_t,int16_t);
void GameInteractor_ExecuteOnFlagSet(int type,int flag){
 ++eventDispatches;if(rando)RandomizerOnFlagSetHandler(type,flag);
}
bool Actor_HasParent(Actor*,PlayState*){return parent;}
bool Actor_TextboxIsClosing(Actor*,PlayState*){return closing;}
bool GameInteractor_Should(int,bool){return giveVanilla;}
void Actor_OfferGetItem(Actor*,PlayState*,int,float,float){++offerCount;}
void EffectSsBubble_Spawn(PlayState*,Vec3f*,float,float,float,float){}
void Flags_SetSwitch(PlayState*,int flag){if(flag==3)++switchCount;}
void ItemOcarina_DoNothing(ItemOcarina*,PlayState*);
void ItemOcarina_StartSoTCutscene(ItemOcarina*,PlayState*);
'''
code += function(flags, 's32 Flags_GetEventChkInf(s32 flag) {')+'\n'
code += function(flags, 'void Flags_SetEventChkInf(s32 flag) {')+'\n'
code += helper_body+'\n'
code += function(hooks, 'void RandomizerOnFlagSetHandler(int16_t flagType, int16_t flag) {')+'\n'
code += recovery_prefix+'\n'
for name in ('DoNothing', 'StartSoTCutscene', 'WaitInWater'):
    body = function(actor, f'void ItemOcarina_{name}(ItemOcarina* this, PlayState* play) {{')
    code += re.sub(r'\bthis\b', 'self', body)+'\n'
code += r'''
void expect(bool value,const char* label){++checks;if(!value){++failures;std::cerr<<"FAIL "<<label<<"\n";}}
void reset(){
 rando=apSave=identityMatches=songActive=itemActive=true;
 closing=parent=giveVanilla=false;player={};gSaveContext={};play={};locations.clear();
 randomizerQueuedChecks={};switchCount=offerCount=eventDispatches=0;
}
int count(RandomizerCheck rc){return locations[rc].reports;}
void recovered(){
 expect(Flags_GetEventChkInf(EVENTCHKINF_LEARNED_SONG_OF_TIME),"song source completed");
 expect(count(RC_SONG_FROM_OCARINA_OF_TIME)==1,"one AP song report");
 expect(randomizerQueuedChecks.empty(),"no local randomized item queue");
 expect(!gSaveContext.cutsceneTrigger,"no deferred cutscene");
}
int main(){
 // Fresh diving pickup without any item textbox. Unrelated later text cannot
 // steal the scene transition. Parent-based vanilla pickup is also covered.
 for(int bits=0;bits<4;++bits){
  reset();parent=bits&1;closing=bits&2;player.stateFlags2=PLAYER_STATE2_DIVING;
  ItemOcarina item{};item.actor.draw=(void*)1;item.actionFunc=ItemOcarina_WaitInWater;
  item.actionFunc(&item,&play);
  expect(Flags_GetEventChkInf(EVENTCHKINF_OBTAINED_OCARINA_OF_TIME),"pickup source completed");
  expect(count(RC_HF_OCARINA_OF_TIME_ITEM)==1,"one AP pickup report");
  expect(item.actor.draw==nullptr&&switchCount==1,"pickup actor consumed");recovered();
  item.actionFunc(&item,&play);
  expect(item.actionFunc==ItemOcarina_DoNothing,"AP cutscene disarmed");
  closing=true;item.actionFunc(&item,&play);recovered();
  int dispatched=eventDispatches;
  for(int i=0;i<120;++i)RandomizerOnPlayerUpdateHandler();
  expect(eventDispatches==dispatched,"repeated frames do not dispatch again");recovered();
 }
 // Proximity without diving cannot grant either check.
 for(int bits=0;bits<8;++bits){
  reset();ItemOcarina item{};item.actor.xzDistToPlayer=bits&1?40:0;
  item.actor.yDistToPlayer=bits&2?20:0;player.stateFlags2=bits&4?PLAYER_STATE2_DIVING:0;
  ItemOcarina_WaitInWater(&item,&play);
  bool reachable=bits==4;
  expect(bool(Flags_GetEventChkInf(EVENTCHKINF_OBTAINED_OCARINA_OF_TIME))==reachable,"physical pickup requirements");
  expect(bool(Flags_GetEventChkInf(EVENTCHKINF_LEARNED_SONG_OF_TIME))==reachable,"paired check follows physical pickup");
 }
 // Save recovery: loading the source flag without a surviving actor repairs
 // the song exactly once, even with a previously collected journal entry.
 for(int prior=0;prior<2;++prior){
  reset();gSaveContext.eventChkInf[0x43>>4]|=1<<(0x43&15);
  locations[RC_HF_OCARINA_OF_TIME_ITEM].obtained=true;
  locations[RC_SONG_FROM_OCARINA_OF_TIME].obtained=prior;
  RandomizerOnPlayerUpdateHandler();
  expect(Flags_GetEventChkInf(EVENTCHKINF_LEARNED_SONG_OF_TIME),"loaded save repaired");
  expect(count(RC_SONG_FROM_OCARINA_OF_TIME)==!prior,"already collected journal is not duplicated");
  expect(count(RC_HF_OCARINA_OF_TIME_ITEM)==0,"recovery does not report pickup twice");
  expect(randomizerQueuedChecks.empty(),"recovery does not give native reward");
  int dispatched=eventDispatches;RandomizerOnPlayerUpdateHandler();
  expect(eventDispatches==dispatched,"recovery idempotent");
 }
 // Missing source, mismatched/inactive AP slot and non-AP save must not
 // complete the song. Inventory receipt is deliberately not an input.
 for(int mode=0;mode<5;++mode){
  reset();if(mode)gSaveContext.eventChkInf[0x43>>4]|=1<<(0x43&15);
  if(mode==1)identityMatches=false;if(mode==2)songActive=false;
  if(mode==3)apSave=false;if(mode==4)rando=false;
  RandomizerOnPlayerUpdateHandler();
  expect(!Flags_GetEventChkInf(EVENTCHKINF_LEARNED_SONG_OF_TIME),"unowned or unreached source stays uncollected");
  expect(count(RC_SONG_FROM_OCARINA_OF_TIME)==0,"no unauthorized AP check");
 }
 // Recovery remains eligible when a slot becomes available after load.
 reset();gSaveContext.eventChkInf[0x43>>4]|=1<<(0x43&15);songActive=false;
 RandomizerOnPlayerUpdateHandler();songActive=true;RandomizerOnPlayerUpdateHandler();recovered();
 // Vanilla and non-AP randomizer retain the original textbox/cutscene path.
 for(int local=0;local<2;++local){
  reset();apSave=false;rando=local;ItemOcarina item{};item.actionFunc=ItemOcarina_StartSoTCutscene;
  item.actionFunc(&item,&play);expect(!gSaveContext.cutsceneTrigger,"native waits for closing textbox");
  closing=true;item.actionFunc(&item,&play);
  expect(gSaveContext.cutsceneTrigger==1&&play.csCtx.segment==gHyruleFieldZeldaSongOfTimeCs,"native cutscene preserved");
  expect(!Flags_GetEventChkInf(EVENTCHKINF_LEARNED_SONG_OF_TIME),"native song timing unchanged");
 }
 std::cout<<checks<<" assertions, "<<failures<<" failures\n";return failures?1:0;
}
'''
src = o/'ocarina.cpp'; exe = o/'ocarina.exe'; src.write_text(code)
c = subprocess.run(['cl', '/nologo', '/std:c++20', '/Zc:preprocessor', '/EHsc', '/MD', '/I'+str(r),
    str(src), '/Fo'+str(o/'ocarina.obj'), '/Fe'+str(exe)], capture_output=True, text=True)
t = subprocess.run([str(exe)], capture_output=True, text=True) if c.returncode == 0 else None
log = c.stdout+c.stderr+(t.stdout+t.stderr if t else '')
match = re.search(r'(\d+) assertions, (\d+) failures', log)
report = dict(passed=c.returncode == 0 and t.returncode == 0,
    checks=int(match[1]) if match else 0, failures=int(match[2]) if match else None, output=log,
    limitations='Compiled production function bodies with engine adapters; not a live gameplay test.')
(o/'native.json').write_text(json.dumps(report, indent=2)); print(log)
raise SystemExit(not report['passed'])
