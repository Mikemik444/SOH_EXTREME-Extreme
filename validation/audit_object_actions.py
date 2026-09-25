"""Remove all normal object-interaction providers from a real full AP state.

Checks a necessary action gate for source-identified pots, grass, crates and
boulders, independent of which physical approach is used. A pass is not proof
that every legal alternative or route has been encoded.
"""
from pathlib import Path
import argparse,json,collections
from run_case import setup,BOOTSTRAP
from location_source_audit import collect
p=argparse.ArgumentParser(parents=[BOOTSTRAP]);p.add_argument('--source-root',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
m=setup(17175,overrides={'shuffle_roll':True,'shuffle_open_chest':'progressive','boss_key_shuffle':'anywhere'},stop_before='pre_fill');w=m.worlds[1];full=m.get_all_state(False);rows,_=collect(a.source_root,w)
types={'Grass','Pot','Crate','SmallCrate','NLCrate','Boulder'}
# Includes swords/sticks, ranged weapons, magic fire, strength and basic Grab,
# every actual bomb/bombchu pool spelling, and the independent shuffled Roll.
remove=['Strength Upgrade','Grab / Power Bracelet','Roll','Kokiri Sword','Master Sword',"Biggoron's Sword","Giant's Knife",'Boomerang','Megaton Hammer','Progressive Bomb Bag','Bombchu Bag','Bombchus (5)','Bombchus (10)','Bombchus (20)','Progressive Hookshot','Progressive Bow','Progressive Slingshot','Progressive Stick Capacity','Progressive Nut Capacity',"Din's Fire"]
s=full.copy();removed=[]
for name in remove:
 if name not in w.item_name_to_id:continue
 while s.count(name,1):
  before=s.count(name,1);s.remove(w.create_item(name));assert s.count(name,1)<before,name
  if name not in removed:removed.append(name)
tests=[]
for row in rows:
 md=row.get('native_metadata') or {}
 if row['kind'] not in ('stock','fork')or md.get('constructor')not in types:continue
 # Event-removed boulders can have a legitimate no-action route after a room
 # event, so only test boulder definitions with an explicit physical local tool.
 defs=[d for d in row['native_sources'] if '_MQ_' not in d['region']]
 if md['constructor']=='Boulder' and not all(any(k in d['condition'] for k in ('CanUse(','BlastOrSmash()','HasExplosives()'))for d in defs):continue
 loc=w.get_location(row['name']);tests.append(dict(id=row['id'],name=row['name'],rc=row['rc'],type=md['constructor'],passed=not loc.can_reach(s),source=defs))
out=dict(scope=__doc__,tests=tests,assertions=len(tests),failures=sum(not t['passed']for t in tests),removed=removed,type_counts=dict(collections.Counter(t['type']for t in tests)))
a.report.write_text(json.dumps(out,indent=2));print({k:v for k,v in out.items()if k!='tests'})
for t in tests:
 if not t['passed']:print('FAIL',t['name'],t['source'])
raise SystemExit(bool(out['failures']))
