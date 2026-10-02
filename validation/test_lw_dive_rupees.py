"""Two physical scales plus a real Lost Woods route, not a blanket Climb gate."""
from run_case import setup, BOOTSTRAP
from ut_harness import tracker
from NetUtils import convert_to_base_types
from pathlib import Path
import argparse, json

p=argparse.ArgumentParser(parents=[BOOTSTRAP])
p.add_argument('--ut-core',type=Path,required=True)
p.add_argument('--report',type=Path,required=True)
a=p.parse_args();tests=[]
names=[f'LW Underwater Shortcut Rupee {i}' for i in range(1,9)]
opts=dict(starting_age='child',closed_forest='on',kakariko_gate='open',
    door_of_time='song_only',start_with_song_of_time=False,song_note_shuffle='off',
    shuffle_swim=True,shuffle_climb=True,shuffle_rock_boulder_soul=True,
    lock_overworld_doors=False,shuffle_ocarina_buttons=False,
    start_inventory={},start_inventory_from_pool={},tricks_in_logic=[],enable_all_tricks=False)

def ck(label,actual,expected):
    tests.append(dict(test=label,actual=actual,expected=expected,passed=actual==expected))

def verify(w,label,closed=True,child=True,climb_shuffle=True):
    ev=tracker(w,a.ut_core)
    for count in range(4):
        for bits in range(8):
            inv=['Progressive Scale']*count
            if bits&1:inv.append('Climb')
            if bits&2:inv.append('Progressive Bomb Bag')
            if bits&4:inv.append('Rock / Boulder Soul')
            result=ev(inv)
            local=bool(bits&1) or not climb_shuffle
            # Outside routes: bomb open the GC shortcut, or use the Silver
            # Scale river bypass and underwater ZR/LW tunnel in both directions.
            alternate=not closed and ((bits&6)==6 or count>=2)
            reachable=local or alternate
            expected=child and count>=2 and reachable
            tag=f'{label}/scales={count}/items={bits}'
            ck(tag+' no time travel',result.state.has('Time Travel',1),False)
            field_access=not closed or (local and ((bits&6)==6 or count>=2))
            ck(tag+' forest exit',w.get_region('Hyrule Field').can_reach(result.state),field_access)
            ck(tag+' Lost Woods route',w.get_region('Lost Woods').can_reach(result.state),reachable)
            for name in names:
                ck(tag+' AP '+name,w.get_location(name).can_reach(result.state),expected)
                ck(tag+' UT '+name,name in result.in_logic_locations,expected)

w=setup(100155,overrides=opts,stop_before='pre_fill').worlds[1]
verify(w,'closed forest')
slot=convert_to_base_types(w.fill_slot_data())
restored=setup(100155,overrides={**opts,'closed_forest':'off','shuffle_swim':False,
    'shuffle_climb':False},passthrough=slot,stop_before='pre_fill').worlds[1]
verify(restored,'restored closed forest')
for changes,label,kwargs in [({'closed_forest':'off'},'forest exit available',{'closed':False}),
    ({'shuffle_climb':False},'Climb innate',{'climb_shuffle':False}),
    ({'starting_age':'adult','closed_forest':'off'},'adult only',{'closed':False,'child':False})]:
    w=setup(100155,overrides={**opts,**changes},stop_before='pre_fill').worlds[1]
    verify(w,label,**kwargs)
passed=all(t['passed'] for t in tests)
a.report.parent.mkdir(parents=True,exist_ok=True)
a.report.write_text(json.dumps(dict(passed=passed,checks=len(tests),
    failures=sum(not t['passed'] for t in tests),tests=tests),indent=2))
print('RESULT',passed,len(tests),flush=True)
for t in [t for t in tests if not t['passed']][:25]:print(t)
raise SystemExit(not passed)
