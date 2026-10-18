"""Actual AP rules for medallion trial doors and shuffled room arrivals.

Run with the supported AP runtime/source world on PYTHONPATH. The controlled
ingress edges isolate physical room access; this is not a native playthrough.
"""
from contextlib import contextmanager
from hashlib import sha256
import argparse
import io
import json
from pathlib import Path
import re
import time
import unittest

import ModuleUpdate
ModuleUpdate.update_ran = True
import settings
settings.no_gui = True
settings.skip_autosave = True
import Utils

from BaseClasses import CollectionState
from Options import OptionError
from test.general import setup_multiworld
from worlds.AutoWorld import call_all
from worlds.soh_extreme import SohExtremeWorld
from worlds.soh_extreme import EntranceRandomizer as ER
from worlds.soh_extreme import EntranceSafety
from worlds.soh_extreme.EnemyRoomLogic import GRAPH, SILVER
from worlds.soh_extreme._vendor_oot_soh.Enums import Ages, Regions


SOURCE = Path(__file__).resolve().parents[2]
TRIALS = (
    ('Forest', 9872, 9873),
    ('Water', 9875, 9874),
    ('Light', 9876, 9877),
    ('Fire', 9878, 9879),
    ('Shadow', 9881, 9880),
    ('Spirit', 9888, 9889),
)
START = 'RR_GANONS_CASTLE_SHADOW_TRIAL_START'
POTS = 'RR_GANONS_CASTLE_SHADOW_TRIAL_POTS_PLATFORM'
SOURCE_FILES = (
    'archipelago/soh_extreme/__init__.py',
    'archipelago/soh_extreme/EnemyRoomLogic.py',
    'archipelago/soh_extreme/EnemyRoomGraph.json',
    'archipelago/soh_extreme/SceneTransitions.py',
    'archipelago/soh_extreme/EntranceRandomizer.py',
    'archipelago/soh_extreme/EntranceCatalog.json',
    'archipelago/soh_extreme/DungeonDoorCatalog.json',
    'archipelago/soh_extreme/DungeonLocationRoutes.json',
    'archipelago/soh_extreme/_vendor_oot_soh/LogicHelpers.py',
    'archipelago/soh_extreme/_vendor_oot_soh/Regions.py',
    'archipelago/soh_extreme/_vendor_oot_soh/RegionAgeAccess.py',
    'soh/Enhancements/randomizer/location_access/dungeons/ganons_castle.cpp',
    'soh/Enhancements/randomizer/MedallionLockedTrials.cpp',
    'tools/tests/test_trial_medallion_logic.py',
)


def build_world(locked, checks, er=True):
    multiworld = setup_multiworld(SohExtremeWorld, steps=(), seed=188, options={
        'starting_age': 'child', 'shuffle_dungeon_doors': int(er),
        'mixed_entrance_pools': {'all'}, 'scene_transition_checks': checks,
        'medallion_locked_trials': locked, 'shuffle_enemy_soul': 2,
        'shuffle_silver': 1, 'shuffle_grab': 1, 'shuffle_climb': 1, 'shuffle_swim': 1,
    })
    for step in ('generate_early', 'create_regions', 'create_items', 'set_rules'):
        call_all(multiworld, step)
    # Each test supplies its complete inventory. Do not let default starting
    # items accidentally certify combat or a medallion gate.
    multiworld.precollected_items[1].clear()
    world = multiworld.worlds[1]
    # Vanilla locked rewards (especially Link's Pocket's Light Medallion) are
    # addressed checks, not implicit test inventory. Preserve only genuine
    # local event locations so room clears and switch actions still sweep.
    for location in world.get_locations():
        if location.address is not None:
            location.item = None
    world.test_locations_by_id = {loc.address: loc for loc in world.get_locations() if loc.address is not None}
    return world


@contextmanager
def direct_regions(world, age, *regions):
    """Control actual region ingress for one age while keeping production rules."""
    root = world.get_region(str(Regions.ROOT))
    original = list(root.exits)
    for edge in original:
        if edge.connected_region is not None:
            edge.connected_region.entrances.remove(edge)
    root.exits.clear()
    for index, region in enumerate(regions):
        target = world.get_region(ER.region_name(region)) if isinstance(region, str) else region
        edge = root.create_exit(f'Test direct physical arrival {index}')
        edge.access_rule = lambda state, age=age: state._soh_extreme_age[1] == age
        edge.connect(target)
    try:
        yield
    finally:
        for edge in list(root.exits):
            edge.connected_region.entrances.remove(edge)
        root.exits.clear()
        root.exits.extend(original)
        for edge in original:
            if edge.connected_region is not None:
                edge.connected_region.entrances.append(edge)


def inventory(world, age, names=()):
    state = CollectionState(world.multiworld)
    for name in names:
        state.collect(world.create_item(name), True)
    state._soh_extreme_age[1] = age
    state.sweep_for_advancements()
    state._soh_extreme_age[1] = age
    return state


def physical_edge(world, endpoint):
    row = ER.ENDPOINTS[endpoint]
    source = world.get_region(ER.region_name(row['source']))
    target = ER.region_name(row['target'])
    return next(edge for edge in source.exits if edge.connected_region and edge.connected_region.name == target)


class TrialMedallionLogicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.locked = build_world(1, 1)
        cls.unlocked = build_world(0, 1)
        cls.no_checks = build_world(1, 0)
        cls.no_er = build_world(1, 1, er=False)

    def test_native_export_and_catalog_identity_are_consistent(self):
        EntranceSafety.validate_catalog(ER.CATALOG)
        native = (SOURCE / 'soh/Enhancements/randomizer/location_access/dungeons/ganons_castle.cpp').read_text()
        self.assertEqual({ER.ENDPOINTS[reverse]['door'] for _, _, reverse in TRIALS}, {8, 9, 10, 11, 12, 16})
        for trial, forward, reverse in TRIALS:
            with self.subTest(trial=trial):
                row = ER.ENDPOINTS[reverse]
                self.assertEqual(row['reverse'], forward)
                self.assertEqual(row['source_scene'], 13)
                self.assertEqual(row['target'], 'RR_GANONS_CASTLE_MAIN')
                region = row['source']
                block = native.split('areaTable[' + region + '] = Region(', 1)[1].split('\n    areaTable[', 1)[0]
                condition = re.search(r'^\s*ENTRANCE\(RR_GANONS_CASTLE_MAIN,\s*(.*)\),\s*$', block, re.M).group(1)
                exported = next(edge['condition'] for edge in GRAPH[region]['exits'] if edge['target'] == row['target'])
                self.assertEqual(condition, exported)

    def test_all_six_reverse_doors_require_their_own_medallion_without_clear(self):
        world = self.locked
        for age in (Ages.CHILD, Ages.ADULT):
            for trial, _, reverse in TRIALS:
                row = ER.ENDPOINTS[reverse]
                rule = ER._source_rule(world, row)
                check = world.test_locations_by_id[row['check_id']]
                wrong = 'Forest Medallion' if trial != 'Forest' else 'Spirit Medallion'
                for names, expected in (((), False), ((wrong,), False), ((trial + ' Medallion',), True)):
                    with self.subTest(age=age, trial=trial, items=names), direct_regions(world, age, row['source']):
                        state = inventory(world, age, names)
                        self.assertEqual(rule(state), expected)
                        self.assertEqual(check.access_rule(state), expected)
                        self.assertEqual(ER._reachable_as_age(world, state, check, age), expected)

    def test_forward_medallions_and_light_strength_gate_are_preserved(self):
        for age in (Ages.CHILD, Ages.ADULT):
            for trial, forward, _ in TRIALS:
                with self.subTest(age=age, trial=trial):
                    row = ER.ENDPOINTS[forward]
                    rule = ER._source_rule(self.locked, row)
                    names = ('Strength Upgrade',) * 4
                    state = inventory(self.locked, age, names)
                    self.assertFalse(rule(state))
                    state.collect(self.locked.create_item(trial + ' Medallion'), True)
                    expected = trial != 'Light' or age == Ages.ADULT
                    self.assertEqual(rule(state), expected)
                    free_rule = ER._source_rule(self.unlocked, row)
                    self.assertEqual(free_rule(inventory(self.unlocked, age, names)), expected)

    def test_disabled_medallion_option_keeps_all_reverse_doors_free(self):
        for age in (Ages.CHILD, Ages.ADULT):
            for trial, _, reverse in TRIALS:
                with self.subTest(age=age, trial=trial):
                    row = ER.ENDPOINTS[reverse]
                    rule = ER._source_rule(self.unlocked, row)
                    state = inventory(self.unlocked, age)
                    self.assertTrue(rule(state))
                    self.assertTrue(self.unlocked.test_locations_by_id[row['check_id']].access_rule(state))

    def test_physical_exit_rules_exist_with_transition_checks_disabled(self):
        world = self.no_checks
        for age in (Ages.CHILD, Ages.ADULT):
            for trial, _, reverse in TRIALS:
                with self.subTest(age=age, trial=trial):
                    row = ER.ENDPOINTS[reverse]
                    self.assertNotIn(row['check_id'], world.test_locations_by_id)
                    source_rule = ER._source_rule(world, row)
                    self.assertFalse(source_rule(inventory(world, age)))
                    self.assertTrue(source_rule(inventory(world, age, (trial + ' Medallion',))))

    def test_arriving_inside_spirit_does_not_require_its_original_entry_medallion(self):
        world = self.locked
        row = ER.ENDPOINTS[529]  # Link's House's physical exit has its own rule.
        source = world.get_region(ER.region_name(row['source']))
        edge = physical_edge(world, row['id'])
        original = edge.connected_region
        original_rule = edge.access_rule
        arrival = world.get_region(ER.region_name(ER.ENDPOINTS[9889]['source']))
        rule = ER._source_rule(world, row)
        edge.connected_region.entrances.remove(edge)
        edge.connect(arrival)
        edge.access_rule = rule
        try:
            for age in (Ages.CHILD, Ages.ADULT):
                with self.subTest(age=age), direct_regions(world, age, source):
                    state = inventory(world, age)
                    self.assertTrue(ER._reachable_as_age(world, state, arrival, age))
                    self.assertTrue(ER._reachable_as_age(world, state, world.test_locations_by_id[9700109], age))
                    self.assertFalse(ER._reachable_as_age(world, state, world.test_locations_by_id[11213345], age))
        finally:
            edge.connected_region.entrances.remove(edge)
            edge.connect(original)
            edge.access_rule = original_rule

    def test_spirit_source_gate_still_blocks_a_shuffled_water_destination(self):
        world = self.locked
        row = ER.ENDPOINTS[9889]
        edge = physical_edge(world, row['id'])
        original, original_rule = edge.connected_region, edge.access_rule
        rule = ER._source_rule(world, row)
        arrival = world.get_region(ER.region_name('RR_WATER_TEMPLE_BOSS_KEY_ROOM'))
        edge.connected_region.entrances.remove(edge)
        edge.connect(arrival)
        edge.access_rule = rule
        try:
            for age in (Ages.CHILD, Ages.ADULT):
                for names, expected in (((), False), (('Water Medallion',), False), (('Spirit Medallion',), True)):
                    with self.subTest(age=age, items=names), direct_regions(world, age, row['source']):
                        state = inventory(world, age, names)
                        self.assertEqual(ER._reachable_as_age(world, state, arrival, age), expected)
                        self.assertEqual(world.test_locations_by_id[11213345].access_rule(state), expected)
        finally:
            edge.connected_region.entrances.remove(edge)
            edge.connect(original)
            edge.access_rule = original_rule

    def test_medallion_receipt_and_removal_refresh_the_same_cached_state(self):
        world = self.locked
        row = ER.ENDPOINTS[9889]
        rule = ER._source_rule(world, row)
        check = world.test_locations_by_id[row['check_id']]
        for age in (Ages.CHILD, Ages.ADULT):
            with self.subTest(age=age), direct_regions(world, age, row['source']):
                state = inventory(world, age)
                self.assertFalse(rule(state))
                self.assertFalse(ER._reachable_as_age(world, state, check, age))
                medal = world.create_item('Spirit Medallion')
                state.collect(medal, True)
                self.assertTrue(rule(state))
                self.assertTrue(ER._reachable_as_age(world, state, check, age))
                state.remove(medal)
                self.assertFalse(rule(state))
                self.assertFalse(ER._reachable_as_age(world, state, check, age))

    def test_water_reverse_can_clear_freezards_with_soul_and_usable_combat(self):
        world = self.locked
        row = ER.ENDPOINTS[9874]
        rule = ER._source_rule(world, row)
        for age in (Ages.CHILD, Ages.ADULT):
            for names, expected in (((), False), (('Progressive Bomb Bag',), False), (('Freezard Soul',), False),
                                    (('Progressive Bomb Bag', 'Freezard Soul'), True)):
                with self.subTest(age=age, items=names), direct_regions(world, age, row['source']):
                    state = inventory(world, age, names)
                    self.assertEqual(rule(state), expected)
                    self.assertEqual(world.test_locations_by_id[row['check_id']].access_rule(state), expected)
                    self.assertFalse(state.has('Water Medallion', 1))

    def test_shadow_reverse_requires_both_enemies_and_their_physical_platforms(self):
        world = self.locked
        row = ER.ENDPOINTS[9880]
        rule = ER._source_rule(world, row)
        complete = ('Progressive Bomb Bag', 'Bubble Soul', 'Like Like Soul')
        for age in (Ages.CHILD, Ages.ADULT):
            for regions, names, expected in (
                    ((START,), complete, False),
                    ((START, POTS), (), False),
                    ((START, POTS), ('Progressive Bomb Bag', 'Bubble Soul'), False),
                    ((START, POTS), ('Progressive Bomb Bag', 'Like Like Soul'), False),
                    ((START, POTS), ('Bubble Soul', 'Like Like Soul'), False),
                    ((START, POTS), complete, True)):
                with self.subTest(age=age, regions=regions, items=names), direct_regions(world, age, *regions):
                    state = inventory(world, age, names)
                    self.assertEqual(rule(state), expected)
                    self.assertEqual(world.test_locations_by_id[row['check_id']].access_rule(state), expected)
                    self.assertFalse(state.has('Shadow Medallion', 1))

    def test_spirit_local_checks_and_other_exit_keep_their_own_requirements(self):
        world = self.locked
        source = ER.ENDPOINTS[9889]['source']
        near = world.test_locations_by_id[9700109]
        airborne = world.test_locations_by_id[9700099]
        alternate = ER._source_rule(world, ER.ENDPOINTS[9891])
        for age in (Ages.CHILD, Ages.ADULT):
            with self.subTest(age=age), direct_regions(world, age, source):
                state = inventory(world, age)
                self.assertTrue(ER._reachable_as_age(world, state, near, age))
                self.assertFalse(ER._reachable_as_age(world, state, airborne, age))
                self.assertFalse(alternate(state))
                for _ in range(5):
                    state.collect(world.create_item(SILVER['RG_GANONS_CASTLE_SILVER_SPIRIT']), True)
                self.assertTrue(alternate(state))
                self.assertFalse(state.has('Spirit Medallion', 1))
                self.assertFalse(ER._source_rule(world, ER.ENDPOINTS[9889])(state))
                state.collect(world.create_item('Progressive Hookshot'), True)
                self.assertEqual(ER._reachable_as_age(world, state, airborne, age), age == Ages.ADULT)

    def test_non_er_silver_route_still_requires_the_physical_entry_path(self):
        world = self.no_er
        near = world.test_locations_by_id[9700109]
        self.assertNotIn(near.name, getattr(world, '_er_locations', {}))
        for age in (Ages.CHILD, Ages.ADULT):
            with self.subTest(age=age, arrival='Main'), direct_regions(world, age, 'RR_GANONS_CASTLE_MAIN'):
                state = inventory(world, age)
                self.assertFalse(ER._reachable_as_age(world, state, near, age))
                state.collect(world.create_item('Spirit Medallion'), True)
                self.assertTrue(ER._reachable_as_age(world, state, near, age))
            # SilverRoomLogic already has exact local collection proxies even
            # without ER. Its pre-existing direct-room behavior must survive.
            with self.subTest(age=age, arrival='Beamos Room'), direct_regions(
                    world, age, 'RR_GANONS_CASTLE_SPIRIT_TRIAL_BEAMOS_ROOM'):
                state = inventory(world, age)
                self.assertTrue(ER._reachable_as_age(world, state, near, age))
                self.assertFalse(state.has('Spirit Medallion', 1))

    def test_region_qualified_actions_reject_unknown_regions_and_non_callbacks(self):
        compiler = self.locked._extreme_room_compiler
        for expression in ('areaTable[RR_NOT_A_REAL_REGION].AnyAgeTime([]{return true;})',
                           'RegionAnyAgeTime(RR_GANONS_CASTLE_SHADOW_TRIAL_POTS_PLATFORM, true)'):
            with self.subTest(expression=expression), self.assertRaises(OptionError):
                compiler.expr(expression, START)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    hashes = lambda: {name: sha256((SOURCE / name).read_bytes()).hexdigest() for name in SOURCE_FILES}
    before = hashes()
    started = time.monotonic()
    output = io.StringIO()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TrialMedallionLogicTests)
    result = unittest.TextTestRunner(stream=output, verbosity=2).run(suite)
    after = hashes()
    passed = result.wasSuccessful() and result.testsRun == 13 and before == after
    report = {'passed': passed, 'test_cases': result.testsRun, 'expected_test_cases': 13,
              'runtime': 'Archipelago ' + Utils.__version__,
              'runtime_path': str(Path(Utils.__file__).resolve().parent), 'source_hashes': after,
              'source_unchanged_during_tests': before == after,
              'elapsed_seconds': round(time.monotonic() - started, 3),
              'coverage': ['All six trial door returns, matching/wrong/no medallion, both ages and disabled option.',
                           'Physical source and transition-check gates agree before and after destination rewiring.',
                           'Physical gates remain when transition checks are disabled; received item cache refresh.',
                           'Water Freezard and Shadow Bubble/Like Like clear alternatives require actual room access.',
                           'Exact ER collection proxies retain local item requirements without inherited entry medallions.',
                           'Non-ER silver routes preserve physical entry/local access; region-qualified actions reject malformed input.'],
              'native_build': False, 'in_game_playthrough': False, 'log': output.getvalue()}
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + '\n')
    print(output.getvalue(), end='')
    print(json.dumps({key: report[key] for key in ('passed', 'test_cases', 'source_unchanged_during_tests', 'elapsed_seconds')}))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
