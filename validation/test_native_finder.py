"""Compile actual native function bodies with controlled non-engine services.

Requires a source tree with the supplied include/ and libultraship headers.
No ROM, live server, UI renderer, full executable link or game playthrough.
"""
import argparse, subprocess, json, re, shutil
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path,required=True);p.add_argument('--overlay',type=Path);p.add_argument('--report',type=Path,required=True);p.add_argument('--compiler',default='clang++');p.add_argument('--helper-root',type=Path);a=p.parse_args()
root=a.source_root.resolve();overlay=a.overlay.resolve() if a.overlay else root
build=a.report.resolve().parent/('native-finder-'+('after' if a.overlay else 'before')+'-'+a.compiler.replace('+','p'));build.mkdir(parents=True,exist_ok=True)
def read(rel):
    q=overlay/rel
    return (q if q.exists() else root/rel).read_text()
def function(s,sig):
    start=s.index(sig);brace=s.index('{',start);depth=0;mode='code';i=brace
    while i<len(s):
        c=s[i];n=s[i:i+2]
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
            if depth==0:return s[start:i+1]
        i+=1
    raise ValueError(sig)
option=read('soh/Enhancements/randomizer/option.h');option=option[option.index('class OptionValue {'):option.index('/**\n * @brief A class describing')]
option_impl=read('soh/Enhancements/randomizer/option.cpp');option_impl=option_impl[option_impl.index('OptionValue::OptionValue('):option_impl.index('size_t Option::GetOptionCount')]
common=r'''
#include <algorithm>
#include <array>
#include <cassert>
#include <cstdio>
#include <cstring>
#include <functional>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>
#include "z64.h"
#include "macros.h"
#include "soh/Enhancements/randomizer/randomizerEnums.h"
namespace Rando {
'''+option+option_impl+r'''
class Context {
public:
    std::array<OptionValue, RSK_MAX> options{};
    std::array<OptionValue, RT_MAX> tricks{};
    static std::shared_ptr<Context> GetInstance() { static auto instance = std::make_shared<Context>(); return instance; }
    OptionValue& GetOption(RandomizerSettingKey key) { return options[key]; }
    OptionValue& GetTrickOption(RandomizerTrick key) { return tricks[key]; }
};
}
static int checks=0, failures=0;
static void check(bool value, const char* label) { ++checks; if(!value) { ++failures; if (failures<=8) std::printf("FAIL %s\n",label); } }
static int finish() { std::printf("checks=%d failures=%d\n", checks, failures); return failures ? 1 : 0; }
'''
results=[]
def run(name,source,extra_inc=()):
    path=build/(name+'.cpp');exe=build/name;path.write_text(source)
    includes=list(extra_inc)+[overlay]+([a.helper_root] if a.helper_root else [])+[root,root/'include',root/'src',root/'soh',root/'assets',root/'libultraship/include',root/'libultraship/include/ship/utils/binarytools']
    cmd=[shutil.which(a.compiler) or a.compiler,'-std=c++20','-fms-extensions','-O1']
    for d in includes:cmd+=['-I',str(d)]
    cmd += [str(path),'-o',str(exe)]
    c=subprocess.run(cmd,capture_output=True,text=True,timeout=45)
    r=subprocess.run([str(exe)],capture_output=True,text=True,timeout=30) if c.returncode==0 else None
    result={'name':name,'passed':c.returncode==0 and r.returncode==0,'compile_exit':c.returncode,'run_exit':r.returncode if r else None,'compile_command':cmd,'compile_stdout':c.stdout,'compile_stderr':c.stderr,'stdout':r.stdout if r else '', 'stderr':r.stderr if r else ''}
    results.append(result); print(name,'PASS' if result['passed'] else 'FAIL',result['stdout'],c.stderr[:4000],flush=True)
    (build/(name+'.log')).write_text(json.dumps(result,indent=2))

tracker=read('soh/Enhancements/randomizer/randomizer_check_tracker.cpp')
start=tracker.index('static SohExtreme::CheckFinderStateSnapshot lastFinderState') if 'static SohExtreme::CheckFinderStateSnapshot lastFinderState' in tracker else tracker.index('static int16_t lastFinderBombchuItem')
end=tracker.index('std::array<bool, RCAREA_INVALID> filterAreasHidden',start)
state_declarations=tracker[start:end]
refresh=common+r'''
#include "soh/Enhancements/randomizer/CheckFinderState.h"
SaveContext gSaveContext{};
static PlayState play{};
PlayState* gPlayState = &play;
static bool loaded=true, enabled=true;
#ifndef CVAR_PREFIX_TRACKER
#define CVAR_PREFIX_TRACKER "gTrackers"
#endif
uint8_t gItemSlots[256]{};
class GameInteractor { public: static bool IsSaveLoaded() {return loaded;} };
static int CVarGetInteger(const char*,int) {return enabled;}
static int requests=0;
static void RecalculateAvailableChecks(){++requests;}
'''+state_declarations+function(tracker,'void CheckTrackerLiveLogicStateUpdate() {')+r'''
static void refreshExpected(bool changed, const char* label) {
    int before=requests; CheckTrackerLiveLogicStateUpdate(); check((requests!=before)==changed,label);
    before=requests; CheckTrackerLiveLogicStateUpdate(); check(requests==before,"unchanged repeated sample");
}
int main(){
    gItemSlots[ITEM_BOMBCHU]=SLOT_BOMBCHU;gItemSlots[ITEM_BEAN]=SLOT_BEAN;
    gSaveContext.ship.quest.id=QUEST_RANDOMIZER;
    ResetLiveFinderStateSnapshot();refreshExpected(true,"initial live sample schedules");
    for (int i=0;i<5;++i) refreshExpected(false,"stable frame");
    const int abilityFlags[] = {RAND_INF_CAN_CLIMB,RAND_INF_CAN_GRAB,RAND_INF_CAN_SWIM};
    for(const int flag:abilityFlags){
        gSaveContext.ship.randomizerInf[flag>>4]^=uint16_t(1u<<(flag&15));refreshExpected(true,"grant ability without receive callback");
        gSaveContext.ship.randomizerInf[flag>>4]^=uint16_t(1u<<(flag&15));refreshExpected(true,"remove ability without receive callback");
    }
    // All flag words use the same typed comparison, including individual souls,
    // Flow of Time, shuffled songs, and collected AP/native checks.
    for(size_t i=0;i<sizeof(gSaveContext.ship.randomizerInf)/sizeof(gSaveContext.ship.randomizerInf[0]);++i){
        gSaveContext.ship.randomizerInf[i]^=uint16_t(0x8001u);refreshExpected(true,"rando flag word changed");
    }
    gSaveContext.inventory.items[SLOT_HOOKSHOT]=ITEM_LONGSHOT;refreshExpected(true,"equipment gained");
    gSaveContext.inventory.items[SLOT_HOOKSHOT]=ITEM_NONE;refreshExpected(true,"equipment lost");
    gSaveContext.inventory.upgrades ^= 1;refreshExpected(true,"progressive level changed");
    gSaveContext.inventory.equipment ^= 1;refreshExpected(true,"sword/shield changed");
    gSaveContext.inventory.questItems ^= 1;refreshExpected(true,"song/medallion changed");
    gSaveContext.inventory.dungeonKeys[3]++;refreshExpected(true,"spendable dungeon key changed");
    gSaveContext.ship.stats.dungeonKeys[3]++;refreshExpected(true,"total dungeon key changed");
    gSaveContext.inventory.dungeonItems[3] ^=1;refreshExpected(true,"dungeon boss key changed");
    gSaveContext.ship.quest.data.randomizer.silverGanonSpirit++;refreshExpected(true,"silver rupee room count changed");
    gSaveContext.ship.quest.data.randomizer.bombchuUpgradeLevel++;refreshExpected(true,"bombchu bag changed");
    gSaveContext.inventory.ammo[SLOT_BOMBCHU]++;refreshExpected(true,"bombchu refill");
    gSaveContext.inventory.ammo[SLOT_BOMBCHU]--;refreshExpected(true,"last bombchu consumed");
    gSaveContext.inventory.ammo[SLOT_BEAN]++;refreshExpected(true,"bean ammo changed");
    gSaveContext.healthCapacity+=FULL_HEART_HEALTH;refreshExpected(true,"heart capacity changed");
    gSaveContext.isMagicAcquired=1;refreshExpected(true,"magic acquired");
    gSaveContext.eventChkInf[0]^=1;refreshExpected(true,"quest event changed");
    gSaveContext.sceneFlags[SCENE_GERUDO_VALLEY].swch^=1;refreshExpected(true,"saved bean puzzle changed");
    play.actorCtx.flags.swch^=1;refreshExpected(true,"live room switch changed");
    play.actorCtx.flags.tempClear^=1;refreshExpected(true,"live room clear changed");
    gSaveContext.linkAge^=1;refreshExpected(true,"age changed");
    gSaveContext.nightFlag^=1;refreshExpected(true,"day/night changed");
    gSaveContext.dayTime++;gSaveContext.health++;gSaveContext.magic++;refreshExpected(false,"clock/health animation does not force searches");
    play.sceneNum++;refreshExpected(true,"scene changed");
    play.roomCtx.curRoom.num++;refreshExpected(true,"room changed");
    Rando::Context::GetInstance()->GetOption(RSK_SHUFFLE_CLIMB).Set(1);refreshExpected(true,"active seed option changed");
    enabled=false;refreshExpected(false,"disabled tracker dormant");
    enabled=true;refreshExpected(true,"reenabled tracker refreshes");
    loaded=false;refreshExpected(false,"unloaded safe");loaded=true;refreshExpected(true,"reload refreshes");
    gPlayState=nullptr;refreshExpected(false,"no play state safe");gPlayState=&play;refreshExpected(true,"restored play state refreshes");
    return finish();
}
'''
run('live_state_refresh',refresh)
loc_source=read('soh/Enhancements/randomizer/location_access.cpp')
cond=common+r'''
namespace Rando {
class LocationData { public: ActorID actor=ACTOR_EN_BOX; int params=5<<12; ActorID GetActorID() const{return actor;} int GetActorParams() const{return params;} };
namespace StaticData { static LocationData data; static const LocationData* GetLocation(RandomizerCheck){return &data;} }
}
struct TestLogic {
 bool IsChild=false,IsAdult=false,AtDay=false,AtNight=false;bool chest=true,large=true;
 bool HasItem(RandomizerGet) const{return chest;} bool CanOpenLargeChest() const{return large;}
};
static auto logic=std::make_shared<TestLogic>();
static unsigned baseMask=0,methodMask=0;
static unsigned ageTimeBit(){return (logic->IsChild?1u:logic->IsAdult?4u:0u) << (logic->AtNight?1:0);}
static bool MegaSoulAllowsLocation(RandomizerCheck){return (methodMask&ageTimeBit())!=0;}
struct Region {bool childDay=false,childNight=false,adultDay=false,adultNight=false;};
class LocationAccess {
public:
 RandomizerCheck location=RC_GV_WATERFALL_FREESTANDING_POH;
 bool GetConditionsMet() const{return (baseMask&ageTimeBit())!=0;}
 bool CheckConditionAtAgeTime(bool& age,bool& time) const;
 bool ConditionsMet(Region*,bool) const;
};
'''+function(loc_source,'bool LocationAccess::CheckConditionAtAgeTime(bool& age, bool& time) const {')+'\n'+function(loc_source,'bool LocationAccess::ConditionsMet(Region* parentRegion, bool calculatingAvailableChecks) const {')+r'''
int main(){
 LocationAccess loc;
 for (unsigned access=0;access<16;++access) for(baseMask=0;baseMask<16;++baseMask)
 for(methodMask=0;methodMask<16;++methodMask) for(unsigned stale=0;stale<4;++stale){
   Region region{bool(access&1),bool(access&2),bool(access&4),bool(access&8)};
   logic->IsChild=stale<2;logic->IsAdult=stale>=2;logic->AtDay=!(stale&1);logic->AtNight=stale&1;
   check(loc.ConditionsMet(&region,true)==bool(access&baseMask&methodMask),"base and interaction must share reachable age/time");
 }
 baseMask=methodMask=15;Region any{true,true,true,true};auto ctx=Rando::Context::GetInstance();
 ctx->GetOption(RSK_SHUFFLE_OPEN_CHEST).Set(RO_OPEN_CHEST_PROGRESSIVE);
 logic->chest=false;check(!loc.ConditionsMet(&any,true),"missing open chest stays blocked");
 logic->chest=true;logic->large=false;Rando::StaticData::data.params=0;check(!loc.ConditionsMet(&any,true),"large chest tier stays blocked");
 Rando::StaticData::data.params=5<<12;check(loc.ConditionsMet(&any,true),"small chest tier remains valid");
 return finish();
}
'''
run('shared_age_time_gates',cond)
scope=common+r'''
#include "soh/Enhancements/randomizer/CheckFinderState.h"
struct TestLogic {
 SaveContext* mSaveContext=nullptr;
 bool CalculatingAvailableChecks=false,IsChild=false,IsAdult=false,AtDay=false,AtNight=false;
 RandomizerRegion CurrentRegionKey=RR_GERUDO_VALLEY;RandomizerCheck CurrentCheckKey=RC_GV_WATERFALL_FREESTANDING_POH;
 void SetSaveContext(SaveContext* s){mSaveContext=s;}
};
int main(){
 SaveContext original{},live{},nestedSave{};
 for(int bits=0;bits<32;++bits){
  TestLogic logic{&original,bool(bits&1),bool(bits&2),bool(bits&4),bool(bits&8),bool(bits&16)};
  const TestLogic before=logic;
  try {
   SohExtreme::ScopedCheckFinderLogic<TestLogic,SaveContext> scope(logic,live);
   check(logic.mSaveContext==&live&&logic.CalculatingAvailableChecks,"enters live inventory mode");
   // These are the production search's entry/exit operations; keep the mode
   // until AP enemy and speech rows finish, not just until native search returns.
   bool previous=logic.CalculatingAvailableChecks;
   logic.CalculatingAvailableChecks=false;logic.CalculatingAvailableChecks=true;
   logic.CalculatingAvailableChecks=previous;
   check(logic.CalculatingAvailableChecks,"native search leaves synthetic checks live");
   {
    SohExtreme::ScopedCheckFinderLogic<TestLogic,SaveContext> nested(logic,nestedSave);
    logic.IsAdult=true;logic.IsChild=false;
   }
   check(logic.mSaveContext==&live&&logic.CalculatingAvailableChecks,"nested scope restores outer mode");
   logic.CurrentRegionKey=RR_NONE;logic.CurrentCheckKey=RC_UNKNOWN_CHECK;
   logic.IsChild=!before.IsChild;logic.IsAdult=!before.IsAdult;logic.AtDay=!before.AtDay;logic.AtNight=!before.AtNight;
   throw std::runtime_error("test unwind");
  }catch(const std::runtime_error&){}
  check(logic.mSaveContext==before.mSaveContext&&logic.CalculatingAvailableChecks==before.CalculatingAvailableChecks&&
        logic.IsChild==before.IsChild&&logic.IsAdult==before.IsAdult&&logic.AtDay==before.AtDay&&logic.AtNight==before.AtNight&&logic.CurrentRegionKey==before.CurrentRegionKey&&logic.CurrentCheckKey==before.CurrentCheckKey,"scope restores caller after exception");
 }
 SohExtreme::CheckFinderStateSnapshot snapshot;
 snapshot.BeginSample();snapshot.Observe(-1);snapshot.Observe(true);check(snapshot.EndSample(),"first snapshot");
 snapshot.BeginSample();snapshot.Observe(-1);snapshot.Observe(true);check(!snapshot.EndSample(),"identical signed snapshot");
 snapshot.BeginSample();snapshot.Observe(0);snapshot.Observe(true);check(snapshot.EndSample(),"changed snapshot");
 snapshot.BeginSample();snapshot.Observe(0);check(snapshot.EndSample(),"removed field changes");
 snapshot.Reset();snapshot.BeginSample();check(snapshot.EndSample(),"reset snapshot changes");
 return finish();
}
'''
run('live_logic_scope',scope)
report={'tests':results,'all_passed':all(t['passed'] for t in results),'compiler':a.compiler,'source_root':str(root),'overlay':str(overlay),'scope':'Production function bodies/OptionValue and real supplied z64 save/play/enum headers. Engine callbacks, UI, context container and category predicate are controlled test services. No complete Windows/game build.'}
a.report.write_text(json.dumps(report,indent=2));raise SystemExit(not report['all_passed'])
