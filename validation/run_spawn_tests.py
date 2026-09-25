"""Compile real catalogue/policy/call-site code. Engine services are test substitutes.
Not a full game build or a live-server test. No game assets required.
"""
import argparse, json, subprocess, sys
from pathlib import Path
from run_native_tests import function
p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
root=a.source_root.resolve();rand=root/'soh/Enhancements/randomizer';build=a.report.parent/'spawn-test-build';build.mkdir(parents=True,exist_ok=True);results=[]
def test(name,code,lang='cpp'):
 f=build/(name+'.'+lang);f.write_text(code);exe=build/name
 cmd=['g++' if lang=='cpp' else 'gcc','-std=c++17' if lang=='cpp' else '-std=c11','-O2','-Wall','-Wextra','-Werror','-I',str(root),str(f),'-o',str(exe)]
 c=subprocess.run(cmd,text=True,capture_output=True);r=subprocess.run([str(exe)],text=True,capture_output=True) if c.returncode==0 else None
 d=dict(name=name,passed=c.returncode==0 and r.returncode==0,command=cmd,compile_stderr=c.stderr,stdout=r.stdout if r else '',stderr=r.stderr if r else '')
 results.append(d);print('PASS' if d['passed'] else 'FAIL',name,d['stdout'],d['compile_stderr'],d['stderr'],flush=True)
mega=(rand/'MegaSouls.cpp').read_text()
# Every generated alias exercises the actual resolver; mutations must not match.
test('exact_spawn_catalog',r'''
#include <cassert>
#include <cstdio>
#include <set>
#include "soh/Enhancements/randomizer/EnemySpawnCatalog.h"
using namespace SohExtreme;
int main() {
    size_t n=0,c=0; std::set<int> placements;
    for(const auto& a:kEnemySpawnAliases) {
        assert(FindExactEnemySpawn(a.key)==a.placement);
        auto changed=a.key; changed.x += 123456; assert(FindExactEnemySpawn(changed)==-1);
        changed=a.key; changed.room=127; assert(FindExactEnemySpawn(changed)==-1);
        placements.insert(a.placement); ++n;
    }
    for(const auto& a:kEnemyChildAliases) {
        auto free=[](int){return false;}; auto full=[](int){return true;};
        assert(FindExactEnemyChild(a.source,a.childId,a.params,a.slot,free)==a.placement);
        assert(FindExactEnemyChild(a.source,a.childId,a.params,a.slot,full)==-1);
        auto moved=a.source; moved.z+=123456;
        assert(FindExactEnemyChild(moved,a.childId,a.params,a.slot,free)==-1);
        assert(FindExactEnemyChild(a.source,a.childId,a.params,32767,free)==-1);
        placements.insert(a.placement); ++c;
    }
    printf("%zu exact static aliases; %zu scripted aliases; coordinate, room, slot and occupancy negatives passed (%zu identified placements).\n",n,c,placements.size());
}
''')
# Preserve the actual OptionValue class (including explicit bool) and real call.
option=function((rand/'option.h').read_text(),'class OptionValue')+';'
optcpp=(rand/'option.cpp').read_text();option+='\n'+'\n'.join(function(optcpp,sig) for sig in ['OptionValue::OptionValue(uint8_t val)', 'uint8_t OptionValue::Get()', 'void OptionValue::Set(uint8_t val)', 'OptionValue::operator bool() const'])
test('real_option_callsite',r'''
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <type_traits>
#include "soh/Enhancements/randomizer/EnemyDropPolicy.h"
namespace Rando {
'''+option+r'''
}
static_assert(!std::is_convertible<Rando::OptionValue,bool>::value,"test must preserve explicit-only conversion");
struct Actor{ bool enemy=true,scrub=false,gold=false,pot=false,statue=false,soul=true,pending=false;int id=0;};
struct EnemyDefeatIdentity:SohExtreme::EnemyLifeDropState{};
static EnemyDefeatIdentity life; static bool rando=true,attached=true;static Rando::OptionValue option;
#define IS_RANDO rando
#define ACTOR_EN_TUBO_TRAP 0x11D
#define RAND_GET_OPTION(x) option
static bool IsMegaEnemySoulActor(Actor* a){return a->enemy;}
static bool IsMegaScrubActor(int){return false;}
static bool IsGoldSkulltulaActor(Actor* a){return a->gold;}
static bool IsMegaPotActor(int){return false;}
static bool IsStructuralArmosStatue(Actor* a){return a->statue;}
static bool HasRequiredEnemySoul(Actor* a){return a->soul;}
static bool MegaSoul_IsEnemyDefeatLocationPending(Actor* a){return a->pending;}
struct ObjectExtension {
 static ObjectExtension& GetInstance(){static ObjectExtension x;return x;}
 template<class T>T* Get(Actor*){return attached?&life:nullptr;}
};
'''+function(mega,'extern "C" int MegaSoul_ConsumeNormalEnemyDrop(')+r'''
int main(){
    Actor a;
    for(int i=0;i<128;++i){
        rando=(i&1);attached=(i&2);option.Set((i&4)?1:0);a.enemy=(i&8);a.soul=(i&16);a.pending=(i&32);
        life={};life.rewardWasAp=(i&64);
        int expected=(!rando||!attached||!a.enemy||!option.Get())?0:(!a.soul||a.pending||life.rewardWasAp)?-1:1;
        assert(MegaSoul_ConsumeNormalEnemyDrop(&a)==expected);
        if(expected==1)assert(MegaSoul_ConsumeNormalEnemyDrop(&a)==-1);
    }
    assert(MegaSoul_ConsumeNormalEnemyDrop(nullptr)==0);
    puts("Actual explicit-bool OptionValue declaration and real MegaSoul call compiled; 128 call-site states passed.");
}
''')
# Both arena stages, including failed allocations and no spawning when the pair is disabled.
controller=(root/'src/overlays/actors/ovl_Bg_Mori_Bigst/z_bg_mori_bigst.c').read_text()
test('bow_room_spawn_lifecycle',r'''
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <stdarg.h>
typedef struct Actor Actor; struct Actor{ int room;Actor* child;struct{struct{int z;}rot;}home;};
typedef struct {int clear;} PlayState;
typedef struct BgMoriBigst {struct{Actor actor;}dyna;} BgMoriBigst;
static bool pair=true,allocate=true;static int slots[10],paramsSeen[10],count;static Actor child;
#define ACTOR_EN_TEST 2
#define VB_MORI_BIGST_SUMMON_STALFOS_PAIR 1
static void BgMoriBigst_StalfosFight(BgMoriBigst* x,PlayState* p){(void)x;(void)p;}
static void BgMoriBigst_StalfosPairFight(BgMoriBigst* x,PlayState* p){(void)x;(void)p;}
static void BgMoriBigst_SetupAction(BgMoriBigst* x,void(*f)(BgMoriBigst*,PlayState*)){(void)x;(void)f;}
static void Flags_UnsetClear(PlayState* p,int r){(void)r;p->clear=0;}
static void Flags_SetClear(PlayState* p,int r){(void)r;p->clear=1;}
static bool GameInteractor_Should(int v,bool b,BgMoriBigst* x,PlayState* p){(void)v;(void)b;(void)x;(void)p;return pair;}
static int osSyncPrintf(const char* f,...){(void)f;return 0;}
static Actor* MegaSoul_SpawnEnemyChild(PlayState* p,Actor* parent,int slot,int id,float x,float y,float z,int rx,int ry,int rz,int params){
    (void)parent;(void)x;(void)y;(void)z;(void)rx;(void)ry;(void)rz;
    assert(p->clear==0);assert(id==ACTOR_EN_TEST);slots[count]=slot;paramsSeen[count++]=params;return allocate?&child:NULL;
}
'''+function(controller,'void BgMoriBigst_SetupStalfosFight(BgMoriBigst* this, PlayState* play) {')+'\n'+function(controller,'void BgMoriBigst_SetupStalfosPairFight(BgMoriBigst* this, PlayState* play) {')+r'''
int main(){
    BgMoriBigst x={0};PlayState p={1};
    BgMoriBigst_SetupStalfosFight(&x,&p);assert(count==1&&slots[0]==0&&paramsSeen[0]==1&&x.dyna.actor.home.rot.z==1&&p.clear==1);
    BgMoriBigst_SetupStalfosPairFight(&x,&p);assert(count==3&&slots[1]==1&&slots[2]==2&&paramsSeen[1]==5&&paramsSeen[2]==5&&x.dyna.actor.home.rot.z==3&&p.clear==1);
    allocate=false;BgMoriBigst_SetupStalfosPairFight(&x,&p);assert(count==5&&x.dyna.actor.home.rot.z==3);
    pair=false;BgMoriBigst_SetupStalfosPairFight(&x,&p);assert(count==5&&p.clear==1);
    puts("Real Bow-room single/pair functions retain wave counters, pass distinct slots, and handle disabled/failed spawns.");
}
''','c')
# Compile all generated finder rows using the actual native enum definitions and struct.
tracker=(rand/'randomizer_check_tracker.cpp').read_text()
start=tracker.index('enum EnemyFinderCombat :'); end=tracker.index('static constexpr size_t kEnemyDefeatFinderEntryCount')
test('native_enum_and_finder_table', '#include <cstddef>\n#include <cstdint>\n#include <cassert>\n#include <set>\n#include <cstdio>\n#include "soh/Enhancements/randomizer/randomizerEnums.h"\n'+tracker[start:end]+r''' 
int main(){std::set<int64_t> ids;for(const auto& e:kEnemyDefeatFinderEntries){assert(e.spawnMask>0&&e.spawnMask<16);assert(ids.insert(e.locationId).second);assert(e.region!=RR_NONE);}assert(ids.size()==753);puts("753 native finder rows compiled with production enums and exact struct; unique IDs and valid masks passed.");}
''')
test('public_c_bridge_header', '#include "soh/Enhancements/randomizer/EnemyDropBridge.h"\nint main(void){return 0;}\n', 'c')
a.report.write_text(json.dumps({'passed':all(x['passed'] for x in results),'suites':results},indent=2));raise SystemExit(not all(x['passed'] for x in results))
