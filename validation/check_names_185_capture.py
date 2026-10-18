from pathlib import Path
import json,random,hashlib,sys
import ModuleUpdate
ModuleUpdate.update_ran = True
import settings
settings.no_gui=True
settings.skip_autosave=True
import yaml
from BaseClasses import CollectionState
from Generate import roll_settings
from test.general import setup_multiworld
from worlds.AutoWorld import call_all
from worlds.soh_extreme import SohExtremeWorld
from worlds.soh_extreme._vendor_oot_soh.Enums import Ages
source=Path('/workspace/scratch/8fddab5b8169/source/archipelago/soh_extreme')
random.seed(1)
rolled=roll_settings(yaml.safe_load(Path('/workspace/scratch/8fddab5b8169/upload/SOH-EXTREME(20261017-230302).yaml').read_text()))
options={name:getattr(rolled,name).value for name in SohExtremeWorld.options_dataclass.type_hints}
options={name:dict(value) if isinstance(value,dict) else value for name,value in options.items()}
report={'source_sha256':{p.relative_to(source).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in source.rglob('*') if p.is_file() and p.suffix in ('.py','.json')},'datapackage':dict(SohExtremeWorld.location_name_to_id),'ages':{}}
for starting_age in ('child','adult'):
 mw=setup_multiworld(SohExtremeWorld,steps=(),seed=1,options=dict(options,starting_age=starting_age))
 world=mw.worlds[1]
 for stage in ('generate_early','create_regions','create_items','set_rules'):call_all(mw,stage)
 locations=sorted((loc for loc in world.get_locations() if loc.address is not None),key=lambda loc:loc.address)
 cases={}
 for label,items in (
   ('actual_start',None),
   ('sword_and_souls',('Kokiri Sword','Master Sword','Keese Soul','Deku Baba Soul','Skulltula Soul','Jabu Jabu Tentacle Soul')),
   ('mobility',('Climb','Grab / Power Bracelet','Progressive Scale','Progressive Scale','Progressive Hookshot','Progressive Hookshot','Crawl','Shovel','Roll','Speak Zora','NPC Soul','Open Chest')),
   ('all',None)):
  state=mw.get_all_state(False) if label=='all' else CollectionState(mw)
  if items:
   for name in items:state.collect(world.create_item(name),True)
  if label!='all':state.sweep_for_advancements(locations=[loc for loc in world.get_locations() if loc.item is not None and loc.item.player==1])
  for age in (Ages.CHILD,Ages.ADULT):
   state._soh_extreme_age[1]=age
   cases[label+':'+age.name]=[loc.address for loc in locations if loc.can_reach_as_age(state,age)]
 report['ages'][starting_age]={'locations':{str(loc.address):{'name':loc.name,'parent':loc.parent_region.name,'rule':type(loc.access_rule).__qualname__,'items':sorted(loc.access_rule.item_dependencies()) if hasattr(loc.access_rule,'item_dependencies') else [],'regions':sorted(loc.access_rule.region_dependencies()) if hasattr(loc.access_rule,'region_dependencies') else []} for loc in locations},'cases':cases}
 print(starting_age,len(locations),'captured',flush=True)
Path(sys.argv[1]).write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
