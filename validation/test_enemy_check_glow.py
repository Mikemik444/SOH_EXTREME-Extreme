"""Compile production enemy-glow eligibility and draw body with controlled services.

Uses the real species/shared/skulltula soul policy and pending-check predicate.
Render calls are recorded, not executed by a GPU; no visual playtest is implied.
"""
from pathlib import Path
from run_native_tests import function
import argparse, json, re, subprocess
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output', type=Path, required=True)
a=p.parse_args();r=Path(__file__).resolve().parent.parent;o=a.output.resolve();o.mkdir(parents=True,exist_ok=True)
source=(r/'soh/Enhancements/randomizer/MegaSouls.cpp').read_text(encoding='utf-8')
actor=(r/'src/code/z_actor.c').read_text(encoding='utf-8')
body='\n'.join(function(source,s) for s in ('static int GetEnemySoulMode(', 'static RandomizerInf EnemySoulInfForActorId(',
    'static bool IsStructuralArmosStatue(', 'static RandomizerInf EnemySoulInfForActor(',
    'static bool IsGoldSkulltulaActor(', 'static bool IsOrdinarySkulltulaActor(', 'static bool HasRequiredEnemySoul(',
    'static bool IsSkulltulaSoulLocked(', 'static bool EnemyDefeatLocationStillPending(',
    'extern "C" bool MegaSoul_ShouldHighlightEnemy('))
# Keep the real retirement catalog; the flag also permits isolated outbox cases.
body=body.replace('SohExtreme::IsRetiredEnemyPlacement(placementIndex)',
    '(retired || SohExtreme::IsRetiredEnemyPlacement(placementIndex))')
enums=sorted(set(re.findall(r'\b(?:ACTOR|RAND_INF|RSK)_\w+',body)))
draw=function(actor,'static void Actor_DrawEnemyCheckGlow(')
actor_draw=function(actor,'void Actor_Draw(PlayState* play, Actor* actor) {')
assert actor_draw.index('Actor_DrawEnemyCheckGlow(play, actor)') > actor_draw.index('actor->shape.shadowDraw(actor, lights, play)')
code=r'''
#include <cstdint>
#include <cmath>
#include <iostream>
#include <map>
#include <set>
#include "soh/Enhancements/randomizer/EnemyDropPolicy.h"
#include "soh/Enhancements/randomizer/EnemySpawnCatalog.h"
using RandomizerInf=int;using s16=int16_t;using u8=uint8_t;using f32=float;
'''+ 'enum Constants{'+','.join(enums)+'};\n'+r'''
bool rando=true,apSave=true,active=true,reported=false,collected=false,retired=false;
#define IS_RANDO rando
std::map<int,int>options;std::set<int>souls;
struct Option{int v;int Get(){return v;}operator bool(){return v!=0;}};
#define RAND_GET_OPTION(k) Option{options[k]}
bool MegaHas(int f){return souls.count(f);}
struct Vec3f{float x=0,y=0,z=0;};
void drawCallback(){}
struct Actor{int id=ACTOR_EN_FIREFLY,params=1;void(*draw)()=drawCallback;void(*update)()=drawCallback;
 struct{Vec3f pos;}world,focus;};
struct EnemyDefeatIdentity{int32_t placementIndex=0;int64_t locationId=9800000;bool deathObserved=false;};
struct ObjectExtension{std::map<const Actor*,EnemyDefeatIdentity>values;
 static ObjectExtension&GetInstance(){static ObjectExtension e;return e;}
 template<class T>T*Get(const Actor*a){auto it=values.find(a);return it==values.end()?nullptr:&it->second;}};
constexpr size_t kEnemyPlacementCount=9000;
bool Archipelago_IsCurrentSaveActive(){return apSave;}
bool Archipelago_IsLocationActive(int64_t){return active;}
bool Archipelago_IsLocationReported(int64_t){return reported;}
bool EnemyDefeatWasCollected(size_t){return collected;}
'''+body+r'''
struct GraphicsContext{}gfx;
struct PlayState{struct{GraphicsContext*gfxCtx=&gfx;}state;uint32_t gameplayFrames=0;int billboardMtxF=0;}play;
int stack=0,disps=0,halos=0,primAlpha=0;float lastHeight=0,lastScale=0;
constexpr int MTXMODE_NEW=0,MTXMODE_APPLY=1;
#define M_PI 3.14159265358979323846
#define CLAMP(x,a,b) ((x)<(a)?(a):(x)>(b)?(b):(x))
#define OPEN_DISPS(...) (++disps)
#define CLOSE_DISPS(...) (--disps)
#define gDPPipeSync(...) ((void)0)
#define gDPSetPrimColor(dl,a,b,r,g,c,alpha) (primAlpha=(alpha))
#define gDPSetEnvColor(...) ((void)0)
#define gSPMatrix(...) ((void)0)
#define gSPDisplayList(...) (++halos)
float Math_SinS(s16 a){return std::sin(a*3.14159265358979323846/32768.0);}
void Matrix_Push(){++stack;}void Matrix_Pop(){--stack;}
void Matrix_Translate(float,float y,float,int){lastHeight=y;}
void Matrix_Mult(int*,int){}void Matrix_Scale(float x,float,float,int){lastScale=x;}
void Matrix_RotateZ(float,int){}void Gfx_SetupDL_25Xlu(GraphicsContext*){}
'''+draw+r'''
int checks=0;
#define CK(x) do{++checks;if(!(x)){std::cerr<<"FAIL line "<<__LINE__<<": "<<#x<<"\n";return 1;}}while(0)
void reset(){rando=apSave=active=true;reported=collected=retired=false;options.clear();souls.clear();ObjectExtension::GetInstance().values.clear();}
int main(){
 // Each actual soul mapping is exercised in disabled/shared/individual mode.
 const std::pair<int,int> species[]={
'''
mapping=function(source,'static RandomizerInf EnemySoulInfForActorId(')
groups=re.findall(r'((?:\s*case ACTOR_\w+:)+)\s*return (RAND_INF_\w+);',mapping)
pairs=[(a,soul) for group,soul in groups for a in re.findall(r'case (ACTOR_\w+):',group)]
assert len(pairs)>40
code+=','.join('{'+aid+','+inf+'}' for aid,inf in pairs)+r'''};
 for(auto [id,own]:species)for(int mode=0;mode<3;++mode)for(int flags=0;flags<4;++flags){
  reset();options[RSK_SHUFFLE_ENEMY_SOUL]=mode;Actor enemy;enemy.id=id;
  ObjectExtension::GetInstance().values[&enemy]={};
  if(flags&1)souls.insert(RAND_INF_ENEMY_SOUL);if(flags&2)souls.insert(own);
  CK(MegaSoul_ShouldHighlightEnemy(&enemy)==(mode==0||(mode==1&&(flags&1))||(mode==2&&(flags&2))));
  // Death alone must not hide an uncollected drop's indicator.
  ObjectExtension::GetInstance().values[&enemy].deathObserved=true;
  CK(MegaSoul_ShouldHighlightEnemy(&enemy)==(mode==0||(mode==1&&(flags&1))||(mode==2&&(flags&2))));
 }
 for(int id:{ACTOR_EN_ST,ACTOR_EN_SW})for(int mode=0;mode<3;++mode)for(bool shuffle:{false,true})for(bool has:{false,true}){
  reset();options[RSK_SHUFFLE_ENEMY_SOUL]=mode;options[RSK_SHUFFLE_SKULLTULA_SOUL]=shuffle;
  souls.insert(RAND_INF_ENEMY_SOUL);souls.insert(RAND_INF_ENEMY_SOUL_KEESE);if(has)souls.insert(RAND_INF_SKULLTULA_SOUL);
  Actor enemy;enemy.id=id;enemy.params=0;ObjectExtension::GetInstance().values[&enemy]={};
  CK(MegaSoul_ShouldHighlightEnemy(&enemy)==(!shuffle||has));
 }
 for(int bits=0;bits<256;++bits){
  reset();Actor enemy;ObjectExtension::GetInstance().values[&enemy]={};
  rando=bits&1;apSave=bits&2;active=bits&4;reported=bits&8;collected=bits&16;retired=bits&32;
  if(bits&64)enemy.draw=nullptr;if(bits&128)enemy.update=nullptr;
  CK(MegaSoul_ShouldHighlightEnemy(&enemy)==(rando&&apSave&&active&&!reported&&!collected&&!retired&&enemy.draw&&enemy.update));
 }
 reset();Actor enemy;CK(!MegaSoul_ShouldHighlightEnemy(&enemy));CK(!MegaSoul_ShouldHighlightEnemy(nullptr));
 ObjectExtension::GetInstance().values[&enemy]={};
 auto&identity=ObjectExtension::GetInstance().values[&enemy];
 for(int index:{-1,9000,99999}){identity.placementIndex=index;CK(!MegaSoul_ShouldHighlightEnemy(&enemy));}
 identity.placementIndex=0;identity.locationId=-1;CK(!MegaSoul_ShouldHighlightEnemy(&enemy));identity.locationId=9800000;
 // Draw guards, balanced matrix/display scopes, pulse limits and unchanged model.
 Actor_DrawEnemyCheckGlow(nullptr,&enemy);CK(halos==0&&stack==0&&disps==0);
 play.state.gfxCtx=nullptr;Actor_DrawEnemyCheckGlow(&play,&enemy);CK(halos==0);play.state.gfxCtx=&gfx;
 for(int frame=0;frame<256;++frame){play.gameplayFrames=frame;enemy.focus.pos.y=frame-80;
  int before=halos;Actor_DrawEnemyCheckGlow(&play,&enemy);
  CK(halos==before+1&&stack==0&&disps==0&&enemy.draw==drawCallback&&enemy.update==drawCallback);
  CK(lastHeight>=18.0f&&lastHeight<=80.0f&&lastScale>=0.0279f&&lastScale<=0.0421f&&primAlpha>=65&&primAlpha<=135);
 }
 collected=true;int before=halos;Actor_DrawEnemyCheckGlow(&play,&enemy);CK(halos==before);
 collected=false;options[RSK_SHUFFLE_ENEMY_SOUL]=2;souls.insert(RAND_INF_ENEMY_SOUL_WOLFOS);
 Actor_DrawEnemyCheckGlow(&play,&enemy);CK(halos==before); // wrong enemy soul
 souls.insert(RAND_INF_ENEMY_SOUL_KEESE);Actor_DrawEnemyCheckGlow(&play,&enemy);CK(halos==before+1);
 // Exact Zora's River source identities, before Octorok init changes params
 // from 0xFF00 to zero and changes home.y to the surface of the water.
 int riverSpawns=0;
 for(const auto& alias:SohExtreme::kEnemySpawnAliases){
  if(alias.key.scene!=84||alias.key.actorId!=14)continue;
  ++riverSpawns;reset();enemy.id=ACTOR_EN_OKUTA;enemy.params=0;
  enemy.focus.pos.y=enemy.world.pos.y+15.0f;
  int index=SohExtreme::FindExactEnemySpawn(alias.key);CK(index==alias.placement);
  ObjectExtension::GetInstance().values[&enemy]={index,9800000+index,false};
  options[RSK_SHUFFLE_ENEMY_SOUL]=2;
  before=halos;Actor_DrawEnemyCheckGlow(&play,&enemy);CK(halos==before);
  souls.insert(RAND_INF_ENEMY_SOUL_OCTOROK);
  for(int frame=0;frame<256;++frame){
   play.gameplayFrames=frame;before=halos;Actor_DrawEnemyCheckGlow(&play,&enemy);
   CK(halos==before+1);
   // Keep the marker clear of the head throughout the floating/breathing
   // animation; the ordinary 15-unit focus sits inside its opaque model.
   CK(lastHeight-enemy.world.pos.y>=85.0f&&lastScale>=0.0499f);
  }
  enemy.draw=nullptr;before=halos;Actor_DrawEnemyCheckGlow(&play,&enemy);CK(halos==before);
  enemy.draw=drawCallback;Actor_DrawEnemyCheckGlow(&play,&enemy);CK(halos==before+1);
  collected=true;before=halos;Actor_DrawEnemyCheckGlow(&play,&enemy);CK(halos==before);
  collected=false;reported=true;Actor_DrawEnemyCheckGlow(&play,&enemy);CK(halos==before);
 }
 CK(riverSpawns==9);
 std::cout<<checks<<" enemy glow assertions passed\n";
}
'''
src=o/'enemy_glow.cpp';exe=o/'enemy_glow.exe';src.write_text(code,encoding='utf-8')
c=subprocess.run(['cl','/nologo','/std:c++20','/Zc:preprocessor','/EHsc','/MD','/I'+str(r),str(src),'/Fo'+str(o/'enemy_glow.obj'),'/Fe'+str(exe)],capture_output=True,text=True)
t=subprocess.run([str(exe)],capture_output=True,text=True) if c.returncode==0 else None
log=c.stdout+c.stderr+(t.stdout+t.stderr if t else '')
report=dict(passed=c.returncode==0 and t.returncode==0,species=len(pairs),output=log,scope=__doc__)
(o/'glow.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(log);raise SystemExit(not report['passed'])
