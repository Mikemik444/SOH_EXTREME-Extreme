"""Compile production ledge/bridge/crate predicates; audit every native soul entry."""
from pathlib import Path
from run_native_tests import function
from source_index import body_at, split_top
import argparse, json, re, subprocess
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--source-root',type=Path,default=Path(__file__).resolve().parent.parent)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args();root=a.source_root.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
logic=(root/'soh/Enhancements/randomizer/logic.cpp').read_text(encoding='utf-8')
gv=(root/'soh/Enhancements/randomizer/location_access/overworld/gerudo_valley.cpp').read_text(encoding='utf-8')
hf=(root/'soh/Enhancements/randomizer/location_access/overworld/hyrule_field.cpp').read_text(encoding='utf-8')
ledge=next(line for line in gv.splitlines() if 'ENTRANCE(RR_GV_CRATE_LEDGE' in line)
ledge=body_at(ledge,ledge.index('(')+1)[0];ledge=split_top(ledge)[1]
bridge=[]
for line in hf.splitlines():
    if 'LOCATION(RC_HF_WONDER_BRIDGE_' in line:bridge.append(split_top(body_at(line,line.index('(')+1)[0])[0:2])
assert len(bridge)==3
code=r'''
#include <cassert>
#include <iostream>
#include <set>
#include "soh/Enhancements/randomizer/randomizerEnums.h"
struct Context {std::set<int> options;bool GetOption(int i){return options.count(i)!=0;}} context;
struct Logic {
 Context*ctx=&context;bool IsChild=true,IsAdult=false,AtDay=true;
 std::set<int> items;
 bool HasItem(int i){return items.count(i)!=0;}
 bool HasAnimalSoul(int){return items.count(RG_ANIMAL_SOUL_CUCCO)!=0;}
 bool CanUse(int i){return HasItem(i)&&((i==RG_MEGATON_HAMMER||i==RG_LONGSHOT)?IsAdult:true);}
 bool HasExplosives(){return HasItem(RG_BOMB_BAG)||HasItem(RG_BOMBCHU_5);}
 bool CanJumpslash(){return IsChild?(HasItem(RG_KOKIRI_SWORD)||HasItem(RG_STICKS)):(HasItem(RG_MASTER_SWORD)||HasItem(RG_MEGATON_HAMMER));}
 bool CanBreakCrates();bool CanBreakSmallCrates();
} value;Logic*logic=&value;
'''
code += function(logic,'bool Logic::CanBreakCrates(')+'\n'+function(logic,'bool Logic::CanBreakSmallCrates(')
code += '\nbool ledge(){return '+ledge+';}\n'
for name,expr in bridge:code+='bool check_'+name+'(){return '+expr+';}\n'
code+='int main(){int checks=0;\n'
code+=r'''
 for(int mask=0;mask<32;++mask){
  logic->IsAdult=mask&1;logic->IsChild=!logic->IsAdult;logic->AtDay=mask&2;logic->items.clear();
  if(mask&4)logic->items.insert(RG_POWER_BRACELET);
  if(mask&8)logic->items.insert(RG_ANIMAL_SOUL_CUCCO);
  if(mask&16)logic->items.insert(RG_LONGSHOT);
  assert(ledge()==((!(mask&1)&&(mask&4)&&(mask&8))||((mask&1)&&(mask&16))));++checks;
'''
for name,_ in bridge:code+=f'assert(check_{name}()==(!(mask&1)&&bool(mask&2)));++checks;\n'
code+='}\n'
code+=r'''
 for(bool soulShuffle:{false,true})for(bool rollShuffle:{false,true})for(bool adult:{false,true})for(bool soul:{false,true}){
  logic->IsAdult=adult;logic->IsChild=!adult;context.options.clear();
  if(soulShuffle)context.options.insert(RSK_SHUFFLE_CRATE_SOUL);
  if(rollShuffle)context.options.insert(RSK_SHUFFLE_ROLL);
  for(auto tool:{RG_NONE,RG_ROLL,RG_BOMB_BAG,RG_BOMBCHU_5,RG_POWER_BRACELET,RG_KOKIRI_SWORD,RG_STICKS,RG_MEGATON_HAMMER}){
   logic->items={tool};if(soul)logic->items.insert(RG_CRATE_SOUL);
   bool exists=!soulShuffle||soul;
   bool large=!rollShuffle||tool==RG_ROLL||tool==RG_BOMB_BAG||tool==RG_BOMBCHU_5||(adult&&tool==RG_MEGATON_HAMMER);
   bool small=large||tool==RG_POWER_BRACELET||(!adult&&(tool==RG_KOKIRI_SWORD||tool==RG_STICKS));
   assert(logic->CanBreakCrates()==(exists&&large));++checks;
   assert(logic->CanBreakSmallCrates()==(exists&&small));++checks;
  }
 }
 std::cout<<"PASS "<<checks<<" native route/action assertions\n";
}
'''
src=out/'native_routes.cpp';exe=out/'native_routes.exe';src.write_text(code,encoding='utf-8')
build=subprocess.run(['cl','/nologo','/std:c++20','/Zc:preprocessor','/EHsc','/MD','/I',str(root),str(src),
    '/Fo'+str(out/'native_routes.obj'),'/Fe'+str(exe)],capture_output=True,text=True)
run=subprocess.run([str(exe)],capture_output=True,text=True) if build.returncode==0 else None
log=build.stdout+build.stderr+(run.stdout+run.stderr if run else '')
items=(root/'soh/Enhancements/randomizer/item_list.cpp').read_text(encoding='utf-8');souls=[]
for m in re.finditer(r'itemTable\[(RG_\w*SOUL\w*)\]\s*=\s*Item\(',items):
    args=split_top(body_at(items,m.end())[0])
    souls.append(dict(item=m[1],advancement=args[4],animation=args[12],category=args[13],
        passed=args[4]=='true' and args[12]=='CHEST_ANIM_LONG' and args[13]=='ITEM_CATEGORY_MAJOR'))
assert len(souls)>60, len(souls)
passed=build.returncode==0 and run.returncode==0 and all(s['passed'] for s in souls)
(out/'native.json').write_text(json.dumps(dict(passed=passed,log=log,native_assertions=384,
    soul_count=len(souls),souls=souls,scope=__doc__),indent=2),encoding='utf-8')
print(log);print('Soul metadata',len(souls),'failures',sum(not s['passed'] for s in souls))
raise SystemExit(0 if passed else 1)
