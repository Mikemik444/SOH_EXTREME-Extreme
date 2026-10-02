"""The cow grotto is below the summit climb; its exit cannot bypass that climb.

Exercise actual AP and Universal Tracker with small received-item inventories,
both starting ages, disabled shuffles and restored slot settings.
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
opts = dict(closed_forest='off', kakariko_gate='open', door_of_time='song_only',
    lock_overworld_doors=False, song_note_shuffle='off', start_with_song_of_time=False,
    shuffle_ocarina_buttons=False, shuffle_climb=True, shuffle_shovel=True,
    shuffle_rock_boulder_soul=True, bombchu_bag='progressive_bags',
    start_inventory={}, start_inventory_from_pool={}, tricks_in_logic=[], enable_all_tricks=False)
pickups = [f'DMT Cow Grotto Rupee {i}' for i in range(1, 7)] + [
    'DMT Cow Grotto Red Rupee', 'DMT Cow Grotto Left Heart',
    'DMT Cow Grotto Middle Left Heart', 'DMT Cow Grotto Middle Right Heart',
    'DMT Cow Grotto Right Heart']

def ck(label, actual, expected):
    tests.append(dict(test=label, actual=actual, expected=expected, passed=actual == expected))

def verify(w, label, shovel_shuffle=True, rock_shuffle=True):
    # The in-game tracker supplies actual shield equipment separately from
    # received AP items. Give the child summit's safety check a real shield.
    w._extreme_live_shields = 2
    ev = tracker(w, a.ut_core)
    for name, address in zip(pickups, list(range(1646,1653))+list(range(1642,1646))):
        ck(label+' stable ID '+name, w.get_location(name).address, address)
    for method in (None, 'Progressive Bomb Bag', 'Bombchu Bag'):
        for bits in range(8):
            inv = [method] if method else []
            if bits&1: inv.append('Shovel')
            if bits&2: inv.append('Rock / Boulder Soul')
            if bits&4: inv.append('Climb')
            result = ev(inv)
            tag = f'{label}/{method}/{bits}'
            physical = method is not None and (not rock_shuffle or bool(bits&2))
            accessible = physical and (not shovel_shuffle or bool(bits&1))
            ck(tag+' trail approach', w.get_region('Death Mountain Trail').can_reach(result.state), True)
            ck(tag+' no age change', result.state.has('Time Travel', 1), False)
            ck(tag+' grotto access', w.get_region('DMT Cow Grotto').can_reach(result.state), accessible)
            ck(tag+' summit keeps climb', w.get_region('Death Mountain Summit').can_reach(result.state),
               physical and bool(bits&4))
            for name in pickups:
                ck(tag+' AP '+name, w.get_location(name).can_reach(result.state), accessible)
                ck(tag+' UT '+name, name in result.in_logic_locations, accessible)
            ck(tag+' cow keeps interaction', w.get_location('DMT Cow Grotto Cow').can_reach(result.state), False)
            ck(tag+' cow keeps interaction UT', 'DMT Cow Grotto Cow' in result.in_logic_locations, False)
    # The three requested items alone suffice; no shield is needed below the
    # climbing wall, and there is no Cow Soul, song, Grab or Climb in this bag.
    w._extreme_live_shields = 0
    result = ev(['Shovel', 'Progressive Bomb Bag', 'Rock / Boulder Soul'])
    for name in pickups:
        ck(label+' only three items AP '+name, w.get_location(name).can_reach(result.state), True)
        ck(label+' only three items UT '+name, name in result.in_logic_locations, True)

for age in ('child', 'adult'):
    options = {**opts, 'starting_age': age}
    w = setup(100154, overrides=options, stop_before='pre_fill').worlds[1]
    verify(w, age)
    if age == 'child':
        slot = convert_to_base_types(w.fill_slot_data())
        old = setup(100154, overrides={**options, 'shuffle_climb':False,
            'shuffle_shovel':False, 'shuffle_rock_boulder_soul':False},
            passthrough=slot, stop_before='pre_fill').worlds[1]
        verify(old, 'restored child slot')
for option in ('shuffle_shovel', 'shuffle_rock_boulder_soul'):
    w = setup(100154, overrides={**opts, 'starting_age':'child', option:False},
              stop_before='pre_fill').worlds[1]
    verify(w, option+' off', option!='shuffle_shovel', option!='shuffle_rock_boulder_soul')

passed = all(t['passed'] for t in tests)
a.report.parent.mkdir(parents=True, exist_ok=True)
a.report.write_text(json.dumps(dict(passed=passed, checks=len(tests),
    failures=sum(not t['passed'] for t in tests), tests=tests), indent=2))
print('RESULT', passed, len(tests), flush=True)
for t in [t for t in tests if not t['passed']][:20]: print(t)
raise SystemExit(not passed)
