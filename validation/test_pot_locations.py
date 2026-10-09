"""Actual AP graph/catalog and UT reconstruction for the missing DC doorway pots."""
import argparse,json,re
from pathlib import Path
from run_case import setup,BOOTSTRAP
from source_index import native_metadata,normalize
from BaseClasses import CollectionState
from NetUtils import convert_to_base_types
from worlds.soh_extreme._vendor_oot_soh.Locations import location_data_table,LocTag
from worlds.soh_extreme._vendor_oot_soh.Enums import Ages
p=argparse.ArgumentParser(parents=[BOOTSTRAP]);p.add_argument('--source-root',type=Path,required=True);p.add_argument('--report',type=Path,required=True)
a=p.parse_args();checks=[]
def ck(name,actual,expected=True):
 checks.append(dict(name=name,actual=actual,expected=expected,passed=actual==expected))
 if actual!=expected:print('FAIL',name,actual,expected,flush=True)
ids={943,944}
mapping={rc:int(i) for rc,i in re.findall(r'static_cast<int>\((RC_\w+)\),\s*(\d+)LL',(a.source_root/'soh/Network/Archipelago/ArchipelagoLocationMap.inc').read_text())}
stock={d.loc_id:(str(n),d) for n,d in location_data_table.items() if d.loc_id is not None}
pots=[d for d in native_metadata(a.source_root).values() if d['constructor']=='Pot' and d['quest']!='RCQUEST_MQ']
for pot in pots:
 entry=stock.get(mapping.get(pot['rc']))
 ck('mapped AP pot '+pot['rc'],entry is not None and bool(entry[1].tags & LocTag.Pot))
 if entry:ck('same named pot '+pot['rc'],normalize(entry[0]),normalize(pot['spoiler_name']))
slot=None
for mode in ('off','overworld','dungeon','all'):
 # Disable Pot Soul here to avoid its intentional auto-enabling of pots.
 m=setup(1138,overrides=dict(shuffle_pots=mode,shuffle_pot_soul=False));w=m.worlds[1]
 found=[l for l in w.get_locations() if l.address in ids]
 ck(mode+' pot inclusion',len(found),2 if mode in ('dungeon','all') else 0)
 for l in found:ck(mode+' parent '+l.name,l.parent_region.name,'Dodongos Cavern Near Lower Lizalfos')
 if mode=='all':slot=convert_to_base_types(w.fill_slot_data())
for label,passthrough in (('new',slot),('old',{**slot,'extreme_active_locations':[i for i in slot['extreme_active_locations'] if i not in ids]})):
 m=setup(1138,passthrough=passthrough);w=m.worlds[1]
 ck(label+' tracker manifest',sorted(w.fill_slot_data()['extreme_active_locations']),sorted(passthrough['extreme_active_locations']))
 ck(label+' tracker pot count',sum(l.address in ids for l in w.get_locations()),2 if label=='new' else 0)
# Full graph: soul and a real break/lift action must both exist.
m=setup(1138,overrides=dict(shuffle_pots='all',shuffle_pot_soul=True,shuffle_grab=True,shuffle_roll=True,
                          shuffle_deku_stick_bag=True,closed_forest='off'))
w=m.worlds[1];locations=[l for l in w.get_locations() if l.address in ids]
ck('exact two checks',sorted(l.address for l in locations),[943,944])
for soul in (False,True):
 s=m.get_all_state(False).copy()
 if not soul:
  while s.has('Pot Soul',1):s.remove(w.create_item('Pot Soul'))
 for l in locations:ck('full graph soul='+str(soul)+' '+l.name,l.can_reach(s),soul)
for age in (Ages.CHILD,Ages.ADULT):
 for soul in (False,True):
  for name,items,usable in (('none',[],False),('roll',['Roll'],False),('grab',['Strength Upgrade'],True),
                           ('sword',['Kokiri Sword'],age==Ages.CHILD),('bombs',['Progressive Bomb Bag'],True)):
   s=CollectionState(m)
   for it in m.precollected_items[1]:s.remove(it)
   for item in items+(['Pot Soul'] if soul else []):s.collect(w.create_item(item),True)
   s._soh_extreme_age[1]=age
   for l in locations:ck(f'physical {age}/{soul}/{name} '+l.name,l.access_rule(s),soul and usable)
report=dict(passed=all(c['passed'] for c in checks),count=len(checks),native_pots=len(pots),checks=checks,
 scope='Source catalog identity and real AP CollectionState/location rules plus UT slot-data reconstruction; not live gameplay.')
a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(report,indent=2))
print('ASSERTIONS',len(checks),'FAILURES',sum(not c['passed'] for c in checks),flush=True)
raise SystemExit(not report['passed'])
