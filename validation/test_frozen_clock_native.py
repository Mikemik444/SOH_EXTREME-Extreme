"""Compile the real passive clock freeze, Sun's Song transition and region resets.

Game state and region storage are test adapters. No connected gameplay is simulated.
"""
import argparse,json,re,subprocess
from pathlib import Path
from run_native_tests import function

p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
r=Path(__file__).resolve().parents[1];out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
client=(r/'soh/Network/Archipelago/ArchipelagoClient.cpp').read_text(encoding='utf-8')
environment=(r/'src/code/z_kankyo.c').read_text(encoding='utf-8')
regions=(r/'soh/Enhancements/randomizer/location_access.cpp').read_text(encoding='utf-8')
freeze=function(client,'extern "C" bool Archipelago_ShouldFreezeTime(void)')
initialize=function(client,'if (CVarGetInteger(CVAR_RANDOMIZER_SETTING("ShuffleFlowOfTime"), 0))')
tick=function(environment,'if (!Archipelago_ShouldFreezeTime() ||')
parameter=(r/'src/code/z_parameter.c').read_text(encoding='utf-8')
song=function(parameter,'if (play->envCtx.timeIncrement != 0)')
assert 'Keep Flow of Time frozen' not in client
classify=function(environment,'if (((void)0, gSaveContext.dayTime) > 0xC000')
# The extraction helper returns one brace-delimited body; retain the real else
# branch as well so a previous nightFlag cannot contaminate a daytime case.
tail=environment[environment.index(classify)+len(classify):]
assert tail.lstrip().startswith('else')
classify+=' '+function(tail,'else')
code=r'''
#include <cassert>
#include <cstdint>
#include <iostream>
#include <array>
#include <vector>
#include <string>
using u16=uint16_t;
enum {SUNSSONG_INACTIVE,SUNSSONG_START,SUNSSONG_SPEED_TIME,OCARINA_MODE_04,GAMEMODE_NORMAL,GAMEMODE_END_CREDITS};
struct Save {u16 dayTime=0,skyboxTime=0;int nightFlag=0,sunsSongState=SUNSSONG_INACTIVE,gameMode=GAMEMODE_NORMAL;} gSaveContext;
bool hasFlow=false,shuffle=true,apSave=true;int preset=1,age=0;
bool Archipelago_IsCurrentSaveFile(){return apSave;}
struct Play {struct {int timeIncrement=1;} envCtx;struct {int ocarinaMode=0;} msgCtx;} game;
Play* play=&game;
u16 gTimeSpeed=10,sPrevTimeSpeed=10;int D_80125B60=0;
#define IS_DAY (gSaveContext.dayTime>=0x4555&&gSaveContext.dayTime<=0xC000)
#define CVAR_RANDOMIZER_SETTING(x) x
bool Flags_GetRandomizerInf(int){return hasFlow;}
constexpr int RAND_INF_FLOW_OF_TIME=1;
int CVarGetInteger(const char* key,int fallback){return std::string(key)=="FrozenStartingTime"?preset:shuffle;}
'''+freeze+'\nvoid InitializeClock(){\n'+initialize+'\n}\nvoid Tick(){\n'+tick+'\n}\nvoid SunSong(){\n'+song+'\n}\nvoid ClassifyClock(){\n'+classify+r'''
}
enum RandomizerRegion {RR_ROOT,RR_OTHER};
using RandomizerCheck=int;
struct LocationAccess {RandomizerCheck GetLocation(){return 0;}};
struct Region {
 bool childDay=false,childNight=false,adultDay=false,adultNight=false;
 std::vector<LocationAccess> locations{{}};
 void ResetVariables(){childDay=childNight=adultDay=adultNight=false;}
} table[2];
Region* RegionTable(RandomizerRegion region){return &table[region];}
std::array<RandomizerRegion,2> GetAllRegions(){return {RR_ROOT,RR_OTHER};}
enum {RSK_SHUFFLE_FLOW_OF_TIME,RSK_FROZEN_STARTING_TIME,RSK_SELECTED_STARTING_AGE,RO_AGE_CHILD=0};
struct Value {int value;operator bool()const{return value!=0;}int Get()const{return value;}bool Is(int n)const{return value==n;}};
struct ItemLocation {void ResetVariables(){}};
namespace Rando {struct Context {
 static Context* GetInstance(){static Context c;return &c;}
 Value GetOption(int key){return {key==RSK_SHUFFLE_FLOW_OF_TIME?int(shuffle):key==RSK_FROZEN_STARTING_TIME?preset:age};}
 ItemLocation* GetItemLocation(int){static ItemLocation l;return &l;}
};}
'''+function(regions,'void AccessReset()')+'\n'+function(regions,'void ResetAllLocations()')+r'''
int tests=0;void ck(bool result){++tests;assert(result);}
int main(){
 const u16 clocks[]={0x4555,0x8000,0xB555,0x0000};
 for(preset=1;preset<=4;++preset){
  shuffle=true;hasFlow=false;InitializeClock();ClassifyClock();
  ck(gSaveContext.dayTime==clocks[preset-1]);ck(gSaveContext.skyboxTime==gSaveContext.dayTime);
  ck(bool(gSaveContext.nightFlag)==(preset==4));
  for(age=0;age<2;++age){
   for(auto reset:{AccessReset,ResetAllLocations}){
    table[RR_ROOT].childDay=table[RR_ROOT].childNight=table[RR_ROOT].adultDay=table[RR_ROOT].adultNight=true;
    table[RR_OTHER].childDay=table[RR_OTHER].childNight=table[RR_OTHER].adultDay=table[RR_OTHER].adultNight=true;
    reset();bool night=gSaveContext.nightFlag!=0;
    ck(table[RR_ROOT].childDay==(age==0&&!night));ck(table[RR_ROOT].childNight==(age==0&&night));
    ck(table[RR_ROOT].adultDay==(age==1&&!night));ck(table[RR_ROOT].adultNight==(age==1&&night));
    ck(!table[RR_OTHER].childDay&&!table[RR_OTHER].childNight&&!table[RR_OTHER].adultDay&&!table[RR_OTHER].adultNight);
   }
  }
  for(int frame=0;frame<300;++frame)Tick();ck(gSaveContext.dayTime==clocks[preset-1]);
  // Execute the actual accelerated Sun's Song state machine twice: both
  // night -> day and day -> night, refreezing after each successful change.
  for(int use=0;use<2;++use){
   ClassifyClock();bool wasNight=gSaveContext.nightFlag;
   gSaveContext.sunsSongState=SUNSSONG_START;int frames=0;
   do {SunSong();Tick();++frames;} while(gSaveContext.sunsSongState!=SUNSSONG_INACTIVE&&frames<400);
   ClassifyClock();ck(frames<400);ck(bool(gSaveContext.nightFlag)!=wasNight);
   u16 frozen=gSaveContext.dayTime;for(int frame=0;frame<300;++frame)Tick();
   ck(gSaveContext.dayTime==frozen);ck(gTimeSpeed==10);
  }
  // Scene-reload song changes and loaded save time are explicit writes; the
  // passive tick must preserve them instead of resetting to the seed preset.
  for(auto target:{0,0x8001,0xBEEF}){
   gSaveContext.dayTime=target;for(int frame=0;frame<30;++frame)Tick();ck(gSaveContext.dayTime==target);
  }
  hasFlow=true;gSaveContext.dayTime=0x8000;Tick();ck(gSaveContext.dayTime==0x800A);
  hasFlow=false;shuffle=false;gSaveContext.dayTime=0x8000;Tick();ck(gSaveContext.dayTime==0x800A);
  shuffle=true;apSave=false;gSaveContext.dayTime=0x8000;Tick();ck(gSaveContext.dayTime==0x800A);apSave=true;
  gSaveContext.gameMode=GAMEMODE_END_CREDITS;gSaveContext.dayTime=0x8000;Tick();ck(gSaveContext.dayTime==0x800A);
  gSaveContext.gameMode=GAMEMODE_NORMAL;
 }
 for(auto clock:{0x4554,0x4555,0xB555,0xC000,0xC001}){
  gSaveContext.dayTime=clock;ClassifyClock();ck(bool(gSaveContext.nightFlag)==(clock<0x4555||clock>0xC000));
 }
 std::cout<<"PASS "<<tests<<" compiled clock/reset assertions\n";
}
'''
src=out/'frozen_clock.cpp';exe=out/'frozen_clock.exe';src.write_text(code,encoding='utf-8')
build=subprocess.run(['cl','/nologo','/std:c++20','/EHsc','/MD',str(src),'/Fo'+str(out/'frozen_clock.obj'),'/Fe'+str(exe)],capture_output=True,text=True)
run=subprocess.run([str(exe)],capture_output=True,text=True) if build.returncode==0 else None
log=build.stdout+build.stderr+(run.stdout+run.stderr if run else '')
finder=(r/'soh/Network/Archipelago/ArchipelagoEnemyFinderMap.inc').read_text(encoding='utf-8')
guays=[line for line in finder.splitlines() if 'Lon Lon Ranch' in line and 'Guay' in line]
mask_ok=len(guays)==15 and all(', 2, EFG_NONE,' in line for line in guays)
passed=build.returncode==0 and run.returncode==0 and mask_ok
(out/'native.json').write_text(json.dumps(dict(passed=passed,scope=__doc__,log=log,guay_spawn_masks_match=mask_ok),indent=2),encoding='utf-8')
print(log);raise SystemExit(0 if passed else 1)
