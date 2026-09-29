"""Compile real NPC lookup, language, first-talk and send bodies with engine adapters."""
from pathlib import Path
from run_native_tests import function
import argparse,json,re,subprocess
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
r=Path(__file__).resolve().parents[1];out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
s=(r/'soh/Network/Archipelago/ArchipelagoClient.cpp').read_text(encoding='utf-8')
code=r'''
#include <cassert>
#include <set>
#include <map>
#include <string>
#include <vector>
#include <iostream>
#include "soh/Network/Archipelago/NpcSpeechIdentity.h"
#include "soh/Enhancements/randomizer/randomizerEnums.h"
static int notifications=0,refreshes=0,sends=0,presentations=0;
static bool enabled=true,adult=false;
static std::set<int> options,flags;
#define RAND_GET_OPTION(x) options.count(x)
#define CVAR_RANDOMIZER_SETTING(x) x
#define SPDLOG_INFO(...) ((void)0)
#define SPDLOG_WARN(...) ((void)0)
#define LINK_IS_ADULT adult
#define ACTOR_FLAG_TALK_OFFER_AUTO_ACCEPTED 1
int CVarGetInteger(const char*,int){return enabled;}
bool Flags_GetRandomizerInf(int flag){return flags.count(flag)!=0;}
void AP_SendItem(int64_t){++sends;}
namespace Notification { struct Message {std::string prefix,message,suffix;float remainingTime;};void Emit(Message){++notifications;} }
namespace CheckTracker {void RecalculateAvailableChecks(){++refreshes;}}
class ArchipelagoClient {
public:
 bool gameplay=true,activeLocationsLoaded=true,authenticated=true;
 std::set<int64_t> activeLocations,reportedLocations,pendingLocationReports;
 struct Scout {std::string locationName;};std::map<int64_t,Scout> scoutedLocations;
 static ArchipelagoClient& GetInstance(){static ArchipelagoClient v;return v;}
 bool IsGameplaySessionActive()const{return gameplay;}
 bool IsAuthenticated()const{return authenticated;}
 bool IsLocationActive(int64_t id)const{return activeLocationsLoaded&&activeLocations.count(id);}
 bool IsLocationSubmitted(int64_t id)const{return reportedLocations.count(id)||pendingLocationReports.count(id);}
 void QueueRemotePresentation(int64_t){++presentations;}
 void SendLocation(int64_t,bool);
 bool ReportNpcSpeechLocation(int64_t);
};
struct Vec {float x=0,y=0,z=0;};
struct Actor {Actor* next=nullptr;int id=0,params=0,room=0;int flags=0,naviEnemyId=255,textId=123;struct {Vec pos;} home;};
constexpr int ACTORCAT_MAX=12, MSGMODE_TEXT_START=1;
struct Play {int sceneNum=85; struct {int msgMode=0,textId=0; Actor* talkActor=nullptr;} msgCtx; struct {struct {Actor* head=nullptr;} actorLists[12];} actorCtx;} play;static Play* gPlayState=&play;
// Grotto resolution is separately checked against the production native map.
static int64_t Archipelago_ResolveScrubConversation(const Actor*,int){return -1;}
'''
code+=function(s,'static bool Archipelago_HasNpcLanguage(')+'\n'
code+=function(s,'bool ArchipelagoClient::ReportNpcSpeechLocation(')+'\n'
code+=function(s,'void ArchipelagoClient::SendLocation(')+'\n'
code+=function(s,'static int64_t Archipelago_ConversationForActor(')+'\n'
code+=function(s,'extern "C" bool Archipelago_HasPendingNpcConversation(')+'\n'
callback=function(s,'GameInteractor::Instance->RegisterGameHook<GameInteractor::OnDialogMessage>')
code+='void dialog()'+callback[callback.index('{'):]+'\n'
# Exercise the actual version-2 hook path, including automatic dialogues and
# explicit selected target. Legacy compatibility is covered by AP reconstruction.
start=s.index('        auto& client = ArchipelagoClient::GetInstance();',s.index('// First conversation with a real NPC'))
end=s.index('        // Compatibility with seeds generated before identity version 2.',start)
code+='void talk(Actor* actor,bool* should){\n'+s[start:end]+'}\n'
code+=r'''
int main(){int checks=0;
 auto& client=ArchipelagoClient::GetInstance();
 for(const auto& e:SohExtreme::kNpcSpeechIdentities){
  int scene=e.scene<0?0:e.scene,room=e.room<0?0:e.room;
  auto* actual=SohExtreme::ResolveNpcSpeechIdentity(e.actor,scene,e.params,room,e.age==1,e.home[0],e.home[1],e.home[2]);
  assert(actual&&actual->location==e.location);++checks;
  client.activeLocations.insert(e.location);
 }
 // Real Kokiri type codes, including FFxx spawn parameters and moved actors.
 std::set<int64_t> kokiri;
'''
actors={name:int(v,16) for v,name in re.findall(r'/\* (0x[0-9A-Fa-f]+) \*/.*?\b(ACTOR_\w+)',(r/'include/tables/actor_table.h').read_text())}
code+=f'constexpr int ko={actors["ACTOR_EN_KO"]}, ossan={actors["ACTOR_EN_OSSAN"]}, fishing={actors["ACTOR_FISHING"]};\n'
code+=r'''
 for(int type=0;type<13;++type){
  auto* e=SohExtreme::ResolveNpcSpeechIdentity(ko,85,0xFF00|type,0,false,0,0,0);
  assert(e&&e->language==4);kokiri.insert(e->location);++checks;
  auto* moved=SohExtreme::ResolveNpcSpeechIdentity(ko,43,0xFF00|type,0,true,0,0,0);
  assert(moved&&moved->location==e->location);++checks;
 }
 assert(kokiri.size()==13);++checks;
 auto* owner=SohExtreme::ResolveNpcSpeechIdentity(ossan,45,0,0,false,0,0,0);
 assert(owner&&owner->language==4&&!kokiri.count(owner->location));++checks;
 assert(!SohExtreme::ResolveNpcSpeechIdentity(fishing,73,100,0,false,0,0,0));++checks;
 assert(!SohExtreme::ResolveNpcSpeechIdentity(-999,85,0,0,false,0,0,0));++checks;
 // Correct language, not any language. Soul and setting gates stack.
 Actor actor;actor.id=ko;actor.params=0xFF01;
 options={RSK_SHUFFLE_SPEAK,RSK_SHUFFLE_NPC_SOUL};flags={RAND_INF_CAN_SPEAK_HYLIAN,RAND_INF_NPC_SOUL};
 bool normal=true;talk(&actor,&normal);assert(normal&&sends==0);++checks;
 flags={RAND_INF_CAN_SPEAK_KOKIRI};talk(&actor,&normal);assert(normal&&sends==0);++checks;
 flags.insert(RAND_INF_NPC_SOUL);enabled=false;talk(&actor,&normal);assert(normal&&sends==0);++checks;
 enabled=true;client.gameplay=false;talk(&actor,&normal);assert(normal&&sends==0);++checks;
 client.gameplay=true;talk(&actor,&normal);assert(!normal&&sends==1&&presentations==1);++checks;
 // No second check or presentation while pending; normal talk resumes immediately.
 for(int i=0;i<4;++i){normal=true;talk(&actor,&normal);assert(normal&&sends==1&&presentations==1);++checks;}
 // Server confirmation and reconnect retain identity, and later talk stays normal.
 client.reportedLocations=client.pendingLocationReports;client.pendingLocationReports.clear();
 normal=true;talk(&actor,&normal);assert(normal&&sends==1);++checks;
 // A different Kokiri is a distinct check. Offline checks enter the durable outbox.
 actor.params=0xFF02;client.authenticated=false;normal=true;talk(&actor,&normal);
 assert(!normal&&sends==1&&client.pendingLocationReports.size()==1);++checks;
 normal=true;talk(&actor,&normal);assert(normal&&sends==1&&presentations==2);++checks;
 // Automatic/forced dialogue continues its state machine while checking once.
 actor.params=0xFF03;actor.flags=ACTOR_FLAG_TALK_OFFER_AUTO_ACCEPTED;normal=true;talk(&actor,&normal);
 assert(normal&&presentations==3);++checks;
 talk(&actor,&normal);assert(normal&&presentations==3);++checks;
 // C-Up Navi information is not a conversation with the enemy being described.
 actor.params=0xFF04;actor.naviEnemyId=3;actor.textId=0x603;normal=true;talk(&actor,&normal);
 assert(normal&&presentations==3);++checks;
 actor.naviEnemyId=255;actor.textId=123;client.activeLocations.clear();talk(&actor,&normal);
 assert(normal&&presentations==3);++checks;
 // Existing/default-false hook decisions cannot be overwritten.
 client.activeLocations.insert(*kokiri.begin());normal=false;talk(&actor,&normal);assert(!normal);++checks;
 // Scripted first textbox reports once without changing dialogue state.
 client.activeLocations.clear();for(auto id:kokiri)client.activeLocations.insert(id);
 actor.params=0xFF06;actor.naviEnemyId=255;actor.flags=0;actor.next=nullptr;
 play.msgCtx.msgMode=MSGMODE_TEXT_START;play.msgCtx.talkActor=&actor;play.msgCtx.textId=0x1000;
 play.actorCtx.actorLists[0].head=&actor;
 assert(Archipelago_HasPendingNpcConversation(&actor));++checks;
 int before=presentations;dialog();assert(presentations==before+1);++checks;
 assert(!Archipelago_HasPendingNpcConversation(&actor));++checks;
 dialog();assert(presentations==before+1);++checks;
 // A stale message actor pointer is ignored without dereferencing it.
 play.msgCtx.talkActor=reinterpret_cast<Actor*>(1);dialog();assert(presentations==before+1);++checks;
 play.msgCtx.talkActor=nullptr;dialog();assert(presentations==before+1);++checks;
 std::cout<<"PASS "<<checks<<" compiled speech assertions\n";
}
'''
src=out/'npc_speech.cpp';exe=out/'npc_speech.exe';src.write_text(code,encoding='utf-8')
compile=subprocess.run(['cl','/nologo','/std:c++20','/Zc:preprocessor','/EHsc','/MD','/I',str(r),str(src),'/Fo'+str(out/'npc_speech.obj'),'/Fe'+str(exe)],capture_output=True,text=True)
run=subprocess.run([str(exe)],capture_output=True,text=True) if compile.returncode==0 else None
log=compile.stdout+compile.stderr+(run.stdout+run.stderr if run else '')
passed=compile.returncode==0 and run.returncode==0
# Actual call site must pass the resolved actor, not Player::talkActor (cleared for C-Up).
player=(r/'src/overlays/actors/ovl_player_actor/z_player.c').read_text(encoding='utf-8')
passed &= 'GameInteractor_Should(VB_SKIP_TALKING, true, talkOfferActor)' in player
(out/'native.json').write_text(json.dumps(dict(passed=passed,log=log,scope=__doc__),indent=2),encoding='utf-8')
print(log);raise SystemExit(0 if passed else 1)
