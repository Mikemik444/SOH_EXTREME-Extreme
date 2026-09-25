"""Production AP graph/rules and UT slot-data reconstruction, not game physics.
The separate native test checks the corresponding C++ interaction predicates.
"""
from pathlib import Path
import argparse,itertools,json,traceback
from run_case import setup, BOOTSTRAP
from BaseClasses import CollectionState
from NetUtils import convert_to_base_types
from worlds.soh_extreme._vendor_oot_soh.LogicHelpers import can_use, Items, Regions, Ages
from worlds.soh_extreme.ForkLocations import FORK_LOCATIONS
p=argparse.ArgumentParser(parents=[BOOTSTRAP]);p.add_argument('--group',choices=['individual','combined','unshuffled','speak_off','npc_off','ut'],default='individual');p.add_argument('--report',type=Path,required=True);a=p.parse_args()
results=[];coverage={}
def ck(label,got,want=True):
 if isinstance(want,bool):got=bool(got)
 row=dict(test=label,actual=got,expected=want,passed=got==want);results.append(row)
 if not row['passed']:print('FAIL',label,repr(got)[:800],flush=True)
def without(s,w,names):
 s=s.copy()
 for n in names:
  for _ in range(s.count(n,w.player)):s.remove(w.create_item(n))
 return s
def bare(m,w,names):
 s=CollectionState(m)
 for i in m.precollected_items[w.player]:s.remove(i)
 # The real generator precollects the innate Child Wallet; do not erase
 # that native-start default when constructing a minimal test inventory.
 if not w.options.shuffle_childs_wallet.value:s.collect(w.create_item('Progressive Wallet'),True)
 for n in names:s.collect(w.create_item(n),True)
 return s
def pond(w):return [l for l in w.get_locations() if l.name.startswith(('LH Child Pond','LH Adult Pond')) or l.name in ('LH Child Fishing','LH Adult Fishing')]
options={
 'individual':{},
 'combined':{'shuffle_speak':1,'shuffle_animal_soul':1},
 'unshuffled':{'shuffle_speak':0,'shuffle_animal_soul':0,'shuffle_npc_soul':False,'shuffle_fishing_pole':False,'shuffle_childs_wallet':False,'shuffle_grass_bush_soul':False},
 'speak_off':{'shuffle_speak':0},
 'npc_off':{'shuffle_npc_soul':False},
 'ut':{},
}
try:
 m=setup(1617,overrides={'boss_key_shuffle':'anywhere',**options[a.group]});w=m.worlds[1];full=m.get_all_state(False);ps=pond(w)
 ck('package version',w.world_version.as_simple_string(),'0.11.17')
 coverage['active_pond_checks']=len(ps);coverage['active_bushes']=sum(f.family=='bush' and f.name in {l.name for l in w.get_locations()} for f in FORK_LOCATIONS)
 ck('child + adult standard fish and prizes present',len(ps),32)
 ck('full inventory accessible in AP model',[l.name for l in w.get_locations() if not l.can_reach(full)],[])
 all_speech=['Speak']+['Speak '+x for x in ('Deku','Gerudo','Goron','Hylian','Kokiri','Zora')]
 required=[]
 if w.options.shuffle_npc_soul.value:required.append(('NPC Soul',['NPC Soul']))
 if w.options.shuffle_speak.value:required.append(('Speak',all_speech))
 if w.options.shuffle_animal_soul.value:required.append(('Fish Soul',['Animal Soul','Fish Soul']))
 if w.options.shuffle_fishing_pole.value:required.append(('Fishing Pole',['Fishing Pole']))
 if w.options.shuffle_childs_wallet.value:required.append(('Wallet',['Progressive Wallet','Child Wallet']))
 for name,names in required:
  # Child Wallet is a virtual effect of Progressive Wallet, not a valid item
  # name in some versions; direct remove only the real pool item is necessary.
  names=[n for n in names if n in w.item_name_to_id]
  s=without(full,w,names)
  ck(name+' missing: physical Fishing Hole still reachable',w.get_region(Regions.LH_FISHING_HOLE).can_reach(s))
  for l in ps:ck(name+' missing blocks '+l.name,l.can_reach(s),False)
  restored=s.copy()
  for n in names:
   for _ in range(full.count(n,w.player)):restored.collect(w.create_item(n),True)
  ck(name+' restore reopens all pond checks',[l.name for l in ps if not l.can_reach(restored)],[])
  ck(name+' independent full snapshot remains reachable',[l.name for l in ps if not l.can_reach(full)],[])
 # The rod helper itself is tested in both reachable ages with bare inventory.
 b=(Regions.LH_FISHING_HOLE,w);r=can_use(Items.FISHING_POLE,b).resolve(w);w.register_rule_dependencies(r)
 for age in (Ages.CHILD,Ages.ADULT):
  for npc,talk,fish,rod,wallet in itertools.product((False,True),repeat=5):
   ns=[]
   if npc:ns+=['NPC Soul']
   if talk:ns+=['Speak' if w.options.shuffle_speak.value==1 else 'Speak Hylian']
   if fish:ns+=['Animal Soul' if w.options.shuffle_animal_soul.value==1 else 'Fish Soul']
   if rod:ns+=['Fishing Pole']
   if wallet:ns+=['Progressive Wallet']
   s=bare(m,w,ns);s._soh_age[w.player]=age
   expected=(npc or not w.options.shuffle_npc_soul.value) and (talk or not w.options.shuffle_speak.value) and (fish or not w.options.shuffle_animal_soul.value) and (rod or not w.options.shuffle_fishing_pole.value) and (wallet or not w.options.shuffle_childs_wallet.value)
   ck(f'rod action {age} NPC={npc} talk={talk} fish={fish} rod={rod} wallet={wallet}',r(s),expected)
 if w.options.shuffle_speak.value==2:
  s=without(full,w,['Speak Hylian','Speak']);s.collect(w.create_item('Speak Goron'),True)
  ck('wrong language cannot start fishing',[l.name for l in ps if l.can_reach(s)],[])
 if w.options.shuffle_animal_soul.value==2:
  s=without(full,w,['Fish Soul']);s.collect(w.create_item('Animal Soul'),True)
  ck('global animal soul cannot replace individual Fish Soul',[l.name for l in ps if l.can_reach(s)],[])
 if w.options.shuffle_animal_soul.value==1:
  s=without(full,w,['Animal Soul']);s.collect(w.create_item('Fish Soul'),True)
  ck('individual Fish Soul cannot replace combined Animal Soul',[l.name for l in ps if l.can_reach(s)],[])
 # Overworld/grotto bottled fish are deliberately not NPC minigames.
 other=[l for l in w.get_locations() if l.name in ('ZD Fish 1','ZD Fish 2','ZD Fish 3','ZD Fish 4','ZD Fish 5') or l.name.endswith('Grotto Fish')]
 s=without(full,w,['NPC Soul',*all_speech,'Fishing Pole'])
 ck('ordinary bottled fish not given NPC/rod prerequisites',[l.name for l in other if not l.can_reach(s)],[])
 coverage['bottle_fish_controls']=len(other)
 # Walk-through bushes (En_Wood02), as distinct from En_Kusa grass.
 bs=[f for f in FORK_LOCATIONS if f.family=='bush' and f.name in {l.name for l in w.get_locations()}]
 # Remove every physical weapon/Grab while preserving source-region reachability
 # from the full state's events; evaluate checks only where that region is reachable.
 weapons=['Grab / Power Bracelet','Progressive Strength Upgrade','Progressive Strength','Progressive Bomb Bag','Progressive Bombchu Bag','Bombchu Bag','Bombchus (5)','Bombchus (10)','Bombchus (20)','Kokiri Sword','Master Sword',"Giant's Knife","Biggoron's Sword",'Boomerang','Megaton Hammer','Progressive Hookshot','Progressive Bow','Progressive Slingshot','Roll']
 s=without(full,w,[n for n in weapons if n in w.item_name_to_id])
 reached=[f for f in bs if w.get_location(f.name).parent_region.can_reach(s)]
 coverage['bushes_with_reachable_parent_no_weapons']=len(reached)
 ck('all reachable bushes do not require a cutting tool',[f.name for f in reached if not w.get_location(f.name).can_reach(s)],[])
 if w.options.shuffle_grass_bush_soul.value:
  no_soul=without(full,w,['Grass / Bush Soul'])
  ck('every bush still requires its soul',[f.name for f in bs if w.get_location(f.name).can_reach(no_soul)],[])
 empty=bare(m,w,['Grass / Bush Soul']);empty.sweep_for_advancements()
 near=[f for f in bs if f.rc.startswith('RC_HF_BUSH_NEAR_LAKE_')]
 ck('field reachable with only grass/bush soul',w.get_region(Regions.HYRULE_FIELD).can_reach(empty))
 ck('walk through all eleven lake-side Field bushes',[f.name for f in near if not w.get_location(f.name).can_reach(empty)],[])
 grasses=[w.get_location(n) for n in ('KF Child Grass Maze 1','KF Child Grass Maze 2') if n in {l.name for l in w.get_locations()}]
 ck('grass controls exist',bool(grasses))
 ck('running does not collect cuttable grass',[l.name for l in grasses if l.can_reach(empty)],[])
 if a.group=='ut':
  slot=convert_to_base_types(w.fill_slot_data())
  tm=setup(1699,overrides={'shuffle_npc_soul':False,'shuffle_speak':0,'shuffle_animal_soul':0,'shuffle_bushes':False,'shuffle_grass_bush_soul':False},passthrough=slot);tw=tm.worlds[1];tf=tm.get_all_state(False)
  ck('UT authoritative NPC/language/animal/soul options',[tw.options.shuffle_npc_soul.value,tw.options.shuffle_speak.value,tw.options.shuffle_animal_soul.value,tw.options.shuffle_grass_bush_soul.value],[1,2,2,1])
  for missing in ([],['NPC Soul'],['Speak Hylian'],['Fish Soul'],['Fishing Pole'],['Grass / Bush Soul']):
   expected_state=without(full,w,missing);tracked_state=without(tf,tw,missing)
   selected=[l.name for l in ps]+[f.name for f in bs]
   ck('UT reconstructed fish/bush parity missing '+str(missing),[n for n in selected if w.get_location(n).can_reach(expected_state)!=tw.get_location(n).can_reach(tracked_state)],[])
except Exception as e:
 traceback.print_exc();results.append(dict(test='unhandled exception',passed=False,error=repr(e),traceback=traceback.format_exc()))
rpt=dict(group=a.group,checks=results,total=len(results),failures=sum(not r['passed'] for r in results),coverage=coverage,scope=__doc__)
a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(rpt,indent=2));print('TOTAL',rpt['total'],'FAILURES',rpt['failures'],coverage,flush=True)
raise SystemExit(bool(rpt['failures']))
