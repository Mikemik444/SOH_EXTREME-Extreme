"""Compile the production DC wall predicate and verify its soul/weapon truth table."""
from pathlib import Path
import argparse
import json
import re
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--compiler', default='cl')
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
out = args.output.resolve()
out.mkdir(parents=True, exist_ok=True)
logic = (root / 'soh/Enhancements/randomizer/logic.cpp').read_text(encoding='utf-8')
function = re.search(r'bool Logic::CanDetonateBabyDodongo\(\) \{.*?^\}', logic, re.S | re.M)[0]
source = (root / 'soh/Enhancements/randomizer/location_access/dungeons/dodongos_cavern.cpp').read_text(encoding='utf-8')
expression = re.search(r'ENTRANCE\(RR_DODONGOS_CAVERN_SE_ROOM,\s*(.*?)\),', source)[1]
graph = json.loads((root / 'archipelago/soh_extreme/EnemyRoomGraph.json').read_text())
assert next(e['condition'] for e in graph['RR_DODONGOS_CAVERN_SE_CORRIDOR']['exits']
            if e['target'] == 'RR_DODONGOS_CAVERN_SE_ROOM') == expression

# This actor uses preset 4, not the generic "damage or stun" weapon list.
actor = (root / 'src/overlays/actors/ovl_En_Dodojr/z_en_dodojr.c').read_text()
assert 'DamageTable_Get(4)' in actor
tables = (root / 'src/code/z_collision_btltbls.c').read_text()
table = tables.split('// 4 Used by En_Dodojr', 1)[1].split('// 5', 1)[0]
damage = {name.strip(): (int(amount, 0), int(effect, 0)) for name, amount, effect in
          re.findall(r'/\*\s*(.*?)\s*\*/\s*DMG_ENTRY\((\w+),\s*(\w+)\)', table)}
for name in ('Deku stick', 'Slingshot', 'Explosive', 'Boomerang', 'Normal arrow',
             'Hammer swing', 'Hookshot', 'Kokiri sword', 'Master sword'):
    assert damage[name][0] > 0 and damage[name][1] == 0, name
assert damage['Deku nut'] == (0, 1)
assert damage['Fire magic'][0] == 0

code = r'''
#include <iostream>
enum { RG_MEGATON_HAMMER, RG_FAIRY_SLINGSHOT, RG_FAIRY_BOW, RG_BOOMERANG,
       RG_HOOKSHOT, RG_ENEMY_SOUL, RG_ENEMY_SOUL_BABY_DODONGO, RG_POT_SOUL, RG_POWER_BRACELET };
enum { RSK_SHUFFLE_ENEMY_SOUL, RSK_SHUFFLE_POT_SOUL };
enum { BOMB=1, HAMMER=2, SWORD=4, SLING=8, BOW=16, RANG=32, HOOK=64,
       SHARED=128, BABY=256, POT=512, GRAB=1024, SHIELD=2048, DAMAGE=4096, POT_SHUFFLE=8192 };
struct Option { int value; int Get() const { return value; } operator bool() const {return value != 0;} };
struct Context {
    int mode=0; unsigned bits=0;
    Option GetOption(int key) const { return {key == RSK_SHUFFLE_ENEMY_SOUL ? mode : int(bool(bits & POT_SHUFFLE))}; }
} context;
auto* ctx=&context;
struct Logic {
    bool adult=false;
    bool HasItem(int item) const {
        unsigned bit=item==RG_ENEMY_SOUL?SHARED:item==RG_ENEMY_SOUL_BABY_DODONGO?BABY:
                     item==RG_POT_SOUL?POT:item==RG_POWER_BRACELET?GRAB:0;
        return context.bits & bit;
    }
    bool CanUse(int item) const {
        switch(item) {
          case RG_MEGATON_HAMMER:return adult && (context.bits & HAMMER);
          case RG_FAIRY_SLINGSHOT:return !adult && (context.bits & SLING);
          case RG_FAIRY_BOW:return adult && (context.bits & BOW);
          case RG_BOOMERANG:return !adult && (context.bits & RANG);
          case RG_HOOKSHOT:return adult && (context.bits & HOOK);
        }
        return false;
    }
    bool CanJumpslash() const {return (context.bits & SWORD) || CanUse(RG_MEGATON_HAMMER);}
    bool HasExplosives() const {return context.bits & BOMB;}
    bool TakeDamage() const {return context.bits & DAMAGE;}
    bool CanShield() const {return context.bits & SHIELD;}
    bool CanBreakMudWalls() const {return HasExplosives() || CanUse(RG_MEGATON_HAMMER);}
    bool CanDetonateBabyDodongo();
} value;
auto* logic=&value;
template<class F> bool AnyAgeTime(F f) {return f();}
''' + function + '\nbool wall() { return ' + expression + r'''; }
int main() {
    int checked=0;
    for(int mode=0;mode<3;++mode) for(bool adult:{false,true}) for(unsigned bits=0;bits<16384;++bits) {
        context={mode,bits}; value.adult=adult;
        bool soul=mode==0 || (mode==1 ? (bits&SHARED) : (bits&BABY));
        bool weapon=(bits&(BOMB|SWORD)) || (adult ? (bits&(HAMMER|BOW|HOOK)) : (bits&(SLING|RANG)));
        bool pot=(!(bits&POT_SHUFFLE)||(bits&POT)) && (bits&GRAB) && (bits&SHIELD) && (bits&DAMAGE);
        bool expected=(bits&BOMB) || (adult&&(bits&HAMMER)) || (soul&&(weapon||pot));
        ++checked;
        if(wall()!=expected) {
            std::cerr<<"Failed mode="<<mode<<" adult="<<adult<<" inventory="<<bits<<"\n";
            return 1;
        }
    }
    std::cout<<checked<<" native DC wall cases passed\n";
}
'''
cpp = out / 'dc_keese.cpp'
cpp.write_text(code, encoding='utf-8')
exe = out / 'dc_keese.exe'
if Path(args.compiler).stem.lower() == 'cl':
    command = [args.compiler, '/nologo', '/EHsc', '/std:c++20', str(cpp),
               '/Fo' + str(out / 'dc_keese.obj'), '/Fe' + str(exe)]
else:
    command = [args.compiler, '-std=c++20', str(cpp), '-o', str(exe)]
compile_result = subprocess.run(command, capture_output=True, text=True, timeout=60)
run = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30) if compile_result.returncode == 0 else None
report = dict(passed=compile_result.returncode == 0 and run.returncode == 0,
              compile_exit=compile_result.returncode, run_exit=run.returncode if run else None,
              output=compile_result.stdout + compile_result.stderr + (run.stdout + run.stderr if run else ''),
              scope=__doc__)
(out / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(report['output'])
raise SystemExit(not report['passed'])
