"""Compile production enemy display, scout mailbox and collection functions.

Engine allocation/drawing/network services are controlled fakes; this does not
render the game. Run from a VS x64 developer command prompt.
"""
from pathlib import Path
import argparse, json, re, subprocess
from run_native_tests import function

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
r = Path(__file__).resolve().parent.parent
out = a.output.resolve(); out.mkdir(parents=True, exist_ok=True)
apdir = r / 'soh/Network/Archipelago'
ap = (apdir / 'ArchipelagoClient.cpp').read_text(encoding='utf-8')
header = (apdir / 'ArchipelagoClient.h').read_text(encoding='utf-8')
enemy = (r / 'soh/Enhancements/randomizer/MegaSouls.cpp').read_text(encoding='utf-8')
hooks = (r / 'soh/Enhancements/randomizer/hook_handlers.cpp').read_text(encoding='utf-8')
names = (apdir / 'ArchipelagoNameMap.inc').read_text(encoding='utf-8')
ids = (apdir / 'ArchipelagoItemMap.inc').read_text(encoding='utf-8')
selectors = '\n'.join(function(ap, s) for s in [
    'static RandomizerGet GetRemoteArchipelagoDisplay(',
    'static RandomizerGet MapApItemNameToRandomizerGet(',
    'static RandomizerGet GetIceTrapDisguise(',
    'int32_t ArchipelagoClient::MapApItemToRandomizerGet(',
    'int32_t ArchipelagoClient::GetLocationDisplayItem(',
    'void ArchipelagoClient::QueueLocationInfo(',
])
layout = ap[ap.index('struct SongNotes {'):ap.index('static std::string BuildApSongNotePickupDescription(')]
rg = sorted(set(re.findall(r'\bRG_\w+', selectors + names + ids + layout)) - {'RG_NONE'})
code = r'''
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <deque>
#include <mutex>
#include <string>
#include <unordered_map>
#include <utility>
#include <initializer_list>
'''
code += 'enum RandomizerGet { RG_NONE=0,' + ','.join(rg) + '};\n'
code += '\n'.join(re.findall(r'^constexpr int64_t AP_.*?;', ap, re.M)) + '\n'
code += r'''
int AP_GetPlayerID(){return 1;}
class ArchipelagoClient {public:
 bool active=true; bool IsGameplaySessionActive()const{return active;}
 int32_t MapApItemToRandomizerGet(int64_t)const;
 int32_t GetLocationDisplayItem(int64_t)const;
 void QueueLocationInfo(int64_t,int64_t,int,int,const std::string&,const std::string&,const std::string&,const std::string&);
 std::mutex queueMutex;
'''
code += function(header, 'struct ScoutedLocation {') + ';\n'
code += r'''
 struct PendingScout{int64_t locationId;ScoutedLocation info;};
 std::deque<PendingScout> pendingScouts;
 std::unordered_map<int64_t,ScoutedLocation> scoutedLocations;
} client;
'''
code += 'enum Quests {' + ','.join(sorted(set(re.findall(r'\bQUEST_SONG_\w+', layout)))) + '};\n'
code += layout + '\n' + selectors + '\n'
code += r'''
int32_t Archipelago_GetLocationDisplayItem(int64_t id){return client.GetLocationDisplayItem(id);}
struct Vec3f{float x=0,y=0,z=0;};
struct PlayState{} play;PlayState* gPlayState=&play;
using ActorFunc=void(*)();
struct Actor {struct {Vec3f pos,rot;}world;Vec3f velocity;float speedXZ=0;int params=0;ActorFunc draw=nullptr;};
struct Entry{int model=RG_NONE;};
struct EnItem00{Actor actor;int randoInf=0,randoCheck=0;Entry itemEntry;};
constexpr int ITEM00_SOH_DUMMY=100,RAND_INF_MAX=999,RC_UNKNOWN_CHECK=0;
constexpr size_t kEnemyPlacementCount=8;
Actor* gLiveEnemyPickups[kEnemyPlacementCount]={};
'''
code += function(enemy, 'struct EnemyDefeatDropIdentity {') + ';\n'
code += r'''
struct ObjectExtension {
 std::unordered_map<const Actor*,EnemyDefeatDropIdentity> data;
 static ObjectExtension& GetInstance(){static ObjectExtension x;return x;}
 template<class T>T* Get(const Actor* a){auto i=data.find(a);return i==data.end()?nullptr:&i->second;}
 template<class T>void Set(const Actor* a,T v){data[a]=std::move(v);}
 template<class T>void Remove(const Actor* a){data.erase(a);}
};
namespace Rando {struct Item{int model;Entry GetGIEntry_Copy(){return {model};}};
struct StaticData{static Item RetrieveItem(int id){assert(id!=RG_NONE);return {id};}};}
bool active=true,owned=true,reported=false,submitted=false,accept=true,pending=true,allocated=true;
int reports=0,journal=0,spawns=0,drawn=RG_NONE,killed=0;
bool collected[kEnemyPlacementCount]={};
bool Archipelago_IsCurrentSaveActive(){return active;}
bool Archipelago_IsLocationActive(int64_t){return owned;}
bool Archipelago_IsLocationReported(int64_t){return reported;}
bool Archipelago_IsLocationSubmitted(int64_t){return submitted;}
void Archipelago_ReportLocation(int64_t){++reports;submitted=accept;}
void MarkEnemyDefeatCollected(size_t i){collected[i]=true;}
void PersistEnemyDefeatJournal(){++journal;}
bool EnemyDefeatLocationStillPending(int32_t,int64_t){return pending;}
namespace SohExtreme {bool IsRetiredEnemyPlacement(int i){return i==7;}
bool CanConsumeEnemyPickup(bool a,bool o,bool s){return a&&o&&s;}}
EnItem00 drop;
EnItem00* Item_DropCollectible2(PlayState*,Vec3f*,int params){++spawns;drop.actor.params=params;return allocated?&drop:nullptr;}
float Rand_CenteredFloat(float){return 0;}
void EnItem00_DrawRandomizedItem(EnItem00* i,PlayState*){drawn=i->itemEntry.model;}
void Actor_Kill(Actor*){++killed;}
'''
for sig in ['static void DrawEnemyDefeatPickup(', 'static EnItem00* SpawnEnemyDefeatPickup(',
            'extern "C" bool MegaSoul_IsEnemyDefeatPickup(', 'extern "C" bool MegaSoul_TryCollectEnemyDefeatPickup(']:
    code += function(enemy, sig) + '\n'
# Compile the real dispatch guard too: rejected checks cannot hit dummy fallback.
start = hooks.index('            if (item00->actor.params == ITEM00_SOH_DUMMY &&\n', hooks.index('case VB_GIVE_ITEM_FROM_ITEM_00:'))
block = function(hooks[start:], 'if (item00->actor.params')
code += 'bool collect(EnItem00* item00){bool value=true;bool* should=&value;do{\n' + block
code += '\n++killed; /* generic dummy fallback */\n}while(false);return value;}\n'
code += 'std::pair<const char*,RandomizerGet> knownNames[]={\n' + names + '\n};\n'
cases = re.findall(r'case (\d+)LL: randoGet = (RG_\w+);', ids)
code += 'std::pair<int64_t,RandomizerGet> knownIds[]={' + ','.join('{'+i+','+rg+'}' for i,rg in cases) + '};\n'
code += r'''
int main(){int checks=0;constexpr int64_t loc=9800001;
 auto check=[&](bool v){assert(v);++checks;};
 check(client.GetLocationDisplayItem(loc)==RG_AP_REMOTE_IMPORTANT);
 // The callback owns only its mailbox; data becomes visible on the game thread.
 client.QueueLocationInfo(loc,1,2,1,"Kokiri Sword","Friend","Enemy","SOH-EXTREME");
 check(client.scoutedLocations.empty()&&client.pendingScouts.size()==1);
 client.scoutedLocations[loc]=client.pendingScouts.front().info;client.pendingScouts.clear();
 auto& info=client.scoutedLocations[loc];
 check(info.itemGame=="SOH-EXTREME"&&client.GetLocationDisplayItem(loc)==RG_KOKIRI_SWORD);
 // Every named native mapping, local and same-game remote; never trust foreign collisions.
 for(const auto& pair:knownNames)for(int recipient:{1,2}){
  info.playerId=recipient;info.itemGame="SOH-EXTREME";info.itemName=pair.first;info.itemId=999999999;
  int expected=pair.second==RG_ICE_TRAP?GetIceTrapDisguise(loc):pair.second;
  check(client.GetLocationDisplayItem(loc)==expected);
  if(recipient==2){info.itemGame="OtherGame";check(client.GetLocationDisplayItem(loc)==RG_AP_REMOTE_IMPORTANT);}
 }
 for(auto pair:knownIds){info={};info.playerId=1;info.itemId=pair.first;
  check(client.GetLocationDisplayItem(loc)==(pair.second==RG_ICE_TRAP?GetIceTrapDisguise(loc):pair.second));}
 for(auto id:{AP_ITEM_ROLL,AP_ITEM_OPEN_CHEST,AP_ITEM_ENEMY_SOUL_POE,AP_ITEM_NPC_SOUL,AP_FIRST_SONG_NOTE,AP_LAST_SONG_NOTE,AP_FIRST_SILVER_ITEM,AP_LAST_SILVER_ITEM}){
  info={};info.playerId=1;info.itemId=id;check(client.GetLocationDisplayItem(loc)==client.MapApItemToRandomizerGet(id));
  check(client.GetLocationDisplayItem(loc)!=RG_NONE);
 }
 for(auto game:{"OtherGame",""})for(int flags:{0,1,2,3,4,9,25}){
  info={};info.playerId=2;info.itemId=1;info.itemName="Kokiri Sword";info.itemGame=game;info.flags=flags;
  check(client.GetLocationDisplayItem(loc)==((flags&3)?RG_AP_REMOTE_IMPORTANT:RG_AP_REMOTE_NORMAL));
 }
 info={};info.playerId=1;info.itemId=999999999;check(client.GetLocationDisplayItem(loc)==RG_AP_REMOTE_NORMAL);
 info.flags=1;check(client.GetLocationDisplayItem(loc)==RG_AP_REMOTE_IMPORTANT);
 client.active=false;info.itemId=1;check(client.GetLocationDisplayItem(loc)==RG_AP_REMOTE_IMPORTANT);client.active=true;
 // A live pickup begins as a fallback, updates in place after scouting, and never grants.
 client.scoutedLocations.clear();Actor enemy;
 check(SpawnEnemyDefeatPickup(nullptr,1,loc)==nullptr);
 allocated=false;check(SpawnEnemyDefeatPickup(&enemy,1,loc)==nullptr);allocated=true;
 pending=false;check(SpawnEnemyDefeatPickup(&enemy,1,loc)==nullptr);pending=true;
 auto* item=SpawnEnemyDefeatPickup(&enemy,1,loc);
 check(item&&item->itemEntry.model==RG_AP_REMOTE_IMPORTANT&&item->randoInf==RAND_INF_MAX&&item->randoCheck==RC_UNKNOWN_CHECK);
 int n=spawns;check(SpawnEnemyDefeatPickup(&enemy,1,loc)==item&&spawns==n);
 check(item->actor.draw==reinterpret_cast<ActorFunc>(DrawEnemyDefeatPickup));
 client.QueueLocationInfo(loc,1,1,1,"Kokiri Sword","Me","Enemy","SOH-EXTREME");
 client.scoutedLocations[loc]=client.pendingScouts.front().info;client.pendingScouts.clear();
 DrawEnemyDefeatPickup(item,&play);check(drawn==RG_KOKIRI_SWORD&&reports==0&&journal==0);
 // Model does not affect AP identity, retry, or the no-local-grant dispatch.
 active=false;check(!collect(item)&&killed==0&&reports==0);active=true;
 accept=false;check(!collect(item)&&killed==0&&reports==1&&!collected[1]&&journal==0);
 check(MegaSoul_IsEnemyDefeatPickup(&item->actor));
 accept=true;check(!collect(item)&&killed==1&&reports==2&&collected[1]&&journal==1);
 check(!MegaSoul_IsEnemyDefeatPickup(&item->actor)&&gLiveEnemyPickups[1]==nullptr);
 check(!MegaSoul_TryCollectEnemyDefeatPickup(&item->actor)&&reports==2&&journal==1);
 check(item->itemEntry.model==RG_KOKIRI_SWORD&&item->randoCheck==RC_UNKNOWN_CHECK&&item->randoInf==RAND_INF_MAX);
 std::printf("%d assertions passed\n",checks);
}
'''
src = out / 'models.cpp'; src.write_text(code, encoding='utf-8'); exe = out / 'models.exe'
c = subprocess.run(['cl','/nologo','/std:c++20','/EHsc','/MD','/I',str(apdir),str(src),'/Fo'+str(out/'models.obj'),'/Fe'+str(exe)], capture_output=True, text=True)
t = subprocess.run([str(exe)], capture_output=True, text=True) if c.returncode == 0 else None
report = dict(passed=c.returncode==0 and t.returncode==0, compile_output=c.stdout+c.stderr,
              output=t.stdout+t.stderr if t else '', scope=__doc__)
(out / 'models.json').write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2)); raise SystemExit(not report['passed'])
