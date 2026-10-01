"""Compile production NPC glow, identity, receipt and draw bodies.

Tests current character identities and old seed fallback behavior, local outbox
and server-confirmed checks, NPC Soul, save/scene guards and render bounds.
Engine/network/GPU services are controlled; this is not a live visual playtest.
"""
from pathlib import Path
from run_native_tests import function
import argparse, json, re, subprocess

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args(); r = Path(__file__).resolve().parents[1]; o = a.output.resolve(); o.mkdir(parents=True, exist_ok=True)
s = (r/'soh/Network/Archipelago/ArchipelagoClient.cpp').read_text(encoding='utf-8')
render = (r/'src/code/z_actor.c').read_text(encoding='utf-8')
manual = function(s, 'static bool Archipelago_IsManualSpeechActor(')
actors = {name:int(v,16) for v,name in re.findall(r'/\* (0x[0-9A-Fa-f]+) \*/.*?\b(ACTOR_\w+)',
    (r/'include/tables/actor_table.h').read_text())}
used_actors = sorted(set(re.findall(r'\bACTOR_(?!FLAG_)\w+', manual)))
ossan_names = sorted(set(re.findall(r'\bOSSAN_TYPE_\w+', manual)))
code = r'''
#include <cstdint>
#include <cmath>
#include <iostream>
#include <map>
#include <set>
#include <vector>
#include <string>
#include "soh/Network/Archipelago/NpcSpeechIdentity.h"
#include "soh/Enhancements/randomizer/randomizerEnums.h"
using s16=int16_t;using u8=uint8_t;using f32=float;
'''
code += 'enum Actors {'+','.join(f'{n}={actors[n]}' for n in used_actors)+'};\n'
code += 'enum ShopTypes {'+','.join(ossan_names)+'};\n'
code += r'''
constexpr int ACTORCAT_NPC=4;
constexpr int ACTOR_FLAG_TALK_OFFER_AUTO_ACCEPTED=1;
constexpr int64_t AP_EXTREME_SPEECH_BASE=9600000,AP_EXTREME_SPEECH_FALLBACK_BASE=9650000,AP_EXTREME_SPEECH_FALLBACK_COUNT=512;
bool speechEnabled=true;
std::set<int> options,flags;
#define RAND_GET_OPTION(x) options.count(x)
#define CVAR_RANDOMIZER_SETTING(x) x
#define SPDLOG_INFO(...) ((void)0)
#define SPDLOG_WARN(...) ((void)0)
int CVarGetInteger(const char*,int){return speechEnabled;}
bool Flags_GetRandomizerInf(int x){return flags.count(x);}
bool adult=false;
#define LINK_IS_ADULT adult
struct Vec3f{float x=0,y=0,z=0;};
void drawCallback(){}
struct Actor {int id=ACTOR_EN_KO,params=1,room=0,category=ACTORCAT_NPC,flags=0,textId=123;
 void(*init)()=nullptr;void(*draw)()=drawCallback;void(*update)()=drawCallback;
 struct{Vec3f pos;}home,world,focus;};
struct GraphicsContext{}gfx;
struct PlayState {int sceneNum=85;struct{GraphicsContext*gfxCtx=&gfx;}state;uint32_t gameplayFrames=0;int billboardMtxF=0;}play;
PlayState* gPlayState=&play;
int64_t scrubId=-1,legacyId=-1;
int64_t Archipelago_ResolveScrubConversation(const Actor*,int){return scrubId;}
int64_t Archipelago_ResolveNpcSpeechLocation(const Actor*,int){return legacyId;}
// Legacy actor-to-native-check lookup has separate mutable test inputs. The
// glow must only read its prebuilt RC map, never lazily scout/name-match.
struct Location {int rc=RC_UNKNOWN_CHECK;int GetRandomizerCheck(){return rc;}} native;
struct Randomizer {Location*GetCheckObjectFromActor(int,int,int){return &native;}} randomizer;
struct OTRGlobals {Randomizer*gRandomizer=&randomizer;static OTRGlobals*Instance;};
OTRGlobals globals;OTRGlobals*OTRGlobals::Instance=&globals;
int sends=0,presentations=0,notifications=0,refreshes=0;
void AP_SendItem(int64_t){++sends;}
namespace Notification {struct Message {std::string prefix,message,suffix;float remainingTime;};void Emit(Message){++notifications;}}
namespace CheckTracker {void RecalculateAvailableChecks(){++refreshes;}}
class ArchipelagoClient {public:
 bool gameplay=true,activeLocationsLoaded=true,authenticated=true;
 std::set<int64_t>activeLocations,reportedLocations,pendingLocationReports;
 std::set<uint64_t>fallbackNpcSpeechSeen;std::map<int,int64_t>rcToApLocation;
 struct Scout {std::string locationName;};std::map<int64_t,Scout>scoutedLocations;
 static ArchipelagoClient&GetInstance(){static ArchipelagoClient c;return c;}
 bool IsGameplaySessionActive()const{return gameplay;}
 bool IsAuthenticated()const{return authenticated;}
 bool IsLocationActive(int64_t id)const{return activeLocationsLoaded&&activeLocations.count(id);}
 bool IsLocationSubmitted(int64_t id)const{return reportedLocations.count(id)||pendingLocationReports.count(id);}
 void QueueRemotePresentation(int64_t){++presentations;}
 void SendLocation(int64_t,bool);
 bool ReportNpcSpeechLocation(int64_t);
 bool ShouldHighlightNpcSpeech(const Actor*)const;
};
'''
code += manual+'\n'
for sig in ('static uint64_t Archipelago_NpcSpeechIdentity(', 'static int64_t Archipelago_ConversationForActor(',
            'bool ArchipelagoClient::ShouldHighlightNpcSpeech(', 'extern "C" bool Archipelago_ShouldHighlightNpcSpeech(',
            'void ArchipelagoClient::SendLocation(', 'bool ArchipelagoClient::ReportNpcSpeechLocation('):
    code += function(s, sig)+'\n'
code += r'''
int stack=0,disps=0,halos=0,alpha=0,red=0,green=0,blue=0;float height=0,scale=0;
constexpr int MTXMODE_NEW=0,MTXMODE_APPLY=1;
#define M_PI 3.14159265358979323846
#define CLAMP(x,a,b) ((x)<(a)?(a):(x)>(b)?(b):(x))
#define OPEN_DISPS(...) (++disps)
#define CLOSE_DISPS(...) (--disps)
#define gDPPipeSync(...) ((void)0)
#define gDPSetPrimColor(dl,a,b,r,g,c,v) (red=r,green=g,blue=c,alpha=v)
#define gDPSetEnvColor(...) ((void)0)
#define gSPMatrix(...) ((void)0)
#define gSPDisplayList(...) (++halos)
float Math_SinS(s16 a){return std::sin(a*3.14159265358979323846/32768.0);}
void Matrix_Push(){++stack;}void Matrix_Pop(){--stack;}
void Matrix_Translate(float,float y,float,int){height=y;}
void Matrix_Mult(int*,int){}void Matrix_Scale(float x,float,float,int){scale=x;}
void Matrix_RotateZ(float,int){}void Gfx_SetupDL_25Xlu(GraphicsContext*){}
'''
code += function(render, 'static bool Actor_DrawNpcSpeechGlow(')+'\n'
code += r'''
int checks=0;
#define CK(x) do{++checks;if(!(x)){std::cerr<<"FAIL "<<__LINE__<<" "<<#x<<"\n";return 1;}}while(0)
void reset(){auto&c=ArchipelagoClient::GetInstance();c=ArchipelagoClient{};options.clear();flags.clear();speechEnabled=true;
 gPlayState=&play;play=PlayState{};adult=false;scrubId=legacyId=-1;native.rc=RC_UNKNOWN_CHECK;
 globals.gRandomizer=&randomizer;sends=presentations=notifications=refreshes=0;}
int main(){auto&c=ArchipelagoClient::GetInstance();size_t rows=0;
 for(const auto&e:SohExtreme::kNpcSpeechIdentities){++rows;
  for(int mask=0;mask<32;++mask){reset();Actor a;a.id=e.actor;a.params=e.params;a.room=e.room<0?0:e.room;
   a.home.pos={float(e.home[0]),float(e.home[1]),float(e.home[2])};play.sceneNum=e.scene<0?85:e.scene;adult=e.age==1;
   bool shuffle=mask&1,hasSoul=mask&2,pending=mask&4,confirmed=mask&8,active=mask&16;
   if(shuffle)options.insert(RSK_SHUFFLE_NPC_SOUL);if(hasSoul)flags.insert(RAND_INF_NPC_SOUL);
   if(active)c.activeLocations.insert(e.location);if(pending)c.pendingLocationReports.insert(e.location);
   if(confirmed)c.reportedLocations.insert(e.location);
   CK(Archipelago_ShouldHighlightNpcSpeech(&a)==(active&&!pending&&!confirmed&&(!shuffle||hasSoul)));
   CK(sends==0&&presentations==0&&notifications==0&&c.fallbackNpcSpeechSeen.empty());
  }
 }
 // Independent Kokiri characters and the same person in a different scene/age.
 reset();Actor a;auto id=Archipelago_ConversationForActor(&a);CK(id>=0);c.activeLocations.insert(id);
 CK(Archipelago_ShouldHighlightNpcSpeech(&a));Actor other=a;other.params=2;
 auto otherId=Archipelago_ConversationForActor(&other);CK(otherId!=id);c.activeLocations.insert(otherId);
 c.authenticated=false;CK(c.ReportNpcSpeechLocation(id));CK(sends==0&&presentations==1);
 CK(!Archipelago_ShouldHighlightNpcSpeech(&a));CK(Archipelago_ShouldHighlightNpcSpeech(&other));
 CK(!c.ReportNpcSpeechLocation(id));CK(presentations==1); // first talk only
 play.sceneNum=43;adult=true;a.world.pos={90,80,70};CK(!Archipelago_ShouldHighlightNpcSpeech(&a));
 auto pending=c.pendingLocationReports;c.pendingLocationReports.clear();c.pendingLocationReports=pending;
 CK(!Archipelago_ShouldHighlightNpcSpeech(&a)); // saved outbox reload
 c.pendingLocationReports.clear();c.reportedLocations.insert(id);c.authenticated=true;
 CK(!Archipelago_ShouldHighlightNpcSpeech(&a)); // reconnect/server confirmation
 c.reportedLocations.clear();CK(Archipelago_ShouldHighlightNpcSpeech(&a)); // different save, no cache
 // Lifecycle/setting guards, including a still-visible actor with missing Soul.
 for(int bits=0;bits<64;++bits){reset();Actor n;
  c.activeLocations.insert(Archipelago_ConversationForActor(&n));
  if(bits&1)c.gameplay=false;if(bits&2)speechEnabled=false;if(bits&4)c.activeLocationsLoaded=false;
  if(bits&8)n.draw=nullptr;if(bits&16)n.update=nullptr;if(bits&32)n.init=drawCallback;
  CK(Archipelago_ShouldHighlightNpcSpeech(&n)==(bits==0));
 }
 reset();Actor n;c.activeLocations.insert(Archipelago_ConversationForActor(&n));
 options.insert(RSK_SHUFFLE_NPC_SOUL);flags.insert(RAND_INF_CAN_SPEAK_KOKIRI);
 CK(!Archipelago_ShouldHighlightNpcSpeech(&n));flags.insert(RAND_INF_NPC_SOUL);
 CK(Archipelago_ShouldHighlightNpcSpeech(&n));flags.erase(RAND_INF_NPC_SOUL);
 CK(!Archipelago_ShouldHighlightNpcSpeech(&n));options.clear();
 CK(Archipelago_ShouldHighlightNpcSpeech(&n)); // soul shuffle disabled
 CK(!Archipelago_ShouldHighlightNpcSpeech(nullptr));gPlayState=nullptr;
 CK(!Archipelago_ShouldHighlightNpcSpeech(&n));gPlayState=&play;
 // Known grotto scrub uses the same resolved conversation ID as receipt handling.
 reset();n.id=ACTOR_EN_DNS;scrubId=10000101;c.activeLocations.insert(scrubId);
 CK(Archipelago_ShouldHighlightNpcSpeech(&n));c.pendingLocationReports.insert(scrubId);
 CK(!Archipelago_ShouldHighlightNpcSpeech(&n));scrubId=10000102;c.activeLocations.insert(scrubId);
 CK(Archipelago_ShouldHighlightNpcSpeech(&n));
 // Legacy generic bank: repeated rendering never consumes a slot or changes identity.
 reset();n.id=ACTOR_EN_KO;n.params=1;c.activeLocations.insert(AP_EXTREME_SPEECH_FALLBACK_BASE);
 auto hash=Archipelago_NpcSpeechIdentity(&n,play.sceneNum);
 for(int i=0;i<1000;++i){CK(Archipelago_ShouldHighlightNpcSpeech(&n));CK(c.fallbackNpcSpeechSeen.empty()&&c.pendingLocationReports.empty()&&sends==0);}
 c.fallbackNpcSpeechSeen.insert(hash);CK(!Archipelago_ShouldHighlightNpcSpeech(&n));
 n.world.pos={100,200,300};CK(!Archipelago_ShouldHighlightNpcSpeech(&n));
 c.fallbackNpcSpeechSeen.clear();c.pendingLocationReports.insert(AP_EXTREME_SPEECH_FALLBACK_BASE);
 CK(!Archipelago_ShouldHighlightNpcSpeech(&n)); // exhausted bank
 c.activeLocations.insert(AP_EXTREME_SPEECH_FALLBACK_BASE+1);CK(Archipelago_ShouldHighlightNpcSpeech(&n));
 legacyId=AP_EXTREME_SPEECH_BASE+11;c.activeLocations.insert(legacyId);CK(Archipelago_ShouldHighlightNpcSpeech(&n));
 c.reportedLocations.insert(legacyId);CK(!Archipelago_ShouldHighlightNpcSpeech(&n));
 // Native reward mapping is preferred before old ambiguous scene/actor fallback.
 native.rc=123;c.rcToApLocation[123]=12;c.activeLocations.insert(AP_EXTREME_SPEECH_BASE+12);
 CK(Archipelago_ShouldHighlightNpcSpeech(&n));c.pendingLocationReports.insert(AP_EXTREME_SPEECH_BASE+12);
 CK(!Archipelago_ShouldHighlightNpcSpeech(&n));
 // A checked modern character never borrows an old fallback-bank check.
 reset();n=Actor{};id=Archipelago_ConversationForActor(&n);c.activeLocations={id,AP_EXTREME_SPEECH_FALLBACK_BASE};
 c.reportedLocations.insert(id);CK(!Archipelago_ShouldHighlightNpcSpeech(&n));
 // Rendering stays in the existing live draw pass and leaves actor callbacks intact.
 reset();n=Actor{};c.activeLocations.insert(Archipelago_ConversationForActor(&n));
 int before=halos;CK(!Actor_DrawNpcSpeechGlow(nullptr,&n));CK(halos==before);
 play.state.gfxCtx=nullptr;CK(!Actor_DrawNpcSpeechGlow(&play,&n));CK(halos==before);play.state.gfxCtx=&gfx;
 for(int frame=0;frame<512;++frame){play.gameplayFrames=frame;n.focus.pos.y=frame-100;before=halos;
  CK(Actor_DrawNpcSpeechGlow(&play,&n));CK(halos==before+1&&stack==0&&disps==0);
  CK(height>=20&&height<=85&&scale>=0.0339f&&scale<=0.0461f&&alpha>=75&&alpha<=135);
  CK(red==130&&green==245&&blue==255&&n.draw==drawCallback&&n.update==drawCallback);
 }
 options.insert(RSK_SHUFFLE_NPC_SOUL);before=halos;CK(!Actor_DrawNpcSpeechGlow(&play,&n));CK(halos==before);
 flags.insert(RAND_INF_NPC_SOUL);CK(Actor_DrawNpcSpeechGlow(&play,&n));
 c.ReportNpcSpeechLocation(Archipelago_ConversationForActor(&n));before=halos;
 CK(!Actor_DrawNpcSpeechGlow(&play,&n));CK(halos==before&&stack==0&&disps==0);
 std::cout<<checks<<" NPC speech glow assertions passed across "<<rows<<" identity rows\n";
}
'''
src = o/'npc_glow.cpp'; exe = o/'npc_glow.exe'; src.write_text(code, encoding='utf-8')
c = subprocess.run(['cl','/nologo','/std:c++20','/Zc:preprocessor','/EHsc','/MD','/I'+str(r),
                    str(src),'/Fo'+str(o/'npc_glow.obj'),'/Fe'+str(exe)], capture_output=True, text=True)
t = subprocess.run([str(exe)], capture_output=True, text=True) if c.returncode == 0 else None
draw_actor = function(render, 'void Actor_Draw(PlayState* play, Actor* actor) {')
callsite = ('if (!Actor_DrawNpcSpeechGlow(play, actor))' in draw_actor and
            draw_actor.index('Actor_DrawNpcSpeechGlow(play, actor)') > draw_actor.index('actor->shape.shadowDraw(actor, lights, play)'))
log = c.stdout+c.stderr+(t.stdout+t.stderr if t else '')
passed = c.returncode == 0 and t.returncode == 0 and callsite
result = re.search(r'(\d+) NPC speech glow assertions passed across (\d+) identity rows', log)
report = dict(passed=passed, assertions=int(result[1]) if result else 0,
              identity_rows=int(result[2]) if result else 0, callsite=callsite, output=log, scope=__doc__)
(o/'glow.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(log); raise SystemExit(not passed)
