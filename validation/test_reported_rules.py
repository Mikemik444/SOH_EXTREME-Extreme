"""Fresh-state tests of the packaged AP rules, not cached all-items events."""
from run_case import setup, BOOTSTRAP
from BaseClasses import CollectionState
from NetUtils import convert_to_base_types
from pathlib import Path
import argparse,json
p=argparse.ArgumentParser(parents=[BOOTSTRAP]);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
checks=[]
def ck(name,actual,expected=True):
 checks.append({'test':name,'passed':actual==expected,'actual':actual,'expected':expected})
 if actual!=expected:print('FAIL',name,actual,expected,flush=True)
def fresh(m,excluded=(),extra=()):
 # Collect physical items into a fresh state; never remove a virtual song while
 # keeping its complete note group or retain old swept room-clear events.
 w=m.worlds[1];s=CollectionState(m);excluded=set(excluded)
 physical=list(m.itempool)+[l.item for l in w.get_locations() if l.address is not None and l.item is not None]
 for item in physical:
  if item.name not in excluded:s.collect(item,True)
 for name in extra:s.collect(w.create_item(name),True)
 s.sweep_for_advancements(locations=[l for l in w.get_locations() if l.address is None]);return s

m=setup(11921,overrides={'boss_key_shuffle':'anywhere'},stop_before='pre_fill');w=m.worlds[1]
notes=[n for n in w.item_name_to_id if n.startswith('Song Note ')]
buttons=[n for n in w.item_name_to_id if 'Button' in n]
sheiks=[l for l in w.get_locations() if l.address is not None and l.name.startswith('Sheik')]
ck('all six Sheik song checks',len(sheiks),6)
for name in ('NPC Soul','Speak Hylian'):
 s=fresh(m,[name])
 for l in sheiks:ck(l.name+' without '+name,l.can_reach(s),False)
s=fresh(m)
for l in sheiks:ck(l.name+' complete prerequisites',l.can_reach(s))
closed={'Rock / Boulder Soul','NPC Soul','Speak Goron','Grab / Power Bracelet','Strength Upgrade','Progressive Ocarina','Bolero of Fire'}|set(notes)|set(buttons)
s=fresh(m,closed)
for n in closed:ck('missing inventory '+n,s.count(n,1),0)
ck('bombchus still present',s.count('Bombchu Bag',1)>0)
ck('Climb alone cannot fix missing rocks',s.count('Climb',1)>0)
for l in w.get_locations():
 if l.address is not None and (l.name.startswith('DMC ') or l.name.startswith('EXTREME Dmc ') or l.name=='Sheik in Crater'):
  ck('closed all crater routes: '+l.name,l.can_reach(s),False)
for rr in ('Death Mountain Summit','DMC Upper Nearby','DMC Lower Local','DMC Central Nearby'):
 ck('closed region '+rr,w.get_region(rr).can_reach(s),False)
# Restore complete genuine approaches independently, without requiring unrelated
# alternate-route items. Source dependencies, not a blanket crater item list.
for mode,restore in [('summit',{'Rock / Boulder Soul'}),('Goron',{'NPC Soul','Speak Goron','Grab / Power Bracelet'})]:
 s=fresh(m,closed,extra=restore)
 ck(mode+' route restored',w.get_region('DMC Upper Nearby' if mode=='summit' else 'DMC Lower Local').can_reach(s))
# Bolero route: full group derived from this world's actual note layout.
warp = set(w.SONG_NOTE_GROUPS['Bolero of Fire']) | set(buttons) | {'Progressive Ocarina'}
ss=fresh(m,closed-warp)
ck('complete Bolero route without rocks/NPC/Grab',w.get_region('DMC Central Nearby').can_reach(ss))
for requirement in list(w.SONG_NOTE_GROUPS['Bolero of Fire']) + ['Progressive Ocarina','Ocarina A Button','Ocarina C Down Button','Ocarina C Right Button']:
 ss=fresh(m,(closed-warp)|{requirement})
 ck('Bolero route missing '+requirement,w.get_region('DMC Central Nearby').can_reach(ss),False)
for missing in ('Climb','Rock / Boulder Soul'):
 s=fresh(m,closed-{'Rock / Boulder Soul'}|{missing})
 ck('summit route needs '+missing,w.get_region('Death Mountain Summit').can_reach(s),False)
# Silver checks now have coupled exact parent/method routes, not entryway aliases.
from worlds.soh_extreme.ForkLocations import FORK_LOCATIONS
silvers=[f for f in FORK_LOCATIONS if f.family=='silver']
for f in silvers:
 l=w.get_location(f.name);ck('exact silver parent '+f.name,l.parent_region.name.startswith('EXTREME Silver Access:'))
s=fresh(m,["Din's Fire",'Fire Arrows'])
for f in silvers:
 if f.rc.startswith('RC_SHADOW_'):ck('Shadow torch door blocks '+f.name,w.get_location(f.name).can_reach(s),False)
# Options individually disabled/shared: disabling speech must never disable NPC
# Soul, and global speech must not accidentally demand the per-language copy.
for overrides,deny,allow in [
 ({'shuffle_speak':'off'},['NPC Soul'],['Speak','Speak Hylian']),
 ({'shuffle_speak':'on'},['Speak'],['Speak Hylian']),
 ({'shuffle_speak':'individual_languages','shuffle_npc_soul':False},['Speak Hylian'],['NPC Soul']),
]:
 mm=setup(11922,overrides=dict({'boss_key_shuffle':'anywhere'},**overrides),stop_before='pre_fill');ww=mm.worlds[1]
 for state_missing,expected in ((deny,False),(allow,True)):
  ss=fresh(mm,state_missing)
  for l in ww.get_locations():
   if l.name.startswith('Sheik') and l.address is not None:ck(str(overrides)+l.name+str(state_missing),l.can_reach(ss),expected)
# Reconstructed UT world must preserve all rows for the exact slot options.
slot=convert_to_base_types(w.fill_slot_data())
mm=setup(11999,overrides={'shuffle_npc_soul':False,'shuffle_speak':'off','boss_key_shuffle':'anywhere'},stop_before='pre_fill',passthrough=slot)
ww=mm.worlds[1]
for missing in ([],['NPC Soul'],['Speak Hylian'],closed):
 s=fresh(m,missing);ss=fresh(mm,missing)
 orig={l.address:l.can_reach(s) for l in w.get_locations() if l.address is not None}
 regen={l.address:l.can_reach(ss) for l in ww.get_locations() if l.address is not None}
 ck('UT same active IDs '+str(len(missing)),sorted(orig),sorted(regen));checks[-1].update(actual=len(orig),expected=len(regen))
 for i in orig:ck('UT availability '+str(i)+' missing '+str(len(missing)),orig[i],regen[i])
a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps({'passed':all(c['passed'] for c in checks),'assertions':len(checks),'failures':[c for c in checks if not c['passed']],'scope':'fresh AP state and slot reconstruction; not physical gameplay'},indent=2))
print(a.report.read_text());raise SystemExit(not all(c['passed'] for c in checks))
