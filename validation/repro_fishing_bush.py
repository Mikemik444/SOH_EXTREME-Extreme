from pathlib import Path
import sys, json, argparse
from run_case import setup, BOOTSTRAP
from BaseClasses import CollectionState
from worlds.soh_extreme._vendor_oot_soh.LogicHelpers import can_use, Items, Regions
from worlds.soh_extreme.ForkLocations import FORK_LOCATIONS
p=argparse.ArgumentParser(parents=[BOOTSTRAP]);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
m=setup(1616,overrides={'boss_key_shuffle':'anywhere'});w=m.worlds[1]
full=m.get_all_state(False)
pond=[l for l in w.get_locations() if l.name.startswith(('LH Child Pond','LH Adult Pond')) or l.name in ('LH Child Fishing','LH Adult Fishing')]
result={'world_version':w.world_version.as_simple_string(),'pond_checks':len(pond),'cases':{}}
for missing in ('NPC Soul','Speak Hylian','Fish Soul'):
 s=full.copy()
 for _ in range(s.count(missing,1)):s.remove(w.create_item(missing))
 result['cases'][missing]={'fishing_hole_reachable':w.get_region(Regions.LH_FISHING_HOLE).can_reach(s),'incorrectly_available_pond_checks':[l.name for l in pond if l.can_reach(s)]}
s=CollectionState(m)
for i in m.precollected_items[1]:s.remove(i)
s.collect(w.create_item('Grass / Bush Soul'),True)
s.sweep_for_advancements()
bushes=[f for f in FORK_LOCATIONS if f.family=='bush' and f.rc.startswith('RC_HF_BUSH_NEAR_LAKE_')]
result['bushes']={'field_reachable':w.get_region(Regions.HYRULE_FIELD).can_reach(s),'checks':{f.name:w.get_location(f.name).can_reach(s) for f in bushes}}
a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
