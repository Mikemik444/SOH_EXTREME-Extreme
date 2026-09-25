"""Compile actual journal/recovery/rebinding functions against deterministic service substitutes.
This does not compile or run the whole game; no game assets are needed.
"""
from pathlib import Path
import argparse,json,subprocess
from run_native_tests import function
p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
root=a.source_root.resolve();mega=(root/'soh/Enhancements/randomizer/MegaSouls.cpp').read_text()
build=a.report.parent/'journal-test-build';build.mkdir(parents=True,exist_ok=True)
code=r'''
#include <cassert>
#include <type_traits>
#include <cstdint>
#include <cstddef>
#include <cstdio>
#include <array>
#include <mutex>
#include <set>
#include <unordered_map>
#include "soh/Enhancements/randomizer/EnemyDropPolicy.h"
#include "soh/Enhancements/randomizer/EnemySpawnCatalog.h"
#include "soh/Enhancements/randomizer/EnemyDropBridge.h"
struct Vec3f {float x=0,y=0,z=0;};
struct Actor {int16_t id=0;int bgCheckFlags=1;float yDistToWater=-1;};
struct Player {Actor actor;};
struct PlayState {int sceneNum=0;};
static PlayState play; static PlayState* gPlayState=&play;
static Player fixturePlayer; static bool activeSave=true,cutscene=false,isRando=true,acceptReports=true;
static int saveCalls=0,recoverCalls=0,reportCalls=0,grottoId=-1,lastRecovered=-1;
static std::set<int64_t> reported,active;
#define IS_RANDO isRando
#define GET_PLAYER(p) (&fixturePlayer)
#define BGCHECKFLAG_GROUND 1
static bool Player_InCsMode(PlayState*){return cutscene;}
namespace EntranceTracker {static int GetCurrentGrottoId(){return grottoId;}}
static bool Archipelago_IsCurrentSaveActive(){return activeSave;}
static bool Archipelago_IsLocationActive(int64_t id){return active.count(id)!=0;}
static bool Archipelago_IsLocationReported(int64_t id){return reported.count(id)!=0;}
static void Archipelago_ReportLocation(int64_t id){++reportCalls;if(acceptReports)reported.insert(id);}
struct {int fileNum=0;} gSaveContext;
struct SaveManager {static SaveManager* Instance;void SaveSection(int file,int section,bool){assert(file<3&&section==17);++saveCalls;}};
static SaveManager manager;SaveManager* SaveManager::Instance=&manager;
''' + function(mega,'struct EnemyDefeatPlacement')+';\n' +r'''
static constexpr EnemyDefeatPlacement kEnemyDefeatPlacements[]={
#include "soh/Enhancements/randomizer/EnemyDefeatPlacements.inc"
};
static constexpr size_t kEnemyPlacementCount=sizeof(kEnemyDefeatPlacements)/sizeof(kEnemyDefeatPlacements[0]);
static std::array<uint8_t,kEnemyPlacementCount> gEnemyDefeatCompleted{};
static std::mutex gEnemyDefeatSaveMutex;
static int gEnemyDefeatSaveSection=17;
static std::array<Actor*,kEnemyPlacementCount> gLiveEnemyPickups{},gLiveEnemyPlacements{};
static Actor pickup;
static void SpawnEnemyDefeatPickup(Actor*,int32_t index,int64_t){++recoverCalls;lastRecovered=index;gLiveEnemyPickups[index]=&pickup;}
''' + function(mega,'struct EnemyDefeatIdentity')+';\n'+function(mega,'struct EnemySourceIdentity')+';\n'+r'''
struct ObjectExtension {
 std::unordered_map<const Actor*,EnemyDefeatIdentity> values;
 std::unordered_map<const Actor*,EnemySourceIdentity> sources;
 static ObjectExtension& GetInstance(){static ObjectExtension x;return x;}
 template<class T>T* Get(const Actor* actor){
  if constexpr(std::is_same_v<T,EnemySourceIdentity>){auto i=sources.find(actor);return i==sources.end()?nullptr:&i->second;}
  else {auto i=values.find(actor);return i==values.end()?nullptr:&i->second;}
 }
};
'''
for signature in ['static void PersistEnemyDefeatJournal()', 'static void MarkEnemyDefeatEarned(', 'static bool EnemyDefeatWasCollected(', 'static void MarkEnemyDefeatCollected(', 'static bool EnemyDefeatLocationStillPending(', 'static void ReplayCollectedEnemyChecks()', 'static void RecoverEarnedEnemyPickups()', 'extern "C" void MegaSoul_BeginEnemyDefeatLife(']:
 code+='\n'+function(mega,signature)
code+=r'''
int main(){
 for(const auto& p:kEnemyDefeatPlacements)active.insert(p.locationId);
 MarkEnemyDefeatEarned(0);assert(gEnemyDefeatCompleted[0]==2&&saveCalls==1&&!EnemyDefeatWasCollected(0));
 MarkEnemyDefeatEarned(0);assert(saveCalls==1);
 MarkEnemyDefeatEarned(kEnemyPlacementCount);assert(saveCalls==1);
 ReplayCollectedEnemyChecks();assert(reportCalls==0); // Earned is NOT collected.
 RecoverEarnedEnemyPickups();assert(recoverCalls==1&&lastRecovered==0&&reportCalls==0);
 RecoverEarnedEnemyPickups();assert(recoverCalls==1); // No duplicate live pickup.
 gLiveEnemyPickups[0]=nullptr;cutscene=true;RecoverEarnedEnemyPickups();assert(recoverCalls==1);
 cutscene=false;fixturePlayer.actor.bgCheckFlags=0;RecoverEarnedEnemyPickups();assert(recoverCalls==1);
 fixturePlayer.actor.bgCheckFlags=1;fixturePlayer.actor.yDistToWater=2;RecoverEarnedEnemyPickups();assert(recoverCalls==1);
 fixturePlayer.actor.yDistToWater=-1;play.sceneNum=99;RecoverEarnedEnemyPickups();assert(recoverCalls==1);
 play.sceneNum=0;RecoverEarnedEnemyPickups();assert(recoverCalls==2);
 MarkEnemyDefeatCollected(0);assert(EnemyDefeatWasCollected(0));
 acceptReports=false;ReplayCollectedEnemyChecks();assert(reportCalls==1&&!reported.count(9800000));
 acceptReports=true;ReplayCollectedEnemyChecks();assert(reportCalls==2&&reported.count(9800000));
 ReplayCollectedEnemyChecks();assert(reportCalls==2);MarkEnemyDefeatEarned(0);assert(gEnemyDefeatCompleted[0]==1);
 // Saved 0/1 receipts retain their meaning; newly-earned 2 remains recoverable.
 gEnemyDefeatCompleted[1]=1;gEnemyDefeatCompleted[2]=2;reported.clear();reportCalls=0;
 ReplayCollectedEnemyChecks();assert(reported.count(9800000)&&reported.count(9800001)&&!reported.count(9800002));
 gEnemyDefeatCompleted.fill(0);gLiveEnemyPickups.fill(nullptr);reported.clear();recoverCalls=0;
 for(size_t i=0;i<kEnemyPlacementCount;++i)if(kEnemyDefeatPlacements[i].grottoId>=0){
   gEnemyDefeatCompleted[i]=2;play.sceneNum=kEnemyDefeatPlacements[i].scene;grottoId=120;
   RecoverEarnedEnemyPickups();assert(recoverCalls==0);grottoId=kEnemyDefeatPlacements[i].grottoId;
   RecoverEarnedEnemyPickups();assert(recoverCalls==1&&lastRecovered==static_cast<int>(i));break;
 }
 // One pooled Field Poe must bind each authored source, not its current/death position.
 Actor poe;
 auto& ext=ObjectExtension::GetInstance();ext.values[&poe]={};int previous=-1,fieldSources=0;
 for(const auto& alias:SohExtreme::kEnemySpawnAliases){
   const auto& e=kEnemyDefeatPlacements[alias.placement];
   if(e.scene!=0x51||e.actorId!=0x175)continue;
   poe.id=e.actorId;auto& id=ext.values[&poe];id.defeatHandled=id.normalDropHandled=id.rewardWasAp=id.deathObserved=true;
   MegaSoul_BeginEnemyDefeatLife(&poe,alias.placement);
   assert(id.locationId==e.locationId&&id.placementIndex==alias.placement&&!id.defeatHandled&&!id.normalDropHandled&&!id.rewardWasAp&&!id.deathObserved);
   assert(id.spawnPos.x==alias.key.x&&id.spawnPos.y==alias.key.y&&id.spawnPos.z==alias.key.z);
   if(previous>=0&&previous!=alias.placement)assert(gLiveEnemyPlacements[previous]==nullptr);
   assert(gLiveEnemyPlacements[alias.placement]==&poe);previous=alias.placement;++fieldSources;
 }
 assert(fieldSources>=10);
 MegaSoul_BeginEnemyDefeatLife(nullptr,0);MegaSoul_BeginEnemyDefeatLife(&poe,-1);
 // A legacy collected offspring receipt is not resent to a stale server.
 gEnemyDefeatCompleted.fill(0);reported.clear();reportCalls=0;gLiveEnemyPickups.fill(nullptr);
 for(int i=765;i<=785;++i)gEnemyDefeatCompleted[i]=1;
 ReplayCollectedEnemyChecks();assert(reportCalls==0&&reported.empty());
 for(int i=765;i<=785;++i)gEnemyDefeatCompleted[i]=2;
 play.sceneNum=kEnemyDefeatPlacements[765].scene;recoverCalls=0;
 RecoverEarnedEnemyPickups();assert(recoverCalls==0);
 puts("Real journal/recovery functions: earned vs collected, offline replay, duplicate prevention, grounded recovery, grotto isolation and all Field Poe source rebindings passed.");
}
'''
f=build/'journal.cpp';f.write_text(code);exe=build/'journal';cmd=['g++','-std=c++17','-O2','-Wall','-Wextra','-Werror','-I',str(root),str(f),'-o',str(exe)]
c=subprocess.run(cmd,text=True,capture_output=True);r=subprocess.run([str(exe)],text=True,capture_output=True) if c.returncode==0 else None
result={'name':'journal_and_pooled_identity','passed':c.returncode==0 and r.returncode==0,'compile_command':cmd,'compile_stderr':c.stderr,'stdout':r.stdout if r else '', 'stderr':r.stderr if r else ''}
a.report.write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2));raise SystemExit(not result['passed'])
