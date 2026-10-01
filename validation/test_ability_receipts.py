"""Compile the complete AP ProcessItem and receipt callback with controlled engine services.

Engine animation completion is driven explicitly. This exercises async/sync
callbacks, denied/interrupted gives, progressive receipts, and every song note.
It is not a rendered or connected game test.
"""
from pathlib import Path
import argparse, ast, json, re, subprocess
from run_native_tests import function
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args();r=Path(__file__).resolve().parent.parent;o=a.output.resolve();o.mkdir(parents=True,exist_ok=True)
ap=(r/'soh/Network/Archipelago/ArchipelagoClient.cpp').read_text(encoding='utf-8')
native=(r/'soh/Enhancements/randomizer/randomizer.cpp').read_text(encoding='utf-8')
logic=(r/'soh/Enhancements/randomizer/logic.cpp').read_text(encoding='utf-8')
body='\n'.join(function(ap,sig) for sig in ('static std::string BuildApSongNotePickupDescription(',
    'static bool ApplyExtremePersistentApItem(', 'void ArchipelagoClient::RefreshSongNotes(',
    'void ArchipelagoClient::FinalizeMajorItemReceipt(', 'bool ArchipelagoClient::ProcessItem(', 'void ArchipelagoClient::ReofferPendingPresentation('))
layout=ap[ap.index('struct SongNotes {'):ap.index('static std::string BuildApSongNotePickupDescription(')]
world_tree=ast.parse((r/'archipelago/soh_extreme/__init__.py').read_text(encoding='utf-8'))
note_layout=next(ast.literal_eval(n.value) for n in ast.walk(world_tree) if isinstance(n,ast.Assign)
    and any(isinstance(t,ast.Name) and t.id=='SONG_NOTE_LAYOUT' for t in n.targets))
assert list(note_layout)==[(name,int(count)) for name,count in re.findall(r'\{"([^"]+)", (\d+), QUEST_',layout)]
open_grant=function(native,'if (item == RG_OPEN_CHEST &&')
combined_speak=function(native,'if (item == RG_SPEAK_HYLIAN &&')
receipt_entry=function((r/'src/code/z_parameter.c').read_text(encoding='utf-8'),'u8 Return_Item_Entry(GetItemEntry itemEntry, u8 returnItem) {')
code=r'''
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <map>
#include <set>
#include <string>
#include <vector>
#include <iostream>
#define SPDLOG_INFO(...) ((void)0)
#define SPDLOG_DEBUG(...) ((void)0)
#define SPDLOG_WARN(...) ((void)0)
#define SPDLOG_ERROR(...) ((void)0)
using s16=int16_t;
'''
for enum,file in [('RandomizerGet','RandomizerGet.h'),('RandomizerInf','RandomizerInf.h')]:
 names=re.findall(r'^RANDO_ENUM_ITEM\((\w+)\)',(r/'soh/Enhancements/randomizer/randomizerEnums'/file).read_text(),re.M)
 code+='enum '+enum+' {'+','.join(names)+'};\n'
code+='\n'.join(re.findall(r'^constexpr (?:int64_t|uint32_t|int) AP_\w+\s*=.*?;',ap,re.M))+'\n'
options=sorted(set(re.findall(r'\b(?:RSK|RO)_\w+',body+layout+open_grant+combined_speak)))
code+='enum Options {'+','.join(options)+'};\n'
code+='enum Quests {'+','.join(sorted(set(re.findall(r'\bQUEST_SONG_\w+',layout))))+'};\n'
code+=r'''
using GetItemCategory=int;
constexpr int MOD_NONE=0,MOD_RANDOMIZER=1,ITEM_NONE=-1,ITEM_CATEGORY_MAJOR=1,ITEM_CATEGORY_SMALL_KEY=2,ITEM_CATEGORY_BOSS_KEY=3;
constexpr int PLAYER_STATE1_IN_ITEM_CS=1,PLAYER_STATE1_GETTING_ITEM=2,PLAYER_STATE1_CARRYING_ACTOR=4,PLAYER_STATE1_IN_WATER=8;
constexpr int BGCHECKFLAG_GROUND=1,GAMEOVER_INACTIVE=0,TRANS_TRIGGER_OFF=0,UPG_WALLET=0,QUEST_HEART_PIECE=24,FULL_HEART_HEALTH=16;
struct GetItemEntry {int itemId=0,modIndex=MOD_RANDOMIZER,getItemId=0;};
struct Actor{int bgCheckFlags=1;};
struct Player {int stateFlags1=0;Actor actor;int getItemId=0;GetItemEntry getItemEntry;Actor*interactRangeActor=nullptr;}player;
constexpr int GI_NONE=0;
struct Play {struct{int state=0;}gameOverCtx;int transitionTrigger=0;}play,*gPlayState=&play;
using PlayState=Play;
struct Save {int health=48,healthCapacity=48,healthAccumulator=0,rupees=0,rupeeAccumulator=0;struct{uint32_t questItems=0;}inventory;struct{int pendingIceTrapCount=0;}ship;}gSaveContext;
#define GET_PLAYER(x) (&::player)
bool blocked=false,paused=false,allowGive=true,syncGive=false,allowFlags=true;
bool Player_InBlockingCsMode(Play*,Player*){return blocked;}
namespace GameInteractor{bool IsGameplayPaused(){return paused;}}
std::set<int> flags;int grantCalls=0,giveCalls=0,vanillaGives=0,commits=0,tokenCount=0;
bool Flags_GetRandomizerInf(int f){return flags.count(f);}
void Flags_SetRandomizerInf(int f){if(allowFlags)flags.insert(f);}
bool HasNote(int first,int offset){return Flags_GetRandomizerInf(first+offset);}
void SetQuestSong(int q){gSaveContext.inventory.questItems|=1u<<q;}
uint64_t CaptureApPersistentGrantDigest(){uint64_t n=0;for(int f:flags)n+=f+1;return n;}
std::map<int,int>options;
struct Option{int k;int Get(){return options[k];}bool Is(int v){return Get()==v;}bool IsNot(int v){return !Is(v);}};
#define RAND_GET_OPTION(k) Option{k}
struct NativeRando{int GetRandoSettingValue(int k){return options[k];}}nativeRando;
struct Globals{NativeRando*gRandomizer=&nativeRando;};namespace OTRGlobals{Globals global;Globals*Instance=&global;}
int walletLevel=0;
#define CUR_UPG_VALUE(x) walletLevel
#define CUR_CAPACITY(x) (walletLevel==0?99:walletLevel==1?200:walletLevel==2?500:999)
void Inventory_ChangeUpgrade(int,int v){walletLevel=v;}
void Item_Give(Play*,uint8_t){++vanillaGives;}
struct Notice{std::string prefix,message,suffix;float remainingTime;};namespace Notification{void Emit(Notice){}}
uint64_t gNewSaveReplayTargetCount=0;uint32_t gAwaitingMajorFrames=0;
std::string GetApItemDisplayName(int64_t){return "item";}
namespace Rando{namespace StaticData{
std::map<RandomizerGet,int> RandoGetToRandInf={
'''
code+='\n'.join(re.findall(r'\{\s*RG_\w+,\s*RAND_INF_\w+\s*\},',logic))
code+=r'''
};
struct Item{RandomizerGet id;struct Name{std::string english="item";};Name GetName(){return {};}
GetItemEntry GetGIEntry_Copy(){return {id,MOD_RANDOMIZER,id};}
GetItemCategory GetCategory(){return ITEM_CATEGORY_MAJOR;}bool IsMajorItem(){return true;}};
Item RetrieveItem(RandomizerGet id){return {id};}
}}
class ArchipelagoClient {public:
bool active=true,remotePresentationActive=false,remotePresentationReceived=false;bool IsGameplaySessionActive()const{return active;}
void ReofferPendingPresentation();
bool awaitingMajorItemReceipt=false;uint64_t awaitingMajorSequence=0,appliedItemCount=0;
int64_t awaitingMajorApItemId=0;int awaitingMajorModIndex=0,awaitingMajorItemId=0,awaitingMajorGetItemId=0;
std::string songNotePickupDescription;
void MarkItemApplied(uint64_t s){++commits;appliedItemCount=s+1;}
void SendTrapLink(const char*){}
void RefreshSongNotes();void FinalizeMajorItemReceipt(int,int,int);
bool ProcessItem(int64_t,bool,uint64_t);
}client;
GetItemEntry scheduled,gAwaitingMajorEntry,gRemotePresentationEntry;std::map<int,int> silverCounts;
using u8=uint8_t;
void GameInteractor_ExecuteOnItemReceiveHooks(GetItemEntry e){client.FinalizeMajorItemReceipt(e.modIndex,e.itemId,e.getItemId);}
'''+receipt_entry+r'''
int Randomizer_Item_Give(Play*,GetItemEntry giEntry){
 ++grantCalls;RandomizerGet item=static_cast<RandomizerGet>(giEntry.getItemId);
'''+open_grant+combined_speak+r'''
 auto it=Rando::StaticData::RandoGetToRandInf.find(item);
 if(it!=Rando::StaticData::RandoGetToRandInf.end())Flags_SetRandomizerInf(it->second);
 if(item==RG_ADULT_WALLET)Inventory_ChangeUpgrade(UPG_WALLET,1);
 if(item==RG_GIANT_WALLET)Inventory_ChangeUpgrade(UPG_WALLET,2);
 if(item==RG_TYCOON_WALLET)Inventory_ChangeUpgrade(UPG_WALLET,3);
 if(item==RG_GOLD_SKULLTULA_TOKEN)++tokenCount;
 if(item>=RG_SHADOW_SILVER_BLADES&&item<=RG_GANONS_CASTLE_MQ_SILVER_SHADOW)++silverCounts[item];
 return Return_Item_Entry(giEntry,RG_NONE);
}
bool GiveItemEntryWithoutActor(Play* p,GetItemEntry e){
 if(!allowGive)return false;
 ++giveCalls;scheduled=e;
 player.getItemId=e.getItemId;player.getItemEntry=e;player.interactRangeActor=&player.actor;
 if(syncGive)Randomizer_Item_Give(p,e);
 return true;
}
'''+layout+body+r'''
int checks=0;
#define CK(x) do{++checks;if(!(x)){std::cerr<<"Failed line "<<__LINE__<<": "<<#x<<"\n";return 1;}}while(0)
void reset(){client={};flags.clear();silverCounts.clear();gSaveContext={};gPlayState=&play;play={};player={};walletLevel=0;blocked=paused=syncGive=false;allowGive=allowFlags=true;giveCalls=grantCalls=commits=vanillaGives=0;gNewSaveReplayTargetCount=0;options[RSK_SHUFFLE_OPEN_CHEST]=RO_OPEN_CHEST_PROGRESSIVE;options[RSK_SHUFFLE_GRAB]=1;options[RSK_SHUFFLE_SWIM]=1;}
int main(){
 reset();
 // A discarded offer is republished on each safe player update, with no grant.
 CK(client.ProcessItem(AP_FIRST_SONG_NOTE,true,0));
 for(int frame=0;frame<25;++frame){int before=giveCalls;player.getItemId=GI_NONE;
  client.ReofferPendingPresentation();CK(giveCalls==before+1&&commits==0&&flags.empty());
  CK(scheduled.getItemId==RG_AP_NOTE_ZELDA&&client.awaitingMajorItemReceipt);}
 // Player_Update clears only the interaction pointer after a missed offer.
 // The retained entry must be re-offered immediately, even before the timeout.
 for(int frame=0;frame<120;++frame){int before=giveCalls;
  player.interactRangeActor=nullptr;
  client.ReofferPendingPresentation();
  CK(giveCalls==before+1&&player.interactRangeActor==&player.actor);
  CK(commits==0&&flags.empty()&&client.awaitingMajorItemReceipt);
 }
 // A real actor's offer (including an identical item) must never be replaced.
 for(int mismatch=0;mismatch<5;++mismatch){int before=giveCalls;Actor other;
  player.getItemId=scheduled.getItemId;player.getItemEntry=scheduled;player.interactRangeActor=nullptr;
  if(mismatch==0)player.interactRangeActor=&other;
  if(mismatch==1)++player.getItemId;
  if(mismatch==2)++player.getItemEntry.modIndex;
  if(mismatch==3)++player.getItemEntry.itemId;
  if(mismatch==4)++player.getItemEntry.getItemId;
  client.ReofferPendingPresentation();CK(giveCalls==before&&commits==0);
 }
 player={};
 // Every independent safety gate still prevents an offer.
 for(int block=0;block<10;++block){int before=giveCalls;
  if(block==0)client.active=false;if(block==1)gSaveContext.health=0;
  if(block==2)play.gameOverCtx.state=1;if(block==3)play.transitionTrigger=1;
  if(block==4)paused=true;if(block==5)blocked=true;
  if(block==6)player.stateFlags1=PLAYER_STATE1_IN_ITEM_CS;
  if(block==7)player.stateFlags1=PLAYER_STATE1_IN_WATER;
  if(block==8)player.actor.bgCheckFlags=0;
  Actor other;if(block==9){player.getItemId=9;player.interactRangeActor=&other;}
  client.ReofferPendingPresentation();CK(giveCalls==before&&commits==0);
  client.active=true;gSaveContext.health=48;play={};paused=blocked=false;player={};
 }
 Randomizer_Item_Give(gPlayState,scheduled);CK(commits==1&&flags.size()==1);
 int done=giveCalls;client.ReofferPendingPresentation();CK(giveCalls==done);
 reset();client.remotePresentationActive=true;gRemotePresentationEntry={RG_AP_REMOTE_IMPORTANT,MOD_RANDOMIZER,RG_AP_REMOTE_IMPORTANT};
 client.ReofferPendingPresentation();CK(giveCalls==1&&commits==0&&scheduled.getItemId==RG_AP_REMOTE_IMPORTANT);
 player.interactRangeActor=nullptr;client.ReofferPendingPresentation();CK(giveCalls==2&&commits==0);
 client.remotePresentationReceived=true;client.ReofferPendingPresentation();CK(giveCalls==2);
 // A growing committed history does not introduce a timeout for later offers.
 reset();
 for(uint64_t sequence=0;sequence<4000;++sequence){
  CK(client.ProcessItem(AP_ITEM_OPEN_CHEST,true,sequence));
  int before=giveCalls;player.interactRangeActor=nullptr;
  client.ReofferPendingPresentation();CK(giveCalls==before+1&&commits==sequence);
  Randomizer_Item_Give(gPlayState,scheduled);
  CK(commits==sequence+1&&client.appliedItemCount==sequence+1&&!client.awaitingMajorItemReceipt);
  client.FinalizeMajorItemReceipt(scheduled.modIndex,scheduled.itemId,scheduled.getItemId);
  CK(commits==sequence+1);
 }
 reset();
 // Each physical Open Chest receipt advances exactly one tier, on completion.
 CK(client.ProcessItem(AP_ITEM_OPEN_CHEST,true,0));CK(giveCalls==1&&grantCalls==0&&client.awaitingMajorItemReceipt&&flags.empty());
 client.FinalizeMajorItemReceipt(MOD_RANDOMIZER,RG_ROLL,RG_ROLL);CK(commits==0);
 Randomizer_Item_Give(gPlayState,scheduled);CK(commits==1&&Flags_GetRandomizerInf(RAND_INF_CAN_OPEN_CHEST)&&!Flags_GetRandomizerInf(RAND_INF_CAN_OPEN_LARGE_CHEST));
 CK(client.ProcessItem(AP_ITEM_OPEN_CHEST,true,1));Randomizer_Item_Give(gPlayState,scheduled);CK(commits==2&&Flags_GetRandomizerInf(RAND_INF_CAN_OPEN_LARGE_CHEST));
 CK(client.ProcessItem(AP_ITEM_OPEN_CHEST,true,2));Randomizer_Item_Give(gPlayState,scheduled);CK(commits==3&&giveCalls==3);
 reset();syncGive=true;CK(client.ProcessItem(AP_ITEM_OPEN_CHEST,true,0));CK(commits==1&&!client.awaitingMajorItemReceipt&&!Flags_GetRandomizerInf(RAND_INF_CAN_OPEN_LARGE_CHEST));
 reset();options[RSK_SHUFFLE_SPEAK]=1;CK(client.ProcessItem(AP_ITEM_SPEAK,true,0));
 CK(commits==0&&flags.empty());Randomizer_Item_Give(gPlayState,scheduled);CK(commits==1&&flags.size()==6);
 for(bool tycoon:{false,true})for(bool full:{false,true})for(bool infinite:{false,true}){
  reset();options[RSK_INCLUDE_TYCOON_WALLET]=tycoon;options[RSK_FULL_WALLETS]=full;
  options[RSK_INFINITE_UPGRADES]=infinite?int(RO_INF_UPGRADES_OFF)+1:RO_INF_UPGRADES_OFF;
  for(int i=0;i<7;++i){gSaveContext.rupees=7;int before=walletLevel;
   CK(client.ProcessItem(AP_ITEM_PROGRESSIVE_WALLET,true,i));CK(walletLevel==before&&commits==i&&gSaveContext.rupees==7);
   Randomizer_Item_Give(gPlayState,scheduled);CK(commits==i+1&&giveCalls==i+1&&walletLevel==std::min(i,tycoon?3:2));
   CK(gSaveContext.rupees==(full?CUR_CAPACITY(UPG_WALLET):7));
  }
 }
 reset();options[RSK_SHUFFLE_OPEN_CHEST]=0;CK(client.ProcessItem(AP_ITEM_OPEN_CHEST,true,0));Randomizer_Item_Give(gPlayState,scheduled);CK(Flags_GetRandomizerInf(RAND_INF_CAN_OPEN_LARGE_CHEST));
 reset();allowGive=false;CK(!client.ProcessItem(AP_ITEM_OPEN_CHEST,true,0));CK(flags.empty()&&commits==0&&!client.awaitingMajorItemReceipt);
 allowGive=true;CK(client.ProcessItem(AP_ITEM_OPEN_CHEST,true,0));CK(flags.empty()); // interruption before engine grant
 client.awaitingMajorItemReceipt=false;CK(client.ProcessItem(AP_ITEM_OPEN_CHEST,true,0));Randomizer_Item_Give(gPlayState,scheduled);CK(!Flags_GetRandomizerInf(RAND_INF_CAN_OPEN_LARGE_CHEST)&&commits==1);
 const int64_t abilities[]={AP_ITEM_ROLL,AP_ITEM_GRAB,AP_ITEM_CLIMB,AP_ITEM_CRAWL,AP_ITEM_SPEAK,
 AP_ITEM_SPEAK_DEKU,AP_ITEM_SPEAK_GERUDO,AP_ITEM_SPEAK_GORON,AP_ITEM_SPEAK_HYLIAN,AP_ITEM_SPEAK_KOKIRI,AP_ITEM_SPEAK_ZORA,AP_ITEM_FLOW_OF_TIME,AP_ITEM_SHOVEL};
 for(auto id:abilities){reset();player.stateFlags1=PLAYER_STATE1_IN_WATER;CK(!client.ProcessItem(id,true,0)&&giveCalls==0&&flags.empty());
 player.stateFlags1=0;player.actor.bgCheckFlags=0;CK(!client.ProcessItem(id,true,0));player.actor.bgCheckFlags=1;
 CK(client.ProcessItem(id,true,0)&&giveCalls==1&&flags.empty()&&commits==0);
 CK(!client.ProcessItem(AP_ITEM_CLIMB,true,1)&&giveCalls==1); // offer cannot be overwritten by a receive burst
 Randomizer_Item_Give(gPlayState,scheduled);CK(vanillaGives==0&&commits==1&&!flags.empty());}
 reset();CK(client.ProcessItem(AP_ITEM_FLOW_OF_TIME,true,0));CK(scheduled.getItemId==RG_FLOW_OF_TIME&&!Flags_GetRandomizerInf(RAND_INF_FLOW_OF_TIME));Randomizer_Item_Give(gPlayState,scheduled);CK(gSaveContext.inventory.questItems==0&&Flags_GetRandomizerInf(RAND_INF_FLOW_OF_TIME));
 // Base progressive ability tiers (Grab/Swim) must also hold overhead.
 for(auto id : {
'''
itemmap=(r/'soh/Network/Archipelago/ArchipelagoItemMap.inc').read_text()
token_id=int(re.search(r'case (\d+)LL: randoGet = RG_GOLD_SKULLTULA_TOKEN;',itemmap)[1])
code=code.replace(' const int64_t abilities[]=',f''' reset();CK(client.ProcessItem({token_id},true,0)&&giveCalls==1&&tokenCount==0&&commits==0);
 Randomizer_Item_Give(gPlayState,scheduled);CK(commits==1&&tokenCount==1);
 const int64_t abilities[]=''',1)
ids=[int(re.search(r'case (\d+)LL: randoGet = '+rg+r';',itemmap)[1]) for rg in ('RG_PROGRESSIVE_STRENGTH','RG_PROGRESSIVE_SCALE','RG_FISHING_POLE','RG_ROCS_FEATHER','RG_OCARINA_A_BUTTON','RG_OCARINA_C_UP_BUTTON','RG_OCARINA_C_DOWN_BUTTON','RG_OCARINA_C_LEFT_BUTTON','RG_OCARINA_C_RIGHT_BUTTON')]
table=(r/'soh/Enhancements/randomizer/item_list.cpp').read_text(encoding='utf-8')
ability_entries=['RG_ROLL','RG_POWER_BRACELET','RG_BRONZE_SCALE','RG_CLIMB','RG_CRAWL','RG_OPEN_CHEST',
    'RG_SPEAK_DEKU','RG_SPEAK_GERUDO','RG_SPEAK_GORON','RG_SPEAK_HYLIAN','RG_SPEAK_KOKIRI','RG_SPEAK_ZORA',
    'RG_FLOW_OF_TIME','RG_AP_SONG_NOTE','RG_SHOVEL','RG_FISHING_POLE','RG_ROCS_FEATHER',
    'RG_OCARINA_A_BUTTON','RG_OCARINA_C_UP_BUTTON','RG_OCARINA_C_DOWN_BUTTON','RG_OCARINA_C_LEFT_BUTTON','RG_OCARINA_C_RIGHT_BUTTON']
for rg in ability_entries:
    entry=re.search(r'itemTable\['+rg+r'\]\s*=\s*Item\(.*?;',table,re.S)[0]
    assert 'CHEST_ANIM_LONG' in entry and 'ITEM_CATEGORY_MAJOR' in entry,rg
soul_entries=dict(re.findall(r'itemTable\[(RG_\w*SOUL\w*)\]\s*=\s*(Item\(.*?;)',table,re.S))
for rg,entry in soul_entries.items():
    assert 'CHEST_ANIM_LONG' in entry and 'ITEM_CATEGORY_MAJOR' in entry,rg
soul_cases=dict((rg,item) for item,rg in re.findall(r'case (\w+): randoGet = (RG_\w*SOUL\w*);',
    itemmap+function(ap,'bool ArchipelagoClient::ProcessItem(')))
assert set(soul_cases)==set(soul_entries),set(soul_entries)-set(soul_cases)
code+=','.join(str(i) for i in ids)+r'''}){reset();CK(client.ProcessItem(id,true,0)&&giveCalls==1);Randomizer_Item_Give(gPlayState,scheduled);CK(commits==1);}
 reset();int offset=0;
 for(const auto& song:kApSongNotes){for(int i=0;i<song.count;++i){const int64_t id=AP_FIRST_SONG_NOTE+offset+i;
 CK(client.ProcessItem(id,true,offset+i));CK(scheduled.getItemId==song.display&&client.awaitingMajorItemReceipt);
 CK(!Flags_GetRandomizerInf(RAND_INF_SONG_NOTE_0+offset+i));
 CK(client.songNotePickupDescription.find(song.name)!=std::string::npos);
 CK(client.songNotePickupDescription.find(std::to_string(i+1)+"/"+std::to_string(song.count))!=std::string::npos);
 Randomizer_Item_Give(gPlayState,scheduled);CK(Flags_GetRandomizerInf(RAND_INF_SONG_NOTE_0+offset+i));
 CK(((gSaveContext.inventory.questItems&(1u<<song.quest))!=0)==(i+1==song.count));
 }offset+=song.count;}CK(offset==74&&commits==74&&giveCalls==74&&vanillaGives==0);
 CK(client.ProcessItem(AP_FIRST_SONG_NOTE,true,74));CK(client.songNotePickupDescription.find("6/6")!=std::string::npos);Randomizer_Item_Give(gPlayState,scheduled);CK(flags.size()==74);
 reset();allowFlags=false;CK(client.ProcessItem(AP_FIRST_SONG_NOTE,true,0));Randomizer_Item_Give(gPlayState,scheduled);CK(commits==0&&client.awaitingMajorItemReceipt);
 allowFlags=true;Randomizer_Item_Give(gPlayState,scheduled);CK(commits==1&&Flags_GetRandomizerInf(RAND_INF_SONG_NOTE_0));
 reset();gNewSaveReplayTargetCount=100;CK(client.ProcessItem(AP_FIRST_SONG_NOTE,true,0));CK(giveCalls==0&&Flags_GetRandomizerInf(RAND_INF_SONG_NOTE_0));
 CK(client.ProcessItem(AP_ITEM_OPEN_CHEST,true,1));CK(giveCalls==0&&Flags_GetRandomizerInf(RAND_INF_CAN_OPEN_CHEST)&&!Flags_GetRandomizerInf(RAND_INF_CAN_OPEN_LARGE_CHEST));
 reset();for(int64_t id=AP_FIRST_SILVER_ITEM;id<=AP_LAST_SILVER_ITEM;++id){
 CK(client.ProcessItem(id,true,id-AP_FIRST_SILVER_ITEM));CK(client.awaitingMajorItemReceipt&&silverCounts[scheduled.getItemId]==0);
 Randomizer_Item_Give(gPlayState,scheduled);CK(silverCounts[scheduled.getItemId]==1);}
 CK(commits==AP_LAST_SILVER_ITEM-AP_FIRST_SILVER_ITEM+1);
 std::cout<<checks<<" assertions passed\n";
}
'''
tests=''
for rg,item in soul_cases.items():
    tests+=f'''reset();CK(client.ProcessItem({item},true,0)&&giveCalls==1);CK(scheduled.getItemId=={rg});
 CK(flags.empty()&&commits==0&&client.awaitingMajorItemReceipt);
 CK(!client.ProcessItem(AP_ITEM_ROLL,true,1)&&giveCalls==1&&scheduled.getItemId=={rg});
 Randomizer_Item_Give(gPlayState,scheduled);CK(Flags_GetRandomizerInf(Rando::StaticData::RandoGetToRandInf.at({rg})));
 CK(commits==1&&!client.awaitingMajorItemReceipt);
 CK(client.ProcessItem({item},true,1)&&giveCalls==2);Randomizer_Item_Give(gPlayState,scheduled);
 CK(commits==2);
'''
code=code.replace(' std::cout<<checks',tests+' std::cout<<checks')
flag_majors=[(int(i),rg) for i,rg in re.findall(r'case (\d+)LL: randoGet = (RG_\w+);',itemmap) if 29<=int(i)<=37 or 251<=int(i)<=274]
tests=''
for item,rg in flag_majors:
    tests+=f'''reset();allowGive=false;CK(!client.ProcessItem({item},true,0)&&flags.empty()&&commits==0);
 allowGive=true;CK(client.ProcessItem({item},true,0)&&flags.empty()&&commits==0);
 Randomizer_Item_Give(gPlayState,scheduled);CK(commits==1&&Flags_GetRandomizerInf(Rando::StaticData::RandoGetToRandInf.at({rg})));
 client.FinalizeMajorItemReceipt(scheduled.modIndex,scheduled.itemId,scheduled.getItemId);CK(commits==1);
'''
code=code.replace(' std::cout<<checks',tests+' std::cout<<checks')
src=o/'ability_receipts.cpp';src.write_text(code,encoding='utf-8');exe=o/'ability_receipts.exe'
c=subprocess.run(['cl','/nologo','/std:c++20','/Zc:preprocessor','/EHsc','/MD','/I',str(r/'soh/Network/Archipelago'),str(src),'/Fo'+str(o/'ability_receipts.obj'),'/Fe'+str(exe)],capture_output=True,text=True)
t=subprocess.run([str(exe)],capture_output=True,text=True) if not c.returncode else None
log=c.stdout+c.stderr+(t.stdout+t.stderr if t else '')
passed=c.returncode==0 and t.returncode==0
(o/'receipts.log').write_text(log)
(o/'receipts.json').write_text(json.dumps(dict(passed=passed,scope=__doc__,native_ability_entries=ability_entries,soul_entries=list(soul_cases),output=log),indent=2))
print(log);raise SystemExit(0 if passed else 1)
