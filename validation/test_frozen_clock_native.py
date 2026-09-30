"""Compile the real clock freeze, engine day/night classification and region resets.

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
freeze=function(client,'if (CVarGetInteger(CVAR_RANDOMIZER_SETTING("ShuffleFlowOfTime"), 0) &&')
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
struct Save {u16 dayTime=0,skyboxTime=0;int nightFlag=0;} gSaveContext;
bool hasFlow=false,shuffle=true;int preset=1,age=0;
int dummyPlay=1;int* gPlayState=&dummyPlay;
#define CVAR_RANDOMIZER_SETTING(x) x
bool Flags_GetRandomizerInf(int){return hasFlow;}
constexpr int RAND_INF_FLOW_OF_TIME=1;
int CVarGetInteger(const char* key,int fallback){return std::string(key)=="FrozenStartingTime"?preset:shuffle;}
void FreezeTime(){
'''+freeze+'\n}\nvoid ClassifyClock(){\n'+classify+r'''
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
  shuffle=true;hasFlow=false;FreezeTime();ClassifyClock();
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
  hasFlow=true;gSaveContext.dayTime=0xCAFE;FreezeTime();ck(gSaveContext.dayTime==0xCAFE);
  hasFlow=false;shuffle=false;gSaveContext.dayTime=0xBEEF;FreezeTime();ck(gSaveContext.dayTime==0xBEEF);
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
