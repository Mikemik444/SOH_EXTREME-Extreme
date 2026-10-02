"""Real AP/UT gate access: Gerudo NPC soul, exact language, age and approach."""
from run_case import setup, BOOTSTRAP
from ut_harness import tracker
from NetUtils import convert_to_base_types
from pathlib import Path
import argparse,json
p=argparse.ArgumentParser(parents=[BOOTSTRAP]);p.add_argument('--ut-core',type=Path,required=True);p.add_argument('--report',type=Path,required=True)
a=p.parse_args();tests=[];coverage={}
names=('Gerudo Training Ground Lobby Left Chest','Wasteland Before Quicksand Crate')
opts=dict(closed_forest='off',starting_age='adult',door_of_time='song_only',
    shuffle_climb=True,shuffle_grab=False,shuffle_roll=False,shuffle_open_chest='progressive',
    shuffle_npc_soul=True,shuffle_speak='individual_languages',shuffle_childs_wallet=True,
    shuffle_crates='all',shuffle_crate_soul=False,shuffle_enemy_drops=True,
    shuffle_enemy_soul='off',shuffle_ocarina_buttons=False,song_note_shuffle='off',
    shuffle_flow_of_time=False,lock_overworld_doors=False,
    enable_all_tricks=False,tricks_in_logic=[],start_inventory={},start_inventory_from_pool={})
base=['Progressive Hookshot']*2+['Progressive Bow','Progressive Wallet','Open Chest','Open Chest']
def ck(label,actual,expected):
    tests.append(dict(test=label,actual=actual,expected=expected,passed=actual==expected))
def interior(l):
    parent=l.parent_region.name.lower()
    return 'training ground' in parent or 'wasteland' in parent or l.name.startswith('EXTREME Gtg ')
def compare(w,ev,inv,expected,label):
    r=ev(inv)
    for name,ok in zip(names,expected):
        ck(label+' AP '+name,bool(w.get_location(name).can_reach(r.state)),ok)
        ck(label+' UT '+name,name in r.in_logic_locations,ok)
    if not any(expected):
        pending=[l for l in w.get_locations() if l.address is not None and interior(l)]
        ck(label+' all interior AP checks blocked',sum(l.can_reach(r.state) for l in pending),0)
        ck(label+' all interior UT checks blocked',sum(l.name in r.in_logic_locations for l in pending),0)
    return r
for mode,npc_shuffle in (('individual_languages',True),('on',True),('off',True),('individual_languages',False),('on',False),('off',False)):
    options={**opts,'shuffle_speak':mode,'shuffle_npc_soul':npc_shuffle}
    w=setup(100150,overrides=options,stop_before='pre_fill').worlds[1];ev=tracker(w,a.ut_core)
    for name in names:ck(mode+' location exists '+name,w.get_location(name).address is not None,True)
    coverage[f'{mode}/{npc_shuffle}']=len([l for l in w.get_locations() if l.address is not None and interior(l)])
    for mask in range(16):
        card,npc,speak,climb=[bool(mask&(1<<i)) for i in range(4)]
        inv=base.copy()
        if card:inv+=['Gerudo Membership Card']
        if npc:inv+=['NPC Soul']
        if speak:inv+=['Speak' if mode=='on' else 'Speak Gerudo']
        if climb:inv+=['Climb']
        gate=card and (npc or not npc_shuffle) and (speak or mode=='off')
        compare(w,ev,inv,(gate,gate and climb),f'{mode}/{npc_shuffle}/{mask}')
    if mode=='individual_languages' and npc_shuffle:
        full=base+['Gerudo Membership Card','NPC Soul','Speak Gerudo','Climb']
        compare(w,ev,[n for n in full if n!='Speak Gerudo']+['Speak Hylian'],(False,False),'wrong language')
        compare(w,ev,[n for n in full if n!='Progressive Wallet'],(False,True),'no wallet')
        slot=convert_to_base_types(w.fill_slot_data())
        restored=setup(100150,overrides={**options,'shuffle_npc_soul':False,'shuffle_speak':'off'},passthrough=slot,stop_before='pre_fill').worlds[1]
        compare(restored,tracker(restored,a.ut_core),[n for n in full if n!='NPC Soul'],(False,False),'existing slot missing NPC soul')
        compare(restored,tracker(restored,a.ut_core),[n for n in full if n!='Speak Gerudo'],(False,False),'existing slot missing Gerudo speech')
        compare(restored,tracker(restored,a.ut_core),full,(True,True),'existing slot complete')
# Unshuffled Climb is innate, but does not replace the guard interaction.
w=setup(100150,overrides={**opts,'shuffle_climb':False},stop_before='pre_fill').worlds[1];ev=tracker(w,a.ut_core)
full=base+['Gerudo Membership Card','NPC Soul','Speak Gerudo']
compare(w,ev,full,(True,True),'Climb shuffle off')
# A real child inventory cannot use adult-only entry until time travel is reachable.
w=setup(100150,overrides={**opts,'starting_age':'child'},stop_before='pre_fill').worlds[1];ev=tracker(w,a.ut_core)
full+=['Climb','Progressive Ocarina']
compare(w,ev,full,(False,False),'child no adult access')
compare(w,ev,full+['Song of Time'],(True,True),'child with adult access')
# Requiem reaches the Colossus-side wasteland independently of the gate guard.
warp=ev(['Progressive Ocarina','Requiem of Spirit'])
ck('Requiem reaches wasteland near Colossus without soul/speech/card',warp.state.can_reach('Wasteland Near Colossus','Region',1),True)
ck('Requiem does not open the fortress gate',warp.state.has('GF Gate Open',1),False)
# The existing GTG ledge clip remains an explicitly enabled alternate route.
w=setup(100150,overrides={**opts,'tricks_in_logic':['GF Ledge Clip into GTG']},stop_before='pre_fill').worlds[1];ev=tracker(w,a.ut_core)
compare(w,ev,base+['Climb','Gerudo Membership Card'],(True,False),'enabled GTG clip without guard soul/speech')
# A reverse desert traversal reaches the sand side without opening either gate.
w=setup(100150,overrides={**opts,'tricks_in_logic':['HW Reverse']},stop_before='pre_fill').worlds[1];ev=tracker(w,a.ut_core)
reverse=compare(w,ev,base+['Progressive Ocarina','Requiem of Spirit'],(False,True),'enabled reverse desert route without guard')
ck('reverse desert arrival leaves fortress gate closed',reverse.state.has('GF Gate Open',1),False)
passed=all(t['passed'] for t in tests)
a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(dict(passed=passed,checks=len(tests),coverage=coverage,tests=tests),indent=2))
print('RESULT',passed,len(tests),'assertions',flush=True)
for t in [t for t in tests if not t['passed']][:12]:print(t)
raise SystemExit(not passed)
