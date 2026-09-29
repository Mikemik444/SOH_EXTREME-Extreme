"""Physical ledge, crate action and frozen-time regressions through actual AP/UT."""
from run_case import setup, BOOTSTRAP
from ut_harness import tracker
from BaseClasses import ItemClassification, CollectionState
from worlds.soh_extreme._vendor_oot_soh.Enums import Regions, Ages, Events
from worlds.soh_extreme._vendor_oot_soh.LogicHelpers import can_break_crates, can_break_small_crates
from pathlib import Path
import argparse, itertools, json, hashlib
p = argparse.ArgumentParser(parents=[BOOTSTRAP])
p.add_argument('--ut-core', type=Path, required=True)
p.add_argument('--report', type=Path, required=True)
a = p.parse_args(); tests = []
def ck(name, actual, expected=True):
    tests.append(dict(test=name, actual=actual, expected=expected, passed=actual==expected))

common = dict(closed_forest='off', starting_age='child', door_of_time='song_only',
    shuffle_speak='off', shuffle_npc_soul=False, lock_overworld_doors=False,
    song_note_shuffle='off', shuffle_ocarina_buttons=False,
    shuffle_grab=True, shuffle_roll=True, shuffle_crate_soul=True,
    enable_all_tricks=False, tricks_in_logic=[])

for mode in ('individual_animals','all_animals_as_1','off'):
    m=setup(290937, overrides=dict(common, shuffle_animal_soul=mode), stop_before='pre_fill'); w=m.worlds[1]
    evaluate=tracker(w,a.ut_core)
    excluded={'Roll','Crate Soul','Strength Upgrade','Grab / Power Bracelet','Cucco Soul','Animal Soul',
        'Progressive Bomb Bag','Bombchu Bag','Bombchus (5)','Bombchus (10)','Bombchus (20)',
        'Progressive Hookshot','Megaton Hammer','Song of Time','Prelude of Light'}
    base=[it.name for it in m.itempool if it.name not in excluded]
    for grab,cucco,soul,roll in itertools.product((False,True),repeat=4):
        names=base+(['Strength Upgrade'] if grab else [])+(['Roll'] if roll else [])+(['Crate Soul'] if soul else [])
        if cucco and mode!='off': names += ['Cucco Soul' if mode=='individual_animals' else 'Animal Soul']
        result=evaluate(names); expected=grab and (cucco or mode=='off') and soul and roll
        for name in ('GV Crate Freestanding PoH','GV Freestanding PoH Crate'):
            ck(f'{mode}/{grab}/{cucco}/{soul}/{roll} AP {name}',w.get_location(name).can_reach(result.state),expected)
            ck(f'{mode}/{grab}/{cucco}/{soul}/{roll} UT {name}',name in result.in_logic_locations,expected)
    # A usable Longshot is a real adult alternative, preserving the native route.
    for count in (1,2):
        r=evaluate(base+['Song of Time','Progressive Ocarina','Crate Soul','Roll']+['Progressive Hookshot']*count)
        for name in ('GV Crate Freestanding PoH','GV Freestanding PoH Crate'):
            ck(f'{mode} adult hookshot tier {count} {name}',w.get_location(name).can_reach(r.state),count==2)
    # Crate Soul never supplies an action. Large/small crates have different tools.
    for age in (Ages.CHILD,Ages.ADULT):
        for soul in (False,True):
            for name,items,large,small in (
                ('nothing',[],False,False),('roll',['Roll'],True,True),
                ('bomb',['Progressive Bomb Bag'],True,True),('chu',['Bombchu Bag'],True,True),
                ('grab',['Strength Upgrade'],False,True),('stick',['Progressive Stick Capacity'],False,age==Ages.CHILD),
                ('sword',['Kokiri Sword'],False,age==Ages.CHILD),('hammer',['Megaton Hammer'],age==Ages.ADULT,age==Ages.ADULT)):
                s=CollectionState(m)
                for item in m.precollected_items[1]:s.remove(item)
                for n in items+(['Crate Soul'] if soul else []):s.collect(w.create_item(n),True)
                if name=='stick':
                    # Isolated action helper: supply its renewable-ammo event.
                    # Without it, capacity alone is not usable stick ammo.
                    s.collect(next(l.item for l in w.get_locations() if l.item and l.item.name==Events.CAN_FARM_STICKS),True)
                s._soh_age[1]=age
                b=(Regions.GERUDO_VALLEY,w)
                ck(f'{mode}/{age}/{soul}/{name} large crate helper',can_break_crates(b).resolve(w)(s),soul and large)
                ck(f'{mode}/{age}/{soul}/{name} small crate helper',can_break_small_crates(b).resolve(w)(s),soul and small)
    for name in sorted(n for n in w.item_name_to_id if 'Soul' in n):
        for classification in (None,ItemClassification.filler):
            item=w.create_item(name,classification=classification)
            ck(f'{name} always important override={classification}',bool(item.classification & ItemClassification.progression))

for phase in ('day','night'):
    m=setup(290938,overrides=dict(common,shuffle_flow_of_time=True,frozen_starting_time=phase),stop_before='pre_fill'); w=m.worlds[1]
    evaluate=tracker(w,a.ut_core)
    base=[it.name for it in m.itempool if it.name not in ('Flow of Time','Song of Time','Prelude of Light')]
    for flow in (False,True):
        result=evaluate(base+(['Flow of Time'] if flow else [])); day=phase=='day' or flow
        for i in range(1,4):
            name=f'EXTREME Hf Wonder Bridge {i}'
            ck(f'{phase}/{flow} bridge AP {i}',w.get_location(name).can_reach(result.state),day)
            ck(f'{phase}/{flow} bridge UT {i}',name in result.in_logic_locations,day)
        for region in ('Market Entrance','Market','Hyrule Castle Grounds','HC Past Gate','HC Moat','HC Garden'):
            ck(f'{phase}/{flow} region {region}',w.get_region(region).can_reach(result.state),day)
        if not day:
            # Every actual castle check, including fork checks and enemy checks,
            # must be blocked when no physical route into child castle exists.
            castle=[l for l in w.get_locations() if l.address is not None and
                    (l.name.startswith(('HC ','EXTREME Hc ','Enemy Defeat: Hyrule Castle')))]
            ck('castle coverage is nonempty',len(castle)>10)
            for l in castle:ck('frozen night no castle '+l.name,l.can_reach(result.state),False)
    # Removing a receipt must invalidate previously cached daytime access.
    s=evaluate(base+['Flow of Time']).state
    if phase=='night':
        s.remove(w.create_item('Flow of Time'))
        for i in range(1,4):ck(f'removed flow bridge {i}',w.get_location(f'EXTREME Hf Wonder Bridge {i}').can_reach(s),False)

passed=all(t['passed'] for t in tests)
a.report.parent.mkdir(parents=True,exist_ok=True)
a.report.write_text(json.dumps(dict(passed=passed,checks=len(tests),tests=tests,
    ut_source_sha256=hashlib.sha256(a.ut_core.read_bytes()).hexdigest()),indent=2),encoding='utf-8')
print('PASS' if passed else 'FAIL',len(tests),'assertions')
for t in [t for t in tests if not t['passed']][:25]:print(t)
raise SystemExit(0 if passed else 1)
