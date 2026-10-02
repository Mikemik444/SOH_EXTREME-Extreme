"""Compile production spawn matching and enemy reward handling against asset identities.

Engine allocation/reporting services are controlled adapters, not a live game.
The fixture independently records the supplied scene's entrance-to-room command.
"""
import argparse, json, re, runpy, subprocess, zipfile
from pathlib import Path
from run_native_tests import function

p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--baseline-source-zip',type=Path);a=p.parse_args()
r=Path(__file__).resolve().parents[1];out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
fixture=json.loads((r/'validation/fixtures/grotto_enemy_spawns.json').read_text())
catalog=runpy.run_path(str(r/'archipelago/soh_extreme/EnemyDropLocations.py'))
entries=catalog['ENEMY_DROP_LOCATIONS'];checks=[]
def ck(name,value):
    checks.append(dict(test=name,passed=bool(value)))
by_key={(e.grotto_id,e.room,e.actor_index,e.actor_id,e.params):e for e in entries if e.scene_id==62}
actual=[]
loads=(r/'soh/Enhancements/randomizer/randomizer_grotto.c').read_text().split('static const GrottoLoadInfo')[1].split('// clang-format on')[0]
load_entries=re.findall(r'\.entranceIndex = (ENTR_\w+),',loads)
for row in fixture['grottos']:
    ck('native entrance '+str(row['grotto_id']),load_entries[row['grotto_id']]==row['entrance'])
    for enemy in row['enemies']:
        key=(row['grotto_id'],row['room'],enemy['index'],enemy['actor_id'],enemy['params'])
        ck('physical enemy has check '+str(key),key in by_key)
        if key in by_key:actual.append((row,enemy,by_key[key]))
ck('eight physical grotto checks, no phantom duplicates',len(actual)==len(by_key)==8)
finder=(r/'soh/Network/Archipelago/ArchipelagoEnemyFinderMap.inc').read_text()
for _,_,e in actual:
    line=next(line for line in finder.splitlines() if f'{e.address}LL' in line)
    ck('finder/AP region '+str(e.address),f'RR_{e.region_token},' in line and e.name in line)
    ck('finder/AP grotto '+str(e.address),f', 62, {e.room}, {e.grotto_id}, {e.actor_id},' in line)
retired=catalog['ENEMY_GROTTO_RETIRED_IDS']
ck('retired IDs absent from finder',all(f'{i}LL' not in finder for i in retired))
meadow=next(e for e in entries if e.address==9800536)
ck('outdoor Wolfos belongs before its gate',meadow.region_token=='SFM_ENTRYWAY' and meadow.spawn_mask==3)
ck('outdoor finder belongs before its gate','RR_SFM_ENTRYWAY,' in next(line for line in finder.splitlines() if '9800536LL' in line))
s=(r/'soh/Enhancements/randomizer/MegaSouls.cpp').read_text()
if a.baseline_source_zip:
    with zipfile.ZipFile(a.baseline_source_zip) as z:s=z.read('soh/Enhancements/randomizer/MegaSouls.cpp').decode()
# Exercise the actual grotto resolver: the UI tracker ID is unset for vanilla
# entrances. Earlier tests gave both paths a valid UI ID and missed this bug.
grotto_source=(r/'soh/Enhancements/randomizer/randomizer_grotto.c').read_text()
scene_ids={name:int(value,16) for value,name in re.findall(r'/\* 0x([0-9A-Fa-f]+) \*/ DEFINE_SCENE\(\w+, \w+, (SCENE_\w+)',(r/'include/tables/scene_table.h').read_text())}
load_data=re.findall(r'\.entranceIndex = (ENTR_\w+),\s*\.content = (0x\w+),\s*\.scene = (SCENE_\w+)',loads)
assert len(load_data)==33
resolver=r'''
using s8=int8_t;using s16=int16_t;
constexpr int NUM_GROTTOS=33,ENTRANCE_GROTTO_LOAD_START=0x700,RESPAWN_MODE_RETURN=0;
constexpr int RSK_SHUFFLE_GROTTO_ENTRANCES=0,RSK_SHUFFLE_OVERWORLD_SPAWNS=1,RSK_SHUFFLE_WARP_SONGS=2;
int shuffleMask=0;int8_t grottoId=-1;
int Randomizer_GetSettingValue(int option){return shuffleMask&(1<<option);}
struct Respawn {int16_t entranceIndex=0;int8_t data=0;};
struct {Respawn respawn[1];} gSaveContext;
struct Entrance {int8_t scene=0;};Entrance gEntranceTable[33];
struct GrottoLoadInfo {int entranceIndex;int8_t content,scene;};
const GrottoLoadInfo grottoLoadTable[]={
'''+''.join(f'{{{i},static_cast<int8_t>({data}),{scene_ids[scene]}}},\n' for i,(_,data,scene) in enumerate(load_data))+r'''};
'''+function(grotto_source,'s16 Grotto_GetRenamedGrottoIndexFromOriginal(')+'\n'+function(grotto_source,'s8 Grotto_CurrentGrotto()')+r'''
void selectGrotto(int id,int mode,int trackerId){
 shuffleMask=mode;grottoId=id;EntranceTracker::grotto=trackerId;
 gSaveContext.respawn[0].entranceIndex=id;gSaveContext.respawn[0].data=grottoLoadTable[id].content;
 gEntranceTable[id].scene=grottoLoadTable[id].scene;
}
'''
code=r'''
#include <cassert>
#include <cstdio>
#include <cstdint>
#include <iostream>
#include "soh/Enhancements/randomizer/EnemySpawnCatalog.h"
#include "soh/Enhancements/randomizer/EnemyDropPolicy.h"
bool rando=true,ap=true;
#define IS_RANDO rando
bool Archipelago_IsCurrentSaveActive(){return ap;}
constexpr int SCENE_GROTTOS=62,SCENE_FOREST_TEMPLE=3,ACTOR_EN_PO_SISTERS=0xF,ACTOR_EN_TUBO_TRAP=0x11D;
namespace EntranceTracker {int grotto=-1;int GetCurrentGrottoId(){return grotto;}}
struct Placement {int16_t scene,room,grottoId,actorListIndex,actorId;uint16_t params;int64_t locationId;};
constexpr Placement kEnemyDefeatPlacements[]={
#include "soh/Enhancements/randomizer/EnemyDefeatPlacements.inc"
};
constexpr size_t kEnemyPlacementCount=sizeof(kEnemyDefeatPlacements)/sizeof(Placement);
'''+resolver+function(s,'extern "C" int32_t MegaSoul_FindEnemyDefeatSpawn(')+r'''
struct Vec3f {float x=0,y=0,z=0;};
struct Actor {int id=431;struct {Vec3f pos;}world;};
struct EnItem00 {} pickup;
struct EnemyDefeatIdentity : SohExtreme::EnemyLifeDropState {int placementIndex=-1;int64_t locationId=-1;} identity;
struct ObjectExtension {
 static ObjectExtension& GetInstance(){static ObjectExtension value;return value;}
 template<typename T>T* Get(Actor*){return &identity;}
};
int drops=0,earned=0,normalDrops=0;bool pending=true,hasSoul=true,allocate=true;
bool IsMegaEnemySoulActor(Actor*){return true;}
bool IsMegaScrubActor(int){return false;}bool IsGoldSkulltulaActor(Actor*){return false;}
bool IsMegaPotActor(int){return false;}bool HasRequiredEnemySoul(Actor*){return hasSoul;}
bool EnemyDefeatLocationStillPending(int index,int64_t id){return pending && index>=0 && !SohExtreme::IsRetiredEnemyPlacement(index);}
void MarkEnemyDefeatEarned(size_t){++earned;}
EnItem00* SpawnEnemyDefeatPickup(Actor*,int index,int64_t id){assert(id==kEnemyDefeatPlacements[index].locationId);if(!allocate)return nullptr;++drops;return &pickup;}
void* gPlayState=nullptr;
void Item_DropCollectibleRandom(void*,Actor*,Vec3f*,int){++normalDrops;}
#define RAND_GET_OPTION(x) true
'''+function(s,'auto handleEnemyDeath = [](Actor* actor)')+r''';
int tests=0;
void verify(bool value){++tests;assert(value);}
void reward(int index){
 Actor actor;identity={};identity.placementIndex=index;identity.locationId=kEnemyDefeatPlacements[index].locationId;
 drops=earned=normalDrops=0;pending=true;hasSoul=true;allocate=true;
 handleEnemyDeath(&actor);verify(drops==1 && earned==1 && identity.defeatHandled && identity.rewardWasAp);
 handleEnemyDeath(&actor);verify(drops==1 && earned==1 && normalDrops==0);
 // A repeated kill after collection receives ordinary loot, not another check.
 identity={};identity.placementIndex=index;identity.locationId=kEnemyDefeatPlacements[index].locationId;
 pending=false;handleEnemyDeath(&actor);verify(drops==1 && normalDrops==1);
 // No soul, no award. Allocation failure can be retried during the death animation.
 identity={};identity.placementIndex=index;identity.locationId=kEnemyDefeatPlacements[index].locationId;
 pending=true;hasSoul=false;handleEnemyDeath(&actor);verify(drops==1 && !identity.defeatHandled);
 hasSoul=true;allocate=false;handleEnemyDeath(&actor);verify(drops==1 && !identity.defeatHandled);
 allocate=true;handleEnemyDeath(&actor);verify(drops==2 && identity.defeatHandled);
}
int main(){
'''
for row,enemy,e in actual:
    args=[62,e.room,e.actor_index,e.actor_id,e.params,*enemy['position']]
    call=lambda vals:'MegaSoul_FindEnemyDefeatSpawn('+','.join(map(str,vals))+')'
    code+=f'for(int mode=0;mode<8;++mode){{selectGrotto({e.grotto_id},mode,mode?{e.grotto_id}:-1);verify({call(args)}=={e.address-9800000});reward({e.address-9800000});\n'
    code+=f'EntranceTracker::grotto=25;verify({call(args)}=={e.address-9800000});\n'
    for pos in (1,2,3,4):
        changed=list(args);changed[pos]+=100
        code+=f'verify({call(changed)}==-1);\n'
    code+=f'selectGrotto(25,mode,{e.grotto_id});verify({call(args)}==-1);\n'
    code+=f'selectGrotto({e.grotto_id},mode,-1);ap=false;verify({call(args)}==-1);ap=true;rando=false;verify({call(args)}==-1);rando=true;}}\n'
mw=fixture['meadow_wolfos'];args=[mw['scene'],mw['room'],mw['index'],mw['actor_id'],mw['params'],*mw['position']]
code+=f'verify({call(args)}==536);reward(536);\n'
for index in (i-9800000 for i in retired):
    code+=f'verify(SohExtreme::IsRetiredEnemyPlacement({index}));verify(kEnemyDefeatPlacements[{index}].locationId==9800000LL+{index});\n'
code+='std::cout<<"PASS "<<tests<<" compiled spawn/reward assertions\\n"; }\n'
src=out/'grotto_native.cpp';exe=out/'grotto_native.exe';src.write_text(code,encoding='utf-8')
compile=subprocess.run(['cl','/nologo','/std:c++20','/EHsc','/MD','/I',str(r),str(src),'/Fo'+str(out/'grotto_native.obj'),'/Fe'+str(exe)],capture_output=True,text=True)
run=subprocess.run([str(exe)],capture_output=True,text=True) if compile.returncode==0 else None
log=compile.stdout+compile.stderr+(run.stdout+run.stderr if run else '')
ck('production native spawn matching and reward handling',compile.returncode==0 and run.returncode==0)
wolfos=(r/'src/overlays/actors/ovl_En_Wf/z_en_wf.c').read_text(encoding='utf-8')
ck('Wolfos terminal death dispatches enemy reward hook','GameInteractor_ExecuteOnEnemyDefeat(&this->actor)' in function(wolfos,'void EnWf_SetupDie(EnWf* this) {'))
report=dict(passed=all(c['passed'] for c in checks),checks=checks,log=log,scope=__doc__)
(out/'native.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(log);print('source assertions',len(checks));raise SystemExit(0 if report['passed'] else 1)
