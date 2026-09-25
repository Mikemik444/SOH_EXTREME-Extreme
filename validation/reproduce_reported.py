"""Record the same fresh physical inventory in a baseline or patched AP world."""
from run_case import setup, BOOTSTRAP
from BaseClasses import CollectionState
from pathlib import Path
import argparse,json
p=argparse.ArgumentParser(parents=[BOOTSTRAP]);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
m=setup(11921,overrides={'boss_key_shuffle':'anywhere'},stop_before='pre_fill');w=m.worlds[1]
physical=list(m.itempool)+[l.item for l in w.get_locations() if l.address is not None and l.item is not None]
notes={n for n in w.item_name_to_id if n.startswith('Song Note ')}
buttons={n for n in w.item_name_to_id if 'Button' in n}
def state_without(missing):
 s=CollectionState(m)
 for item in physical:
  if item.name not in missing:s.collect(item,True)
 s.sweep_for_advancements(locations=[l for l in w.get_locations() if l.address is None]);return s
sheiks=[l for l in w.get_locations() if l.name.startswith('Sheik') and l.address is not None]
result={'loaded_from':__import__('worlds.soh_extreme',fromlist=['']).__file__,'version':w.world_version.as_simple_string(),'sheik':{}}
for missing in ('NPC Soul','Speak Hylian'):
 s=state_without({missing});result['sheik'][missing]={l.name:l.can_reach(s) for l in sheiks}
missing={'Rock / Boulder Soul','NPC Soul','Speak Goron','Grab / Power Bracelet','Strength Upgrade','Progressive Ocarina','Bolero of Fire'}|notes|buttons
s=state_without(missing)
result['crater_without_any_complete_route']={name:w.get_region(name).can_reach(s) for name in ('Death Mountain Summit','DMC Upper Nearby','DMC Lower Local','DMC Central Nearby')}
result['bombchu_bag_count']=s.count('Bombchu Bag',1)
result['physical_inventory_omitted']=sorted(missing)
a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
