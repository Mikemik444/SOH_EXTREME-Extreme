"""Compile complete production lifetime functions with deterministic engine services."""
from pathlib import Path
import argparse,json,subprocess
from run_native_tests import function
p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args();root=a.source_root.resolve();b=a.report.parent/'lifecycle-test-build';b.mkdir(parents=True,exist_ok=True);results=[]
def test(name,code):
 f=b/(name+'.c');f.write_text(code);exe=b/name;cmd=['gcc','-std=c11','-O2','-Wall','-Wextra','-Werror','-Wno-unused-parameter',str(f),'-o',str(exe)]
 c=subprocess.run(cmd,capture_output=True,text=True);r=subprocess.run([str(exe)],capture_output=True,text=True) if c.returncode==0 else None
 d={'name':name,'passed':c.returncode==0 and r.returncode==0,'command':cmd,'compile_stderr':c.stderr,'stdout':r.stdout if r else '', 'stderr':r.stderr if r else ''};results.append(d);print(json.dumps(d,indent=2))
fm=(root/'src/overlays/actors/ovl_En_Floormas/z_en_floormas.c').read_text()
code=r'''
#include <assert.h>
#include <stddef.h>
#include <stdio.h>
typedef struct Actor {struct Actor* parent;struct Actor* child;int placement,flags,killed;struct{struct{float x,y,z;}pos;}world;void(*draw)(void);} Actor;
typedef struct PlayState {int unused;} PlayState;
typedef struct EnFloormas {Actor actor;void(*actionFunc)(struct EnFloormas*,PlayState*);}EnFloormas;
#define ACTOR_FLAG_ATTENTION_ENABLED 1
#define ACTOR_FLAG_UPDATE_CULLING_DISABLED 2
static int events,kills;static Actor* recipient;
static int MegaSoul_GetEnemyDefeatPlacement(const Actor* a){return a->placement;}
static void GameInteractor_ExecuteOnEnemyDefeat(Actor* a){++events;recipient=a;}
static void Actor_Kill(Actor* a){assert(!a->killed);a->killed=1;++kills;}
static void EnFloormas_SmWait(EnFloormas* a,PlayState* p){(void)a;(void)p;}
static void active(EnFloormas* a,PlayState* p){(void)a;(void)p;}
'''+function(fm,'void EnFloormas_SetupSmWait(EnFloormas* this) {')+r'''
int main(void){
 int permutations[6][3]={{0,1,2},{0,2,1},{1,0,2},{1,2,0},{2,0,1},{2,1,0}},cases=0;
 for(int root=0;root<3;++root){for(int order=0;order<6;++order){
  EnFloormas a[3]={0};events=kills=0;recipient=NULL;
  for(int i=0;i<3;++i){a[i].actor.parent=&a[(i+1)%3].actor;a[i].actor.child=&a[(i+2)%3].actor;a[i].actor.placement=i==root?100:-1;a[i].actor.flags=3;a[i].actor.world.pos.x=(float)(i*100);a[i].actionFunc=active;}
  EnFloormas_SetupSmWait(&a[permutations[order][0]]);assert(events==0&&kills==0);
  EnFloormas_SetupSmWait(&a[permutations[order][1]]);assert(events==0&&kills==0);
  EnFloormas_SetupSmWait(&a[permutations[order][2]]);assert(events==1&&kills==3&&recipient==&a[root].actor&&recipient->world.pos.x==(float)(permutations[order][2]*100));++cases;
 }}
 // Two merge slaves entering wait are not the extinction of a live master.
 EnFloormas a[3]={0};events=kills=0;
 for(int i=0;i<3;++i){a[i].actor.parent=&a[(i+1)%3].actor;a[i].actor.child=&a[(i+2)%3].actor;a[i].actor.placement=i==0?100:-1;a[i].actionFunc=active;}
 EnFloormas_SetupSmWait(&a[1]);EnFloormas_SetupSmWait(&a[2]);assert(events==0&&kills==0);
 // Reactivated fragments after a merge do not retain a false death status.
 a[1].actionFunc=a[2].actionFunc=active;
 EnFloormas_SetupSmWait(&a[0]);assert(events==0);EnFloormas_SetupSmWait(&a[1]);assert(events==0);EnFloormas_SetupSmWait(&a[2]);assert(events==1&&recipient==&a[0].actor);
 printf("%d Floormaster root-position/kill-order cases plus merge/re-split: one final event for the original placement, never for an early fragment death.\n",cases);
}
'''
test('floormaster_group_terminal',code)
crow=(root/'src/overlays/actors/ovl_En_Crow/z_en_crow.c').read_text()
code=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
typedef float f32;
typedef struct PlayState{int unused;}PlayState;
typedef struct Actor{int flags,params;struct{float x,y,z;}scale;struct{int health;}colChkInfo;void(*draw)(struct Actor*,PlayState*);}Actor;
typedef struct EnCrow{Actor actor;int timer,skelAnime;}EnCrow;
#define ACTOR_FLAG_ATTENTION_ENABLED 1
#define ACTOR_FLAG_UPDATE_CULLING_DISABLED 2
static int resets,idles;static bool arrived;
static void MegaSoul_ResetEnemyDefeatLife(Actor* a){assert(a->colChkInfo.health==1);++resets;}
static void EnCrow_SetupFlyIdle(EnCrow* a){(void)a;++idles;}
static void EnCrow_Draw(Actor* a,PlayState* p){(void)a;(void)p;}
static void SkelAnime_Update(int* a){(void)a;}
static bool Math_StepToF(float* v,float target,float speed){(void)speed;if(arrived)*v=target;return arrived;}
'''+function(crow,'void EnCrow_Respawn(EnCrow* this, PlayState* play) {')+r'''
int main(void){PlayState p={0};
 for(int type=0;type<2;++type){EnCrow a={0};a.actor.params=type;a.actor.flags=2;a.timer=2;resets=idles=0;arrived=false;
  EnCrow_Respawn(&a,&p);assert(a.timer==1&&resets==0&&idles==0);
  EnCrow_Respawn(&a,&p);assert(a.timer==0&&resets==0&&idles==0);
  arrived=true;EnCrow_Respawn(&a,&p);assert(resets==1&&idles==1&&a.actor.colChkInfo.health==1&&a.actor.flags==1);
  assert(a.actor.scale.y==a.actor.scale.x&&a.actor.scale.z==a.actor.scale.x);
 }
 puts("Ordinary and enlarged Guay: no drop-state reset while absent/growing; one reset when its next life becomes active.");
}
'''
test('guay_actual_respawn',code)
dha=(root/'src/overlays/actors/ovl_En_Dha/z_en_dha.c').read_text()
code=r'''
#include <assert.h>
#include <stddef.h>
#include <stdio.h>
typedef short s16;typedef struct Vec3f{float x,y,z;}Vec3f;
typedef struct Actor{struct Actor* parent;int params;struct{float yOffset;}shape;struct{Vec3f pos;}world;}Actor;
typedef struct Player{Actor actor;int stateFlags2;struct{int actionVar2;}av2;}Player;
typedef struct PlayState{int unused;}PlayState;
typedef struct EnDha{Actor actor;s16 limbAngleX[2];int skelAnime,actionTimer;}EnDha;
#define PLAYER_STATE2_GRABBED_BY_ENEMY 1
#define ENDH_DEATH 10
static Player fixturePlayer;static int resets,waits,kills;
#define GET_PLAYER(p) (&fixturePlayer)
static s16 Math_SmoothStepToS(s16* v,int target,int scale,int step,int min){(void)scale;(void)step;(void)min;*v=target;return 0;}
static void SkelAnime_Update(int* a){(void)a;}
static void func_80033480(PlayState* p,Vec3f* v,float x,int y,int z,int w,int k){(void)p;(void)v;(void)x;(void)y;(void)z;(void)w;(void)k;}
static void Actor_Kill(Actor* a){(void)a;++kills;}
static void MegaSoul_ResetEnemyDefeatLife(Actor* a){assert(a->shape.yOffset==0);++resets;}
static void EnDha_SetupWait(EnDha* a){(void)a;++waits;}
'''+function(dha,'void EnDha_Die(EnDha* this, PlayState* play) {')+r'''
int main(void){PlayState p={0};EnDha a={0};Actor parent={0};a.actor.parent=&parent;
 fixturePlayer.actor.parent=&a.actor;fixturePlayer.stateFlags2=1;
 a.actionTimer=2;a.actor.shape.yOffset=-11000;EnDha_Die(&a,&p);assert(resets==0&&waits==0&&fixturePlayer.actor.parent==NULL&&fixturePlayer.av2.actionVar2==200);
 EnDha_Die(&a,&p);assert(a.actionTimer==1&&resets==0);
 EnDha_Die(&a,&p);assert(a.actionTimer==0&&resets==0);
 a.actor.shape.yOffset=-1000;EnDha_Die(&a,&p);assert(resets==0&&waits==0);
 EnDha_Die(&a,&p);assert(resets==1&&waits==1);
 // Parent death removes the arm without pretending it has regrown.
 a.actor.shape.yOffset=-12000;a.actionTimer=1;parent.params=ENDH_DEATH;EnDha_Die(&a,&p);assert(kills==1&&resets==1);
 puts("Dead Hand arm: sinking and underground delay do not reset receipts; confirmed regrowth resets only life flags; parent-death cleanup is not regrowth.");
}
'''
test('dead_hand_arm_regrowth',code)
a.report.write_text(json.dumps({'passed':all(r['passed'] for r in results),'suites':results},indent=2));raise SystemExit(not all(r['passed'] for r in results))
