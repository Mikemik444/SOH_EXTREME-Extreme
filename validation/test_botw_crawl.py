"""Crawling into the Well gates stock, enemy, silver and boulder checks.

Use received inventories in the real AP/Universal Tracker evaluator, without
injecting region reachability or event items. Keep all existing network IDs.
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
opts = dict(starting_age='child', closed_forest='off', kakariko_gate='open',
    door_of_time='song_only', start_with_song_of_time=False, song_note_shuffle='off',
    lock_overworld_doors=False, shuffle_ocarina_buttons=False, shuffle_crawl=True,
    shuffle_climb=True, shuffle_rock_boulder_soul=True, shuffle_boulders='all',
    bombchu_bag='progressive_bags', start_inventory={}, start_inventory_from_pool={},
    tricks_in_logic=[], enable_all_tricks=False)
boulders = [f'EXTREME Botw Boulder {i}' for i in range(1, 7)]

def ck(label, actual, expected):
    tests.append(dict(test=label, actual=actual, expected=expected, passed=actual == expected))

def verify(w, label):
    ev = tracker(w, a.ut_core)
    for i, name in enumerate(boulders):
        ck(label+' stable ID '+name, w.get_location(name).address, 9700003+i)
    for weapon in (None, 'Progressive Bomb Bag', 'Bombchu Bag', 'Megaton Hammer'):
        for bits in range(16):
            # Boomerang can pass the entrance spider, but cannot break a boulder.
            inv = ['Progressive Ocarina', 'Boomerang']
            for bit, item in ((1, 'Crawl'), (2, 'Rock / Boulder Soul'),
                              (4, 'Climb'), (8, 'Song of Storms')):
                if bits & bit: inv.append(item)
            if weapon: inv.append(weapon)
            result = ev(inv)
            tag = f'{label}/{weapon}/{bits}'
            child = w.options.starting_age.current_key == 'child'
            drained = child and bool(bits & 8)
            crawl = bool(bits & 1) or not w.options.shuffle_crawl.value
            soul = bool(bits & 2) or not w.options.shuffle_rock_boulder_soul.value
            interior = drained and crawl
            collect = interior and soul and weapon in ('Progressive Bomb Bag', 'Bombchu Bag')
            ck(tag+' no age change', result.state.has('Time Travel', 1), False)
            ck(tag+' entryway', w.get_region('Bottom of the Well Entryway').can_reach(result.state), drained)
            ck(tag+' perimeter', w.get_region('Bottom of the Well Perimeter').can_reach(result.state), interior)
            ck(tag+' basement', w.get_region('Bottom of the Well Basement').can_reach(result.state), interior)
            for name in boulders:
                ck(tag+' AP '+name, w.get_location(name).can_reach(result.state), collect)
                ck(tag+' UT '+name, name in result.in_logic_locations, collect)
            # No checks inside the Well should leak through its entryway when
            # the child crawlspace cannot be passed, including other families.
            if not interior:
                for loc in w.get_locations():
                    if loc.address is not None and (loc.name.startswith(('Bottom of the Well ', 'EXTREME Botw '))
                            or loc.name.startswith('Enemy Defeat: Bottom of the Well ')):
                        ck(tag+' blocked AP '+loc.name, loc.can_reach(result.state), False)
                        ck(tag+' blocked UT '+loc.name, loc.name in result.in_logic_locations, False)

w = setup(100158, overrides=opts, stop_before='pre_fill').worlds[1]
verify(w, 'child')
slot = convert_to_base_types(w.fill_slot_data())
for label, changes, passthrough in (
    ('crawl innate', {'shuffle_crawl':False}, None),
    ('rock soul innate', {'shuffle_rock_boulder_soul':False}, None),
    ('no private graph', {'shuffle_enemy_drops':False, 'shuffle_silver':0}, None),
    ('adult without child access', {'starting_age':'adult'}, None),
    ('restored slot', {'shuffle_crawl':False, 'shuffle_rock_boulder_soul':False}, slot),
):
    w = setup(100158, overrides={**opts, **changes}, passthrough=passthrough,
              stop_before='pre_fill').worlds[1]
    verify(w, label)

passed = all(t['passed'] for t in tests)
a.report.parent.mkdir(parents=True, exist_ok=True)
a.report.write_text(json.dumps(dict(passed=passed, checks=len(tests),
    failures=sum(not t['passed'] for t in tests), tests=tests), indent=2))
print('RESULT', passed, len(tests), flush=True)
for t in [t for t in tests if not t['passed']][:20]: print(t)
raise SystemExit(not passed)
