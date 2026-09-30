"""Compare every active chest with native actor size under real AP/UT receipts."""
from run_case import setup, BOOTSTRAP
from ut_harness import tracker
from generate_chest_contract import collect_chests
from worlds.soh_extreme.PhysicalChestTypes import CHEST_TYPES_BY_AP_ID
from pathlib import Path
import argparse, json
p=argparse.ArgumentParser(parents=[BOOTSTRAP]);p.add_argument('--ut-core',type=Path,required=True)
p.add_argument('--report',type=Path,required=True);a=p.parse_args();tests=[]
def ck(name,value,expected=True):tests.append(dict(test=name,actual=value,expected=expected,passed=value==expected))
m=setup(291030,overrides={'shuffle_open_chest':'progressive','shuffle_chest_minigame':True})
w=m.worlds[1];evaluate=tracker(w,a.ut_core)
rows=collect_chests();active={l.address:l for l in w.get_locations() if type(l.address)is int}
ck('production chest types match every native identity',CHEST_TYPES_BY_AP_ID,{i:r['type'] for i,r in rows.items()})
items=[*m.itempool,*[l.item for l in active.values() if l.item]]
base=[i.name for i in items if i.name in w.item_name_to_id and i.name!='Open Chest']
for count in (0,1,2):
    result=evaluate(base+['Open Chest']*count)
    for address,row in rows.items():
        if address not in active:continue
        loc=active[address];minimum=2 if row['large'] else 1
        # Parent routes may need a different chest first; never demand access
        # merely because this local chest ability exists. Full inventory is a control.
        if count<minimum or count==2:
            ck(f'{count} receipts/AP {loc.name}',loc.can_reach(result.state),count==2)
            ck(f'{count} receipts/UT {loc.name}',loc.name in result.in_logic_locations,count==2)
    ck(f'{count} receipts: talking to Chest Game owner needs no chest ability',
       'NPC Speech: Treasure Chest Game Owner' in result.in_logic_locations)
result=dict(passed=all(t['passed'] for t in tests),assertions=len(tests),
    active_chests=sum(i in active for i in rows),tests=tests)
a.report.write_text(json.dumps(result,indent=2));print('PASS' if result['passed'] else 'FAIL',len(tests))
for t in [t for t in tests if not t['passed']]:print(t['test'])
raise SystemExit(not result['passed'])
