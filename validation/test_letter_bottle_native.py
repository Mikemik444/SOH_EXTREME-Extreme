"""Compile native letter-delivery and BottleCount bodies with controlled inventory."""
from pathlib import Path
from run_native_tests import function
from source_index import native_sources
import argparse, json, subprocess
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args(); r = Path(__file__).resolve().parent.parent; o = a.output.resolve(); o.mkdir(parents=True, exist_ok=True)
_, regions = native_sources(r)
event = next(e['condition'] for e in regions['RR_ZORAS_DOMAIN']['events'] if e['event'] == 'LOGIC_DELIVER_RUTOS_LETTER')
native = (r / 'soh/Enhancements/randomizer/logic.cpp').read_text(encoding='utf-8')
code = r'''
#include <cstdint>
#include <iostream>
#include <set>
#include <map>
#include "soh/Enhancements/randomizer/randomizerEnums.h"
enum{SLOT_BOTTLE_1=0,SLOT_BOTTLE_4=3,ITEM_NONE=0,ITEM_LETTER_RUTO=1,ITEM_BIG_POE=2,ITEM_BOTTLE=3,ITEM_MILK_FULL=4};
struct Save{struct{uint8_t items[4]{};}inventory;}save;
struct Option{int v;bool IsNot(int i){return v!=i;}operator bool(){return v!=0;}};
struct Context{std::map<int,int>opts;Option GetOption(int i){return {opts[i]};}}context,*ctx=&context;
struct Logic{bool IsChild=true;std::set<int>items,events;
 bool HasItem(int i){return items.count(i);}bool CanUse(int i){return HasItem(i);}
 bool Get(int e){return events.count(e);}Save*GetSaveContext(){return &save;}
 uint8_t BottleCount();bool HasBottle();}value,*logic=&value;
'''
code += function(native, 'uint8_t Logic::BottleCount()') + '\n' + function(native, 'bool Logic::HasBottle()')
code += '\nbool delivery(){return ' + event + ';}\n'
code += r'''
int checks=0;
#define CK(x) do{++checks;if(!(x)){std::cerr<<"FAIL line "<<__LINE__<<": "<<#x<<"\n";return 1;}}while(0)
int main(){
 for(int bits=0;bits<256;++bits){
  bool child=bits&1,npcShuffle=bits&2,npc=bits&4,speakShuffle=bits&8,speak=bits&16,letter=bits&32,domain=bits&64,open=bits&128;
  value={};context={};save={};value.IsChild=child;
  context.opts[RSK_SHUFFLE_NPC_SOUL]=npcShuffle;context.opts[RSK_SHUFFLE_SPEAK]=speakShuffle;
  context.opts[RSK_ZORAS_FOUNTAIN]=open?RO_ZF_OPEN:RO_ZF_CLOSED;
  if(npc)value.items.insert(RG_NPC_SOUL);if(speak)value.items.insert(RG_SPEAK_ZORA);
  value.items.insert(RG_SPEAK_HYLIAN); // a different language is not enough
  if(letter){value.items.insert(RG_RUTOS_LETTER);save.inventory.items[0]=ITEM_LETTER_RUTO;}
  bool expected=child&&letter&&!open&&(!npcShuffle||npc)&&(!speakShuffle||speak);
  CK(delivery()==expected);CK(value.BottleCount()==0&&!value.HasBottle());
  if(domain&&delivery())value.events.insert(LOGIC_DELIVER_RUTOS_LETTER);
  CK(value.BottleCount()==int(domain&&expected));CK(value.HasBottle()==(domain&&expected));
  save.inventory.items[1]=ITEM_BOTTLE;CK(value.BottleCount()==1+int(domain&&expected));
  save.inventory.items[2]=ITEM_MILK_FULL;CK(value.BottleCount()==2+int(domain&&expected));
  save.inventory.items[3]=ITEM_BIG_POE;CK(value.BottleCount()==2+int(domain&&expected));
 }
 // Actual completed exchange leaves an empty bottle usable independently of
 // the event search and today's actor/route availability.
 value={};save={};save.inventory.items[0]=ITEM_BOTTLE;CK(value.HasBottle());
 std::cout<<checks<<" native bottle assertions passed\n";
}
'''
src = o / 'letter_native.cpp'; exe = o / 'letter_native.exe'; src.write_text(code, encoding='utf-8')
c = subprocess.run(['cl','/nologo','/std:c++20','/Zc:preprocessor','/EHsc','/MD','/I'+str(r),str(src),'/Fo'+str(o/'letter_native.obj'),'/Fe'+str(exe)], capture_output=True, text=True)
t = subprocess.run([str(exe)], capture_output=True, text=True) if c.returncode == 0 else None
log = c.stdout + c.stderr + (t.stdout+t.stderr if t else '')
report = dict(passed=c.returncode==0 and t.returncode==0, output=log, scope=__doc__)
(o/'native.json').write_text(json.dumps(report, indent=2), encoding='utf-8'); print(log); raise SystemExit(not report['passed'])
