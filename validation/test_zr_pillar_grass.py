"""ZR pillar grass: real AP/UT receipts must include the physical Cucco route.

No region access or time-travel event is injected. Exercises shuffled settings,
child-only spawns and misleading adult/remote equipment independently.
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

def ck(name, actual, expected):
    tests.append(dict(test=name, actual=bool(actual), expected=bool(expected), passed=bool(actual)==bool(expected)))

for mode, shuffled in [('individual_animals', True), ('all_animals_as_1', True), ('off', True), ('off', False)]:
    options = dict(closed_forest='off', starting_age='child', door_of_time='song_only',
        shuffle_grass='all', shuffle_grass_bush_soul=True, shuffle_grab=shuffled,
        shuffle_swim=shuffled, shuffle_animal_soul=mode, shuffle_rock_boulder_soul=True,
        shuffle_climb=True, lock_overworld_doors=False, shuffle_flow_of_time=False,
        shuffle_speak='off', shuffle_npc_soul=False, shuffle_ocarina_buttons=False,
        song_note_shuffle='off', tricks_in_logic=[], enable_all_tricks=False,
        start_inventory={}, start_inventory_from_pool={})
    m = setup(100147, overrides=options, stop_before='pre_fill'); w = m.worlds[1]
    evaluate = tracker(w, a.ut_core)
    grass = w.get_location('ZR Near Freestanding PoH Grass')
    ck(f'{mode}/{shuffled} stable AP ID', grass.address == 2177, True)
    for mask in range(64):
        grab, cucco, swim, soul, cut, adult = [bool(mask & (1 << i)) for i in range(6)]
        names = ['Rock / Boulder Soul', 'Climb', 'Master Sword', 'Hover Boots']
        # Actual deep swimming opens the upper river without explosives or Grab.
        if swim: names += ['Progressive Scale'] * 2
        elif not shuffled: names += ['Progressive Scale']  # ordinary Silver Scale opens upper-river access
        if grab: names += ['Strength Upgrade']
        if cucco and mode != 'off': names += ['Cucco Soul' if mode == 'individual_animals' else 'Animal Soul']
        if soul: names += ['Grass / Bush Soul']
        # Boomerang can cut grass but cannot replace reaching this child pillar.
        if cut: names += ['Boomerang']
        if adult: names += ['Progressive Ocarina', 'Song of Time']
        result = evaluate(names)
        expected = (grab or not shuffled) and (cucco or mode == 'off') and (swim or not shuffled) and soul and cut
        label = f'{mode}/{shuffled}/{mask}'
        ck(label+' AP', grass.can_reach(result.state), expected)
        ck(label+' UT', grass.name in result.in_logic_locations, expected)
    # Adult access/equipment must not make this child-only actor spawn as adult.
    # Start as adult, with Door of Time shut and no playable Song of Time.
    adult_m = setup(100148, overrides={**options, 'starting_age':'adult'}, stop_before='pre_fill')
    adult_w = adult_m.worlds[1]
    adult_result = tracker(adult_w, a.ut_core)(['Grass / Bush Soul', 'Cucco Soul', 'Animal Soul',
        'Strength Upgrade', 'Progressive Scale', 'Progressive Scale', 'Boomerang', 'Hover Boots', 'Master Sword', 'Climb'])
    ck(f'{mode}/{shuffled} adult without child access', 'ZR Near Freestanding PoH Grass' in adult_result.in_logic_locations, False)

    if mode == 'individual_animals':
        slot = convert_to_base_types(w.fill_slot_data())
        restored = setup(100147, overrides={**options, 'shuffle_grab':False, 'shuffle_animal_soul':'off'},
            stop_before='pre_fill', passthrough=slot).worlds[1]
        ev = tracker(restored, a.ut_core)
        for grab in (False, True):
            for cucco in (False, True):
                inventory = ['Progressive Scale']*2 + ['Grass / Bush Soul', 'Boomerang']
                if grab: inventory += ['Strength Upgrade']
                if cucco: inventory += ['Cucco Soul']
                ck(f'existing slot reconstruction {grab}/{cucco}',
                    'ZR Near Freestanding PoH Grass' in ev(inventory).in_logic_locations, grab and cucco)

passed = all(t['passed'] for t in tests)
a.report.parent.mkdir(parents=True, exist_ok=True)
a.report.write_text(json.dumps(dict(passed=passed, checks=len(tests), tests=tests), indent=2), encoding='utf-8')
print(f'{"PASS" if passed else "FAIL"} {len(tests)} ZR pillar grass assertions')
for t in [t for t in tests if not t['passed']][:12]: print(t)
raise SystemExit(not passed)
