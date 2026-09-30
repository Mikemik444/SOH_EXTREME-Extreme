"""Compile the native Skull Kid interaction gate across soul modes/behaviors."""
from pathlib import Path
from run_native_tests import function
import argparse, json, subprocess
p = argparse.ArgumentParser(); p.add_argument('--output', type=Path, required=True)
a = p.parse_args(); out = a.output.resolve(); out.mkdir(parents=True, exist_ok=True)
r = Path(__file__).resolve().parents[1]
s = (r/'soh/Enhancements/randomizer/location_access/overworld/lost_woods.cpp').read_text()
code = r'''
#include <cassert>
#include <iostream>
#include <map>
#include <set>
#include "soh/Enhancements/randomizer/randomizerEnums.h"
struct Option {int value=0; int Get(){return value;} operator bool(){return value!=0;}};
namespace Rando {struct Context {
 std::map<int,Option> options;
 Option GetOption(int key){return options[key];}
 static Context* GetInstance(){static Context c;return &c;}
};}
struct Logic {std::set<int> owned;bool HasItem(int item){return owned.count(item)!=0;}} value;
Logic* logic=&value;
''' + function(s, 'static bool CanInteractWithSkullKid(') + r'''
int main(){int tests=0;auto ctx=Rando::Context::GetInstance();
for(int mode=0;mode<3;++mode) for(int behavior=0;behavior<2;++behavior)
for(int npc=0;npc<2;++npc) for(int speech=0;speech<2;++speech)
for(int mask=0;mask<16;++mask){
 ctx->options[RSK_SHUFFLE_ENEMY_SOUL].value=mode;
 ctx->options[RSK_ENEMY_SOUL_BEHAVIOR].value=behavior;
 ctx->options[RSK_SHUFFLE_NPC_SOUL].value=npc;
 ctx->options[RSK_SHUFFLE_SPEAK].value=speech;
 logic->owned.clear();
 if(mask&1)logic->owned.insert(RG_NPC_SOUL);
 if(mask&2)logic->owned.insert(RG_SPEAK_KOKIRI);
 if(mask&4)logic->owned.insert(RG_ENEMY_SOUL_SKULL_KID);
 if(mask&8)logic->owned.insert(RG_ENEMY_SOUL);
 bool expected=(!npc || (mask&1)) && (!speech || (mask&2)) &&
   (!mode || behavior || (mask&(mode==1?8:4)));
 assert(CanInteractWithSkullKid()==expected);++tests;
}
std::cout<<"PASS "<<tests<<" native Skull Kid assertions\n";}
'''
src=out/'skull_native.cpp';exe=out/'skull_native.exe';src.write_text(code)
build=subprocess.run(['cl','/nologo','/std:c++20','/Zc:preprocessor','/EHsc','/MD','/I',str(r),
    str(src),'/Fo'+str(out/'skull_native.obj'),'/Fe'+str(exe)],capture_output=True,text=True)
run=subprocess.run([str(exe)],capture_output=True,text=True) if build.returncode==0 else None
log=build.stdout+build.stderr+(run.stdout+run.stderr if run else '')
passed=build.returncode==0 and run.returncode==0
(out/'skull-native.json').write_text(json.dumps(dict(passed=passed,assertions=384,log=log),indent=2))
print(log);raise SystemExit(not passed)
