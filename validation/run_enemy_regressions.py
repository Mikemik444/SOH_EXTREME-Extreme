"""Real AP-core enemy and Forest rule regressions. See run_case for environment setup."""
from pathlib import Path
import argparse,json,dataclasses,sys
from run_case import setup,BOOTSTRAP
from BaseClasses import CollectionState
from worlds.soh_extreme.EnemyDropLocations import ENEMY_DROP_LOCATIONS
from worlds.soh_extreme.EnemyDropRules import enemy_drop_rule
p=argparse.ArgumentParser(parents=[BOOTSTRAP]);p.add_argument('--report',type=Path,required=True);a=p.parse_args();results=[]
def check(name,actual,expected=True):
 results.append(dict(name=name,passed=actual==expected,actual=actual,expected=expected));print('PASS' if actual==expected else 'FAIL',name,repr(actual),flush=True)
mw=setup(1201);w=mw.worlds[1]
def state_without(names=()):
 s=CollectionState(mw)
 for item in list(mw.itempool)+[l.item for l in mw.get_filled_locations() if l.item and l.address is not None]:
  if item.name not in names:s.collect(item,True)
 s.sweep_for_advancements([l for l in mw.get_filled_locations() if l.item and l.address is None and l.item.name not in names])
 return s
byid={e.address:e for e in ENEMY_DROP_LOCATIONS}
# Use names for all access requests rather than a separately invented graph.
def reachable(s,id):return w.get_location(byid[id].name).can_reach(s)
full=state_without()
check('all 753 enemy checks are reachable with complete inventory',all(w.get_location(e.name).can_reach(full) for e in ENEMY_DROP_LOCATIONS))
no_bow=state_without({'Progressive Bow'})
for id in (9800720,9800721,9800722):
 check('Bow arena does not require its own Bow '+str(id),reachable(no_bow,id))
no_stalfos=state_without({'Stalfos Soul'})
for id in (9800137,9800138,9800720,9800721,9800722):check('Stalfos requires own soul '+str(id),reachable(no_stalfos,id),False)
no_sisters=state_without({'Poe Sister Soul'})
for id in range(9800566,9800570):check('Poe Sister requires own soul '+str(id),reachable(no_sisters,id),False)
for name in ['Forest Temple Red Poe Chest','Forest Temple Blue Poe Chest']:
 check(name+' event cannot bypass missing sister soul',w.get_location(name).can_reach(no_sisters),False)
# The first Strength Upgrade also grants virtual Grab; remove both sources.
no_grab=state_without({'Grab / Power Bracelet','Strength Upgrade','Progressive Strength Upgrade'})
check('Amy cube puzzle requires Grab',reachable(no_grab,9800569),False)
no_climb=state_without({'Climb'})
# A trick-free normal route must not substitute Bunny Hood for the block-room ladder.
for id in (9800720,9800721,9800722):check('Bow route requires Climb '+str(id),reachable(no_climb,id),False)
for soul in ['Poe Soul','Leever Soul','Stalchild Soul','Big Octo Soul','Moblin Soul','Flying Pot Soul','Dead Hand Soul']:
 s=state_without({soul})
 checks=[e for e in ENEMY_DROP_LOCATIONS if e.soul_item==soul]
 check('catalogue contains '+soul,len(checks)>0)
 check('every '+soul+' check blocks without soul',all(not w.get_location(e.name).can_reach(s) for e in checks))
for soul in ['Poe Soul','Leever Soul','Stalchild Soul','Big Octo Soul']:
 check(soul+' is progression',w.create_item(soul).advancement)
night_only=[e for e in ENEMY_DROP_LOCATIONS if e.spawn_mask in (2,8,10)]
s=state_without({'Flow of Time'})
check('day-frozen state blocks every night-only enemy',all(not w.get_location(e.name).can_reach(s) for e in night_only))
check('night-only catalogue entries exist',len(night_only)>0)
# Verify no removed helper/statue became an active enemy by accident.
check('structural and child Skull Kid helper IDs not checks',not ({9800549,9800554} & set(byid)))
# A child-only copy of an otherwise reachable location cannot borrow an adult weapon.
child=next(e for e in ENEMY_DROP_LOCATIONS if e.scene_id==0 and e.room==0)
child=dataclasses.replace(child,spawn_mask=3,combat='melee')
s=state_without({'Kokiri Sword','Progressive Stick Capacity'})
check('child-only enemy cannot use adult sword or hammer',enemy_drop_rule(w,child).resolve(w)(s),False)
a.report.write_text(json.dumps({'passed':all(r['passed'] for r in results),'checks':results},indent=2));raise SystemExit(not all(r['passed'] for r in results))
