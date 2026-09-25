"""Targeted production AP rules, positive alternatives, and whole-graph UT replay.

No physics, live UI, or game-process verification. Full-inventory tests retain
historical events except when explicitly removing a contents/event dependency.
"""
from pathlib import Path
import argparse,json,traceback,itertools,collections
from run_case import setup,BOOTSTRAP
from BaseClasses import CollectionState,Location
from NetUtils import convert_to_base_types
from source_index import native_sources,native_metadata
from worlds.soh_extreme._vendor_oot_soh.LogicHelpers import *
from worlds.soh_extreme.NativeLocationRequirements import FORK_LOCATION_AGES
from worlds.soh_extreme.ForkLocations import FORK_LOCATIONS
p=argparse.ArgumentParser(parents=[BOOTSTRAP]);p.add_argument('--source-root',type=Path,required=True);p.add_argument('--group',choices=['actions','lacs','ut'],default='actions');p.add_argument('--report',type=Path,required=True);a=p.parse_args()
results=[];coverage={}
def ck(label,actual,expected=True):
 if isinstance(expected,bool):actual=bool(actual)
 row=dict(test=label,passed=actual==expected,actual=actual,expected=expected);results.append(row)
 if not row['passed']:print('FAIL',label,repr(actual)[:1000],flush=True)
def without(state,w,names):
 s=state.copy();events={l.item.name:l.item for l in w.get_locations() if l.item}
 for name in names:
  while s.count(name,w.player):
   item=w.create_item(name) if name in w.item_name_to_id else events[name]
   old=s.count(name,w.player);s.remove(item);assert s.count(name,w.player)<old,name
 return s

def bare(m,w,names=()):
 s=CollectionState(m)
 for item in m.precollected_items[w.player]:s.remove(item)
 for n in names:s.collect(w.create_item(n),True)
 return s

def resolved(r,w):
 r=r.resolve(w);w.register_rule_dependencies(r);return r

def byid(w,i):return next(l for l in w.get_locations() if l.address==i)
try:
 m=setup(17173,overrides={'boss_key_shuffle':'anywhere','shuffle_roll':True,'shuffle_open_chest':'progressive'},stop_before='pre_fill');w=m.worlds[1];full=m.get_all_state(False)
 ck('version',w.world_version.as_simple_string(),'0.11.17')
 ck('all inventory locations in AP model',[l.name for l in w.get_locations() if not l.can_reach(full)],[])
 if a.group=='actions':
  # Grass collection is an OR, not a global Grab AND. The native per-location
  # source scan also checks that resource events kept their cutting methods.
  b=(Regions.KOKIRI_FOREST,w);r=resolved(can_collect_grass(b),w)
  for age in (Ages.CHILD,Ages.ADULT):
   for soul,grab,sword in itertools.product((False,True),repeat=3):
    items=(['Grass / Bush Soul'] if soul else [])+(['Grab / Power Bracelet'] if grab else [])
    if sword:items+=['Kokiri Sword' if age==Ages.CHILD else 'Master Sword']
    s=bare(m,w,items);s._soh_age[1]=age
    ck(f'grass soul={soul} Grab={grab} sword={sword} age={age}',r(s),soul and(grab or sword))
  for missing in (['Grab / Power Bracelet'],['Kokiri Sword','Master Sword',"Biggoron's Sword","Giant's Knife",'Boomerang','Megaton Hammer','Progressive Bomb Bag','Bombchu Bag']):
   s=without(full,w,missing)
   for name in ('KF Child Grass Maze 1','KF Child Grass Maze 2'):
    ck('grass valid alternative '+str(missing)+' '+name,w.get_location(name).can_reach(s))
  md=native_metadata(a.source_root);src,_=native_sources(a.source_root)
  leftovers=[dict(rc=rc,source=d) for rc,ds in src.items() if md.get(rc,{}).get('constructor')=='Grass' for d in ds if 'CanCutShrubs()' in d['condition']]
  ck('no native Grass LOCATION still requires cutting only',leftovers,[])
  coverage['native_grass_location_definitions']=sum(len(ds) for rc,ds in src.items() if md.get(rc,{}).get('constructor')=='Grass')
  ids={l.address for l in w.get_locations()};ck('nonexistent native pot IDs retired',bool(ids&{943,944}),False)
  ck('renamed beehive remains existing ID 787',byid(w,787).name,'ZR Storms Grotto Beehive')
  # Strict required prerequisites on corrected full graph checks.
  requirements={64:['Cucco Soul','Grab / Power Bracelet','NPC Soul','Speak Hylian'],35:['Speak Deku','NPC Soul'],9700145:['Grab / Power Bracelet','Strength Upgrade'],9700221:['Progressive Hookshot'],9700663:['Grab / Power Bracelet','Strength Upgrade'],9700563:['Progressive Wallet']}
  for i,names in requirements.items():
   l=byid(w,i);ck('corrected check positive '+l.name,l.can_reach(full))
   for name in names:
    s=without(full,w,[name]);ck(l.name+' missing '+name,l.can_reach(s),False)
    ck('independent original remains reachable '+l.name,l.can_reach(full))
  # Exact cutscene checks use a separate group with their selected goal/mode.
  # Contents must actually be accessible, not just an empty bottle.
  for ids,content,buy in [((9700478,9700571),'Can Access Blue Fire','Buy Blue Fire'),((9700479,9700572),'Can Access Bugs','Buy Bottle Bug'),((9700480,9700573),'Can Access Fish','Buy Fish')]:
   removed=without(full,w,[content,buy])
   for i in ids:
    ck(byid(w,i).name+' requires contents',byid(w,i).can_reach(removed),False)
  # Golden Scale threshold: all physical scales removed through the real receipt
  # path so virtual Swim cannot outlive its supplying first progressive item.
  water=without(full,w,['Progressive Scale'])
  for count in range(4):
   if count:water.collect(w.create_item('Progressive Scale'),True)
   for i in range(1610,1618):
    ck(f'LW underwater pickup {i} scale tier {count}',byid(w,i).can_reach(water),count==3)
  # Actual GTG water locals: every rupee needs Swim and playable Song of Time.
  selected=[f for f in FORK_LOCATIONS if f.rc in {'RC_GTG_MIDDLE_WATER_SILVER','RC_GTG_ABOVE_TARGET_WATER_SILVER','RC_GTG_LEFT_WATER_SILVER','RC_GTG_UNDER_TARGET_WATER_SILVER','RC_GTG_RIGHT_WATER_SILVER'}]
  ck('five GTG water checks exist',len(selected),5)
  for missing in ('Progressive Scale','Progressive Ocarina','Song Note 25'):
   s=without(full,w,[missing])
   for f in selected:ck(f.name+' missing '+missing,w.get_location(f.name).can_reach(s),False)
  # Every emitted age gate is present in the actual AP location expression;
  # no adult-only actor may borrow a child-accessible parent, or vice versa.
  fork_by_rc={f.rc:f for f in FORK_LOCATIONS}
  for rc,age in FORK_LOCATION_AGES.items():
   f=fork_by_rc[rc];l=w.get_location(f.name)
   s=full.copy();s._soh_age[1]=Ages.ADULT if age=='child' else Ages.CHILD
   ck(f.name+' wrong age cannot collect',Location.can_reach(l,s),False)
  coverage['fork_age_gates']=len(FORK_LOCATION_AGES)
 elif a.group=='lacs':
  # Instantiate every selected condition. Changing options here occurs BEFORE
  # resolving a new helper rule and never alters a rule already used by a seed.
  opts=w.options
  defaults={name:getattr(opts,name).value for name in ('triforce_hunt','ganons_castle_boss_key','ganons_castle_boss_key_greg_modifier')}
  for key in ('stones','medallions','dungeon_rewards','dungeons','skull_tokens'):
   getattr(opts,'ganons_castle_boss_key_'+key+'_required').value=3
  b=(Regions.TEMPLE_OF_TIME,w)
  med=[Items.FOREST_MEDALLION,Items.FIRE_MEDALLION,Items.WATER_MEDALLION]
  stones=[Items.KOKIRIS_EMERALD,Items.GORONS_RUBY,Items.ZORAS_SAPPHIRE]
  for hunt in (0,1):
   opts.triforce_hunt.value=hunt
   for mode in range(8):
    opts.ganons_castle_boss_key.value=mode
    for greg_mode in range(3):
     opts.ganons_castle_boss_key_greg_modifier.value=greg_mode
     r=resolved(can_trigger_lacs(b),w)
     for n in range(4):
      for greg in (False,True):
       s=bare(m,w,[])
       # Event items are real locked progression events, not invented flags.
       items=list(stones[:n])+list(med[:n])+[Items.GOLD_SKULLTULA_TOKEN]*n
       if greg:items.append(Items.GREG_THE_GREEN_RUPEE)
       for name in items:s.collect(w.create_item(str(name)),True)
       events={l.item.name:l.item for l in w.get_locations() if l.item}
       for ev in dungeon_events[:n]:s.collect(events[str(ev)],True)
       bonus=greg and greg_mode==1
       expected=False
       if not hunt:
        if mode in (3,4,6):expected=n+bonus>=3
        if mode==5:expected=2*n+bonus>=3
        if mode==7:expected=n>=3
       ck(f'LACS hunt={hunt} mode={mode} gregmode={greg_mode} n={n} greg={greg}',r(s),expected)
     both=bare(m,w,[str(Items.SHADOW_MEDALLION),str(Items.SPIRIT_MEDALLION)])
     ck(f'LACS pair follows selected mode hunt={hunt} mode={mode} gregmode={greg_mode}',r(both),bool(hunt or mode in (0,1,2)))
  for name,value in defaults.items():getattr(opts,name).value=value
  # Reproduce the original default-YAML error on the actual location, not just
  # the helper: six other rewards must not replace Shadow/Spirit in hunt mode.
  for n in ('Shadow Medallion','Spirit Medallion'):
   ck('Triforce actual cutscene missing '+n,byid(w,59).can_reach(without(full,w,[n])),False)
 elif a.group=='ut':
  # Reconstruct the entire graph from slot data against conflicting local knobs.
  # No comparing just one selected category: every address/name is included.
  slot=convert_to_base_types(w.fill_slot_data())
  tm=setup(17174,overrides={'boss_key_shuffle':'anywhere','shuffle_npc_soul':False,'shuffle_speak':0,'shuffle_animal_soul':0,'shuffle_grass_bush_soul':False,'shuffle_grab':False,'shuffle_climb':False,'shuffle_roll':False},passthrough=slot,stop_before='pre_fill');tw=tm.worlds[1];tf=tm.get_all_state(False)
  names={l.name for l in w.get_locations()};tnames={l.name for l in tw.get_locations()}
  ck('UT graph location set',sorted(tnames),sorted(names));results[-1].update(actual=len(tnames),expected=len(names))
  for name in ('shuffle_npc_soul','shuffle_speak','shuffle_animal_soul','shuffle_grass_bush_soul','shuffle_grab','shuffle_climb','shuffle_roll'):
   ck('UT authoritative option '+name,getattr(tw.options,name).value,getattr(w.options,name).value)
  patterns=[[],['Grab / Power Bracelet'],['Climb'],['Crawl'],['NPC Soul'],['Speak Hylian'],['Speak Deku'],['Grass / Bush Soul'],['Pot Soul'],['Crate Soul'],['Rock / Boulder Soul'],['Cucco Soul'],['Fish Soul'],['Progressive Scale'],['Progressive Hookshot'],['Progressive Ocarina'],['Song Note 25'],['Flow of Time'],['Roll']]
  for missing in patterns:
   s=without(full,w,missing);ts=without(tf,tw,missing)
   mismatch=[n for n in sorted(names&tnames) if w.get_location(n).can_reach(s)!=tw.get_location(n).can_reach(ts)]
   ck('whole-graph UT availability missing '+str(missing),mismatch,[])
  coverage.update(graph_locations=len(names),inventory_scenarios=len(patterns),location_comparisons=len(names)*len(patterns))
except Exception as e:
 traceback.print_exc();results.append(dict(test='unhandled exception',passed=False,error=repr(e),traceback=traceback.format_exc()))
rpt=dict(scope=__doc__,group=a.group,checks=results,total=len(results),failures=sum(not r['passed'] for r in results),coverage=coverage)
a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(rpt,indent=2));print('TOTAL',rpt['total'],'FAILURES',rpt['failures'],coverage,flush=True);raise SystemExit(bool(rpt['failures']))
