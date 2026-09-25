"""Compile actual Poe-intro identification and the production update-gate lambda body."""
from pathlib import Path
import argparse,subprocess,json
from run_native_tests import function
p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args();root=a.source_root.resolve();s=(root/'soh/Enhancements/randomizer/MegaSouls.cpp').read_text()
code=r'''
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <unordered_map>
#include "soh/Enhancements/randomizer/EnemySpawnCatalog.h"
struct Actor {int id=145,params=0,colorFilterTimer=0;int16_t colorFilterParams=0;struct{int health=10,damage=0;}colChkInfo;};
struct EnemySourceIdentity {SohExtreme::EnemySpawnKey key;};
struct ObjectExtension {std::unordered_map<const Actor*,EnemySourceIdentity> map;static ObjectExtension& GetInstance(){static ObjectExtension x;return x;}template<class T>T* Get(const Actor* a){auto i=map.find(a);return i==map.end()?nullptr:&i->second;}};
#define ACTOR_EN_PO_SISTERS 145
#define RAND_GET_OPTION(x) false
#define RAND_INF_NPC_SOUL 0
static bool missing=true;static int hidden=0,restored=0;
static bool MegaHas(int){return true;}
static bool IsMegaNpcSoulActor(Actor*){return false;}
static bool IsMegaEnemySoulGone(Actor*){return missing;}
static bool IsMegaEnemySoulInvincible(Actor*){return false;}
static void HideGoneEnemy(Actor*){++hidden;}
static void RestoreGoneEnemy(Actor*){++restored;}
'''+function(s,'static bool IsPoeSisterIntroActor(')+'\n'+function(s,'[](void* actorRef, bool* should) {').replace('[](void* actorRef, bool* should)','static void Gate(void* actorRef, bool* should)',1)+r'''
int main(){
 Actor a;auto& map=ObjectExtension::GetInstance().map;
 for(int sister=0;sister<4;++sister){
   map[&a]={};map[&a].key.params=static_cast<uint16_t>(0x1000|(sister<<8));a.params=0;bool run=true;
   assert(IsPoeSisterIntroActor(&a));Gate(&a,&run);assert(run&&hidden==sister+1);
 }
 for(int params:{0,0x100,0x200,0x300,0x400,0x800,0xC00}){
   map[&a].key.params=params;bool run=true;assert(!IsPoeSisterIntroActor(&a));Gate(&a,&run);assert(!run);
 }
 missing=false;bool run=true;Gate(&a,&run);assert(run&&restored==1);
 map.clear();a.params=0x1000;assert(IsPoeSisterIntroActor(&a));a.id=2;assert(!IsPoeSisterIntroActor(&a));assert(!IsPoeSisterIntroActor(nullptr));
 puts("Four real intro variants stay hidden but update; combat sisters/decoys remain frozen without their soul; post-init erased params and soul unlock covered.");
}
'''
b=a.report.parent/'poe-intro-build';b.mkdir(parents=True,exist_ok=True);f=b/'intro.cpp';f.write_text(code);exe=b/'intro';cmd=['g++','-std=c++17','-O2','-Wall','-Wextra','-Werror','-I',str(root),str(f),'-o',str(exe)];c=subprocess.run(cmd,text=True,capture_output=True);r=subprocess.run([str(exe)],text=True,capture_output=True) if c.returncode==0 else None
result={'passed':c.returncode==0 and r.returncode==0,'name':'poe_intro_lifecycle_gate','compile_command':cmd,'compile_stderr':c.stderr,'stdout':r.stdout if r else '', 'stderr':r.stderr if r else ''};a.report.write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2));raise SystemExit(not result['passed'])
