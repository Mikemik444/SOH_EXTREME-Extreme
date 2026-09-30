"""Execute changed production function bodies with controlled engine services.

This validates state transitions without claiming an in-game/AP-server playthrough.
Run from a VS x64 developer environment. Supply the nlohmann header include
directory and the APCpp source directory after CMake has applied its repairs.
Example: python validation/test_ap_gameplay_fixes.py --include-dir PATH
         --apcpp-source build-vs/_deps/apcpp-src --output work/ap-gameplay-tests
"""
from pathlib import Path
import ast, json, subprocess, sys, re, argparse
sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_native_tests import function
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source-root', type=Path, default=Path(__file__).resolve().parent.parent)
parser.add_argument('--include-dir', type=Path, required=True, help='Directory containing nlohmann/json.hpp')
parser.add_argument('--apcpp-source', type=Path, required=True, help='Patched APCpp source directory')
parser.add_argument('--output', type=Path, default=Path('work/ap-gameplay-tests'))
args = parser.parse_args()
ROOT = args.source_root.resolve()
OUT = args.output.resolve()
OUT.mkdir(parents=True, exist_ok=True)
ap = (ROOT/'soh/Network/Archipelago/ArchipelagoClient.cpp').read_text()
fish = (ROOT/'soh/Enhancements/randomizer/fishsanity.cpp').read_text()
results=[]
def run(name, source):
    src=OUT/(name+'.cpp'); exe=OUT/(name+'.exe')
    src.write_text(source)
    proc=subprocess.run(['cl','/nologo','/std:c++20','/Zc:preprocessor','/EHsc','/MD','/I',str(args.include_dir.resolve()),str(src),'/Fo'+str(OUT/(name+'.obj')),'/Fe'+str(exe)],capture_output=True,text=True)
    result=subprocess.run([str(exe)],capture_output=True,text=True) if proc.returncode==0 else None
    passed=proc.returncode==0 and result.returncode==0
    log=proc.stdout+proc.stderr+(result.stdout+result.stderr if result else '')
    (OUT/(name+'.log')).write_text(log)
    results.append({'name':name,'passed':passed,'log':str(OUT/(name+'.log'))})
    print(('PASS ' if passed else 'FAIL ')+name, flush=True)
    if not passed: print(log[-8000:])

common=r'''
#include <cassert>
#include <cstdint>
#include <string>
#include <array>
#include <set>
#include <unordered_set>
#include <unordered_map>
#include <deque>
#include <mutex>
#include <thread>
#include <vector>
#include <algorithm>
#include <limits>
#include <nlohmann/json.hpp>
#define SPDLOG_INFO(...) ((void)0)
#define SPDLOG_DEBUG(...) ((void)0)
#define SPDLOG_WARN(...) ((void)0)
#define SPDLOG_ERROR(...) ((void)0)
'''

reward=ap[ap.index('    // These rewards must behave identically'):ap.index('    // A newly-created local AP file')]
run('ap_rewards',common+r'''
using s16=int16_t;
enum { RG_GOLD_SKULLTULA_TOKEN,RG_PIECE_OF_HEART,RG_HEART_CONTAINER,RG_PROGRESSIVE_WALLET,RG_WALLET_INF,
ITEM_NONE=255,UPG_WALLET=0,RAND_INF_HAS_WALLET=0,RAND_INF_HAS_INFINITE_MONEY=1,
RSK_INCLUDE_TYCOON_WALLET=0,RSK_INFINITE_UPGRADES=1,RSK_FULL_WALLETS=2,RO_INF_UPGRADES_OFF=0,
QUEST_HEART_PIECE=24,FULL_HEART_HEALTH=16 };
struct Option {int value;int Get(){return value;}bool IsNot(int x){return value!=x;}} options[3];
#define RAND_GET_OPTION(k) options[k]
struct {struct {uint32_t questItems=0;}inventory;int health=16,healthCapacity=48,healthAccumulator=0,rupees=0,rupeeAccumulator=0;}gSaveContext;
int walletLevel=0,tokens=0,notifications=0; bool flags[2]={}; void* gPlayState=nullptr;
bool Flags_GetRandomizerInf(int f){return flags[f];}void Flags_SetRandomizerInf(int f){flags[f]=true;}
void Inventory_ChangeUpgrade(int,int v){walletLevel=v;}
int capacity(){return std::array<int,4>{99,200,500,999}[walletLevel];}
#define CUR_UPG_VALUE(x) walletLevel
#define CUR_CAPACITY(x) capacity()
void Item_Give(void*,uint8_t item){if(item==RG_PIECE_OF_HEART)gSaveContext.inventory.questItems+=1u<<28;
else if(item==RG_HEART_CONTAINER){gSaveContext.healthCapacity+=16;gSaveContext.health+=16;}else ++tokens;}
struct GI {int itemId;}; struct Item {GI GetGIEntry_Copy(){return {RG_WALLET_INF};}
struct Name {std::string english="reward";};Name GetName(){return {};}bool IsMajorItem(){return false;}}item;
namespace Rando::StaticData {Item RetrieveItem(int){return {};}}
void Randomizer_Item_Give(void*,GI){flags[RAND_INF_HAS_INFINITE_MONEY]=true;}
namespace Notification {struct N{std::string prefix,message,suffix;float remainingTime;};void Emit(N){++notifications;}}
bool give(int randoGet,bool historicalNewSaveReplay=false){GI giEntry{randoGet};
'''+reward+r'''
return false;}
int main(){
for(bool historical:{false,true}){
 gSaveContext={};gSaveContext.healthCapacity=48;notifications=0;
 for(int i=1;i<=8;++i){gSaveContext.health=1;gSaveContext.healthAccumulator=-8;assert(give(RG_PIECE_OF_HEART,historical));
 assert(gSaveContext.healthCapacity==48+(i/4)*16);assert(gSaveContext.health==gSaveContext.healthCapacity);
 assert(gSaveContext.inventory.questItems>>28==i%4);assert(gSaveContext.healthAccumulator==0);}
 gSaveContext.health=1;assert(give(RG_HEART_CONTAINER,historical));assert(gSaveContext.health==96);
 assert(notifications==(historical?0:9));
 for(bool tycoon:{false,true})for(bool full:{false,true})for(bool infinite:{false,true}){
  flags[0]=flags[1]=false;walletLevel=0;gSaveContext.rupees=7;options[0].value=tycoon;options[1].value=infinite;options[2].value=full;
  // Silent wallet reconstruction; live tier/animation/fill is covered by the
  // complete ProcessItem callback harness in test_ability_receipts.py.
  for(int i=0;i<7;++i){assert(give(RG_PROGRESSIVE_WALLET,true));assert(flags[0]);assert(walletLevel==std::min(i,tycoon?3:2));
   assert(gSaveContext.rupees==(full?capacity():7));}
  assert(flags[1]==infinite);
 }
}
}
''')

parser=function(ap,'static bool ParseFlatStringIntObject(const std::string& raw, std::unordered_map<std::string, int64_t>& out) {')
active=function(ap,'void ArchipelagoClient::SetActiveLocationsFromJson(')
mail='\n'.join(function(ap,s) for s in ['void ArchipelagoClient::QueueSlotData(', 'void ArchipelagoClient::DrainSlotData(', 'void ArchipelagoClient::BeginItemReplay(', 'void ArchipelagoClient::QueueItem('])
run('ap_mailbox_and_replay',common+r'''
class ArchipelagoClient {public:
std::mutex queueMutex;std::unordered_map<std::string,std::string>pendingSlotData;
std::unordered_set<int64_t>activeLocations;bool activeLocationsLoaded=false,scoutsRequested=true,checkFinderMappingsPrepared=true,activeLocationsPendingRefresh=false;
std::unordered_map<int,int>scoutedLocations,scoutedLocationNameIndex;
bool deathLinkEnabled=false,trapLinkEnabled=false,kakarikoGateOpen=false;
std::thread::id gameThread=std::this_thread::get_id();int settingsCalls=0;
uint64_t incomingItemOrdinal=0;std::vector<int64_t>receivedItemSnapshot;
struct PendingItem{int64_t id;bool notify;uint64_t sequence;};std::deque<PendingItem>pendingItems;
void QueueSlotData(const std::string&,const std::string&);void DrainSlotData();void BeginItemReplay();void QueueItem(int64_t,bool);
void SetActiveLocationsFromJson(const std::string&);
void SetSlotSettingsFromJson(const std::string&){assert(std::this_thread::get_id()==gameThread);++settingsCalls;}
void SetShopPricesFromJson(const std::string&){} void SetLocationNameMapFromJson(const std::string&){}
};
'''+parser+active.replace('activeLocationsPendingRefresh.store(true);','activeLocationsPendingRefresh = true;')+mail+r'''
int main(){
 std::unordered_map<std::string,int64_t>obj;
 assert(ParseFlatStringIntObject(R"({"escaped\"name":42,"unicode\u0041":-3})",obj));assert(obj["escaped\"name"]==42);assert(obj["unicodeA"]==-3);
 for(auto bad:{"{\"x\":9223372036854775808}","{\"x\":1e99}","{\"x\":true}","{\"x\":1,}","[]","{\"x\":2}junk"})assert(!ParseFlatStringIntObject(bad,obj));
 ArchipelagoClient c;c.SetActiveLocationsFromJson("[1,2,3]");
 for(auto bad:{"[1,-2]","[0]","[true]","[1.5]","[99999999999999999999999999]","[1,]","{}"}){c.SetActiveLocationsFromJson(bad);assert(c.activeLocations.size()==3);}
 std::thread net([&]{for(int i=0;i<10000;++i)c.QueueSlotData("extreme_soh_cvars","{}");c.QueueSlotData("death_link","1");});
 net.join();assert(c.settingsCalls==0);assert(!c.deathLinkEnabled);c.DrainSlotData();assert(c.settingsCalls==1&&c.deathLinkEnabled);
 c.QueueItem(44,true);c.QueueItem(7,true);c.BeginItemReplay();assert(c.pendingItems.empty());c.QueueItem(44,false);c.QueueItem(7,false);
 assert(c.pendingItems.size()==2&&c.pendingItems[0].sequence==0&&c.pendingItems[1].sequence==1);
 c.SetActiveLocationsFromJson("[]");assert(c.activeLocations.empty());
}
''')

goal=function(ap,'void ArchipelagoClient::UpdateGoal() {')
run('ap_goal',common+r'''
enum {RC_WINCON,RSK_WINCON_TRIFORCE_COUNT,RSK_WINCON,RO_WINCON_TRIFORCE_PIECES=7,RCSHOW_COLLECTED=1,TRANS_TRIGGER_OFF=0,
PLAYER_STATE1_IN_ITEM_CS=1,PLAYER_STATE1_GETTING_ITEM=2};
struct Option{int v=0;int Get(){return v;}bool Is(int x){return v==x;}}options[4];
#define RAND_GET_OPTION(k) options[k]
struct Player{int stateFlags1=0;}testPlayer;
struct Play {int transitionTrigger=0;}play;Play* gPlayState=&play;
#define GET_PLAYER(p) (&testPlayer)
bool paused=false,blocking=false,warp=false;int reports=0;
bool Player_InBlockingCsMode(Play*,Player*){return blocking;}
namespace GameInteractor{bool IsGameplayPaused(){return paused;}}
void GameInteractor_SetTriforceHuntCreditsWarpActive(bool v){warp=v;}
void AP_StoryComplete(){++reports;}
struct {struct {struct {struct {struct {int triforcePiecesCollected=0;}randomizer;}data;}quest;struct{bool gameComplete=false;}stats;}ship;int health=48;}gSaveContext;
struct Win {bool obtained=false;int changes=0;bool HasObtained(){return obtained;}void SetCheckStatus(int){obtained=true;++changes;}}win;
namespace Rando {struct Context {static Context* GetInstance(){static Context c;return &c;}Win*GetItemLocation(int){return &win;}};}
struct ArchipelagoClient{bool active=true,auth=true,awaitingMajorItemReceipt=false,goalReported=false;
 bool IsGameplaySessionActive(){return active;}bool IsAuthenticated(){return auth;}void UpdateGoal();};
'''+goal+r'''
int main(){ArchipelagoClient c;options[RSK_WINCON].v=7;options[RSK_WINCON_TRIFORCE_COUNT].v=25;
 gSaveContext.ship.quest.data.randomizer.triforcePiecesCollected=24;c.UpdateGoal();assert(!warp&&reports==0);
 gSaveContext.ship.quest.data.randomizer.triforcePiecesCollected=25;c.awaitingMajorItemReceipt=true;c.UpdateGoal();assert(!warp&&reports==0);
 c.awaitingMajorItemReceipt=false;blocking=true;c.UpdateGoal();assert(!warp&&reports==1&&win.changes==1);
 blocking=false;c.UpdateGoal();assert(warp&&reports==1);c.UpdateGoal();assert(reports==1&&win.changes==1);
 c.auth=false;c.UpdateGoal();assert(!c.goalReported);c.auth=true;c.UpdateGoal();assert(reports==2);
 gSaveContext.ship.stats.gameComplete=true;warp=false;c.UpdateGoal();assert(!warp&&reports==2);
 win={};gSaveContext.ship.stats.gameComplete=false;c.goalReported=false;options[RSK_WINCON].v=0;c.UpdateGoal();assert(!warp&&reports==2);
 options[RSK_WINCON].v=7;options[RSK_WINCON_TRIFORCE_COUNT].v=0;c.UpdateGoal();assert(!warp&&reports==2);
}
''')

table=fish[fish.index('std::array<std::pair<RandomizerCheck, RandomizerCheck>, 17>'):fish.index('\nstd::unordered_map<int8_t, RandomizerCheck>')]
checks=sorted(set(re.findall(r'\bRC_[A-Z0-9_]+',table)) - {'RC_UNKNOWN_CHECK'})
fish_impl='\n'.join(function(fish,x) for x in ['static CheckIdentity GetPondFish(', 'static CheckIdentity IdentifyPondFish(', 'static void UpdateCurrentPondFish('])
catch=fish[fish.index('    // Detect fish catch'):fish.index('    if (actor->id == ACTOR_EN_FISH',fish.index('    // Detect fish catch'))]
run('pond_checks',common+'\nenum RandomizerCheck {RC_UNKNOWN_CHECK=0,'+','.join(checks)+'};\n'+r'''
using s16=int16_t;using RandomizerInf=int;
enum {RAND_INF_MAX=99999,RO_FISHSANITY_POND=2,RO_FISHSANITY_BOTH=4,ACTOR_FISHING=10};
namespace Rando::StaticData {extern std::array<std::pair<RandomizerCheck,RandomizerCheck>,17>randomizerFishingPondFish;}
'''+table+r'''
struct CheckIdentity{int randomizerInf;RandomizerCheck randomizerCheck;};
struct PondOptions{int mode=2,numFish=17;bool ageSplit=true;}testOptions;
PondOptions GetOptions(){return testOptions;} bool adult=false,apSave=true,fishPresent=true;
#define LINK_IS_ADULT adult
bool IsAdultPond(){return adult&&testOptions.ageSplit;}
bool GetPondFishShuffled(){return (testOptions.mode==2||testOptions.mode==4)&&testOptions.numFish>0;}
std::set<int>activeChecks,flags;
bool Archipelago_IsCurrentSaveActive(){return apSave;}
bool Archipelago_ShouldHandleCheck(int rc){return activeChecks.contains(rc);}
bool Flags_GetRandomizerInf(int inf){return flags.contains(inf);}
void Flags_SetRandomizerInf(int inf){assert(inf!=RAND_INF_MAX);flags.insert(inf);}
struct RandoStub{int GetRandomizerInfFromCheck(int rc){return rc?1000+rc:RAND_INF_MAX;}}rando;
struct Globals{RandoStub*gRandomizer=&rando;};Globals globals;
struct OTRGlobals{static inline Globals*Instance=&globals;};
static const CheckIdentity defaultIdentity{RAND_INF_MAX,RC_UNKNOWN_CHECK};
CheckIdentity NextChildPondFish=defaultIdentity,NextAdultPondFish=defaultIdentity;
bool IsFish(CheckIdentity*f){return f->randomizerCheck!=RC_UNKNOWN_CHECK&&f->randomizerInf!=RAND_INF_MAX;}
'''+fish_impl+r'''
struct Actor{int id=ACTOR_FISHING;s16 params=100;};struct Fishing{Actor actor;int fishState=0;};
struct Play{int sceneNum=0;}testPlay;Play*gPlayState=&testPlay;
bool MegaSoul_ArePondFishPresent(){return fishPresent;}
std::unordered_set<Actor*>hoistedFish;
CheckIdentity IdentifyFish(int,int params){return IdentifyPondFish(params);}
void update(Fishing*fish){void*refActor=fish;Actor*actor=&fish->actor;
'''+catch+r'''
}
int main(){
 for(auto pair:Rando::StaticData::randomizerFishingPondFish){activeChecks.insert(pair.first);activeChecks.insert(pair.second);}
 // Invalid actor params and the missing second adult loach never index the table.
 for(bool age:{false,true}){adult=age;for(int param:{-32768,-1,0,99,117,255,32767})assert(IdentifyPondFish(param).randomizerCheck==RC_UNKNOWN_CHECK);}
 adult=true;assert(GetPondFish(116,true).randomizerInf==RAND_INF_MAX);
 activeChecks.clear();for(int i=0;i<15;++i){auto pair=Rando::StaticData::randomizerFishingPondFish[i];activeChecks.insert(pair.first);activeChecks.insert(pair.second);}
 std::set<int>caught;
 for(bool age:{false,true}){adult=age;for(int i=0;i<15;++i){Fishing f;f.actor.params=100+i;f.fishState=6;
  auto id=IdentifyPondFish(100+i);assert(id.randomizerCheck!=RC_UNKNOWN_CHECK);caught.insert(id.randomizerCheck);hoistedFish.clear();update(&f);update(&f);assert(flags.contains(id.randomizerInf));}
  assert(IdentifyPondFish(115).randomizerCheck==RC_UNKNOWN_CHECK);assert(IdentifyPondFish(116).randomizerCheck==RC_UNKNOWN_CHECK);}
 assert(caught.size()==30&&flags.size()==30);
 // Local count mode: a remote/unrelated item callback is not needed to advance,
 // and many hoist frames cannot consume the next sequential check.
 apSave=false;adult=false;testOptions.numFish=3;testOptions.ageSplit=false;flags.clear();hoistedFish.clear();UpdateCurrentPondFish();
 Fishing f;for(int i=0;i<3;++i){f.fishState=6;update(&f);for(int j=0;j<20;++j)update(&f);assert(flags.size()==i+1);f.fishState=0;update(&f);}
 adult=true;f.fishState=6;update(&f);assert(flags.size()==3);
}
''')

tracker=(ROOT/'soh/Enhancements/randomizer/randomizer_check_tracker.cpp').read_text()
run('enemy_finder_option',common+r'''
enum {RSK_SHUFFLE_ENEMY_DROPS=0,RCAREA_KOKIRI_FOREST=0,RCAREA_INVALID=10};
struct Option{bool enabled=false;bool Get(){return enabled;}}option;
#define RAND_GET_OPTION(x) option
bool apActive=true;std::set<int64_t>active{9700001,9700002,25};
bool Archipelago_IsCurrentSaveActive(){return apActive;}bool Archipelago_IsLocationActive(int64_t id){return active.contains(id);}
struct EnemyDefeatFinderEntry{int64_t locationId;int area;};
EnemyDefeatFinderEntry kEnemyDefeatFinderEntries[]={{9700001,0},{9700002,1}};
'''+function(tracker,'static bool IsEnemyDefeatVisible(')+function(tracker,'static bool IsFinderRowEnabled(')+r'''
int main(){for(bool enabled:{false,true}){option.enabled=enabled;for(auto&e:kEnemyDefeatFinderEntries){assert(IsEnemyDefeatVisible(e)==enabled);assert(IsFinderRowEnabled(e.locationId)==enabled);}assert(IsFinderRowEnabled(25));}
 apActive=false;assert(!IsEnemyDefeatVisible(kEnemyDefeatFinderEntries[0]));}
''')

gate=ap[ap.index('    if (gPlayState == nullptr)',ap.index('bool ArchipelagoClient::ProcessItem')):ap.index('    const bool historicalNewSaveReplay',ap.index('bool ArchipelagoClient::ProcessItem'))]
run('ap_receive_safety',common+r'''
enum {GAMEOVER_INACTIVE=0,TRANS_TRIGGER_OFF=0,PLAYER_STATE1_IN_ITEM_CS=1,PLAYER_STATE1_GETTING_ITEM=2,PLAYER_STATE1_CARRYING_ACTOR=4};
struct Player{int stateFlags1=0;}testPlayer;Player*testPlayerPtr=&testPlayer;
struct Play{struct{int state=0;}gameOverCtx;int transitionTrigger=0;}testPlay;Play*gPlayState=&testPlay;
struct{int health=48;}gSaveContext;bool paused=false,blocking=false;
#define GET_PLAYER(p) testPlayerPtr
bool Player_InBlockingCsMode(Play*,Player*){return blocking;}
namespace GameInteractor{bool IsGameplayPaused(){return paused;}}
bool canReceive(int64_t itemId=1){
'''+gate+r'''
return true;}
int main(){assert(canReceive());gPlayState=nullptr;assert(!canReceive());gPlayState=&testPlay;
 for(int bits=0;bits<256;++bits){gSaveContext.health=(bits&1)?0:48;testPlay.gameOverCtx.state=!!(bits&2);testPlay.transitionTrigger=!!(bits&4);
 paused=bits&8;blocking=bits&16;testPlayerPtr=(bits&32)?nullptr:&testPlayer;testPlayer.stateFlags1=(bits&64)?PLAYER_STATE1_GETTING_ITEM:0;
 if(bits&128)testPlayer.stateFlags1|=PLAYER_STATE1_CARRYING_ACTOR;assert(canReceive()==(bits==0));}
}
''')

apcpp=(args.apcpp_source/'Archipelago.cpp').read_text()
queue='\n'.join(function(apcpp,x) for x in ['static void AP_QueueMessage(', 'bool AP_IsMessagePending()', 'AP_Message* AP_GetLatestMessage()', 'void AP_ClearLatestMessage()'])
run('apcpp_message_queue',common+r'''
struct AP_Message{std::string text;};std::mutex messageQueueMutex;std::deque<AP_Message*>messageQueue;
'''+queue+r'''
int main(){assert(AP_GetLatestMessage()==nullptr);AP_ClearLatestMessage();
 constexpr int count=100000;std::thread producer([]{for(int i=0;i<count;++i)AP_QueueMessage(new AP_Message{std::to_string(i)});});
 for(int i=0;i<count;){if(!AP_IsMessagePending()){std::this_thread::yield();continue;}auto*m=AP_GetLatestMessage();assert(m&&m->text==std::to_string(i));AP_ClearLatestMessage();++i;}
 producer.join();assert(!AP_IsMessagePending());assert(AP_GetLatestMessage()==nullptr);}
''')

# Execute the actual slot-data statements for all AP fish modes and both goals.
tree=ast.parse((ROOT/'archipelago/soh_extreme/__init__.py').read_text())
fn=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='fill_slot_data')
selected=[]
for n in fn.body:
    code=ast.unparse(n)
    if (isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name) and n.value.func.id=='cv' and n.value.args and isinstance(n.value.args[0],ast.Constant) and str(n.value.args[0].value).startswith('Fishsanity')) or (isinstance(n,ast.Assign) and code.startswith('pond_fish =')) or (isinstance(n,ast.If) and code.startswith("if data['triforce_hunt']:")):
        selected.append(n)
compiled=compile(ast.Module(body=selected,type_ignores=[]),'<production slot settings>','exec')
for mode in range(4):
    for hunt in (False,True):
        settings={};exec(compiled,{'cv':lambda k,v:settings.__setitem__(k,v),'data':{'shuffle_fish':mode,'triforce_hunt':hunt,'triforce_hunt_pieces_required':25}})
        assert settings['Fishsanity']==(0,2,3,4)[mode]
        assert settings['FishsanityPondCount']==(17 if mode in (1,3) else 0)
        assert settings['FishsanityAgeSplit']==int(mode in (1,3))
        assert settings['ShuffleWincon']==(7 if hunt else 0)
        assert settings['WinconTriforceCount']==(25 if hunt else 0)
results.append({'name':'AP fish and goal slot settings: 8 combinations','passed':True})
print('PASS AP slot settings',flush=True)
# Exercise the APWorld's actual percentage calculation, including capped pools.
from types import SimpleNamespace as NS
pool_tree = ast.parse((ROOT/'archipelago/soh_extreme/_vendor_oot_soh/ItemPool.py').read_text())
create = next(n for n in pool_tree.body if isinstance(n, ast.FunctionDef) and n.name == 'create_triforce_pieces')
scope = {'get_open_location_count': lambda w: w.open_count,
         'Items': NS(TRIFORCE_PIECE='Triforce Piece'),
         'ItemClassification': NS(useful=1, skip_balancing=2)}
exec(compile(ast.Module(body=[create], type_ignores=[]), '<production percentage calculation>', 'exec'), scope)
for total in (1, 3, 20, 100, 200):
    for percentage in (1, 25, 50, 75, 100):
        for open_count in (7, 500):
            world = NS(open_count=open_count, using_ut=False,
                       options=NS(triforce_hunt_pieces_total=NS(value=total),
                                  triforce_hunt_pieces_required_percentage=NS(value=percentage)),
                       create_item=lambda item, **kwargs: item)
            world.add_items_to_item_pool_list = lambda items: setattr(world, 'items', items)
            scope['create_triforce_pieces'](world)
            actual_total = min(total, open_count)
            assert len(world.items) == actual_total
            assert world.triforce_pieces_required == max(1, round(actual_total * (percentage * .01)))
            assert world.options.triforce_hunt_pieces_total.value == actual_total
results.append({'name': 'AP Triforce percentage: 50 combinations', 'passed': True})
print('PASS AP Triforce percentage', flush=True)
# Complete progressive Open Chest receipt lifecycle is tested in test_ability_receipts.py.
(OUT/'results.json').write_text(json.dumps(results,indent=2))
sys.exit(0 if all(r['passed'] for r in results) else 1)
