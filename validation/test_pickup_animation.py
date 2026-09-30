"""Compile the engine's real pickup-animation decision with controlled actor state.

Tests Fast Pickup Text, obtained items, randomizer and AP boundaries. This is a
compiled branch test, not a rendered in-game animation test.
"""
from pathlib import Path
import argparse,json,subprocess
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
p.add_argument('--source-root',type=Path,default=Path(__file__).resolve().parents[1]);a=p.parse_args()
r=a.source_root;o=a.output.resolve();o.mkdir(parents=True,exist_ok=True)
s=(r/'src/overlays/actors/ovl_player_actor/z_player.c').read_text(encoding='utf-8')
start=s.index('                uint8_t showItemCutscene =')
end=s.index('                    Player_DetachHeldActor',start)
decision=s[start:end]+'return true;\n} return false;'
code=r'''
#include <cstdint>
#include <iostream>
enum {SCENE_BOMBCHU_BOWLING_ALLEY,MOD_NONE,MOD_RANDOMIZER,ITEM_NONE,
 ACTOR_EN_ITEM00,ACTOR_EN_KAREBABA,ACTOR_EN_DEKUBABA,ACTOR_PLAYER,
 ITEM00_HEART_PIECE,ITEM00_SMALL_KEY,ITEM00_SOH_GIVE_ITEM_ENTRY,ITEM00_SOH_GIVE_ITEM_ENTRY_GI,ITEM00_SOH_DUMMY,
 ITEM_CATEGORY_MAJOR,ITEM_CATEGORY_SMALL_KEY,ITEM_CATEGORY_BOSS_KEY,ITEM_CATEGORY_JUNK,ITEM_CATEGORY_HEALTH,ITEM_CATEGORY_LESSER};
bool apSave=true,rando=true,fast=true,obtained=true;
#define IS_RANDO rando
#define CVAR_ENHANCEMENT(x) x
bool Archipelago_IsCurrentSaveFile(){return apSave;}
int CVarGetInteger(const char*,int){return fast;}
int Item_CheckObtainability(int){return obtained?0:ITEM_NONE;}
struct Actor{int id,params;};struct Play{int sceneNum=-1;} game;
struct Entry{int modIndex=MOD_RANDOMIZER,itemId=0,getItemCategory=ITEM_CATEGORY_MAJOR;};
bool ShouldAnimate(Actor*interactedActor,Entry giEntry){auto*play=&game;
'''+decision+r'''
}
int main(){int checks=0,failed=0;
for(bool ap:{false,true})for(bool f:{false,true})for(bool own:{false,true})for(int mod:{MOD_NONE,MOD_RANDOMIZER})
for(int actor:{ACTOR_EN_ITEM00,ACTOR_EN_KAREBABA,ACTOR_EN_DEKUBABA,ACTOR_PLAYER})
for(int cat:{ITEM_CATEGORY_MAJOR,ITEM_CATEGORY_SMALL_KEY,ITEM_CATEGORY_BOSS_KEY,ITEM_CATEGORY_JUNK,ITEM_CATEGORY_HEALTH,ITEM_CATEGORY_LESSER}){
 apSave=ap;fast=f;obtained=own;Actor source{actor,ITEM00_SOH_DUMMY};
 bool important=cat==ITEM_CATEGORY_MAJOR||cat==ITEM_CATEGORY_SMALL_KEY||cat==ITEM_CATEGORY_BOSS_KEY;
 bool drop=actor!=ACTOR_PLAYER;
 bool expected=(ap&&important)||(!drop||(!f&&!(own&&mod==MOD_NONE)));
 ++checks;if(ShouldAnimate(&source,{mod,0,cat})!=expected)++failed;
}
std::cout<<checks<<" checks; "<<failed<<" failures\n";return failed?1:0;}
'''
src=o/'pickup_animation.cpp';src.write_text(code);exe=o/'pickup_animation.exe'
c=subprocess.run(['cl','/nologo','/std:c++20','/EHsc',str(src),'/Fo'+str(o/'pickup_animation.obj'),'/Fe'+str(exe)],capture_output=True,text=True)
t=subprocess.run([str(exe)],capture_output=True,text=True) if not c.returncode else None
log=c.stdout+c.stderr+(t.stdout+t.stderr if t else '')
passed=c.returncode==0 and t.returncode==0
(o/'animation.json').write_text(json.dumps(dict(passed=passed,scope=__doc__,output=log),indent=2));print(log)
raise SystemExit(not passed)
