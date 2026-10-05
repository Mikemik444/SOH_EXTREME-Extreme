"""A grown bean needs a real child visit; a closed forest still blocks escape."""
from run_case import setup, BOOTSTRAP
from ut_harness import tracker
from pathlib import Path
import argparse, json
p=argparse.ArgumentParser(parents=[BOOTSTRAP])
p.add_argument('--ut-core',type=Path,required=True)
p.add_argument('--report',type=Path,required=True)
a=p.parse_args(); tests=[]
opts=dict(starting_age='child',closed_forest='off',kakariko_gate='open',
    door_of_time='song_only',start_with_song_of_time=False,song_note_shuffle='off',
    lock_overworld_doors=False,shuffle_ocarina_buttons=False,
    shuffle_swim=True,shuffle_climb=True,shuffle_grab=True,shuffle_animal_soul=2,
    shuffle_rock_boulder_soul=True,shuffle_bean_souls=True,
    shuffle_merchants='all',start_with_magic_beans=False,
    start_inventory={},start_inventory_from_pool={},tricks_in_logic=[],enable_all_tricks=False)
name='ZR Near Domain Freestanding PoH'
def ck(label,actual,expected):
    tests.append(dict(test=label,actual=actual,expected=expected,passed=actual==expected))
w=setup(100156,overrides=opts,stop_before='pre_fill').worlds[1];ev=tracker(w,a.ut_core)
base=['Progressive Scale']*2+['Hover Boots','Magic Bean Pack',"Zora's River Bean Soul",
    'Song of Time','Progressive Ocarina','Flow of Time']
for missing in (None,'Magic Bean Pack',"Zora's River Bean Soul",'Song of Time','Hover Boots'):
    inv=[n for n in base if n!=missing]; result=ev(inv)
    ck(f'bean route missing={missing} no Climb',result.state.has('Climb',1),False)
    ck(f'bean route missing={missing} planted',result.state.has('ZR Bean Planted',1),
        missing not in ('Magic Bean Pack',"Zora's River Bean Soul"))
    ck(f'bean route missing={missing} time travel',result.state.has('Time Travel',1),missing!='Song of Time')
    ck(f'bean route missing={missing} AP',w.get_location(name).can_reach(result.state),missing is None)
    ck(f'bean route missing={missing} UT',name in result.in_logic_locations,missing is None)
for child_items in (['Boomerang'], ['Cucco Soul','Strength Upgrade']):
    result=ev([n for n in base if n!='Hover Boots']+child_items)
    ck(str(child_items)+' both ages available',result.state.has('Time Travel',1),True)
    ck(str(child_items)+' adult bean cannot supply child approach AP',w.get_location(name).can_reach(result.state),False)
    ck(str(child_items)+' adult bean cannot supply child approach UT',name in result.in_logic_locations,False)
w=setup(100156,overrides={**opts,'closed_forest':'on'},stop_before='pre_fill').worlds[1]
result=tracker(w,a.ut_core)(['Progressive Scale']*2+['Boomerang','Cucco Soul','Strength Upgrade'])
ck('closed forest no invented field route',w.get_region('Hyrule Field').can_reach(result.state),False)
for location in (name,'GV Waterfall Freestanding PoH'):
    ck('closed forest AP '+location,w.get_location(location).can_reach(result.state),False)
    ck('closed forest UT '+location,location in result.in_logic_locations,False)
passed=all(t['passed'] for t in tests)
a.report.parent.mkdir(parents=True,exist_ok=True)
a.report.write_text(json.dumps(dict(passed=passed,checks=len(tests),failures=sum(not t['passed'] for t in tests),tests=tests),indent=2))
print('RESULT',passed,len(tests))
for t in tests:
    if not t['passed']:print(t)
raise SystemExit(not passed)
