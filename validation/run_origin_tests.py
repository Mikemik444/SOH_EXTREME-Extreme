"""Compile the real C spawn pipeline and C++ identity/resolver code together.
Only engine allocation/resources, hook dispatch and ObjectExtension storage are
service substitutes. Actor categories/constants are extracted from supplied source.
No game/Windows binary or live Archipelago server is executed.
"""
from pathlib import Path
import argparse,json,re,subprocess
from run_native_tests import function
p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
root=a.source_root.resolve();v=Path(__file__).parent;build=a.report.parent/'origin-test-build';build.mkdir(parents=True,exist_ok=True)
mega=(root/'soh/Enhancements/randomizer/MegaSouls.cpp').read_text();engine=(root/'src/code/z_actor.c').read_text();fixtures=v/'fixtures'
header=r'''
#pragma once
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <assert.h>
#include <stdlib.h>
#include <string.h>
#include "actor_constants.h"
#include "soh/Enhancements/randomizer/EnemyDropBridge.h"
typedef int8_t s8;typedef int16_t s16;typedef int32_t s32;typedef uint8_t u8;typedef uint16_t u16;typedef uint32_t u32;typedef float f32;
typedef struct Vec3f {float x,y,z;} Vec3f;
typedef struct Vec3s {s16 x,y,z;} Vec3s;
typedef struct PosRot {Vec3f pos;Vec3s rot;} PosRot;
typedef struct Actor Actor;typedef struct PlayState PlayState;typedef void (*ActorFunc)(Actor*,PlayState*);
struct Actor {s16 id,params;int category,flags,objBankIndex;s8 room;PosRot home,world;Actor* child;Actor* parent;ActorFunc init,destroy,update,draw;};
typedef struct ActorContext {int total;} ActorContext;
struct PlayState {s16 sceneNum;struct {struct {s8 num;}curRoom;}roomCtx;ActorContext actorCtx;int objectCtx;};
typedef struct ActorDBEntry {bool valid;int id,category,flags,objectId,numLoaded;const char* name;size_t instanceSize;ActorFunc init,destroy,update,draw;} ActorDBEntry;
typedef struct ActorEntry {s16 id,params;Vec3s pos,rot;} ActorEntry;
#define ACTOR_NUMBER_MAX 100000
#define HREG(x) 0
#define LUSLOG_WARN(...) ((void)0)
#define osSyncPrintf(...) ((void)0)
#define ZELDA_ARENA_MALLOC_DEBUG(n) TestMalloc(n)
#define CVAR_ENHANCEMENT(x) x
#define SCENE_FOREST_TEMPLE 3
#define SCENE_GROTTOS 62
#define VB_SPAWN_ACTOR_ENTRY 1
#ifdef __cplusplus
extern "C" {
#endif
extern PlayState* gPlayState;extern u32 gSegments[16];extern int gMapLoading;
void* TestMalloc(size_t);ActorDBEntry* ActorDB_Retrieve(s16);void Actor_FreeOverlay(ActorDBEntry*);
int Object_GetIndex(void*,int);int CVarGetInteger(const char*,int);bool Flags_GetClear(PlayState*,s8);
void SetActorListIndex(Actor*,s16);s16 GetActorListIndex(const Actor*);
void Actor_AddToCategory(ActorContext*,Actor*,int);void Actor_Init(Actor*,PlayState*);
void GameInteractor_ExecuteOnActorSpawn(void*);
bool GameInteractor_Should(int,bool,ActorContext*,ActorEntry*,PlayState*,Actor**);
Actor* Actor_Spawn(ActorContext*,PlayState*,s16,f32,f32,f32,s16,s16,s16,s16);
Actor* Actor_SpawnAsChild(ActorContext*,Actor*,PlayState*,s16,f32,f32,f32,s16,s16,s16,s16);
Actor* Actor_SpawnEntry(ActorContext*,ActorEntry*,PlayState*);
void TestCall(ActorFunc,Actor*,PlayState*);void TestHook(void(*)(void*),Actor*);
void TestSceneIndex(s16);void TestPrepared(s32);bool TestContextEmpty(void);
#ifdef __cplusplus
}
#endif
'''
(build/'fixture.h').write_text(header)
code='#include "fixture.h"\n'+r'''
static s16 sEnemySceneSpawnIndex=-1;
static s32 sEnemyPreparedPlacement=-1;
static Actor* sEnemyCallbackSource=NULL;
static Actor* sEnemyExplicitSpawnSource=NULL;
int gMapLoading=0;
'''
for sig in ['static void Actor_CallWithEnemySpawnSource(', 'static void Actor_HookWithEnemySpawnSource(', 'Actor* Actor_Spawn(ActorContext*', 'Actor* Actor_SpawnAsChild(', 'Actor* MegaSoul_SpawnEnemyChild(', 'Actor* MegaSoul_SpawnEnemy(', 'Actor* Actor_SpawnEntry(ActorContext* actorCtx, ActorEntry* actorEntry, PlayState* play) {']:
 code+='\n'+function(engine,sig)
code+=r'''
void TestCall(ActorFunc f,Actor* a,PlayState* p){Actor_CallWithEnemySpawnSource(f,a,p);}
void TestHook(void(*f)(void*),Actor* a){Actor_HookWithEnemySpawnSource(f,a);}
void TestSceneIndex(s16 i){sEnemySceneSpawnIndex=i;}
void TestPrepared(s32 i){sEnemyPreparedPlacement=i;}
bool TestContextEmpty(void){return sEnemySceneSpawnIndex==-1&&sEnemyPreparedPlacement==-1&&sEnemyCallbackSource==NULL&&sEnemyExplicitSpawnSource==NULL;}
'''
(build/'production_spawn.c').write_text(code)
cpp=r'''
#include "fixture.h"
#include <array>
#include <map>
#include <set>
#include <vector>
#include <utility>
#include <cstdio>
#include "soh/Enhancements/randomizer/randomizerEnums.h"
#include "soh/Enhancements/randomizer/EnemySpawnCatalog.h"
#include "soh/Enhancements/randomizer/EnemyDropPolicy.h"
static PlayState play{};PlayState* gPlayState=&play;u32 gSegments[16]{};
static bool isRando=true,activeSave=true,failAllocation=false,clearRoom=false,vetoEntry=false;
static int grottoId=-1;static std::set<int64_t> reported,collected;
#define IS_RANDO isRando
static bool Archipelago_IsCurrentSaveActive(){return activeSave;}
static bool Archipelago_IsLocationActive(int64_t){return true;}
static bool Archipelago_IsLocationReported(int64_t id){return reported.count(id);}
static bool EnemyDefeatWasCollected(size_t index){return collected.count(index);}
namespace EntranceTracker {static int GetCurrentGrottoId(){return grottoId;}}
'''
for sig in ['struct EnemyDefeatPlacement','struct EnemyDefeatIdentity','struct EnemySourceIdentity']:
 cpp+=function(mega,sig)+';\n'
cpp+=r'''
static constexpr EnemyDefeatPlacement kEnemyDefeatPlacements[]={
#include "soh/Enhancements/randomizer/EnemyDefeatPlacements.inc"
};
static constexpr size_t kEnemyPlacementCount=sizeof(kEnemyDefeatPlacements)/sizeof(kEnemyDefeatPlacements[0]);
static std::array<Actor*,kEnemyPlacementCount> gLiveEnemyPlacements{};
struct ObjectExtension{
 template<class T>static std::map<const Actor*,T>& Values(){static std::map<const Actor*,T> v;return v;}
 static ObjectExtension& GetInstance(){static ObjectExtension o;return o;}
 template<class T>T* Get(const Actor* actor){auto& v=Values<T>();auto it=v.find(actor);return it==v.end()?nullptr:&it->second;}
 template<class T>void Set(const Actor* actor,T&& value){Values<T>()[actor]=std::move(value);}
};
static std::map<const Actor*,s16> indices;
extern "C" void SetActorListIndex(Actor* a,s16 i){indices[a]=i;}
extern "C" s16 GetActorListIndex(const Actor* a){auto it=indices.find(a);return it==indices.end()?-1:it->second;}
'''
for sig in ['static bool IsMegaPotActor(', 'static bool IsMegaScrubActor(', 'static bool IsGoldSkulltulaActor(', 'static bool IsOrdinarySkulltulaActor(', 'static RandomizerInf EnemySoulInfForActorId(', 'static bool IsStructuralArmosStatue(', 'static bool IsMegaEnemySoulActor(', 'extern "C" bool MegaSoul_IsEnemySpawnSource(', 'static SohExtreme::EnemySpawnKey EnemySpawnKeyFor(', 'static bool EnemyDefeatLocationStillPending(', 'static void AttachEnemyDefeatIdentity(', 'extern "C" int32_t MegaSoul_FindEnemyDefeatSpawn(', 'extern "C" bool MegaSoul_IsEnemyDefeatPlacementPending(', 'extern "C" int32_t MegaSoul_FindEnemyDefeatChild(', 'extern "C" void MegaSoul_CaptureEnemyDefeatIdentityFrom(', 'extern "C" void MegaSoul_ResetEnemyDefeatLife(', 'extern "C" int32_t MegaSoul_GetEnemyDefeatPlacement(', 'extern "C" void MegaSoul_BeginEnemyDefeatLife(', 'extern "C" bool MegaSoul_HasPendingEnemyInRoom(']:
 cpp+='\n'+function(mega,sig)
rows=json.loads((fixtures/'actor_categories.json').read_text())
cpp+='\nstatic int category(int id){switch(id){\n'+''.join('case %d: return %s;\n'%(e['id'],e['category']) for e in rows)+'default:return ACTORCAT_PROP;}}\n'
cpp+=r'''
static std::map<int,ActorDBEntry> db;
static std::vector<void*> allocated;
static ActorFunc initCallback=nullptr;
static void(*spawnHook)(Actor*)=nullptr;
extern "C" void* TestMalloc(size_t n){if(failAllocation)return nullptr;void* a=std::malloc(n);allocated.push_back(a);return a;}
extern "C" ActorDBEntry* ActorDB_Retrieve(s16 id){auto& v=db[id];v={true,id,category(id),0,0,0,"fixture",sizeof(Actor),initCallback,nullptr,nullptr,nullptr};return &v;}
extern "C" void Actor_FreeOverlay(ActorDBEntry*){}
extern "C" int Object_GetIndex(void*,int){return 0;}
extern "C" int CVarGetInteger(const char*,int){return 0;}
extern "C" bool Flags_GetClear(PlayState*,s8){return clearRoom;}
extern "C" void Actor_AddToCategory(ActorContext* c,Actor* a,int cat){++c->total;a->category=cat;}
extern "C" void Actor_Init(Actor* a,PlayState* p){a->world=a->home;if(a->init)TestCall(a->init,a,p);}
extern "C" void GameInteractor_ExecuteOnActorSpawn(void* a){if(spawnHook)spawnHook(static_cast<Actor*>(a));}
extern "C" bool GameInteractor_Should(int,bool,ActorContext*,ActorEntry*,PlayState*,Actor**){return !vetoEntry;}
static auto& ext=ObjectExtension::GetInstance();
static int tested=0;
static void reset(){
 for(void* a:allocated){std::free(a);}
 allocated.clear();
 ObjectExtension::Values<EnemySourceIdentity>().clear();ObjectExtension::Values<EnemyDefeatIdentity>().clear();
 indices.clear();db.clear();gLiveEnemyPlacements.fill(nullptr);play={};grottoId=-1;reported.clear();collected.clear();
 failAllocation=false;clearRoom=false;vetoEntry=false;initCallback=nullptr;spawnHook=nullptr;assert(TestContextEmpty());
}
static Actor* spawn(const SohExtreme::EnemySpawnKey& k,bool authored=true){
 play.sceneNum=k.scene;play.roomCtx.curRoom.num=static_cast<s8>(k.room);grottoId=k.grotto;
 if(authored)TestSceneIndex(k.actorIndex);
 return Actor_Spawn(&play.actorCtx,&play,k.actorId,k.x,k.y,k.z,0,0,0,static_cast<s16>(k.params));
}
static int expectedInit=-1;
static void mutateInit(Actor* actor,PlayState*){
 assert(MegaSoul_GetEnemyDefeatPlacement(actor)==expectedInit);
 actor->params=0;actor->home.pos={999,999,999};actor->room=-1;
}
static Actor* nested=nullptr;
static int nestedDepth=0;
static void rawChildInit(Actor* actor,PlayState* p){
 if(nestedDepth++)return;
 // Direct Actor_Spawn, not SpawnAsChild; callback origin must still be captured.
 nested=Actor_Spawn(&p->actorCtx,p,ACTOR_EN_BILI,0,0,0,0,0,0,0);
 assert(MegaSoul_GetEnemyDefeatPlacement(nested)==-1);
 assert(ext.Get<EnemySourceIdentity>(nested)->enemyCreated);
 assert(nested->parent==nullptr);
 (void)actor;
}
static void rawSpawnHook(Actor* a){
 spawnHook=nullptr;
 nested=Actor_Spawn(&play.actorCtx,&play,ACTOR_EN_BILI,0,0,0,0,0,0,0);
 assert(ext.Get<EnemySourceIdentity>(nested)->enemyCreated);
 assert(MegaSoul_GetEnemyDefeatPlacement(nested)==-1);(void)a;
}
static void maliciousPrepared(Actor*,PlayState* p){
 TestPrepared(0);
 nested=Actor_Spawn(&p->actorCtx,p,kEnemyDefeatPlacements[0].actorId,0,0,0,0,0,0,kEnemyDefeatPlacements[0].params);
 assert(MegaSoul_GetEnemyDefeatPlacement(nested)==-1);
}
static void maliciousHook(void* a){maliciousPrepared(static_cast<Actor*>(a),&play);}
int main(){
 using namespace SohExtreme;
 // Every exact authored alias: actual C allocation/capture then mutating actor init.
 for(const auto& e:kEnemySpawnAliases){
  reset();expectedInit=e.placement;initCallback=mutateInit;
  Actor* a=spawn(e.key);assert(a);auto* id=ext.Get<EnemyDefeatIdentity>(a);
  assert(id&&id->placementIndex==e.placement&&id->locationId==kEnemyDefeatPlacements[e.placement].locationId);
  assert(id->actorListIndex==e.key.actorIndex&&id->params==e.key.params&&id->spawnPos.y==e.key.y);
  assert(ext.Get<EnemySourceIdentity>(a)->key.params==e.key.params);assert(!ext.Get<EnemySourceIdentity>(a)->enemyCreated);
  // Initial hostile classification survives transformed params/category.
  a->category=ACTORCAT_PROP;assert(MegaSoul_IsEnemySpawnSource(a));++tested;
 }
 // Every nonenemy-controller lane, including room-cleared pending encounters.
 for(const auto& e:kEnemyChildAliases){
  reset();Actor* source=spawn(e.source);assert(source&&!MegaSoul_IsEnemySpawnSource(source));
  clearRoom=true;
  Actor* a=MegaSoul_SpawnEnemyChild(&play,source,e.slot,e.childId,12,34,56,0,0,0,static_cast<s16>(e.params));
  assert(a&&a->parent==source&&MegaSoul_GetEnemyDefeatPlacement(a)==e.placement);
  assert(!ext.Get<EnemySourceIdentity>(a)->enemyCreated);
  assert(MegaSoul_FindEnemyDefeatChild(source,e.childId,e.params,e.slot)==-1);++tested;
 }
 // Each physical grotto's original actor index: no template-to-template collision.
 int grottos=0;
 for(size_t i=0;i<kEnemyPlacementCount;++i){auto& e=kEnemyDefeatPlacements[i];if(e.grottoId<0)continue;
  reset();EnemySpawnKey k{e.scene,e.room,e.grottoId,e.actorListIndex,e.actorId,e.params,0,0,0};
  Actor* a=spawn(k);assert(a&&MegaSoul_GetEnemyDefeatPlacement(a)==static_cast<int>(i));++grottos;++tested;
 }
 assert(grottos==14);
 // The real four sisters remain supported; no introduction or Meg decoy checks.
 for(int sister=0;sister<4;++sister){
  reset();play.sceneNum=SCENE_FOREST_TEMPLE;
  Actor* a=nullptr;
  if(sister==0){EnemySpawnKey k{3,0,-1,1,ACTOR_EN_PO_SISTERS,0,0,0,0};a=spawn(k);}
  else {EnemySpawnKey k{3,0,-1,1,ACTOR_BG_PO_EVENT,0,0,0,0};Actor* source=spawn(k);
   a=MegaSoul_SpawnEnemy(&play,source,0,ACTOR_EN_PO_SISTERS,0,0,0,0,0,0,sister<<8);}
  assert(a&&MegaSoul_GetEnemyDefeatPlacement(a)==566+sister);
  for(int mask:{0x400,0x800,0xC00,0x1000}){
   Actor* d=Actor_SpawnAsChild(&play.actorCtx,a,&play,ACTOR_EN_PO_SISTERS,0,0,0,0,0,0,(sister<<8)|mask);
   assert(d&&MegaSoul_GetEnemyDefeatPlacement(d)==-1&&ext.Get<EnemySourceIdentity>(d)->enemyCreated);
  }++tested;
 }
 // No valid-looking identity is accepted for enemy-created descendants.
 std::set<int> families;for(const auto& placement:kEnemyDefeatPlacements)families.insert(placement.actorId);
 int rejects=0;
 for(int creatorId:families){
  reset();Actor source{};source.id=creatorId;source.params=1;source.category=category(creatorId);
  assert(MegaSoul_IsEnemySpawnSource(&source));
  for(size_t i=0;i<kEnemyPlacementCount;++i){
   auto& e=kEnemyDefeatPlacements[i];Actor child{};child.id=e.actorId;child.params=e.params;child.category=category(e.actorId);
   MegaSoul_CaptureEnemyDefeatIdentityFrom(&child,static_cast<int>(i),&source);
   assert(MegaSoul_GetEnemyDefeatPlacement(&child)==-1);
   MegaSoul_BeginEnemyDefeatLife(&child,static_cast<int>(i));
   assert(MegaSoul_GetEnemyDefeatPlacement(&child)==-1);
   assert(ext.Get<EnemySourceIdentity>(&child)->enemyCreated);++rejects;
  }
 }
 // Bosses count as hostile creators even when not in ordinary enemy-soul mapping.
 reset();Actor boss{};boss.id=ACTOR_BOSS_GOMA;boss.category=ACTORCAT_BOSS;
 assert(MegaSoul_IsEnemySpawnSource(&boss));
 Actor* larva=Actor_SpawnAsChild(&play.actorCtx,&boss,&play,ACTOR_EN_GOMA,0,0,0,0,0,0,0);
 assert(larva&&MegaSoul_GetEnemyDefeatPlacement(larva)==-1&&ext.Get<EnemySourceIdentity>(larva)->enemyCreated);
 // Raw init births, hook births, failed allocation, and context restoration.
 reset();initCallback=rawChildInit;nestedDepth=0;Actor* mother=spawn(kEnemySpawnAliases[0].key);assert(mother&&nested);assert(TestContextEmpty());
 reset();spawnHook=rawSpawnHook;mother=spawn(kEnemySpawnAliases[0].key);assert(mother&&nested);assert(TestContextEmpty());
 reset();mother=spawn(kEnemySpawnAliases[0].key);
 TestCall(maliciousPrepared,mother,&play);TestHook(maliciousHook,mother);assert(TestContextEmpty());
 // An enemy-born helper cannot disguise its own subsequent children as controller encounters.
 auto alias=kEnemyChildAliases[0];play.sceneNum=alias.source.scene;play.roomCtx.curRoom.num=alias.source.room;
 Actor helper{};helper.id=alias.source.actorId;helper.params=alias.source.params;helper.category=category(helper.id);helper.room=alias.source.room;helper.home.pos={float(alias.source.x),float(alias.source.y),float(alias.source.z)};
 SetActorListIndex(&helper,alias.source.actorIndex);MegaSoul_CaptureEnemyDefeatIdentityFrom(&helper,-1,mother);
 assert(MegaSoul_IsEnemySpawnSource(&helper));assert(MegaSoul_FindEnemyDefeatChild(&helper,alias.childId,alias.params,alias.slot)==-1);
 helper.parent=&helper;helper.child=&helper;assert(MegaSoul_IsEnemySpawnSource(&helper)); // no parent recursion
 // Consumed prepared IDs must never leak after an allocation failure.
 reset();Actor* controller=spawn(kEnemyChildAliases[0].source);failAllocation=true;
 auto e=kEnemyChildAliases[0];assert(!MegaSoul_SpawnEnemyChild(&play,controller,e.slot,e.childId,0,0,0,0,0,0,e.params));assert(TestContextEmpty());
 failAllocation=false;assert(spawn(kEnemySpawnAliases[0].key));assert(TestContextEmpty());
 // Unindexed raw aliases and retired IDs do not bind even with matching type/position.
 reset();for(const auto& e:kEnemySpawnAliases){auto k=e.key;k.actorIndex=-1;Actor* a=spawn(k,false);assert(MegaSoul_GetEnemyDefeatPlacement(a)==-1);}
 for(int i=765;i<=785;++i){Actor a{};a.id=ACTOR_EN_PEEHAT;a.params=1;a.category=ACTORCAT_ENEMY;MegaSoul_CaptureEnemyDefeatIdentityFrom(&a,i,nullptr);assert(MegaSoul_GetEnemyDefeatPlacement(&a)==-1);assert(!MegaSoul_IsEnemyDefeatPlacementPending(i));}
 // New-life reset only clears per-life flags, not source or persistent completion.
 reset();Actor* a=spawn(kEnemySpawnAliases[0].key);auto* id=ext.Get<EnemyDefeatIdentity>(a);int placement=id->placementIndex;auto original=ext.Get<EnemySourceIdentity>(a)->key;
 id->deathObserved=id->defeatHandled=id->normalDropHandled=id->rewardWasAp=true;collected.insert(placement);
 MegaSoul_ResetEnemyDefeatLife(a);assert(id->placementIndex==placement&&!id->deathObserved&&!id->defeatHandled&&!id->normalDropHandled&&!id->rewardWasAp);assert(collected.count(placement));assert(SameEnemySpawn(original,ext.Get<EnemySourceIdentity>(a)->key));
 // A vetoed entry has a defined null result and restores nested map-loading state.
 reset();ActorEntry entry{};vetoEntry=true;gMapLoading=7;assert(!Actor_SpawnEntry(&play.actorCtx,&entry,&play));assert(gMapLoading==7);gMapLoading=0;
 printf("%d positive authored/controller/grotto/sister identities; %zu creator families x %zu receipt slots (%d offspring rejections); raw init/hook births, boss larvae, decoys, forged IDs, descendant helpers, cycles, reset and allocation failures passed.\n",tested,families.size(),kEnemyPlacementCount,rejects);
 reset();
}
'''
(build/'production_identity.cpp').write_text(cpp)
commands=[['gcc','-std=c11','-O2','-Wall','-Wextra','-Werror','-I',str(root),'-I',str(fixtures),'-c',str(build/'production_spawn.c'),'-o',str(build/'spawn.o')],['g++','-std=c++17','-O2','-Wall','-Wextra','-Werror','-I',str(root),'-I',str(fixtures),str(build/'production_identity.cpp'),str(build/'spawn.o'),'-o',str(build/'origin')]]
runs=[]
for cmd in commands:
 c=subprocess.run(cmd,capture_output=True,text=True);runs.append(dict(command=cmd,returncode=c.returncode,stdout=c.stdout,stderr=c.stderr))
 if c.returncode:break
if all(r['returncode']==0 for r in runs):
 c=subprocess.run([str(build/'origin')],capture_output=True,text=True);runs.append(dict(command=[str(build/'origin')],returncode=c.returncode,stdout=c.stdout,stderr=c.stderr))
result={'name':'mixed_C_CPP_production_spawn_origin','passed':len(runs)==3 and all(r['returncode']==0 for r in runs),'runs':runs};a.report.write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2));raise SystemExit(not result['passed'])
