"""Compile the production pot ownership/drop functions with controlled engine services."""
from pathlib import Path
import argparse,json,subprocess
from run_native_tests import function
p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path,default=Path(__file__).resolve().parent.parent);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
text=(a.source_root/'soh/Enhancements/randomizer/ShufflePots.cpp').read_text();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
code=r'''
#include <cstdint>
#include <cstdio>
#include <cassert>
using RandomizerCheck=int;
constexpr int RC_UNKNOWN_CHECK=0,RC_MAX=999,RAND_INF_MAX=999;
constexpr int RSK_SHUFFLE_POTS=0,RO_SHUFFLE_POTS_OVERWORLD=2,RO_SHUFFLE_POTS_DUNGEONS=1;
constexpr int GI_NONE=0,ITEM00_SOH_DUMMY=77;
static bool rando=true,ap=true,active=false,obtained=false,allocated=true,dungeon=true;
#define IS_RANDO rando
struct Option{int value=3; bool Is(int v){return value==v;} operator bool()const{return value!=0;}} setting;
#define RAND_GET_OPTION(x) setting
struct Vec3f {float x=0,y=0,z=0;};
using ActorFunc=void(*)();
struct Actor{struct {Vec3f pos,rot;}world;Vec3f velocity;float speedXZ=0;ActorFunc draw=nullptr;};
struct ObjTsubo{Actor actor;};struct PlayState{};
struct Entry{int id=0;};struct EnItem00{Actor actor;int randoInf=0;Entry itemEntry;};
struct CheckIdentity{int randomizerCheck=893,randomizerInf=354;};
static CheckIdentity identity,*identityPtr=&identity;static EnItem00 drop;static int spawns=0,queries=0;
struct ObjectExtension{static ObjectExtension& GetInstance(){static ObjectExtension x;return x;}template<class T>T* Get(Actor*){return identityPtr;}};
bool Archipelago_IsCurrentSaveFile(){return ap;}bool Archipelago_ShouldHandleCheck(int){return active;}
bool Flags_GetRandomizerInf(int){return obtained;}
namespace Rando{struct Location{bool IsDungeon(){return dungeon;}};struct StaticData{static Location* GetLocation(int rc){assert(rc!=RC_UNKNOWN_CHECK&&rc!=RC_MAX);static Location x;return &x;}};
struct Context{static Context* GetInstance(){static Context x;return &x;}Entry GetFinalGIEntry(int rc,bool,int){++queries;return {rc};}};}
EnItem00* Item_DropCollectible2(PlayState*,Vec3f*,int){++spawns;return allocated?&drop:nullptr;}
void EnItem00_DrawRandomizedItem(){}float Rand_CenteredFloat(float){return 0;}
'''
code+=function(text,'uint8_t ObjTsubo_RandomizerHoldsItem(')+'\n'+function(text,'void ObjTsubo_RandomizerSpawnCollectible(')
code+=r'''
int main(){ObjTsubo pot;PlayState play;int count=0;
 for(int a=0;a<2;++a)for(int own=0;own<2;++own)for(int done=0;done<2;++done)
 for(int mode=0;mode<4;++mode)for(int dg=0;dg<2;++dg)for(int randomized=0;randomized<2;++randomized){
  ap=a;active=own;obtained=done;setting.value=mode;dungeon=dg;rando=randomized;
  bool expected=randomized&&!done&&mode&&(!a||own)&&(mode==3||(dg?mode==1:mode==2));
  assert(bool(ObjTsubo_RandomizerHoldsItem(&pot,&play))==expected);++count;
 }
 ap=true;active=true;obtained=false;setting.value=3;rando=true;
 for(int rc:{RC_UNKNOWN_CHECK,RC_MAX}){identity.randomizerCheck=rc;assert(!ObjTsubo_RandomizerHoldsItem(&pot,&play));++count;}
 identity.randomizerCheck=893;identity.randomizerInf=RAND_INF_MAX;assert(!ObjTsubo_RandomizerHoldsItem(&pot,&play));++count;
 identity.randomizerInf=354;identityPtr=nullptr;assert(!ObjTsubo_RandomizerHoldsItem(&pot,&play));++count;
 identityPtr=&identity;ObjTsubo_RandomizerSpawnCollectible(&pot,&play);
 assert(spawns==1&&drop.randoInf==354&&drop.itemEntry.id==893&&drop.actor.draw==EnItem00_DrawRandomizedItem);++count;
 allocated=false;ObjTsubo_RandomizerSpawnCollectible(&pot,&play);assert(spawns==2&&queries==1&&!obtained);++count;
 std::printf("%d assertions passed\n",count);
}
'''
code=code.replace('#include <cassert>','#include <cassert>\n#include <initializer_list>')
src=out/'pot.cpp';exe=out/'pot.exe';src.write_text(code)
c=subprocess.run(['cl','/nologo','/std:c++20','/EHsc','/MD',str(src),'/Fo'+str(out/'pot.obj'),'/Fe'+str(exe)],capture_output=True,text=True)
r=subprocess.run([str(exe)],capture_output=True,text=True) if not c.returncode else None
report=dict(passed=c.returncode==0 and r.returncode==0,compile_exit=c.returncode,compile_output=c.stdout+c.stderr,output=r.stdout+r.stderr if r else '',scope=__doc__)
(out/'runtime.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2));raise SystemExit(not report['passed'])
