"""Exercise native Treasure Chest Game locks, receipts, and upgrade boundaries."""
from run_case import setup, BOOTSTRAP
from ut_harness import tracker
from pathlib import Path
from collections import Counter
import argparse, json
p=argparse.ArgumentParser(parents=[BOOTSTRAP]);p.add_argument('--ut-core',type=Path,required=True)
p.add_argument('--report',type=Path,required=True);a=p.parse_args();tests=[]
def ck(name,value,expected=True):tests.append(dict(test=name,actual=value,expected=expected,passed=value==expected))
for shuffled in (False,True):
 for mode in ('off','on','progressive'):
  m=setup(291031,overrides={'shuffle_chest_minigame':shuffled,'shuffle_open_chest':mode,'skeleton_key':False,'closed_forest':'off'})
  w=m.worlds[1];ev=tracker(w,a.ut_core)
  locations={l.address:l for l in w.get_locations() if type(l.address)is int}
  items=[*m.itempool,*[l.item for l in locations.values() if l.item]]
  names=[i.name for i in items if i.name in w.item_name_to_id]
  ck(f'{shuffled}/{mode}: exact key pool',names.count('Treasure Game Small Key'),6 if shuffled else 0)
  base=[n for n in names if n not in ('Open Chest','Treasure Game Small Key','Treasure Game Key Ring','Skeleton Key','Lens of Truth')]
  chests={i:6 if i==47 else 1+(i-9700553)%5 for i in locations if i==47 or 9700553<=i<=9700562}
  for opening in (0,1,2):
   for kind,count in [('Treasure Game Small Key',n) for n in range(7)]+[('Skeleton Key',1),('Treasure Game Key Ring',1),('Lens of Truth',1)]:
    result=ev(base+['Open Chest']*opening+[kind]*count)
    for i,locks in chests.items():
     keys_ok=(kind in ('Skeleton Key','Treasure Game Key Ring') or (kind=='Treasure Game Small Key' and count>=locks)) if shuffled else kind=='Lens of Truth'
     open_ok=mode=='off' or opening>=(2 if mode=='progressive' else 1)
     expected=bool(keys_ok and open_ok);loc=locations[i]
     label=f'{shuffled}/{mode}/{opening} Open Chest/{kind} x{count}/{loc.name}'
     ck('AP '+label,loc.can_reach(result.state),expected)
     ck('UT '+label,loc.name in result.in_logic_locations,expected)
    if shuffled:
     ck(f'owner independent of Open Chest/{mode}/{opening}/{kind}/{count}',
        'NPC Speech: Treasure Chest Game Owner' in result.in_logic_locations)
  if shuffled:
   for missing in ('NPC Soul','Speak Hylian'):
    result=ev([n for n in base if n!=missing]+['Open Chest']*2+['Skeleton Key'])
    for i in chests:ck(f'keys unlock physical chest without owner/{mode}/{missing}/{i}',locations[i].can_reach(result.state))
    ck(f'owner requires {missing}/{mode}','NPC Speech: Treasure Chest Game Owner' in result.in_logic_locations,False)
result=dict(passed=all(t['passed'] for t in tests),assertions=len(tests),tests=tests)
a.report.write_text(json.dumps(result,indent=2));print('PASS' if result['passed'] else 'FAIL',len(tests))
for t in [t for t in tests if not t['passed']][:40]:print(t)
raise SystemExit(not result['passed'])
