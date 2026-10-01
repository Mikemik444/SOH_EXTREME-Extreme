"""Compile production rock draw/drop policy, removal hook and silver-rock lifecycle.

Rendering, actor allocation, flags and location lookup use controlled services.
This exercises actual function bodies, not a rendered or connected game test.
Run from a Visual Studio x64 developer prompt.
"""
from pathlib import Path
import argparse
import json
import re
import subprocess
from run_native_tests import function

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--output', type=Path, required=True)
p.add_argument('--source-root', type=Path, default=Path(__file__).resolve().parent.parent)
a = p.parse_args()
r = a.source_root.resolve()
o = a.output.resolve()
o.mkdir(parents=True, exist_ok=True)
rocks = (r / 'soh/Enhancements/randomizer/ShuffleRocks.cpp').read_text(encoding='utf-8')
ishi = (r / 'src/overlays/actors/ovl_En_Ishi/z_en_ishi.c').read_text(encoding='utf-8')
body = '\n'.join(function(rocks, s) for s in (
    'static bool Rock_RandomizerIsActiveLocation(', 'uint8_t Rock_RandomizerHoldsItem(CheckIdentity rockIdentity, PlayState* play, bool isBoulder) {',
    'void Rock_RandomizerSpawnCollectible(', 'extern "C" s32 Rock_RandomizerShouldRespawn(',
    'extern "C" void EnIshi_RandomizerDraw(', 'extern "C" void ObjBombiwa_RandomizerDraw(',
    'extern "C" void ObjHamishi_RandomizerDraw(', 'void RegisterShuffleRock('))
body += '\n' + re.sub(r'\bthis\b', 'self', '\n'.join(function(ishi, s) for s in (
    'void EnIshi_Init(Actor* thisx, PlayState* play) {', 'void EnIshi_LiftedUp(EnIshi* this, PlayState* play) {')))
enums = sorted(set(re.findall(r'\b(?:RC|RSK|RO|RAND_INF|ACTOR|VB|SCENE)_\w+', body)))
code = r'''
#include <cstdint>
#include <iostream>
#include <map>
#include <set>
#include <utility>
using s16=int16_t;using s32=int32_t;
using RandomizerCheck=int;
'''
code += 'enum Constants {' + ','.join(enums) + '};\n'
code += r'''
bool rando=true,dungeon=false,allocation=true,hasParent=false;
#define IS_RANDO rando
struct Vec3f{float x=0,y=0,z=0;};
struct Rot{int y=0;};
struct GraphicsContext{};
struct PlayState{struct{GraphicsContext*gfxCtx=nullptr;}state;int sceneNum=12;
 struct{int state=0;}csCtx;struct{struct{int num=0;}curRoom;}roomCtx;}play,*gPlayState=&play;
struct Actor{int id=ACTOR_EN_ISHI,params=0,room=0;float speedXZ=0,uncullZoneForward=0;
 struct{Vec3f pos;Rot rot;}home,world;Vec3f velocity;
 struct{Rot rot;float yOffset=0;}shape;int colChkInfo=0;bool killed=false;
 void(*draw)(Actor*,PlayState*)=nullptr;};
using ActorFunc=void(*)(Actor*,PlayState*);
struct EnIshi{Actor actor;};struct ObjBombiwa{Actor actor;};struct ObjHamishi{Actor actor;};
struct CheckIdentity{int randomizerInf=RAND_INF_MAX,randomizerCheck=RC_UNKNOWN_CHECK;};
CheckIdentity identity;int lastX=0,lastZ=0;
CheckIdentity IdentifyRock(s32 scene,s32 x,s32 z){lastX=x;lastZ=z;return identity;}
std::set<int> collected,switches;
bool Flags_GetRandomizerInf(int f){return collected.count(f);}
bool Flags_GetSwitch(PlayState*,int f){return switches.count(f);}
void Flags_SetSwitch(PlayState*,int f){switches.insert(f);}
std::map<int,int> options;
int Randomizer_GetSettingValue(int s){return options[s];}
#define RAND_GET_OPTION(s) options[s]
struct GetItemEntry{int itemId=0;};
struct EnItem00{Actor actor;int randoInf=RAND_INF_MAX,randoCheck=RC_UNKNOWN_CHECK;GetItemEntry itemEntry;}drop;
int dropCalls=0,haloCalls=0;
constexpr int GI_NONE=0,ITEM00_SOH_DUMMY=1,ROCK_SMALL=0,ROCK_LARGE=1,CS_STATE_IDLE=0;
EnItem00* Item_DropCollectible2(PlayState*,Vec3f*,int){++dropCalls;drop={};return allocation?&drop:nullptr;}
float Rand_CenteredFloat(float){return 10.0f;}
void EnItem00_DrawRandomizedItem(EnItem00*,PlayState*){}
namespace Rando{namespace StaticData{
struct Location{bool IsDungeon(){return dungeon;}}loc;
Location*GetLocation(int){return &loc;}
}struct Context{static Context*GetInstance(){static Context c;return &c;}
struct Option{int value;int Get(){return value;}};
Option GetOption(int k){return {options[k]};}
GetItemEntry GetFinalGIEntry(int rc,bool,int){return {rc};}};}
struct ObjectExtension{std::map<Actor*,CheckIdentity> identities;
static ObjectExtension&GetInstance(){static ObjectExtension e;return e;}
template<class T>T*Get(Actor*a){auto it=identities.find(a);return it==identities.end()?nullptr:&it->second;}
template<class T>void Set(Actor*a,T value){identities[a]=value;}};
#define OPEN_DISPS(...) ((void)0)
#define CLOSE_DISPS(...) ((void)0)
#define gSPMatrix(...) ((void)0)
#define gDPSetPrimColor(...) ((void)0)
#define gSPDisplayList(...) ((void)0)
void Gfx_SetupDL_25Opa(GraphicsContext*){}
void BeginRockSoulTint(GraphicsContext*){}
void EndRockSoulTint(GraphicsContext*){}
void Sparkles(PlayState*,Actor*,bool,CheckIdentity){++haloCalls;}
std::map<int,void(*)(bool*,Actor*)>hooks;
#define COND_ID_HOOK(...) ((void)0)
#define COND_VB_SHOULD(id,condition,...) if(condition)hooks[id]=[](bool*should,Actor*argument)__VA_ARGS__
#define va_arg(args,type) argument
float sRockScales[2]{},D_80A7FA20[2]{},D_80A7FA28[2]{};
int sInitChains[2]{},sColChkInfoInit=0;
void Actor_ProcessInitChain(Actor*,int){}
float Rand_ZeroFloat(int){return 1;}
void Actor_SetScale(Actor*,float){}
void EnIshi_InitCollider(Actor*,PlayState*){}
void Actor_Kill(Actor*a){a->killed=true;}
void CollisionCheck_SetInfo(int*,void*,int*){}
bool EnIshi_SnapToFloor(EnIshi*,PlayState*,float){return true;}
void EnIshi_SetupWait(EnIshi*){}
bool Actor_HasNoParent(Actor*,PlayState*){return !hasParent;}
void EnIshi_SetupFly(EnIshi*){}
void EnIshi_Fall(EnIshi*){}
void func_80A7ED94(Vec3f*,float){}
void Actor_UpdatePos(Actor*){}
void Actor_UpdateBgCheckInfo(PlayState*,Actor*,float,float,float,int){}
'''
code += body + r'''
int checks=0;
#define CK(x) do{++checks;if(!(x)){std::cerr<<"Failed line "<<__LINE__<<": "<<#x<<"\n";return 1;}}while(0)
void reset(){rando=allocation=true;dungeon=hasParent=false;play={};identity={1234,RC_GC_MAZE_BOULDER_1};
 collected.clear();switches.clear();hooks.clear();options.clear();dropCalls=haloCalls=0;
 ObjectExtension::GetInstance().identities.clear();
 options[RSK_SHUFFLE_DUNGEON_ENTRANCES]=RO_DUNGEON_ENTRANCE_SHUFFLE_OFF;}
int main(){
 // All shuffle scopes, ages' shared removal flags, and collected states.
 for(int id:{ACTOR_EN_ISHI,ACTOR_OBJ_BOMBIWA,ACTOR_OBJ_HAMISHI})
 for(int scope:std::initializer_list<int>{0,RO_SHUFFLE_BOULDERS_DUNGEONS,RO_SHUFFLE_BOULDERS_OVERWORLD,RO_SHUFFLE_BOULDERS_ALL})
 for(bool inside:{false,true})for(bool checked:{false,true})for(bool removed:{false,true}){
  reset();dungeon=inside;options[RSK_SHUFFLE_BOULDERS]=scope;
  bool active=scope==RO_SHUFFLE_BOULDERS_ALL||(inside&&scope==RO_SHUFFLE_BOULDERS_DUNGEONS)||(!inside&&scope==RO_SHUFFLE_BOULDERS_OVERWORLD);
  bool pending=active&&!checked;if(checked)collected.insert(identity.randomizerInf);
  EnIshi rock;rock.actor.id=id;rock.actor.params=1;rock.actor.home.pos={71,0,83};rock.actor.world.pos={200,0,300};
  CK(bool(Rock_RandomizerShouldRespawn(&rock.actor))==pending);CK(lastX==71&&lastZ==83);
  ObjectExtension::GetInstance().Set(&rock.actor,identity);
  if(id==ACTOR_EN_ISHI)EnIshi_RandomizerDraw(&rock.actor,&play);
  if(id==ACTOR_OBJ_BOMBIWA)ObjBombiwa_RandomizerDraw(&rock.actor,&play);
  if(id==ACTOR_OBJ_HAMISHI)ObjHamishi_RandomizerDraw(&rock.actor,&play);
  CK(haloCalls==int(pending));
  if(id==ACTOR_EN_ISHI){if(removed)switches.insert(0);EnIshi_Init(&rock.actor,&play);
   CK(rock.actor.killed==(removed&&!pending));
  }else{RegisterShuffleRock();bool should=removed;
   if(hooks.count(VB_BOULDER_BREAK_FLAG))hooks[VB_BOULDER_BREAK_FLAG](&should,&rock.actor);
   CK(should==(removed&&!pending));CK(dropCalls==int(removed&&pending));
   if(dropCalls)CK(drop.randoCheck==identity.randomizerCheck&&drop.randoInf==identity.randomizerInf);
  }
 }
 // Throwing a shuffled silver boulder always records its native switch.
 // Reload preserves a missed check, then respects that switch once collected.
 for(bool checked:{false,true})for(bool parent:{false,true}){
  reset();options[RSK_SHUFFLE_BOULDERS]=RO_SHUFFLE_BOULDERS_ALL;hasParent=parent;
  if(checked)collected.insert(identity.randomizerInf);
  EnIshi rock;rock.actor.params=1|(2<<6);EnIshi_LiftedUp(&rock,&play);
  CK(switches.count(2)==!parent);
  EnIshi_Init(&rock.actor,&play);CK(rock.actor.killed==(!parent&&checked));
 }
 // Breaking an uncollected rock creates exactly one identified AP collectible.
 // Collected/disabled rocks use their original drop; allocation failure is safe.
 for(bool checked:{false,true})for(bool alloc:{false,true}){
  reset();allocation=alloc;options[RSK_SHUFFLE_ROCKS]=1;
  if(checked)collected.insert(identity.randomizerInf);
  Actor rock;ObjectExtension::GetInstance().Set(&rock,identity);RegisterShuffleRock();bool should=true;
  hooks[VB_ROCK_DROP_ITEM](&should,&rock);CK(should==checked);CK(dropCalls==int(!checked));
  if(!checked&&alloc)CK(drop.randoCheck==identity.randomizerCheck&&drop.randoInf==identity.randomizerInf&&drop.itemEntry.itemId==identity.randomizerCheck);
  hooks[VB_ROCK_DROP_ITEM](&should,&rock);CK(dropCalls==int(!checked));
  CK(collected.count(identity.randomizerInf)==checked); // spawn never consumes a check
  // A fresh identity still recovers an uncollected allocation failure next visit.
  CK(bool(Rock_RandomizerShouldRespawn(&rock))==!checked);
 }
 reset();options[RSK_SHUFFLE_BOULDERS]=RO_SHUFFLE_BOULDERS_ALL;
 Actor rock;rock.params=1;
 for(auto invalid:{RC_MAX,RC_UNKNOWN_CHECK}){identity.randomizerCheck=invalid;CK(!Rock_RandomizerShouldRespawn(&rock));}
 identity={RAND_INF_MAX,RC_GC_MAZE_BOULDER_1};CK(!Rock_RandomizerShouldRespawn(&rock));
 identity={1234,RC_GC_MAZE_BOULDER_1};rando=false;CK(!Rock_RandomizerShouldRespawn(&rock));
 rando=true;rock.id=-1;CK(!Rock_RandomizerShouldRespawn(&rock));CK(!Rock_RandomizerShouldRespawn(nullptr));
 // Small rocks never acquire a persistent destruction flag.
 reset();options[RSK_SHUFFLE_ROCKS]=1;EnIshi small;EnIshi_LiftedUp(&small,&play);CK(switches.empty());
 collected.insert(identity.randomizerInf);EnIshi_Init(&small.actor,&play);CK(!small.actor.killed);
 std::cout<<checks<<" boulder lifecycle assertions passed\n";
}
'''
src = o / 'boulder_lifecycle.cpp'
src.write_text(code, encoding='utf-8')
exe = o / 'boulder_lifecycle.exe'
c = subprocess.run(['cl', '/nologo', '/std:c++20', '/Zc:preprocessor', '/EHsc', '/MD',
                    str(src), '/Fo' + str(o / 'boulder_lifecycle.obj'), '/Fe' + str(exe)], capture_output=True, text=True)
t = subprocess.run([str(exe)], capture_output=True, text=True) if not c.returncode else None
log = c.stdout + c.stderr + (t.stdout + t.stderr if t else '')
passed = c.returncode == 0 and t.returncode == 0
(o / 'boulders.log').write_text(log, encoding='utf-8')
(o / 'boulders.json').write_text(json.dumps(dict(passed=passed, scope=__doc__, output=log), indent=2), encoding='utf-8')
print(log)
raise SystemExit(0 if passed else 1)
