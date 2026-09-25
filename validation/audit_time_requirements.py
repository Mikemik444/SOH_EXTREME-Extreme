"""Direct source AtDay/AtNight requirements with the opposite frozen start.

All other real items/events are retained. Flow of Time is removed through the
world's actual receipt-removal path, so a historical cycle cannot bypass the
current frozen-phase requirement. This is not a clock/collision playtest.
"""
from pathlib import Path
import argparse,json
from run_case import setup,BOOTSTRAP
from source_index import split_top,body_at
from location_source_audit import collect

from source_index import mandatory_time as mandatory

if __name__=='__main__':
 p=argparse.ArgumentParser(parents=[BOOTSTRAP]);p.add_argument('--source-root',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args();tests=[]
 for phase in ('day','night'):
  m=setup(17176,overrides={'frozen_starting_time':phase,'shuffle_flow_of_time':True,'boss_key_shuffle':'anywhere'},stop_before='pre_fill');w=m.worlds[1];full=m.get_all_state(False);state=full.copy()
  while state.count('Flow of Time',1):state.remove(w.create_item('Flow of Time'))
  rows,_=collect(a.source_root,w)
  for row in rows:
   defs=[d for d in row['native_sources']if '_MQ_' not in d['region']]
   if row['kind']not in ('stock','fork')or not defs:continue
   gates=set.intersection(*(mandatory(d['condition'])for d in defs))
   for gate in gates:
    need='day'if gate=='logic->AtDay'else 'night'
    if phase==need:continue
    l=w.get_location(row['name']);tests.append(dict(id=row['id'],name=row['name'],frozen=phase,required=need,passed=not l.can_reach(state),source=defs))
 out=dict(scope=__doc__,assertions=len(tests),failures=sum(not t['passed']for t in tests),tests=tests)
 a.report.write_text(json.dumps(out,indent=2));print({k:v for k,v in out.items()if k!='tests'})
 for t in tests:
  if not t['passed']:print('FAIL',t['name'],t['frozen'],t['required'])
 raise SystemExit(bool(out['failures']))
