"""Compile production approach/pickup predicates with an inventory adapter."""
from pathlib import Path
from run_native_tests import function
import argparse, json, re, subprocess, zipfile
p = argparse.ArgumentParser()
p.add_argument('--output', type=Path, required=True)
p.add_argument('--baseline-zip', type=Path)
a = p.parse_args(); r = Path(__file__).resolve().parent.parent
o = a.output.resolve(); o.mkdir(parents=True, exist_ok=True)

def source(name):
    if a.baseline_zip:
        with zipfile.ZipFile(a.baseline_zip) as z:
            try: return z.read(name).decode('utf-8')
            except KeyError: return subprocess.check_output(['git', 'show', 'HEAD:'+name], cwd=r).decode('utf-8')
    return (r/name).read_text(encoding='utf-8')

def predicate(src, kind, key):
    start = src.index(kind+'('+key)
    start = src.index(',', start)+1
    depth = 0
    for end in range(start, len(src)):
        if src[end] == '(' : depth += 1
        elif src[end] == ')':
            if depth == 0: return src[start:end].strip()
            depth -= 1
    raise ValueError(key)

zr = source('soh/Enhancements/randomizer/location_access/overworld/zoras_river.cpp')
gv = source('soh/Enhancements/randomizer/location_access/overworld/gerudo_valley.cpp')
engine = source('soh/Enhancements/randomizer/logic.cpp')
code = r'''
#include <iostream>
#include "soh/Enhancements/randomizer/randomizerEnums.h"
struct Context {
 bool ladderTrick=false, upperTrick=false;
 bool GetTrickOption(RandomizerTrick t) {
  return t==RT_HOOKSHOT_LADDERS ? ladderTrick : t==RT_ZR_UPPER && upperTrick;
 }
} context;
Context* ctx=&context;
struct Logic {
 bool IsChild,IsAdult,climb,swim,deep,grab,cucco,rock,bomb,boom,hovers,bean,hook;
 bool HasItem(RandomizerGet i){
  return i==RG_CLIMB ? climb : i==RG_BRONZE_SCALE ? swim :
   i==RG_SILVER_SCALE ? deep : i==RG_POWER_BRACELET && grab;
 }
 bool HasAnimalSoul(RandomizerGet){return cucco;}
 bool CanUse(RandomizerGet i){return i==RG_BOOMERANG ? IsChild&&boom :
  i==RG_HOVER_BOOTS ? IsAdult&&hovers : i==RG_HOOKSHOT && IsAdult&&hook;}
 bool BeanPlanted(LogicVal){return bean;}
 bool CanBreakRocks(){return rock&&(bomb||grab);}
 bool CanClimbLadder();
} value;
Logic* logic=&value;
'''
code += function(engine, 'bool Logic::CanClimbLadder()')+'\n'
if 'static bool CanReachZrUpperPath()' in zr:
    code += function(zr, 'static bool CanReachZrUpperPath()')+'\n'
for name, src, kind, key in (
    ('river', zr, 'ENTRANCE', 'RR_ZORAS_RIVER'),
    ('ladder', zr, 'ENTRANCE', 'RR_ZR_ATOP_LADDER'),
    ('heart', zr, 'LOCATION', 'RC_ZR_NEAR_DOMAIN_FREESTANDING_POH'),
    ('valley', gv, 'LOCATION', 'RC_GV_WATERFALL_FREESTANDING_POH')):
    code += f'bool {name}(){{return {predicate(src, kind, key)};}}\n'
code += r'''
int main(){int tested=0,failed=0;
 auto check=[&](bool actual,bool expected){++tested;if(actual!=expected)++failed;};
 for(int child=0;child<2;++child)for(int depth=0;depth<3;++depth)
 for(int bits=0;bits<2048;++bits){
  auto& v=value;v.IsChild=child;v.IsAdult=!child;v.swim=depth>=1;v.deep=depth>=2;
  v.climb=bits&1;v.grab=bits&2;v.cucco=bits&4;v.rock=bits&8;v.bomb=bits&16;
  v.boom=bits&32;v.hovers=bits&64;v.bean=bits&128;v.hook=bits&256;
  ctx->ladderTrick=bits&512;ctx->upperTrick=bits&1024;
  bool front=!child||depth>=2||(v.rock&&(v.bomb||v.grab));
  bool cuccoRoute=child&&v.cucco&&v.grab;
  bool high=(v.climb||(!child&&v.hook&&ctx->ladderTrick))&&(!child||v.swim||cuccoRoute);
  high=high||(!child&&v.bean);
  bool pickup=cuccoRoute||(child&&v.boom)||(!child&&(v.hovers||ctx->upperTrick));
  check(river(),front);
  check(ladder(),high);
  check(heart(),high&&pickup);
  check(valley(),cuccoRoute||(v.climb&&v.swim));
 }
 std::cout<<tested<<" assertions, "<<failed<<" failures\n";return failed?1:0;
}
'''
src=o/'river_hearts.cpp'; exe=o/'river_hearts.exe'; src.write_text(code)
c=subprocess.run(['cl','/nologo','/std:c++20','/Zc:preprocessor','/EHsc','/MD','/I'+str(r),
    str(src),'/Fo'+str(o/'river_hearts.obj'),'/Fe'+str(exe)],capture_output=True,text=True)
t=subprocess.run([str(exe)],capture_output=True,text=True) if c.returncode==0 else None
log=c.stdout+c.stderr+(t.stdout+t.stderr if t else '')
match=re.search(r'(\d+) assertions, (\d+) failures',log)
report=dict(passed=c.returncode==0 and t.returncode==0, checks=int(match[1]) if match else 0,
    failures=int(match[2]) if match else None, output=log,
    limitations='Production predicates and ladder helper compiled with an inventory adapter, not live gameplay.')
(o/'native.json').write_text(json.dumps(report,indent=2));print(log)
raise SystemExit(not report['passed'])
