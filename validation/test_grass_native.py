"""Compile native grass logic against the player's real Strength/carry predicate.

Run in an MSVC x64 developer terminal. Engine inventory/context services are
controlled; the player predicate, Player_GetStrength and logic methods are
extracted from production sources, not independently reimplemented expectations.
"""
from pathlib import Path
from run_native_tests import function
import argparse, json, re, subprocess

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--source-root', type=Path, default=Path(__file__).resolve().parent.parent)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
root = a.source_root.resolve()
out = a.output.resolve()
out.mkdir(parents=True, exist_ok=True)
logic = (root/'soh/Enhancements/randomizer/logic.cpp').read_text(encoding='utf-8')
player = (root/'src/overlays/actors/ovl_player_actor/z_player.c').read_text(encoding='utf-8')
library = (root/'src/code/z_player_lib.c').read_text(encoding='utf-8')
hooks = (root/'soh/Enhancements/randomizer/hook_handlers.cpp').read_text(encoding='utf-8')
carry = function(player, 'void func_8083A0F4(')
predicate = re.search(r'GameInteractor_Should\(VB_PREVENT_STRENGTH,\s*(.*?)\)\) \{', carry, re.S).group(1)
grab_hook = hooks[hooks.index('case VB_PREVENT_STRENGTH:'):hooks.index('case VB_GORONS_CONSIDER_FIRE_TEMPLE_FINISHED:')]
assert 'if (!Flags_GetRandomizerInf(RAND_INF_CAN_GRAB))' in grab_hook and '*should = true;' in grab_hook
bracelet = re.search(r'case RG_GORONS_BRACELET:\s*(return [^;]+;)', function(logic, 'bool Logic::HasItem(')).group(1)
methods = '\n'.join(function(logic, 'bool Logic::'+n+'(') for n in
                    ('CanCutShrubs','CanPickUpGrass','CanCollectGrass','CanBreakRocks'))
code = r'''
#include <cassert>
#include <iostream>
#include <set>
#include "soh/Enhancements/randomizer/randomizerEnums.h"
using s32=int;
int strength=0; bool adult=false, grab=false;
constexpr int UPG_STRENGTH=0, PLAYER_STR_NONE=0, PLAYER_STR_BRACELET=1;
constexpr int VB_PLAYER_MEETS_AGE_REQ=1, VB_PREVENT_STRENGTH=2, LINK_AGE_ADULT=0;
constexpr int ACTOR_EN_KUSA=1, ACTOR_EN_BOMBF=2, ACTOR_EN_ISHI=3;
#define CUR_UPG_VALUE(x) strength
#define LINK_IS_ADULT adult
#define CVAR_ENHANCEMENT(x) x
int CVarGetInteger(const char*,int value){return value;}
bool GameInteractor_Should(int id,bool value,int unused=0){return id==VB_PREVENT_STRENGTH ? value || !grab : value;}
'''+function(library,'s32 Player_GetStrength(')+r'''
bool RuntimeCanCarry(int interactActorId){return !GameInteractor_Should(VB_PREVENT_STRENGTH, '''+predicate+r''');}
struct Context {
 bool grassSoulShuffled=false;
 bool GetOption(RandomizerSettingKey k){return k==RSK_SHUFFLE_GRASS_SOUL && grassSoulShuffled;}
};
class Logic {public:
 Context context; Context*ctx=&context;
 bool soul=false; std::set<RandomizerGet> usable;
 int CurrentUpgrade(int){return strength;}
 bool HasItem(RandomizerGet item){switch(item){
 case RG_GORONS_BRACELET: '''+bracelet+r'''
 case RG_POWER_BRACELET:return grab;
 case RG_GRASS_SOUL:return soul;
 default:return false;}}
 bool CanUse(RandomizerGet item){return usable.count(item)!=0;}
 bool HasExplosives(){return CanUse(RG_BOMB_BAG)||CanUse(RG_BOMBCHU_5);}
 bool CanCutShrubs();bool CanPickUpGrass();bool CanCollectGrass();bool CanBreakRocks();
};
'''+methods+r'''
int main(){
 Logic l; int tests=0;
 for(bool a:{false,true}) for(bool g:{false,true}) for(int s=0;s<=3;++s)
 for(bool shuffled:{false,true}) for(bool soul:{false,true}){
  adult=a;grab=g;strength=s;l.soul=soul;l.context.grassSoulShuffled=shuffled;l.usable.clear();
  bool expected=RuntimeCanCarry(ACTOR_EN_KUSA)&&(!shuffled||soul);
  assert(l.CanPickUpGrass()==expected);++tests;
  assert(l.CanCollectGrass()==expected);++tests;
  assert(l.CanBreakRocks()==RuntimeCanCarry(ACTOR_EN_ISHI));++tests;
  for(auto weapon:{RG_KOKIRI_SWORD,RG_MASTER_SWORD,RG_BIGGORON_SWORD,RG_GIANTS_KNIFE,
                  RG_BOOMERANG,RG_MEGATON_HAMMER,RG_BOMB_BAG,RG_BOMBCHU_5}){
   l.usable={weapon};assert(l.CanCollectGrass()==(!shuffled||soul));++tests;
  }
  // A basic stick does not bypass the native grass-cutting rule.
  l.usable={RG_STICKS};assert(l.CanCollectGrass()==expected);++tests;
 }
 std::cout<<"PASS "<<tests<<" native grass/carry/rock assertions\n";
}
'''
src = out/'grass_native.cpp'
exe = out/'grass_native.exe'
src.write_text(code, encoding='utf-8')
build = subprocess.run(['cl','/nologo','/std:c++20','/Zc:preprocessor','/EHsc','/MD','/I',str(root),
    str(src), '/Fo'+str(out/'grass_native.obj'), '/Fe'+str(exe)], capture_output=True, text=True)
run = subprocess.run([str(exe)], capture_output=True, text=True) if build.returncode == 0 else None
log = build.stdout+build.stderr+(run.stdout+run.stderr if run else '')
passed = build.returncode == 0 and run.returncode == 0
(out/'native.json').write_text(json.dumps(dict(passed=passed, log=log), indent=2), encoding='utf-8')
print(log)
raise SystemExit(0 if passed else 1)
