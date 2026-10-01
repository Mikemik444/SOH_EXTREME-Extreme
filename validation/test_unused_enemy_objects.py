"""Unused actor entries: new fill exclusion and old server-manifest UT compatibility."""
from run_case import setup, BOOTSTRAP
from ut_harness import tracker
from pathlib import Path
from NetUtils import convert_to_base_types
from worlds.soh_extreme.EnemyDropLocations import ENEMY_DROP_LOCATIONS, ENEMY_UNUSED_OBJECT_IDS
import argparse, json

p=argparse.ArgumentParser(parents=[BOOTSTRAP]);p.add_argument('--ut-core',type=Path,required=True)
p.add_argument('--report',type=Path,required=True);a=p.parse_args();checks=[]
def ck(name, actual, expected=True):
    checks.append(dict(test=name,actual=actual,expected=expected,passed=actual==expected))
    if actual!=expected:print('FAIL',name,actual,expected,flush=True)
options=dict(shuffle_enemy_drops=True,shuffle_enemy_soul='individual_enemies',shuffle_skulltula_soul=True,
    starting_age='child',shuffle_master_sword=True,closed_forest='off',door_of_time='song_only')
m=setup(930410,overrides=options,stop_before='pre_fill');w=m.worlds[1]
unused=[e for e in ENEMY_DROP_LOCATIONS if e.address in ENEMY_UNUSED_OBJECT_IDS]
ck('Exactly eight reserved identities',len(unused),8)
active={l.address for l in w.get_locations() if l.address is not None}
for e in unused:
    ck('New seed excludes '+e.name,e.address in active,False)
    ck('Stable ID '+e.name,w.location_name_to_id[e.name],e.address)
slot=convert_to_base_types(w.fill_slot_data())
ck('New manifest has no unused entries',bool(ENEMY_UNUSED_OBJECT_IDS.intersection(slot['extreme_active_locations'])),False)
fresh=setup(930411,overrides=options,passthrough=slot,stop_before='pre_fill').worlds[1]
ck('New UT has no unused entries',bool(ENEMY_UNUSED_OBJECT_IDS.intersection(l.address for l in fresh.get_locations())),False)
# An old server still owns these exact locations. Restore only IDs it declares.
slot['extreme_active_locations']=sorted(set(slot['extreme_active_locations'])|ENEMY_UNUSED_OBJECT_IDS)
old=setup(930412,overrides=dict(options,shuffle_enemy_drops=False),passthrough=slot,stop_before='pre_fill').worlds[1]
ck('Old slot options restored',old.options.shuffle_enemy_drops.value,1)
ev=tracker(old,a.ut_core)
names=[it.name for it in old.multiworld.itempool]+[l.item.name for l in old.get_locations() if l.address is not None and l.item is not None and l.item.name in old.item_name_to_id]
for omit,label in ((set(),'all'),({'Keese Soul'},'no Keese Soul'),({'Skulltula Soul'},'no Skulltula Soul'),({'Octorok Soul'},'no Octorok Soul'),({'Progressive Ocarina'},'no adult')):
    result=ev([n for n in names if n not in omit])
    for e in unused:
        ck('Old ID '+e.name,old.get_location(e.name).address,e.address)
        # The exterior checks remain adult-only; restored enemies still use
        # their own soul, not NPC Soul. Skullwalltulas use Skulltula Soul.
        soul=e.soul_item or ('Skulltula Soul' if e.actor_id==149 else '')
        expected=soul not in omit and not (e.scene_id==83 and label=='no adult')
        ck(label+' AP '+e.name,old.get_location(e.name).can_reach(result.state),expected)
        ck(label+' UT '+e.name,e.name in result.in_logic_locations,expected)
partial=dict(slot);partial['extreme_active_locations']=[n for n in slot['extreme_active_locations'] if n!=9800621]
pw=setup(930413,overrides=options,passthrough=partial,stop_before='pre_fill').worlds[1]
ck('An absent old ID is never inferred',9800621 in {l.address for l in pw.get_locations()},False)
off=setup(930414,overrides=dict(options,shuffle_enemy_drops=False),stop_before='pre_fill').worlds[1]
ck('Enemy checks off',any(l.address in {e.address for e in ENEMY_DROP_LOCATIONS} for l in off.get_locations()),False)
report=dict(passed=all(c['passed'] for c in checks),assertions=len(checks),failures=[c for c in checks if not c['passed']],scope=__doc__)
a.report.write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2));raise SystemExit(not report['passed'])
