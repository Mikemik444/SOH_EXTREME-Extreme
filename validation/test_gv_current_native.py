"""Compile native encounter gates and catalogue; isolate lower-stream footing."""
from pathlib import Path
from run_native_tests import function
import argparse,json,re,subprocess,zipfile
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
p.add_argument('--baseline-source-zip',type=Path);a=p.parse_args()
r=Path(__file__).resolve().parent.parent;o=a.output.resolve();o.mkdir(parents=True,exist_ok=True)
finder='soh/Enhancements/randomizer/randomizer_check_tracker.cpp'
table='soh/Network/Archipelago/ArchipelagoEnemyFinderMap.inc'
if a.baseline_source_zip:
    with zipfile.ZipFile(a.baseline_source_zip) as z:
        s=z.read(finder).decode();entries=z.read(table).decode()
else:
    s=(r/finder).read_text();entries=(r/table).read_text()
enums=s[s.index('enum EnemyFinderCombat'):s.index('// NPC Speech checks are separate AP locations.')]
enums=enums.replace('#include "'+table+'"',entries)
gate=function(s,'static bool EnemyFinderEncounterGate(')
code=r'''
#include <cstdint>
#include <iostream>
#include "soh/Enhancements/randomizer/randomizerEnums.h"
namespace Rando { struct Logic {
 bool IsAdult=true,AtNight=true,irons=false,hook=false,swim=false;
 bool Get(int){return true;}
 bool HasItem(RandomizerGet i){return i==RG_BRONZE_SCALE?swim:true;}
 // Mirror native CanUse: Iron Boots require Swim in this fork.
 bool CanUse(RandomizerGet i){return i==RG_IRON_BOOTS?IsAdult&&irons&&swim:i==RG_HOOKSHOT||i==RG_LONGSHOT?IsAdult&&hook:true;}
 bool HasFireSourceWithTorch(){return true;}
}; }
bool EnemyFinderMelee(Rando::Logic*){return true;}
'''+enums+gate+r'''
int main(){int checks=0,targets=0;Rando::Logic l;
 for(const auto&e:kEnemyDefeatFinderEntries){
  bool lower=e.locationId==9800681||e.locationId==9800683;
  bool upper=e.locationId==9800682||e.locationId==9800684||e.locationId==9800685;
  if(!lower&&!upper)continue;++targets;
  for(int m=0;m<16;++m){l.IsAdult=m&1;l.irons=m&2;l.hook=m&4;l.swim=m&8;
   bool expected=lower?(l.IsAdult&&l.irons&&l.hook&&l.swim):l.swim;
   ++checks;if(EnemyFinderEncounterGate(&l,e)!=expected){std::cerr<<"FAIL "<<e.locationId<<" mask "<<m;return 1;}
  }
 }
 if(targets!=5)return 2;std::cout<<checks<<" native GV current assertions passed\n";
}
'''
src=o/'gv.cpp';exe=o/'gv.exe';src.write_text(code)
c=subprocess.run(['cl','/nologo','/std:c++20','/Zc:preprocessor','/EHsc','/MD','/I'+str(r),str(src),'/Fo'+str(o/'gv.obj'),'/Fe'+str(exe)],capture_output=True,text=True)
t=subprocess.run([str(exe)],capture_output=True,text=True) if c.returncode==0 else None
log=c.stdout+c.stderr+(t.stdout+t.stderr if t else '')
report=dict(passed=c.returncode==0 and t.returncode==0,assertions=80,output=log)
(o/'native.json').write_text(json.dumps(report,indent=2));print(log);raise SystemExit(not report['passed'])
