"""DC room 11 wall access and all Baby Dodongo combat alternatives in AP/UT.

Every case starts with fresh state, before any wall/room-clear event is collected.
Run with --ap-root, --ut-core and --report, like test_enemy_requirements.py.
"""
from pathlib import Path
import argparse
import json

from run_case import setup, BOOTSTRAP
from ut_harness import tracker
from worlds.soh_extreme.EnemyRoomLogic import NativeEnemyRegions
from worlds.soh_extreme._vendor_oot_soh.Enums import Regions

parser = argparse.ArgumentParser(parents=[BOOTSTRAP])
parser.add_argument('--ut-core', type=Path, required=True)
parser.add_argument('--report', type=Path, required=True)
args = parser.parse_args()
tests = []


def check(label, actual, expected=True):
    tests.append(dict(test=label, actual=bool(actual), expected=expected,
                      passed=bool(actual) == expected))
    if bool(actual) != expected:
        print('FAIL', label, bool(actual), expected, flush=True)


options = dict(
    closed_forest='off', door_of_time='song_only', shuffle_enemy_drops=True,
    shuffle_grab=True, shuffle_climb=True, shuffle_pot_soul=True,
    shuffle_master_sword=True, start_with_master_sword=False,
    shuffle_deku_stick_bag=True, shuffle_deku_nut_bag=True,
    song_note_shuffle='off', shuffle_ocarina_buttons=False,
    start_with_ocarina='off', start_with_song_of_time=False,
    start_inventory={}, start_inventory_from_pool={},
    tricks_in_logic=[], enable_all_tricks=False,
)

for age in ('child', 'adult'):
    for mode in ('individual_enemies', 'all_enemies_as_1', 'off'):
        world = setup(131064, overrides=dict(
            options, starting_age=age, shuffle_enemy_soul=mode),
            stop_before='pre_fill').worlds[1]
        evaluate = tracker(world, args.ut_core)
        pool = [i.name for i in world.multiworld.itempool]
        pool += [l.item.name for l in world.get_locations()
                 if l.address is not None and l.item and l.item.name in world.item_name_to_id]
        weapons = {n for n in world.item_name_to_id if any(
            word in n.lower() for word in (
                'sword', 'knife', 'stick', 'nut', 'bomb', 'slingshot', 'bow', 'hookshot', 'shield'))}
        weapons |= {'Boomerang', 'Megaton Hammer', "Din's Fire", 'Fire Arrows',
                    'Ice Arrows', 'Light Arrows'}
        excluded = weapons | {'Baby Dodongo Soul', 'Keese Soul', 'Enemy Soul', 'Pot Soul',
                              'Progressive Ocarina', 'Song of Time'}
        base = [n for n in pool if n not in excluded]
        soul = ['Baby Dodongo Soul'] if mode == 'individual_enemies' else (
            ['Enemy Soul'] if mode == 'all_enemies_as_1' else [])
        keese = ['Keese Soul'] if mode == 'individual_enemies' else []
        ranged = 'Boomerang' if age == 'child' else 'Progressive Hookshot'
        sword = 'Kokiri Sword' if age == 'child' else 'Master Sword'
        shield = 'Deku Shield' if age == 'child' else 'Hylian Shield'
        tag = age + ' ' + mode

        def run(label, items, wall, bats, baby, remove=()):
            for name in items:
                assert name in world.item_name_to_id, name
            # Shields are locally bought equipment. The embedded tracker receives
            # ownership from the live game, not from AP's useful-item inventory.
            world._extreme_live_shields = (1 if shield == 'Deku Shield' else 2) if shield in items else 0
            result = evaluate([n for n in base if n not in remove] + items)
            for region in (NativeEnemyRegions.RR_DODONGOS_CAVERN_SE_ROOM,
                           Regions.DODONGOS_CAVERN_SE_ROOM):
                check(tag + ' ' + label + ' ' + str(region),
                      result.state.can_reach(str(region), 'Region', 1), wall)
            for index in range(1, 4):
                name = f"Enemy Defeat: Dodongo's Cavern Room 11 Keese {index}"
                check(tag + ' ' + label + ' AP ' + name,
                      world.get_location(name).can_reach(result.state), bats)
                check(tag + ' ' + label + ' UT ' + name,
                      name in result.in_logic_locations, bats)
            for index in range(1, 7):
                name = f"Enemy Defeat: Dodongo's Cavern Room 1 Baby Dodongo {index}"
                check(tag + ' ' + label + ' AP ' + name,
                      world.get_location(name).can_reach(result.state), baby)
                check(tag + ' ' + label + ' UT ' + name,
                      name in result.in_logic_locations, baby)

        run('soul without kill method', soul + keese, False, False, False)
        run('weapon without Baby soul', [ranged] + keese,
            mode == 'off', mode == 'off', mode == 'off')
        run('Baby soul and ranged weapon', soul + keese + [ranged], True, True, True)
        run('sword opens wall but cannot reach these Keese', soul + keese + [sword],
            True, False, True)
        run('Dins Fire does not kill Baby Dodongo', soul + keese + ["Din's Fire"],
            False, False, False)
        run('usable bomb bag opens wall without Baby soul',
            keese + ['Progressive Bomb Bag', ranged], True,
            mode != 'all_enemies_as_1', mode == 'off')
        run('Hammer must be age-usable', keese + ['Megaton Hammer', ranged],
            age == 'adult' or mode == 'off',
            (age == 'adult' or mode == 'off') and mode != 'all_enemies_as_1',
            mode == 'off')
        if mode != 'all_enemies_as_1':
            run('Keese soul remains independent', soul + [ranged],
                True, mode == 'off', True)
        if mode == 'individual_enemies':
            run('wrong shared soul cannot substitute', ['Enemy Soul', 'Keese Soul', ranged],
                False, False, False)
        run('pot kill still needs its soul', soul + keese + [shield],
            False, False, False)
        run('corridor pot alternative', soul + keese + [shield, 'Pot Soul'],
            True, False, False)
        run('pot cannot bypass missing Baby soul', keese + [shield, 'Pot Soul'],
            mode == 'off', False, False)
        run('pot requires Grab', soul + keese + [shield, 'Pot Soul'],
            False, False, False, remove={'Grab / Power Bracelet', 'Strength Upgrade',
                                       'Progressive Strength Upgrade'})

report = dict(passed=all(t['passed'] for t in tests), assertions=len(tests), tests=tests,
              scope=__doc__)
args.report.parent.mkdir(parents=True, exist_ok=True)
args.report.write_text(json.dumps(report, indent=2), encoding='utf-8')
print('RESULT', report['passed'], len(tests), 'DC wall assertions', flush=True)
raise SystemExit(not report['passed'])
