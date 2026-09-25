"""Generate unconditional standard-layout age and day/night requirements.

Input is the all-location source audit, not location-name guesses. A requirement
is emitted only when it occurs on EVERY native LOCATION alternative. Speech
anchors and automatic starting checks are deliberately excluded.
"""
from pathlib import Path
import argparse,json
from source_index import mandatory_age as mandatory, mandatory_time
p=argparse.ArgumentParser();p.add_argument('--audit',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
data=json.loads(a.audit.read_text());rows={}
for r in data['rows']:
 if r['kind']!='fork':continue
 ds=[d for d in r['native_sources'] if '_MQ_' not in d['region']]
 if not ds:continue
 gates=set.intersection(*(mandatory(d['condition']) for d in ds))
 if not gates:continue
 assert len(gates)==1,(r['rc'],gates)
 rows[r['rc']]='child' if 'logic->IsChild' in gates else 'adult'
out='''# Generated from standard-layout native LOCATION expressions.
# These are necessary age/time gates, NOT complete room/interaction rules.
# A phase is listed only when every native alternative requires that phase.
# Reproduce with validation/generate_fork_age_table.py and the source audit.

FORK_LOCATION_AGES = {
'''
for rc,age in sorted(rows.items()):out+=f'    {rc!r}: {age!r},\n'
out+='}\n\nFORK_LOCATION_TIMES = {\n'
times={}
for r in data['rows']:
 if r['kind']!='fork':continue
 ds=[d for d in r['native_sources'] if '_MQ_' not in d['region']]
 if not ds:continue
 gates=set.intersection(*(mandatory_time(d['condition']) for d in ds))
 if not gates:continue
 assert len(gates)==1,(r['rc'],gates)
 times[r['rc']]='day' if 'logic->AtDay' in gates else 'night'
for rc,phase in sorted(times.items()):out+=f'    {rc!r}: {phase!r},\n'
out+='}\n';a.output.write_text(out);print('Age gates:',len(rows),'Time gates:',len(times))
