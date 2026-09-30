"""Skeleton Key replaces small/overworld keys through real AP and UT rules."""
from run_case import setup, BOOTSTRAP
from ut_harness import tracker
from BaseClasses import CollectionState
from worlds.soh_extreme._vendor_oot_soh.Items import item_data_table, GroupTag
from worlds.soh_extreme._vendor_oot_soh.LogicHelpers import small_keys, key_to_ring, can_open_overworld_door
from worlds.soh_extreme._vendor_oot_soh.Enums import Regions
from pathlib import Path
import argparse, json

p=argparse.ArgumentParser(parents=[BOOTSTRAP])
p.add_argument('--ut-core',type=Path,required=True)
p.add_argument('--report',type=Path,required=True)
a=p.parse_args(); tests=[]
def ck(name,actual,expected=True):
    tests.append(dict(test=name,actual=actual,expected=expected,passed=actual==expected))

m=setup(291011,overrides={'small_key_shuffle':'anywhere','gerudo_fortress_key_shuffle':'anywhere',
    'fortress_carpenters':'normal','key_rings':'off','skeleton_key':True,'lock_overworld_doors':True},
    stop_before='pre_fill')
w=m.worlds[1]; evaluate=tracker(w,a.ut_core)
key_tags=GroupTag.Small_Key|GroupTag.Key_Ring|GroupTag.Overworld_Key
keys={str(name) for name,data in item_data_table.items() if (data.tags or 0)&key_tags}
network=[l for l in w.get_locations() if type(l.address) is int]
items=[*m.itempool,*[l.item for l in network if l.item]]
names=[it.name for it in items if it.name in w.item_name_to_id]
ordinary=[n for n in names if n!='Skeleton Key']
skeleton=[n for n in names if n not in keys and n!='Skeleton Key']+['Skeleton Key']
no_keys=[n for n in names if n not in keys and n!='Skeleton Key']
baseline=evaluate(ordinary); substitute=evaluate(skeleton); locked=evaluate(no_keys)
for name in sorted(keys):
    ck('no ordinary key receipt with Skeleton Key: '+name,substitute.state.count(name,1),0)
for loc in network:
    expected=loc.name in baseline.in_logic_locations
    ck('AP Skeleton Key substitutes at '+loc.name,loc.can_reach(substitute.state),expected)
    ck('UT Skeleton Key substitutes at '+loc.name,loc.name in substitute.in_logic_locations,expected)
key_locked=[l.name for l in network if l.name in baseline.in_logic_locations and l.name not in locked.in_logic_locations]
ck('removing all keys blocks real checks',len(key_locked)>0)

bare=CollectionState(m); with_skeleton=CollectionState(m)
with_skeleton.collect(w.create_item('Skeleton Key'),True)
bundle=(Regions.KOKIRI_FOREST,w)
for key in key_to_ring:
    for count in range(1,11):
        rule=small_keys(key,count,bundle).resolve(w);w.register_rule_dependencies(rule)
        ck(f'{key} x{count} without keys',rule(bare),False)
        ck(f'{key} x{count} with Skeleton Key',rule(with_skeleton))
for name,data in item_data_table.items():
    if not ((data.tags or 0)&GroupTag.Overworld_Key):continue
    rule=can_open_overworld_door(name,bundle).resolve(w);w.register_rule_dependencies(rule)
    ck(str(name)+' without keys',rule(bare),False)
    ck(str(name)+' with Skeleton Key',rule(with_skeleton))
missing_climb=evaluate([n for n in skeleton if n!='Climb'])
for region in (Regions.ZR_OPEN_GROTTO,Regions.ZR_FAIRY_GROTTO):
    for loc in w.get_region(str(region)).locations:
        if type(loc.address) is int:
            ck('Skeleton Key does not supply Climb: '+loc.name,loc.can_reach(missing_climb.state),False)
result=dict(passed=all(t['passed'] for t in tests),assertions=len(tests),network_checks=len(network),
    key_locked_without_skeleton=len(key_locked),key_locked_examples=key_locked[:20],tests=tests)
a.report.write_text(json.dumps(result,indent=2),encoding='utf-8')
print('PASS' if result['passed'] else 'FAIL',len(tests),'assertions;',len(key_locked),'checks affected by keys')
for t in [t for t in tests if not t['passed']][:20]:print(t)
raise SystemExit(not result['passed'])
