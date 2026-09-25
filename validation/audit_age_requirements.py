"""Necessary age restrictions explicitly present on every native LOCATION branch.

Uses the real Location.can_reach for one forced age, not SohLocation's either-age
wrapper. This does not infer ages from names or certify physical traversal.
"""
from pathlib import Path
import argparse,json,collections
from run_case import setup,BOOTSTRAP
from BaseClasses import Location
from source_index import split_top,body_at
from location_source_audit import collect
from worlds.soh_extreme._vendor_oot_soh.Enums import Ages

from source_index import mandatory_age as mandatory

if __name__=='__main__':
 p=argparse.ArgumentParser(parents=[BOOTSTRAP]);p.add_argument('--source-root',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
 m=setup(1717,overrides={'boss_key_shuffle':'anywhere'},stop_before='pre_fill');w=m.worlds[1];s=m.get_all_state(False)
 rows,_=collect(a.source_root,w);tests=[]
 for row in rows:
  defs=[d for d in row['native_sources'] if '_MQ_' not in d['region']]
  if row['kind'] not in ('stock','fork') or not defs:continue
  ages=set.intersection(*(mandatory(d['condition']) for d in defs))
  for age in ages:
   s._soh_age[w.player]=Ages.ADULT if age=='logic->IsChild' else Ages.CHILD
   loc=w.get_location(row['name']);got=Location.can_reach(loc,s)
   tests.append(dict(id=row['id'],name=loc.name,native_age=age,test_age=str(s._soh_age[w.player]),passed=not got,source=defs))
 out=dict(scope=__doc__,assertions=len(tests),failures=sum(not r['passed'] for r in tests),tests=tests)
 a.report.write_text(json.dumps(out,indent=2));print({k:v for k,v in out.items() if k!='tests'})
 for r in tests:
  if not r['passed']:print('FAIL',r['id'],r['name'],r['native_age'])
 raise SystemExit(bool(out['failures']))
