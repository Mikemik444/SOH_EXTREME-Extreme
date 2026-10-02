"""Physical ledge access for Kak's silver boulder in real AP and Universal Tracker."""
from run_case import setup, BOOTSTRAP
from ut_harness import tracker
from NetUtils import convert_to_base_types
from pathlib import Path
import argparse,json
p=argparse.ArgumentParser(parents=[BOOTSTRAP]);p.add_argument('--ut-core',type=Path,required=True);p.add_argument('--report',type=Path,required=True)
a=p.parse_args();tests=[];name='EXTREME Kak Silver Boulder'
opts=dict(closed_forest='off',starting_age='adult',door_of_time='song_only',shuffle_boulders='all',
    shuffle_climb=True,shuffle_grab=True,shuffle_rock_boulder_soul=True,shuffle_animal_soul='individual_animals',
    shuffle_flow_of_time=True,frozen_starting_time='night',shuffle_ocarina_buttons=False,song_note_shuffle='off',
    shuffle_npc_soul=False,shuffle_speak='off',lock_overworld_doors=False,
    enable_all_tricks=False,tricks_in_logic=[],start_inventory={},start_inventory_from_pool={})
def ck(label,actual,expected):
    tests.append(dict(test=label,actual=bool(actual),expected=bool(expected),passed=bool(actual)==bool(expected)))
def compare(w,ev,inv,expected,label):
    r=ev(inv)
    ck(label+' AP',w.get_location(name).can_reach(r.state),expected)
    ck(label+' UT',name in r.in_logic_locations,expected)
for mode,shuffled in (('individual_animals',True),('all_animals_as_1',True),('off',True),('off',False)):
    options={**opts,'shuffle_animal_soul':mode,'shuffle_climb':shuffled,'shuffle_grab':shuffled}
    w=setup(100149,overrides=options,stop_before='pre_fill').worlds[1];ev=tracker(w,a.ut_core)
    ck(mode+' stable ID',w.get_location(name).address==9700487,True)
    base=['Progressive Ocarina','Rock / Boulder Soul']+['Strength Upgrade']*(3 if shuffled else 2)
    for mask in range(16):
        climb,hover,day,cucco=[bool(mask&(1<<i)) for i in range(4)]
        inv=base.copy()
        if climb:inv+=['Climb']
        if hover:inv+=['Hover Boots']
        if day:inv+=['Flow of Time']
        if cucco and mode!='off':inv+=['Cucco Soul' if mode=='individual_animals' else 'Animal Soul']
        for hook in range(3):
            route=climb or not shuffled or hover or (hook==2 and day and (cucco or mode=='off'))
            compare(w,ev,inv+['Progressive Hookshot']*hook,route,f'{mode}/{shuffled}/{mask}/hook{hook}')
    full=base+['Song of Time','Climb']
    compare(w,ev,[n for n in full if n!='Rock / Boulder Soul'],False,mode+' no boulder soul')
    weak=full.copy();weak.remove('Strength Upgrade')
    compare(w,ev,weak,False,mode+' insufficient strength')
    if mode=='individual_animals':
        slot=convert_to_base_types(w.fill_slot_data())
        restored=setup(100149,overrides={**options,'shuffle_climb':False},passthrough=slot,stop_before='pre_fill').worlds[1]
        compare(restored,tracker(restored,a.ut_core),base+['Song of Time'],False,'existing slot no climb')
        compare(restored,tracker(restored,a.ut_core),full,True,'existing slot climb')
# Real child access does not permit lifting adult boulders until time travel.
w=setup(100149,overrides={**opts,'starting_age':'child','frozen_starting_time':'day'},stop_before='pre_fill').worlds[1];ev=tracker(w,a.ut_core)
full=['Progressive Ocarina','Rock / Boulder Soul','Climb']+['Strength Upgrade']*3
compare(w,ev,full,False,'child without adult access')
compare(w,ev,full+['Song of Time'],True,'child with adult access')
# The native night alternative is an explicitly enabled collision/jumpslash trick.
w=setup(100149,overrides={**opts,'tricks_in_logic':['Visible Collision']},stop_before='pre_fill').worlds[1];ev=tracker(w,a.ut_core)
base=['Progressive Ocarina','Song of Time','Rock / Boulder Soul']+['Strength Upgrade']*3+['Progressive Hookshot']*2
compare(w,ev,base,False,'night trick missing jumpslash')
compare(w,ev,base+['Master Sword'],True,'night trick with jumpslash')
passed=all(t['passed'] for t in tests)
a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(dict(passed=passed,checks=len(tests),tests=tests),indent=2))
print('RESULT',passed,len(tests),'assertions',flush=True)
for t in [t for t in tests if not t['passed']][:10]:print(t)
raise SystemExit(not passed)
