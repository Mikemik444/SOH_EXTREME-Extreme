"""Compile the eight production predicates and native Silver/Golden Scale cases."""
from pathlib import Path
import argparse, json, re, subprocess, zipfile
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
p.add_argument('--baseline-zip',type=Path)
a=p.parse_args();r=Path(__file__).resolve().parent.parent
o=a.output.resolve();o.mkdir(parents=True,exist_ok=True)
def source(name):
    if a.baseline_zip:
        with zipfile.ZipFile(a.baseline_zip) as z:
            try:return z.read(name).decode('utf-8')
            except KeyError:return subprocess.check_output(['git','show','HEAD:'+name],cwd=r).decode('utf-8')
    return (r/name).read_text(encoding='utf-8')
lw=source('soh/Enhancements/randomizer/location_access/overworld/lost_woods.cpp')
logic=source('soh/Enhancements/randomizer/logic.cpp')
expressions=re.findall(r'LOCATION\(RC_LW_SHORTCUT_RUPEE_\d,\s*(.*?)\),',lw)
assert len(expressions)==8
scale_cases=re.search(r'case RG_SILVER_SCALE:(.*?)// Silver Rupees',logic,re.S)[0].split('// Silver Rupees')[0]
code=r'''
#include <iostream>
#include "soh/Enhancements/randomizer/randomizerEnums.h"
constexpr int UPG_SCALE=0;
struct Logic {
 bool IsChild,swim;int receipts;
 int CurrentUpgrade(int){return receipts>0?receipts-1:0;}
 bool HasItem(RandomizerGet item){
  if(item==RG_BRONZE_SCALE)return swim;
  switch(item){
'''+scale_cases+r'''
   default:return false;
  }
 }
} value;
Logic* logic=&value;
'''
for i,expr in enumerate(expressions):code+=f'bool check{i}(){{return {expr};}}\n'
code+='bool (*checks[])()={'+','.join(f'check{i}' for i in range(8))+'};\n'
code+=r'''
int main(){int tested=0,failed=0;
 for(int child=0;child<2;++child)for(int swim=0;swim<2;++swim)for(int n=0;n<4;++n){
  logic->IsChild=child;logic->swim=swim;logic->receipts=n;
  for(auto check:checks){++tested;if(check()!=bool(child&&swim&&n>=2))++failed;}
 }
 std::cout<<tested<<" assertions, "<<failed<<" failures\n";return failed?1:0;
}
'''
src=o/'lw_dive.cpp';exe=o/'lw_dive.exe';src.write_text(code)
c=subprocess.run(['cl','/nologo','/std:c++20','/Zc:preprocessor','/EHsc','/MD','/I'+str(r),
    str(src),'/Fo'+str(o/'lw_dive.obj'),'/Fe'+str(exe)],capture_output=True,text=True)
t=subprocess.run([str(exe)],capture_output=True,text=True) if c.returncode==0 else None
log=c.stdout+c.stderr+(t.stdout+t.stderr if t else '')
match=re.search(r'(\d+) assertions, (\d+) failures',log)
report=dict(passed=c.returncode==0 and t.returncode==0,checks=int(match[1]) if match else 0,
    failures=int(match[2]) if match else None,output=log,
    limitations='Production predicates and upgrade switch cases compiled with an inventory adapter, not live gameplay.')
(o/'native.json').write_text(json.dumps(report,indent=2));print(log)
raise SystemExit(not report['passed'])
