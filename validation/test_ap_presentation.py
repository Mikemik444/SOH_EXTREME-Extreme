"""Compile production AP presentation/settings functions with controlled engine services."""
from pathlib import Path
import argparse, json, subprocess
from run_native_tests import function
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--include-dir',type=Path,required=True)
a=p.parse_args();r=Path(__file__).resolve().parent.parent;o=a.output.resolve();o.mkdir(parents=True,exist_ok=True)
ap=(r/'soh/Network/Archipelago/ArchipelagoClient.cpp').read_text(encoding='utf-8')
merchant=(r/'soh/Enhancements/randomizer/Messages/MerchantMessages.cpp').read_text(encoding='utf-8')
items=(r/'soh/Enhancements/randomizer/Messages/ItemMessages.cpp').read_text(encoding='utf-8')
code=r'''
#include <algorithm>
#include <atomic>
#include <cassert>
#include <cstdint>
#include <deque>
#include <map>
#include <mutex>
#include <limits>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>
#include <nlohmann/json.hpp>
#define SPDLOG_INFO(...) ((void)0)
#define SPDLOG_ERROR(...) ((void)0)
#define SPDLOG_DEBUG(...) ((void)0)
#define SPDLOG_WARN(...) ((void)0)
constexpr int RG_AP_NOTE_ZELDA=110,RG_AP_NOTE_PRELUDE=121;
constexpr int RG_AP_REMOTE_IMPORTANT=100,RG_AP_REMOTE_NORMAL=101,RG_ICE_TRAP=102,RG_OPEN_CHEST=103,RG_AP_SONG_NOTE=104;
constexpr int PLAYER_STATE1_IN_ITEM_CS=1,PLAYER_STATE1_GETTING_ITEM=2,PLAYER_STATE1_CARRYING_ACTOR=4,PLAYER_STATE1_IN_WATER=8;
constexpr int BGCHECKFLAG_GROUND=1,GAMEOVER_INACTIVE=0,TRANS_TRIGGER_OFF=0,ITEM_CUSTOM=999;
constexpr int OBJECT_INVALID=0,TEXTBOX_TYPE_BLUE=0,RSK_SHUFFLE_OPEN_CHEST=0,RO_OPEN_CHEST_PROGRESSIVE=1,RAND_INF_CAN_OPEN_CHEST=1;
constexpr int RO_FISHSANITY_POND=2,RO_FISHSANITY_BOTH=4;
constexpr int RSK_SHUFFLE_SILVER=1,RO_SHUFFLE_SILVER_WALLET=2;
using s8=int8_t;
int silverId=105,silverTotal=5; s8 silverCount=0; bool silverWallet=false;
struct Randomizer{
 static s8* SilverFieldFromSaveContext(void*,int item){return item==silverId?&silverCount:nullptr;}
 static int SilverTotal(int){return silverTotal;}
};
using RandomizerGet=int;using RandomizerCheck=int;
struct Entry{int getItemId=0,objectId=1;};
struct Player{int stateFlags1=0;struct{int bgCheckFlags=1;}actor;Entry getItemEntry;int getItemId=0;}player;
struct Play{struct{int state=0;}gameOverCtx;int transitionTrigger=0;}play;Play*gPlayState=&play;
struct {int health=48;} gSaveContext;
#define GET_PLAYER(x) (&::player)
bool busy=false,paused=false,giveAllowed=true;Entry gRemotePresentationEntry;
int gives=0;
bool Player_InBlockingCsMode(Play*,Player*){return busy;}
namespace GameInteractor{bool IsGameplayPaused(){return paused;}}
bool GiveItemEntryWithoutActor(Play*,Entry e){if(!giveAllowed)return false;++gives;player.getItemEntry=e;return true;}
struct Notice{std::string prefix,message,suffix;float remainingTime;};
std::vector<Notice> notices;namespace Notification{void Emit(Notice n){notices.push_back(n);}}
int AP_GetPlayerID(){return 1;}
std::vector<int64_t> sent;std::deque<int64_t> gDeferredLocationReports;
void AP_SendItem(int64_t id){sent.push_back(id);}
struct CustomMessage{
 std::string text;
 CustomMessage()=default;
 CustomMessage(std::string t):text(t){}
 CustomMessage(std::string t,int):text(t){}
 CustomMessage(std::string t,const char*,const char*,int=0):text(t){}
 void Replace(const std::string&key,const std::string&val){size_t pos;while((pos=text.find(key))!=std::string::npos)text.replace(pos,key.size(),val);}
 void Replace(const std::string&key,const CustomMessage&val){Replace(key,val.text);}
 void InsertNames(std::initializer_list<CustomMessage> names){int i=1;for(auto&n:names)Replace("[["+std::to_string(i++)+"]]",n.text);}
 void AutoFormat(int=0){}
 friend CustomMessage operator+(const CustomMessage&a,const CustomMessage&b){return CustomMessage(a.text+b.text);}
};
#define TODO_TRANSLATE ""
using Text=std::string;
struct Hint{CustomMessage GetHintMessage(){return CustomMessage("No Hint");}};
struct Item{
 Entry GetGIEntry_Copy(){return {RG_AP_REMOTE_IMPORTANT,1};}
 std::string GetColor(){return "%g";}std::string GetName(){return "Native Item";}std::string GetArticle(){return "a ";}
 bool HasCustomIcon(){return true;}Hint GetHint(){return {};}
};
bool isShop=false;struct Location{int rgid=RG_AP_REMOTE_IMPORTANT,price=45;int GetPlacedRandomizerGet(){return rgid;}int GetPrice(){return price;}bool IsShop(){return isShop;}}location;
constexpr int RHT_MYSTERIOUS_ITEM_CAPITAL=0;
namespace Rando{namespace StaticData{Item RetrieveItem(int){return {};}Hint hintTextTable[1];Location*GetLocation(int){return &location;}}}
struct Override{int LooksLike(){return 1;}std::string GetTrickName(){return "Ice disguise";}std::string GetTrickArticle(){return "a ";}}over;
#define RAND_GET_ITEM(rc) (&::location)
#define RAND_GET_OVERRIDE(rc) over
std::string remoteName="Hookshot for Friend",pickupName="Hookshot for Friend";int refreshes=0;
void Archipelago_RefreshPlacementForCheck(int){++refreshes;}
const char*Archipelago_GetRemoteItemDescription(int){return remoteName.c_str();}
const char*Archipelago_GetRemotePickupDescription(){return pickupName.c_str();}
const char*Archipelago_GetSongNotePickupDescription(){return "You found a Bolero of Fire note!&Notes: 3/8.";}
bool Flags_GetRandomizerInf(int){return false;}
struct Option{int k;bool Is(int){return k==RSK_SHUFFLE_SILVER&&silverWallet;}};
struct Context{Option GetOption(int k){return {k};}}context;
struct Globals{Context*gRandoContext=&context;};namespace OTRGlobals{Globals global;Globals*Instance=&global;}
bool ParseFlatStringIntObject(const std::string&s,std::unordered_map<std::string,int64_t>&o){try {o=nlohmann::json::parse(s).get<decltype(o)::element_type>();}catch(...){return false;}return true;}
class ArchipelagoClient {public:
 static ArchipelagoClient* active;static ArchipelagoClient&GetInstance(){return *active;}
 bool activeLocationsLoaded=true;std::unordered_set<int64_t>activeLocations,reportedLocations,pendingLocationReports;
 bool IsGameplaySessionActive(){return true;}bool IsAuthenticated(){return true;}
 int64_t ResolveApLocationForCheck(int32_t rc){return rc;}
 void ReportCheck(int32_t);void SendLocation(int64_t,bool=false);
 struct ScoutedLocation{int playerId=2,flags=1;std::string itemName="Hookshot",playerName="Friend";};
 std::unordered_map<int64_t,ScoutedLocation>scoutedLocations;
 std::deque<int64_t>remotePresentations;std::unordered_set<int64_t>presentedRemoteLocations;
 std::string remotePickupDescription;bool remotePresentationActive=false,remotePresentationReceived=false,awaitingMajorItemReceipt=false;
 unsigned remotePresentationFrames=0;
 void QueueRemotePresentation(int64_t);bool ProcessRemotePresentation();
 std::mutex queueMutex;std::deque<int>pendingItems;std::unordered_map<std::string,int>slotSettings;std::string cachedSlotSettingsJson;bool slotSettingsLoaded=false;
 std::atomic_bool slotSettingsPendingApply=false;void SetSlotSettingsFromJson(const std::string&);
};
ArchipelagoClient* ArchipelagoClient::active=nullptr;
'''
# Keep the fake JSON transport minimal; the production settings validation is still used.
code=code.replace('decltype(o)::element_type','std::unordered_map<std::string,int64_t>')
for sig in ('static std::string ApMessageName(', 'void ArchipelagoClient::QueueRemotePresentation(', 'bool ArchipelagoClient::ProcessRemotePresentation(', 'void ArchipelagoClient::SetSlotSettingsFromJson(', 'void ArchipelagoClient::ReportCheck(', 'void ArchipelagoClient::SendLocation(', 'extern "C" void Archipelago_ReportCheck(', 'extern "C" void Archipelago_ReportLocation(', 'extern "C" void Archipelago_ReconcileLocation('):code+='\n'+function(ap,sig)
code+='\n'+function(merchant,'void BuildMerchantMessage(')+'\n'+function(items,'void BuildCustomItemMessage(')
code+=r'''
int main(){
 ArchipelagoClient c;c.scoutedLocations[10]={};c.QueueRemotePresentation(10);c.QueueRemotePresentation(10);assert(c.remotePresentations.size()==1);
 player.stateFlags1=PLAYER_STATE1_IN_WATER;assert(!c.ProcessRemotePresentation()&&gives==0);
 player.stateFlags1=0;player.actor.bgCheckFlags=0;assert(!c.ProcessRemotePresentation());player.actor.bgCheckFlags=1;
 busy=true;assert(!c.ProcessRemotePresentation());busy=false;paused=true;assert(!c.ProcessRemotePresentation());paused=false;
 c.awaitingMajorItemReceipt=true;assert(!c.ProcessRemotePresentation());c.awaitingMajorItemReceipt=false;
 c.pendingItems.push_back(1);assert(!c.ProcessRemotePresentation()&&gives==0);c.pendingItems.clear();
 giveAllowed=false;assert(!c.ProcessRemotePresentation()&&c.remotePickupDescription.empty());giveAllowed=true;
 assert(c.ProcessRemotePresentation()&&gives==1&&c.remotePickupDescription=="Hookshot for Friend");
 assert(c.ProcessRemotePresentation()&&gives==1);c.remotePresentationReceived=true;busy=true;assert(c.ProcessRemotePresentation()&&!c.remotePickupDescription.empty());busy=false;
 assert(c.ProcessRemotePresentation()&&c.remotePresentations.empty()&&c.remotePickupDescription.empty());
 c.scoutedLocations[11]={1,1,"Bow","Me"};c.QueueRemotePresentation(11);assert(!c.ProcessRemotePresentation()&&gives==1);
 c.scoutedLocations[12]={2,0,"Rupee","Friend"};c.QueueRemotePresentation(12);assert(!c.ProcessRemotePresentation()&&gives==1&&notices.back().message=="found Rupee for");
 c.QueueRemotePresentation(13);assert(!c.ProcessRemotePresentation()&&c.remotePresentations.size()==1);c.scoutedLocations[13]={2,2,"Useful Item","Friend"};assert(c.ProcessRemotePresentation());
 c.remotePresentationReceived=true;assert(c.ProcessRemotePresentation());
 ArchipelagoClient::active=&c;c.activeLocations={9700123,9800520,9800521,9800522};
 // A rock uses ReportCheck; Jigsaw's real progression flags include bit 0.
 c.scoutedLocations[9700123]={2,1,"1 Puzzle Piece","Jig2"};
 Archipelago_ReportCheck(9700123);Archipelago_ReportCheck(9700123);
 assert(c.remotePresentations.size()==1&&gDeferredLocationReports.size()==1);
 assert(c.ProcessRemotePresentation()&&c.remotePickupDescription=="1 Puzzle Piece for Jig2");
 c.remotePresentationReceived=true;assert(c.ProcessRemotePresentation());
 // AP-only enemy pickups must queue exactly the same remote presentation.
 c.scoutedLocations[9800520]={2,1,"3 Puzzle Pieces","Jig2"};
 Archipelago_ReportLocation(9800520);Archipelago_ReportLocation(9800520);
 assert(sent.size()==1&&c.remotePresentations.size()==1);
 assert(c.ProcessRemotePresentation()&&c.remotePickupDescription=="3 Puzzle Pieces for Jig2");
 c.remotePresentationReceived=true;assert(c.ProcessRemotePresentation());
 // Journal/reconnect retry is silent. Same-slot rewards use the real receive.
 Archipelago_ReconcileLocation(9800521);assert(sent.size()==2&&c.remotePresentations.empty());
 c.scoutedLocations[9800522]={1,1,"Guay Soul","Me"};Archipelago_ReportLocation(9800522);
 int beforeGive=gives;assert(!c.ProcessRemotePresentation()&&gives==beforeGive&&c.remotePresentations.empty());
 for(int flags:{1,2,3,9,25}){ // advancement/useful and AP's progression subtypes
  int id=9900000+flags;c.activeLocations.insert(id);c.scoutedLocations[id]={2,flags,"Puzzle Piece","Jig2"};
  Archipelago_ReportLocation(id);assert(c.ProcessRemotePresentation());
  c.remotePresentationReceived=true;assert(c.ProcessRemotePresentation()&&c.remotePresentations.empty());
 }
 assert(ApMessageName("Bad%gName^&@#\x01").find('%')==std::string::npos);assert(ApMessageName(std::string(1000,'x')).size()==163);
 CustomMessage message("Selling [[color]][[1]] for [[2]]");BuildMerchantMessage(message,1,false);assert(message.text.find("Hookshot for Friend")!=std::string::npos&&message.text.find("45")!=std::string::npos&&message.text.find("No Hint")==std::string::npos&&refreshes==1);
 isShop=true;message=CustomMessage("[[1]]");BuildMerchantMessage(message,1,false);assert(message.text==remoteName);
 remoteName="";isShop=false;message=CustomMessage("[[1]]");BuildMerchantMessage(message,1,false);assert(message.text=="an Archipelago item");
 player.getItemEntry={RG_AP_REMOTE_IMPORTANT,1};BuildCustomItemMessage(&player,message);assert(message.text.find(pickupName)!=std::string::npos);
 player.getItemEntry={RG_AP_REMOTE_NORMAL,1};BuildCustomItemMessage(&player,message);assert(message.text.find(pickupName)!=std::string::npos);
 player.getItemEntry={RG_AP_SONG_NOTE,1};BuildCustomItemMessage(&player,message);assert(message.text.find("Bolero of Fire")!=std::string::npos&&message.text.find("3/8")!=std::string::npos);
 player.getItemEntry={silverId,1};
 for(int total:{3,5,6,10}){silverTotal=total;for(int count=0;count<=total+2;++count){silverCount=count;
  silverWallet=false;BuildCustomItemMessage(&player,message);assert(message.text.find(std::to_string(std::min(count+1,total))+"/"+std::to_string(total))!=std::string::npos);
  silverWallet=true;BuildCustomItemMessage(&player,message);assert(message.text.find(std::to_string(total)+"/"+std::to_string(total))!=std::string::npos);
 }}
 c.SetSlotSettingsFromJson(R"({"Fishsanity":4,"StartingDekuShield":1})");assert(c.slotSettingsLoaded&&c.slotSettingsPendingApply);
 assert(c.slotSettings.at("ShopShieldsTunicsGate")==0&&c.slotSettings.at("StartingDekuShield")==1&&c.slotSettings.at("StartingWallet")==0&&c.slotSettings.at("StartingBottle1")==0&&c.slotSettings.at("ShuffleMasks")==0);
 assert(c.slotSettings.at("MQDungeonsSelection")==0&&c.slotSettings.at("ShuffleInteriorsEntrances")==0&&c.slotSettings.at("FishsanityPondCount")==17);
 auto settings=c.slotSettings;c.SetSlotSettingsFromJson(R"({"StartingWallet":999999999999999})");assert(c.slotSettings==settings);
}
'''
src=o/'presentation.cpp';src.write_text(code,encoding='utf-8');exe=o/'presentation.exe'
run=subprocess.run(['cl','/nologo','/std:c++20','/Zc:preprocessor','/EHsc','/MD','/I',str(a.include_dir),'/I',str(r/'soh/Network/Archipelago'),str(src),'/Fo'+str(o/'presentation.obj'),'/Fe'+str(exe)],capture_output=True,text=True)
result=subprocess.run([str(exe)],capture_output=True,text=True) if run.returncode==0 else None
passed=run.returncode==0 and result.returncode==0
log=run.stdout+run.stderr+(result.stdout+result.stderr if result else '')
(o/'presentation.log').write_text(log);(o/'presentation.json').write_text(json.dumps({'passed':passed,'scope':'Production functions compiled with controlled engine services; no live game','cases':['remote major animation','rock ReportCheck to Jigsaw presentation','enemy ReportLocation to Jigsaw presentation','journal reconciliation silent','AP progression/useful flag subtypes','filler names','same-slot receipt ownership','deduplicated checks','missing scouts','water/air/cutscene/pause deferral','failed give retry','receipt lifecycle','message control-character handling','scrub/shop names and prices','important and normal pickup text','song note progress text','silver puzzle counts and pouches','old seed native defaults','explicit seed settings preserved','invalid settings rejected']},indent=2))
print('PASS presentation/settings' if passed else log[-6000:]);raise SystemExit(0 if passed else 1)
