"""Adult Gerudo Valley Wonder remains reachable in a child-start world."""
from run_case import setup,BOOTSTRAP
from worlds.soh_extreme._vendor_oot_soh.Enums import Ages
from pathlib import Path
import argparse,json
p=argparse.ArgumentParser(parents=[BOOTSTRAP]);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
m=setup(290934,stop_before='pre_fill');w=m.worlds[1]
loc=w.get_location('EXTREME Gv Wonder Upper Waterfall');tests=[]
def ck(name,actual,expected):
    tests.append(dict(test=name,actual=actual,expected=expected,passed=actual==expected))
    assert actual==expected,tests[-1]
ck('physical parent',loc.parent_region.name,'Gerudo Valley')
ck('stable network ID',loc.address,9700247)
s=m.get_all_state(False)
ck('all inventory reaches adult pickup from child start',loc.can_reach(s),True)
for age in (Ages.CHILD,Ages.ADULT):
    copy=s.copy();copy._soh_extreme_age[1]=age
    ck('pickup age '+str(age),loc.access_rule(copy),age==Ages.ADULT)
copy=s.copy();copy.remove(w.create_item('Climb'))
ck('Climb is still required',loc.can_reach(copy),False)
a.report.parent.mkdir(parents=True,exist_ok=True)
a.report.write_text(json.dumps(dict(passed=True,checks=len(tests),tests=tests),indent=2),encoding='utf-8')
print('PASS',len(tests),'waterfall region/age assertions')
