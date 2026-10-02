"""Raised ZR stone and Skulltula routes through real AP and Universal Tracker."""
from run_case import setup, BOOTSTRAP
from ut_harness import tracker
from NetUtils import convert_to_base_types
from pathlib import Path
import argparse,json
p=argparse.ArgumentParser(parents=[BOOTSTRAP]);p.add_argument('--ut-core',type=Path,required=True);p.add_argument('--report',type=Path,required=True)
a=p.parse_args();tests=[]
names=('ZR GS Near Raised Grottos','ZR Near Grottos Gossip Stone Fairy','ZR Near Grottos Gossip Stone Big Fairy')
def ck(label,actual,expected):
    tests.append(dict(test=label,actual=bool(actual),expected=bool(expected),passed=bool(actual)==bool(expected)))
def compare(w,ev,inventory,expected,label):
    result=ev(inventory)
    for name,exp in zip(names,expected):
        ck(label+' AP '+name,w.get_location(name).can_reach(result.state),exp)
        ck(label+' UT '+name,name in result.in_logic_locations,exp)
opts=dict(closed_forest='off',starting_age='child',door_of_time='song_only',
    shuffle_climb=True,shuffle_grab=True,shuffle_swim=True,shuffle_animal_soul='individual_animals',
    shuffle_skull_tokens='all',shuffle_skulltula_soul=True,shuffle_enemy_soul='off',
    shuffle_stone_fairies=True,shuffle_rock_boulder_soul=True,
    shuffle_flow_of_time=False,skulls_sun_song=False,shuffle_ocarina_buttons=False,song_note_shuffle='off',
    shuffle_npc_soul=False,shuffle_speak='off',lock_overworld_doors=False,
    enable_all_tricks=False,tricks_in_logic=[],start_inventory={},start_inventory_from_pool={})
base=['Progressive Ocarina',"Epona's Song",'Song of Storms','Progressive Scale',
      'Progressive Bomb Bag','Rock / Boulder Soul','Skulltula Soul','Master Sword','Hover Boots','Shovel']
for mode,shuffled in (('individual_animals',True),('all_animals_as_1',True),('off',True),('off',False)):
    options={**opts,'shuffle_animal_soul':mode,'shuffle_climb':shuffled,'shuffle_grab':shuffled}
    w=setup(100149,overrides=options,stop_before='pre_fill').worlds[1];ev=tracker(w,a.ut_core)
    for name,ident in zip(names,(514,1950,1951)):ck(f'{mode}/{shuffled} stable ID {ident}',w.get_location(name).address==ident,True)
    for mask in range(16):
        climb,grab,cucco,adult=[bool(mask&(1<<i)) for i in range(4)]
        inv=base.copy()
        if climb:inv+=['Climb']
        if grab:inv+=['Strength Upgrade']
        if cucco and mode!='off':inv+=['Cucco Soul' if mode=='individual_animals' else 'Animal Soul']
        if adult:inv+=['Song of Time']
        ledge=(climb or not shuffled) and (adult or (grab or not shuffled) and (cucco or mode=='off'))
        for hook in range(3):
            # Native Longshot route reaches the Skulltula from below. It does
            # not reach the stone or replace the normal Hookshot ledge route.
            compare(w,ev,inv+['Progressive Hookshot']*hook,
                (adult and (hook==2 or hook>0 and ledge),ledge,ledge),f'{mode}/{shuffled}/{mask}/hook{hook}')
    if mode=='individual_animals':
        full=base+['Song of Time','Climb','Progressive Hookshot']
        compare(w,ev,[n for n in full if n!='Shovel'],(True,True,True),'outdoor checks need no shovel')
        compare(w,ev,[n for n in full if n!='Skulltula Soul'],(False,True,True),'missing skull soul')
        child=base+['Climb','Strength Upgrade','Cucco Soul']
        compare(w,ev,[n for n in child if n!="Epona's Song"],(False,False,True),'missing gossip song')
        compare(w,ev,[n for n in child if n!='Song of Storms'],(False,True,False),'missing storms')
        compare(w,ev,[n for n in child if n!='Progressive Ocarina'],(False,False,False),'missing ocarina')
        slot=convert_to_base_types(w.fill_slot_data())
        restored=setup(100149,overrides={**options,'shuffle_climb':False},passthrough=slot,stop_before='pre_fill').worlds[1]
        compare(restored,tracker(restored,a.ut_core),[n for n in full if n!='Climb'],(False,False,False),'restored slot missing climb')
        compare(restored,tracker(restored,a.ut_core),full,(True,True,True),'restored slot with climb')
# Night-only Skulltula cannot be forced out by Climb, Longshot, or age alone.
w=setup(100149,overrides={**opts,'shuffle_flow_of_time':True,'frozen_starting_time':'day'},stop_before='pre_fill').worlds[1]
ev=tracker(w,a.ut_core);full=base+['Song of Time','Climb','Progressive Hookshot','Progressive Hookshot']
compare(w,ev,full,(False,True,True),'frozen daytime')
compare(w,ev,full+['Flow of Time'],(True,True,True),'time unlocked')
passed=all(t['passed'] for t in tests)
a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(dict(passed=passed,checks=len(tests),tests=tests),indent=2))
print('RESULT',passed,len(tests),'assertions',flush=True)
for t in [t for t in tests if not t['passed']][:10]:print(t)
raise SystemExit(not passed)
