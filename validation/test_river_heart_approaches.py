"""Real received-item AP/UT routes for the two reported waterfall hearts."""
from run_case import setup, BOOTSTRAP
from ut_harness import tracker
from NetUtils import convert_to_base_types
from pathlib import Path
import argparse, json

p = argparse.ArgumentParser(parents=[BOOTSTRAP])
p.add_argument('--ut-core', type=Path, required=True)
p.add_argument('--report', type=Path, required=True)
a = p.parse_args(); tests = []
opts = dict(starting_age='child', closed_forest='off', kakariko_gate='open',
    door_of_time='song_only', start_with_song_of_time=False, song_note_shuffle='off',
    lock_overworld_doors=False, shuffle_ocarina_buttons=False,
    shuffle_swim=True, shuffle_climb=True, shuffle_grab=True, shuffle_animal_soul=2,
    shuffle_rock_boulder_soul=True, bombchu_bag='progressive_bags',
    start_inventory={}, start_inventory_from_pool={}, tricks_in_logic=[], enable_all_tricks=False)
zr = 'ZR Near Domain Freestanding PoH'; gv = 'GV Waterfall Freestanding PoH'

def ck(label, actual, expected):
    tests.append(dict(test=label, actual=actual, expected=expected, passed=actual == expected))

def verify(w, label, exhaustive=False):
    ev = tracker(w, a.ut_core); o = w.options
    child = o.starting_age.value == 0
    mode = o.shuffle_animal_soul.value
    ck(label+' ZR stable ID', w.get_location(zr).address, 107)
    ck(label+' GV stable ID', w.get_location(gv).address, 121)
    # Five independent capabilities, plus depth and a working rock-breaking tool.
    # Receiving adult equipment cannot manufacture adult access for a child.
    masks = range(32) if exhaustive else (0, 1, 2, 3, 7, 11, 15, 19, 23, 27, 30, 31)
    for method in (None, 'Progressive Bomb Bag', 'Bombchu Bag'):
        for scales in range(3):
            for bits in masks:
                inv = ['Progressive Scale'] * scales + ([method] if method else [])
                for flag, item in ((1, 'Climb'), (2, 'Rock / Boulder Soul'),
                        (4, 'Strength Upgrade'), (8, 'Animal Soul' if mode == 1 else 'Cucco Soul'),
                        (16, 'Boomerang')):
                    if bits & flag: inv.append(item)
                # Hovers are deliberately present: usable only on adult routes.
                inv.append('Hover Boots')
                result = ev(inv)
                climb = bool(bits & 1) or not o.shuffle_climb.value
                rock = bool(bits & 2) or not o.shuffle_rock_boulder_soul.value
                grab = bool(bits & 4) or not o.shuffle_grab.value
                cucco = bool(bits & 8) or mode == 0
                swim = scales >= 1 or not o.shuffle_swim.value
                deep = scales >= (2 if o.shuffle_swim.value else 1)
                upper = not child or deep or (rock and (method is not None or grab))
                approach = climb and (not child or swim or (grab and cucco))
                collect = not child or bool(bits & 16) or (grab and cucco)
                want_zr = upper and approach and collect
                want_gv = (child and grab and cucco) or (climb and swim)
                tag = f'{label}/{method}/scales={scales}/mask={bits}'
                ck(tag+' no time travel', result.state.has('Time Travel', 1), False)
                ck(tag+' upper river', w.get_region('Zora River').can_reach(result.state), upper)
                for name, want in ((zr, want_zr), (gv, want_gv)):
                    ck(tag+' AP '+name, w.get_location(name).can_reach(result.state), want)
                    ck(tag+' UT '+name, name in result.in_logic_locations, want)
    if mode == 2:
        result = ev(['Animal Soul', 'Strength Upgrade', 'Boomerang'])
        ck(label+' wrong shared soul cannot create GV Cucco', gv in result.in_logic_locations, False)

w = setup(100156, overrides=opts, stop_before='pre_fill').worlds[1]
verify(w, 'child individual', True)
slot = convert_to_base_types(w.fill_slot_data())
restored = setup(100156, overrides={**opts, 'shuffle_climb':False,
    'shuffle_rock_boulder_soul':False, 'shuffle_animal_soul':0},
    passthrough=slot, stop_before='pre_fill').worlds[1]
verify(restored, 'restored slot')
for label, changes in (
    ('shared soul', {'shuffle_animal_soul':1}),
    ('soul innate', {'shuffle_animal_soul':0}),
    ('Climb innate', {'shuffle_climb':False}),
    ('Grab innate', {'shuffle_grab':False}),
    ('Swim innate', {'shuffle_swim':False}),
    ('rock soul innate', {'shuffle_rock_boulder_soul':False}),
    ('adult only', {'starting_age':'adult'}),
):
    w = setup(100156, overrides={**opts, **changes}, stop_before='pre_fill').worlds[1]
    verify(w, label)
passed = all(t['passed'] for t in tests)
a.report.parent.mkdir(parents=True, exist_ok=True)
a.report.write_text(json.dumps(dict(passed=passed, checks=len(tests),
    failures=sum(not t['passed'] for t in tests), tests=tests), indent=2))
print('RESULT', passed, len(tests), flush=True)
for t in [t for t in tests if not t['passed']][:20]: print(t)
raise SystemExit(not passed)
