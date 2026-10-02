"""The indoor fishing sign inherits the locked entrance, not outdoor lake access.

Uses real AP reachability and Universal Tracker with received-item inventories.
"""
from run_case import setup, BOOTSTRAP
from ut_harness import tracker
from NetUtils import convert_to_base_types
from pathlib import Path
import argparse, json

p = argparse.ArgumentParser(parents=[BOOTSTRAP])
p.add_argument('--ut-core', type=Path, required=True)
p.add_argument('--report', type=Path, required=True)
a = p.parse_args(); tests = []
indoor = 'EXTREME Lh Fishing Pond Rectangle Sign'
outdoor = 'EXTREME Lh Fishing Sign'
opts = dict(closed_forest='off', door_of_time='song_only', starting_age='child',
    lock_overworld_doors=True, shuffle_sign_soul=True, skip_scarecrows_song=True,
    song_note_shuffle='off', start_with_song_of_time=False, shuffle_ocarina_buttons=False,
    start_inventory={}, start_inventory_from_pool={}, tricks_in_logic=[], enable_all_tricks=False)

def ck(label, actual, expected):
    tests.append(dict(test=label, actual=actual, expected=expected, passed=actual == expected))

def verify(w, label, locked, sign_shuffle, child):
    ev = tracker(w, a.ut_core)
    ck(label+' exact indoor parent', w.get_location(indoor).parent_region.name, 'LH Fishing Hole')
    ck(label+' stable check ID', w.get_location(indoor).address, 9700534)
    base = [it.name for it in w.multiworld.itempool if it.name not in
            ('Song of Time', 'Fishing Hole Key', 'Skeleton Key', 'Sign Soul')]
    for key in (None, 'Fishing Hole Key', 'Skeleton Key', 'Hylia Laboratory Key'):
        for soul in (False, True):
            r = ev(base + ([key] if key else []) + (['Sign Soul'] if soul else []))
            prefix = f'{label}/{key}/{soul}'
            door = not locked or key in ('Fishing Hole Key', 'Skeleton Key')
            readable = soul or not sign_shuffle
            ck(prefix+' no time travel', r.state.has('Time Travel', 1), False)
            ck(prefix+' island approach', w.get_region('LH Fishing Island').can_reach(r.state), True)
            ck(prefix+' physical pond access', w.get_region('LH Fishing Hole').can_reach(r.state), door)
            for name, expected in ((indoor, door and readable), (outdoor, readable)):
                ck(prefix+' AP '+name, w.get_location(name).can_reach(r.state), expected)
                ck(prefix+' UT '+name, name in r.in_logic_locations, expected)
    if child:
        # Reading a sign inside the building does not require renting a rod.
        inv = [n for n in base if n not in ('NPC Soul', 'Speak Hylian', 'Fishing Pole', 'Fish Soul')]
        r = ev(inv + ['Fishing Hole Key', 'Sign Soul'])
        ck(label+' no fishing prerequisites AP', w.get_location(indoor).can_reach(r.state), True)
        ck(label+' no fishing prerequisites UT', indoor in r.in_logic_locations, True)
        # Owning a key never substitutes for actually reaching the island.
        r = ev([n for n in base if n not in ('Progressive Scale', 'Swim')] + ['Fishing Hole Key', 'Sign Soul'])
        ck(label+' no island approach AP', w.get_location(indoor).can_reach(r.state), False)
        ck(label+' no island approach UT', indoor in r.in_logic_locations, False)

for age in ('child', 'adult'):
    for locked in (True, False):
        options = {**opts, 'starting_age': age, 'lock_overworld_doors': locked}
        w = setup(100153, overrides=options, stop_before='pre_fill').worlds[1]
        verify(w, f'{age}/locked={locked}', locked, True, age == 'child')
        if locked:
            slot = convert_to_base_types(w.fill_slot_data())
            old = setup(100153, overrides={**options, 'lock_overworld_doors': False},
                        passthrough=slot, stop_before='pre_fill').worlds[1]
            verify(old, age+'/restored locked settings', True, True, age == 'child')
w = setup(100153, overrides={**opts, 'shuffle_sign_soul': False}, stop_before='pre_fill').worlds[1]
verify(w, 'Sign Soul shuffle off', True, False, True)

passed = all(t['passed'] for t in tests)
a.report.parent.mkdir(parents=True, exist_ok=True)
a.report.write_text(json.dumps(dict(passed=passed, checks=len(tests), tests=tests), indent=2))
print('RESULT', passed, len(tests), flush=True)
for t in [t for t in tests if not t['passed']][:20]: print(t)
raise SystemExit(not passed)
