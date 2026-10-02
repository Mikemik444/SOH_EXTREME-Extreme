"""Lower-stream Octoroks need footing and a usable underwater attack, not just Swim."""
from run_case import setup, BOOTSTRAP
from ut_harness import tracker
from NetUtils import convert_to_base_types
from pathlib import Path
import argparse, json
p=argparse.ArgumentParser(parents=[BOOTSTRAP]);p.add_argument('--ut-core',type=Path,required=True);p.add_argument('--report',type=Path,required=True)
a=p.parse_args();tests=[]
def ck(name,actual,expected):
    tests.append(dict(test=name,actual=bool(actual),expected=bool(expected),passed=bool(actual)==bool(expected)))
opts=dict(closed_forest='off',door_of_time='song_only',starting_age='child',shuffle_enemy_drops=True,
    shuffle_enemy_soul='individual_enemies',shuffle_swim=True,shuffle_flow_of_time=False,
    shuffle_npc_soul=False,shuffle_speak='off',shuffle_ocarina_buttons=False,song_note_shuffle='off',
    lock_overworld_doors=False,tricks_in_logic=[],enable_all_tricks=False,
    start_inventory={},start_inventory_from_pool={})
for mode in ('individual_enemies','all_enemies_as_1','off'):
    m=setup(100148,overrides={**opts,'shuffle_enemy_soul':mode},stop_before='pre_fill');w=m.worlds[1];ev=tracker(w,a.ut_core)
    checks=[w.get_location(f'Enemy Defeat: Gerudo Valley Room 0 Octorok Spawn {i}') for i in (3,5)]
    for loc,ident in zip(checks,(9800681,9800683)):ck('stable ID '+str(ident),loc.address==ident,True)
    for mask in range(64):
        adult,soul,swim,irons,hook,bow=[bool(mask&(1<<i)) for i in range(6)]
        names=['Climb','Strength Upgrade','Master Sword']
        if adult:names+=['Progressive Ocarina','Song of Time']
        if soul and mode!='off':names+=['Octorok Soul' if mode=='individual_enemies' else 'Enemy Soul']
        if swim:names+=['Progressive Scale']
        if irons:names+=['Iron Boots']
        if hook:names+=['Progressive Hookshot']
        if bow:names+=['Progressive Bow']
        result=ev(names);expected=adult and (soul or mode=='off') and swim and irons and hook
        for loc in checks:
            ck(f'{mode}/{mask} AP {loc.address}',loc.can_reach(result.state),expected)
            ck(f'{mode}/{mask} UT {loc.address}',loc.name in result.in_logic_locations,expected)
    # Longshot is a valid upgrade; an unrelated ranged weapon cannot replace it.
    full=['Progressive Ocarina','Song of Time','Octorok Soul','Enemy Soul','Progressive Scale','Iron Boots','Progressive Hookshot','Progressive Hookshot']
    for loc in checks:ck(mode+' Longshot '+str(loc.address),loc.name in ev(full).in_logic_locations,True)
    # Existing server slot settings must restore the same rules.
    if mode=='individual_enemies':
        slot=convert_to_base_types(w.fill_slot_data())
        rw=setup(100148,overrides={**opts,'shuffle_enemy_soul':'off'},passthrough=slot,stop_before='pre_fill').worlds[1]
        rt=tracker(rw,a.ut_core)
        for omitted in ('Iron Boots','Progressive Hookshot','Octorok Soul'):
            result=rt([n for n in full if n!=omitted]+['Progressive Bow'])
            for loc in checks:ck('reconstructed missing '+omitted+' '+str(loc.address),loc.name in result.in_logic_locations,False)
    # The new restriction is confined to the lower stream: upper stream still
    # uses its normal Swim + adult ranged route, without Iron Boots.
    result=ev(['Progressive Ocarina','Song of Time','Octorok Soul','Enemy Soul','Progressive Scale','Progressive Bow'])
    for i in (4,6,7):
        name=f'Enemy Defeat: Gerudo Valley Room 0 Octorok Spawn {i}'
        ck(mode+' upper stream unchanged '+str(i),name in result.in_logic_locations,True)
# With Swim shuffle disabled, its ability is innate; equipment is still needed.
w=setup(100148,overrides={**opts,'shuffle_swim':False},stop_before='pre_fill').worlds[1]
ev=tracker(w,a.ut_core)
full=['Progressive Ocarina','Song of Time','Octorok Soul','Iron Boots','Progressive Hookshot']
for omitted in (None,'Iron Boots','Progressive Hookshot'):
    result=ev([n for n in full if n!=omitted])
    for i in (3,5):
        loc=w.get_location(f'Enemy Defeat: Gerudo Valley Room 0 Octorok Spawn {i}')
        ck(f'innate Swim missing {omitted} AP {i}',loc.can_reach(result.state),omitted is None)
        ck(f'innate Swim missing {omitted} UT {i}',loc.name in result.in_logic_locations,omitted is None)
passed=all(t['passed'] for t in tests)
a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(dict(passed=passed,assertions=len(tests),tests=tests),indent=2))
print('RESULT',passed,len(tests),'assertions',flush=True)
for t in [t for t in tests if not t['passed']][:10]:print(t)
raise SystemExit(not passed)
