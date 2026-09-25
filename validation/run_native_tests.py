"""Compile production policy and extracted engine functions with test-only adapters.

This is not a whole-engine build. Engine services are stubbed; assertions exercise
real function bodies from the supplied source root. No game assets are needed.
Usage: python run_native_tests.py --source-root PATH --report native-results.json
"""
from pathlib import Path
import argparse, subprocess, json, shutil, re

def function(source, signature):
    start=source.index(signature); brace=source.index('{',start)
    depth=0; mode='code';i=brace
    while i<len(source):
        c=source[i];n=source[i:i+2]
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
            if depth==0:return source[start:i+1]
        i+=1
    raise ValueError('Unclosed function '+signature)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source-root',type=Path,required=True);parser.add_argument('--report',type=Path,required=True);a=parser.parse_args()
    root=a.source_root.resolve(); build=a.report.resolve().parent/'native-test-build';build.mkdir(parents=True,exist_ok=True)
    results=[]
    def compile_run(name,source,language):
        compiler=shutil.which('g++' if language=='cpp' else 'gcc')
        if compiler is None:raise RuntimeError('A GCC-compatible C/C++ compiler is required')
        src=build/(name+'.'+language);exe=build/name;src.write_text(source)
        command=[compiler,'-std=c++17' if language=='cpp' else '-std=c11','-O2','-Wall','-Wextra','-Werror','-I',str(root),str(src),'-o',str(exe)]
        c=subprocess.run(command,capture_output=True,text=True)
        r=subprocess.run([str(exe)],capture_output=True,text=True) if c.returncode==0 else None
        passed=c.returncode==0 and r.returncode==0
        results.append(dict(name=name,passed=passed,compile_command=command,compile_stdout=c.stdout,compile_stderr=c.stderr,stdout=r.stdout if r else '',stderr=r.stderr if r else '',returncode=r.returncode if r else c.returncode))
        print(('PASS' if passed else 'FAIL'),name,results[-1]['stdout'],results[-1]['compile_stderr'],results[-1]['stderr'])
    policy=r'''
#include <cassert>
#include <cstdio>
#include "soh/Enhancements/randomizer/EnemyDropPolicy.h"
#include "soh/Enhancements/randomizer/EnemySpawnCatalog.h"
using namespace SohExtreme;
int main() {
  int cases=0;
  for(int bits=0;bits<256;++bits) {
    const bool eligible=bits&1,enabled=bits&2,soul=bits&4,pending=bits&8;
    EnemyLifeDropState s;
    s.rewardWasAp=bits&16;s.normalDropHandled=bits&32;s.deathObserved=bits&64;s.defeatHandled=bits&128;
    bool original=s.normalDropHandled;
    int expected=(!eligible||!enabled)?0:(!soul||pending||s.rewardWasAp||original)?-1:1;
    assert(ConsumeNormalEnemyDrop(s,eligible,enabled,soul,pending)==expected);
    assert(s.normalDropHandled==(original||expected==1));
    assert(ConsumeNormalEnemyDrop(s,eligible,enabled,soul,pending)==(expected==1?-1:expected));
    ++cases;
  }
  for(int b=0;b<16;++b) {assert(EnemyCheckPending(b&1,b&2,b&4,b&8)==((b&1)&&(b&2)&&!(b&4)&&!(b&8)));++cases;}
  for(int b=0;b<8;++b) {assert(CanConsumeEnemyPickup(b&1,b&2,b&4)==((b&1)&&(b&2)&&(b&4)));++cases;}
  EnemyLifeDropState newLife;
  assert(ConsumeNormalEnemyDrop(newLife,true,true,true,false)==1);
  std::printf("%d exhaustive policy cases plus fresh-life normal loot passed\n",cases);
}
'''
    compile_run('enemy_drop_policy',policy,'cpp')
    actor_source=(root/'src/overlays/actors/ovl_En_Hintnuts/z_en_hintnuts.c').read_text()
    hint_function=function(actor_source,'void EnHintnuts_Freeze(EnHintnuts* this, PlayState* play) {')
    hint_stubs=r'''
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
typedef struct {float y;} Vec3f;
typedef struct Actor {int colorFilterTimer;struct Actor* child;struct{Vec3f pos;}world,home;unsigned flags;struct{int health;}colChkInfo;} Actor;
typedef struct {int actorCtx;} PlayState;
typedef struct {Actor actor;int skelAnime;int animFlagAndTimer;} EnHintnuts;
static int sPuzzleCounter,defeats,kills,waits,categories;
static float defeatY;
static const struct{int health;}sColChkInfoInit={1};
#define NA_SE_EN_NUTS_FAINT 0
#define ACTORCAT_PROP 0
#define ACTOR_FLAG_ATTENTION_ENABLED 1u
#define ACTOR_FLAG_UPDATE_CULLING_DISABLED 2u
static void SkelAnime_Update(int* a){(void)a;}
static bool Animation_OnFrame(int* a,float b){(void)a;(void)b;return false;}
static void Audio_PlayActorSound2(Actor* a,int b){(void)a;(void)b;}
static void Actor_ChangeCategory(PlayState* p,int* ctx,Actor* a,int cat){(void)p;(void)ctx;(void)a;(void)cat;++categories;}
static bool Math_StepToF(float* y,float target,float step){*y-=step;if(*y<=target){*y=target;return true;}return false;}
static void Actor_Kill(Actor* a){(void)a;++kills;}
static void GameInteractor_ExecuteOnEnemyDefeat(Actor* a){++defeats;defeatY=a->world.pos.y;}
static void EnHintnuts_SetupWait(EnHintnuts* a){a->animFlagAndTimer=0;++waits;}
'''
    hint_main=r'''
int main(void) {
  PlayState play={0};EnHintnuts a={0};Actor child={0};
  a.actor.home.pos.y=a.actor.world.pos.y=100.0f;a.actor.child=&child;
  sPuzzleCounter=0;EnHintnuts_Freeze(&a,&play);assert(defeats==0&&kills==0);
  sPuzzleCounter=3;EnHintnuts_Freeze(&a,&play);
  assert(defeats==1&&defeatY==100.0f&&categories==1&&a.animFlagAndTimer==1);
  for(int i=0;i<5;++i)EnHintnuts_Freeze(&a,&play);
  assert(defeats==1&&kills==1&&a.actor.world.pos.y==65.0f);
  a=(EnHintnuts){0};a.actor.home.pos.y=a.actor.world.pos.y=100.0f;
  sPuzzleCounter=-4;EnHintnuts_Freeze(&a,&play);assert(a.animFlagAndTimer==2&&defeats==1);
  for(int i=0;i<5;++i)EnHintnuts_Freeze(&a,&play);
  assert(defeats==1&&kills==1&&waits==1&&a.actor.colChkInfo.health==1);
  sPuzzleCounter=3;EnHintnuts_Freeze(&a,&play);assert(defeats==2);
  puts("5 puzzle lifecycle scenarios passed: unresolved, solved surface reward, no repeat, wrong-order reset, later solve");
}
'''
    compile_run('hintnuts_freeze',hint_stubs+'\n'+hint_function+'\n'+hint_main,'c')
    mega=(root/'soh/Enhancements/randomizer/MegaSouls.cpp').read_text()
    funcs='\n'.join(function(mega,s) for s in [
        'static bool EnemyDefeatLocationStillPending(',
        'extern "C" bool MegaSoul_IsEnemyDefeatPlacementPending(',
        'extern "C" bool MegaSoul_TryCollectEnemyDefeatPickup(',
        'extern "C" bool MegaSoul_IsEnemyDefeatSpawnPending('])
    receipt_stubs=r'''
#include <cassert>
#include <cstdint>
#include <cstddef>
#include <cstdio>
#include <unordered_map>
#include <set>
#include "soh/Enhancements/randomizer/EnemyDropPolicy.h"
#include "soh/Enhancements/randomizer/EnemySpawnCatalog.h"
struct Actor {};
struct EnemyDefeatDropIdentity {int32_t placementIndex=-1;int64_t locationId=-1;};
class ObjectExtension {
public:
  std::unordered_map<const Actor*,EnemyDefeatDropIdentity> values;
  static ObjectExtension& GetInstance(){static ObjectExtension s;return s;}
  template<class T>const T* Get(const Actor* a){auto i=values.find(a);return i==values.end()?nullptr:&i->second;}
  template<class T>void Remove(const Actor* a){values.erase(a);}
};
struct EnemyDefeatPlacement{int16_t scene;int8_t room;int8_t grottoId;int16_t actorListIndex;int16_t actorId;uint16_t params;int64_t locationId;};
static constexpr EnemyDefeatPlacement kEnemyDefeatPlacements[]={
#include "soh/Enhancements/randomizer/EnemyDefeatPlacements.inc"
};
static constexpr size_t kEnemyPlacementCount=sizeof(kEnemyDefeatPlacements)/sizeof(kEnemyDefeatPlacements[0]);
static bool activeSave,activeLocation,reported,networkAccepts;
static int reportCalls,grottoId;
static std::set<size_t> receipts;
#define IS_RANDO isRando
#define SCENE_GROTTOS 0x3e
#define SCENE_FOREST_TEMPLE 3
#define ACTOR_EN_PO_SISTERS 145
static Actor* gLiveEnemyPickups[kEnemyPlacementCount]{};
static void PersistEnemyDefeatJournal() {}
namespace EntranceTracker {static int GetCurrentGrottoId(){return grottoId;}}
static bool Archipelago_IsCurrentSaveActive(){return activeSave;}
static bool Archipelago_IsLocationActive(int64_t){return activeLocation;}
static bool Archipelago_IsLocationReported(int64_t){return reported;}
static void Archipelago_ReportLocation(int64_t){++reportCalls;if(networkAccepts)reported=true;}
static bool EnemyDefeatWasCollected(size_t i){return receipts.count(i)>0;}
static void MarkEnemyDefeatCollected(size_t i){receipts.insert(i);}
'''
    receipt_main=r'''
int main(){
  Actor actor;
  for(int b=0;b<16;++b){
    activeSave=b&1;activeLocation=b&2;reported=b&4;networkAccepts=b&8;
    receipts.clear();reportCalls=0;ObjectExtension::GetInstance().values[&actor]={0,9800000};
    const bool expected=activeSave&&activeLocation&&(reported||networkAccepts);
    assert(MegaSoul_TryCollectEnemyDefeatPickup(&actor)==expected);
    assert(receipts.count(0)==static_cast<size_t>(expected));
    assert((ObjectExtension::GetInstance().Get<EnemyDefeatDropIdentity>(&actor)==nullptr)==expected);
    if(expected)assert(!MegaSoul_TryCollectEnemyDefeatPickup(&actor));
  }
  activeSave=activeLocation=true;reported=false;networkAccepts=false;receipts.clear();
  ObjectExtension::GetInstance().values[&actor]={0,9800000};
  assert(!MegaSoul_TryCollectEnemyDefeatPickup(&actor));
  networkAccepts=true;assert(MegaSoul_TryCollectEnemyDefeatPickup(&actor));
  assert(!MegaSoul_TryCollectEnemyDefeatPickup(nullptr));
  ObjectExtension::GetInstance().values[&actor]={-1,9800000};assert(!MegaSoul_TryCollectEnemyDefeatPickup(&actor));
  ObjectExtension::GetInstance().values[&actor]={static_cast<int>(kEnemyPlacementCount),9800000};assert(!MegaSoul_TryCollectEnemyDefeatPickup(&actor));
  receipts.clear();reported=false;
  for(int sister=0;sister<4;++sister){
    assert(!MegaSoul_IsEnemyDefeatSpawnPending(3,0,-1,ACTOR_EN_PO_SISTERS,sister<<8));
    assert(MegaSoul_IsEnemyDefeatSpawnPending(3,0,0,ACTOR_EN_PO_SISTERS,sister<<8));
    for(int decoy: {0x0400,0x0800,0x1000})
      assert(!MegaSoul_IsEnemyDefeatSpawnPending(3,0,-1,ACTOR_EN_PO_SISTERS,(sister<<8)|decoy));
  }
  auto e=kEnemyDefeatPlacements[0];
  assert(MegaSoul_IsEnemyDefeatSpawnPending(e.scene,e.room,e.actorListIndex,e.actorId,e.params));
  assert(!MegaSoul_IsEnemyDefeatSpawnPending(e.scene,e.room,e.actorListIndex,e.actorId,static_cast<uint16_t>(e.params^0x100)));
  assert(!MegaSoul_IsEnemyDefeatSpawnPending(e.scene,e.room,-1,e.actorId,e.params));
  receipts.insert(0);assert(!MegaSoul_IsEnemyDefeatSpawnPending(e.scene,e.room,e.actorListIndex,e.actorId,e.params));
  for(size_t i=0;i<kEnemyPlacementCount;++i){
    const auto& g=kEnemyDefeatPlacements[i];if(g.grottoId<0||g.actorListIndex<0)continue;
    receipts.clear();grottoId=g.grottoId;
    assert(MegaSoul_IsEnemyDefeatSpawnPending(g.scene,g.room,g.actorListIndex,g.actorId,g.params));
    grottoId=120;assert(!MegaSoul_IsEnemyDefeatSpawnPending(g.scene,g.room,g.actorListIndex,g.actorId,g.params));
  }
  // Stale servers/saves cannot make retired offspring pickups count.
  activeSave=activeLocation=reported=networkAccepts=true;receipts.clear();reportCalls=0;
  for(int i=765;i<=785;++i){
    ObjectExtension::GetInstance().values[&actor]={i,9800000+i};
    assert(!MegaSoul_TryCollectEnemyDefeatPickup(&actor));
    assert(!receipts.count(i)&&reportCalls==0);
  }
  puts("16 pickup truth-table cases and disconnected retry, duplicate pickup, invalid identity, exact spawn and grotto isolation passed");
}
'''
    compile_run('enemy_pickup_receipts',receipt_stubs+'\n'+funcs+'\n'+receipt_main,'cpp')
    capture_func=function(mega,'static void AttachEnemyDefeatIdentity(Actor* actor) {')
    capture_stubs=r'''
#include <cassert>
#include <cstdint>
#include <cstddef>
#include <cstdio>
#include <unordered_map>
#include <utility>
#include "soh/Enhancements/randomizer/EnemyDropPolicy.h"
#include "soh/Enhancements/randomizer/EnemySpawnCatalog.h"
struct Vec3f{float x=0,y=0,z=0;};
struct Actor{int16_t id=55,params=1;int8_t room=0;int sourceIndex=3,placement=0;bool eligible=true,statue=false;struct{Vec3f pos;}home;};
struct PlayState{int sceneNum=0;};
struct EnemyDefeatIdentity:SohExtreme::EnemyLifeDropState{
  int32_t placementIndex=-1;int16_t scene=-1;int8_t room=-1,grottoId=-1;
  int16_t actorListIndex=-1,actorId=-1;uint16_t params=0;Vec3f spawnPos{};int64_t locationId=-1;
};
class ObjectExtension{
public:
  std::unordered_map<Actor*,EnemyDefeatIdentity> values;
  static ObjectExtension& GetInstance(){static ObjectExtension s;return s;}
  template<class T>T* Get(Actor* a){auto i=values.find(a);return i==values.end()?nullptr:&i->second;}
  template<class T>void Set(Actor* a,T&& value){values[a]=std::forward<T>(value);}
  template<class T>void Remove(Actor* a){values.erase(a);}
};
struct EnemyDefeatPlacement{int16_t scene;int8_t room;int8_t grottoId;int16_t actorListIndex;int16_t actorId;uint16_t params;int64_t locationId;};
static constexpr EnemyDefeatPlacement kEnemyDefeatPlacements[]={
#include "soh/Enhancements/randomizer/EnemyDefeatPlacements.inc"
};
static PlayState play;static PlayState* gPlayState=&play;static bool isRando=true;static int grottoId;
#define IS_RANDO isRando
#define SCENE_GROTTOS 0x3e
namespace EntranceTracker {static int GetCurrentGrottoId(){return grottoId;}}
static bool IsMegaEnemySoulActor(Actor* a){return a->eligible;}
static bool IsStructuralArmosStatue(Actor* a){return a->statue;}
static int16_t GetActorListIndex(Actor* a){return static_cast<int16_t>(a->sourceIndex);}
'''
    capture_main=r'''
int main(){
  auto& ext=ObjectExtension::GetInstance();Actor a;a.home.pos={12,34,56};
  AttachEnemyDefeatIdentity(&a);auto* captured=ext.Get<EnemyDefeatIdentity>(&a);
  assert(captured&&captured->locationId==-1&&captured->actorListIndex==3&&captured->params==1&&captured->spawnPos.y==34);
  a.params=99;a.room=7;a.sourceIndex=44;a.placement=5;a.home.pos={80,90,100};
  AttachEnemyDefeatIdentity(&a);captured=ext.Get<EnemyDefeatIdentity>(&a);
  assert(captured->locationId==-1&&captured->params==1&&captured->room==0&&captured->actorListIndex==3&&captured->spawnPos.y==34);
  ext.Remove<EnemyDefeatIdentity>(&a);AttachEnemyDefeatIdentity(&a);captured=ext.Get<EnemyDefeatIdentity>(&a);
  assert(captured->locationId==-1&&captured->params==99&&captured->actorListIndex==44&&captured->spawnPos.y==90);
  ext.Remove<EnemyDefeatIdentity>(&a);a.placement=-1;a.sourceIndex=-1;AttachEnemyDefeatIdentity(&a);
  assert(ext.Get<EnemyDefeatIdentity>(&a)->locationId==-1);
  ext.Remove<EnemyDefeatIdentity>(&a);a.statue=true;AttachEnemyDefeatIdentity(&a);assert(!ext.Get<EnemyDefeatIdentity>(&a));
  a.statue=false;a.eligible=false;AttachEnemyDefeatIdentity(&a);assert(!ext.Get<EnemyDefeatIdentity>(&a));
  a.eligible=true;isRando=false;AttachEnemyDefeatIdentity(&a);assert(!ext.Get<EnemyDefeatIdentity>(&a));
  isRando=true;play.sceneNum=SCENE_GROTTOS;grottoId=12;AttachEnemyDefeatIdentity(&a);
  assert(ext.Get<EnemyDefeatIdentity>(&a)->grottoId==12);
  AttachEnemyDefeatIdentity(nullptr);
  puts("9 unmapped snapshot scenarios passed (address binding tested separately): initial snapshot, immutable mutation, pointer reuse, dynamic spawn, statue, non-enemy, vanilla, grotto, null");
}
'''
    compile_run('enemy_spawn_identity',capture_stubs+'\n'+capture_func+'\n'+capture_main,'cpp')
    a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps({'scope':'Production policy header and complete extracted engine functions; stubbed engine/AP services; not a whole-game build','suites':results,'passed':all(r['passed'] for r in results)},indent=2))
    return 0 if all(r['passed'] for r in results) else 1
if __name__=='__main__':raise SystemExit(main())
