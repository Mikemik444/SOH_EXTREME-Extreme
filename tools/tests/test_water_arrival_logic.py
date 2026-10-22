"""Actual AP world tests for wet arrivals, controls, combat and fixed carriers.

The uploaded seed's verified options and saved map are used without a new
fill. Controlled ingresses isolate individual physical contexts; every rule,
event sweep, item collect and saved-map connection is the production code.
"""
from contextlib import contextmanager
from hashlib import sha256
import argparse
import io
import json
from pathlib import Path
import re
import sys
import time
import unittest

from test_entrance_blockers import (
    SOURCE, Ages, Regions, ER, N, SohExtremeWorld, CollectionState, Item,
    ItemClassification, Utils, arrivals, inventory, reached, region, physical_edge,
    setup_multiworld, call_all,
)
from worlds.soh_extreme.EnemyDropLocations import ENEMY_DROP_LOCATIONS
from worlds.soh_extreme import SceneTransitions
from worlds.soh_extreme import TrackerMirror

sys.path.insert(0, str(SOURCE / 'tools'))
from update_water_logic_exports import expected_exports, native_regions, compact


W = 'RR_WATER_TEMPLE_'
GTG = 'RR_GERUDO_TRAINING_GROUND_UNDERWATER'
LOW = 'LOGIC_WATER_LOW'
MID = 'LOGIC_WATER_MIDDLE'
HIGH = 'LOGIC_WATER_HIGH'
SONG = ("Zelda's Lullaby", 'Progressive Ocarina')
WET = ('Iron Boots', 'Swim')
WET_TIME = (*WET, 'Zora Tunic')
SHELLS = {entry.address: entry for entry in ENEMY_DROP_LOCATIONS if entry.address in
          {9800232, 9800233, 9800272, 9800273, 9800274, 9800443, 9800444, 9800445, 9800446}}
SOURCE_FILES = (
    'archipelago/soh_extreme/__init__.py',
    'archipelago/soh_extreme/Options.py',
    'archipelago/soh_extreme/EnemyRoomLogic.py',
    'archipelago/soh_extreme/EnemyRoomGraph.json',
    'archipelago/soh_extreme/DungeonLocationRoutes.json',
    'archipelago/soh_extreme/NativeLogic.py',
    'archipelago/soh_extreme/EntranceRandomizer.py',
    'archipelago/soh_extreme/EntranceCatalog.json',
    'archipelago/soh_extreme/EntranceDestinationPolicy.json',
    'archipelago/soh_extreme/EnemyDropLocations.py',
    'archipelago/soh_extreme/EnemyDropRules.py',
    'archipelago/soh_extreme/_vendor_oot_soh/LogicHelpers.py',
    'archipelago/soh_extreme/_vendor_oot_soh/RegionAgeAccess.py',
    'archipelago/soh_extreme/_vendor_oot_soh/location_access/overworld/gerudo_fortress.py',
    'archipelago/soh_extreme/_vendor_oot_soh/location_access/overworld/market.py',
    'archipelago/soh_extreme/_vendor_oot_soh/location_access/dungeons/water_temple.py',
    'soh/Enhancements/randomizer/logic.cpp',
    'soh/Enhancements/randomizer/logic.h',
    'soh/Enhancements/randomizer/location_access/dungeons/water_temple.cpp',
    'soh/Enhancements/randomizer/location_access/overworld/gerudo_fortress.cpp',
    'soh/Enhancements/randomizer/randomizer_check_tracker.cpp',
    'soh/Network/Archipelago/ArchipelagoEnemyFinderMap.inc',
    'tools/update_water_logic_exports.py',
    'tools/tests/test_entrance_blockers.py',
    'tools/tests/test_water_arrival_logic.py',
)
FACTS = {}


def build_world(evidence, *, simplified_songs=True, entrances=True):
    options = {key: row['value'] for key, row in evidence['resolved_options'].items()}
    if simplified_songs:
        options.update(song_note_shuffle=0, shuffle_ocarina_buttons=0)
    if not entrances:
        options.update({option: 0 for option in ER.CATEGORIES.values()})
        options['mixed_entrance_pools'] = []
    mw = setup_multiworld(SohExtremeWorld, steps=(), seed=evidence['seed'], options=options)
    for stage in ('generate_early', 'create_regions', 'create_items', 'set_rules'):
        call_all(mw, stage)
    mw.precollected_items[1].clear()
    world = mw.worlds[1]
    for location in world.get_locations():
        if location.address is not None:
            location.item = None
    world.water_checks = {location.address: location for location in world.get_locations()
                          if location.address is not None}
    return world


@contextmanager
def no_exits(world, token):
    """Keep the local action context, without obtaining a remote control."""
    source = region(world, token)
    original = list(source.exits)
    for edge in original:
        if edge.connected_region:
            edge.connected_region.entrances.remove(edge)
    source.exits.clear()
    try:
        yield
    finally:
        source.exits.extend(original)
        for edge in original:
            if edge.connected_region:
                edge.connected_region.entrances.append(edge)


@contextmanager
def route(world, source_id, target_id):
    source = ER.ENDPOINTS[source_id]
    target = ER.ENDPOINTS[target_id]
    edge = physical_edge(world, source_id)
    old_region, old_rule = edge.connected_region, edge.access_rule
    source_rule = ER._source_rule(world, source)
    edge.connected_region.entrances.remove(edge)
    edge.connect(region(world, target['target']))
    edge.access_rule = ER._routed_rule(source_rule, ER._arrival_rule(world, target))
    for dependency in getattr(edge.access_rule, '_er_dependencies', ()):
        world._register_rule_indirects(dependency, edge)
    try:
        yield edge, source_rule
    finally:
        edge.connected_region.entrances.remove(edge)
        edge.connect(old_region)
        edge.access_rule = old_rule


def edge_rule(world, source, target):
    return next(edge.access_rule for edge in region(world, source).exits
                if edge.connected_region is region(world, target))


class WaterArrivalTests(unittest.TestCase):
    evidence = None
    cases = 0

    @classmethod
    def setUpClass(cls):
        cls.world = build_world(cls.evidence)

    def decision(self, actual, expected, label):
        type(self).cases += 1
        self.assertEqual(bool(actual), bool(expected), label)

    def test_complete_native_water_export_parity(self):
        exports, facts = expected_exports()
        for path, expected in exports.items():
            self.assertEqual(path.read_bytes(), expected, str(path))
        self.assertEqual((facts['native_regions'], facts['native_mapped_location_routes']), (62, 60))
        FACTS['native_export'] = facts
        native = (SOURCE / 'soh/Enhancements/randomizer/logic.cpp').read_text()
        self.assertIn('bool Logic::WaterTempleDoorsShuffled()', native)
        self.assertIn('Archipelago_IsCurrentSaveFile()', native)
        self.assertIn('CVAR_RANDOMIZER_SETTING("ShuffleDungeonDoors")', native)

    def test_eight_arrival_endpoints_age_swim_boots_and_dry_level_matrix(self):
        world = self.world
        expected = {8860: LOW, 8861: LOW, 8878: LOW, 8879: LOW,
                    8862: MID, 8863: MID, 8866: MID, 8867: MID}
        self.assertEqual(set(ER.WATER_ARRIVAL_LEVELS), set(expected))
        for target, dry in expected.items():
            rule = ER._arrival_rule(world, ER.ENDPOINTS[target])
            for age in (Ages.CHILD, Ages.ADULT):
                for names in ((), ('Swim',), ('Iron Boots',), WET):
                    for flags in ((), (LOW,), (MID,), (HIGH,)):
                        with self.subTest(target=target, age=age, items=names, flags=flags):
                            state = inventory(world, age, names, flags, sweep=False)
                            can_walk = LOW in flags or (dry == MID and MID in flags)
                            can_submerge = age == Ages.ADULT and names == WET
                            self.decision(rule(state), can_walk or can_submerge,
                                          (target, age, names, flags))

    def test_physical_source_check_survives_unsafe_destination(self):
        world = self.world
        for age in (Ages.CHILD, Ages.ADULT):
            with arrivals(world, (age, W + 'LOW_EMBLEM')), route(world, 8858, 8860) as (edge, source_rule):
                state = inventory(world, age)
                self.decision(source_rule(state), True, 'dry physical source')
                check = world.water_checks[ER.ENDPOINTS[8858]['check_id']]
                self.decision(ER._reachable_as_age(world, state, check, age), True, 'source item credit')
                self.decision(ER._reachable_as_age(world, state, edge, age), False, 'wet arrival edge')
                self.decision(reached(world, state, W + 'MAIN', age), False, 'wet destination checks')

    def test_received_items_invalidate_cached_routed_arrival(self):
        world = self.world
        with arrivals(world, (Ages.ADULT, W + 'LOW_EMBLEM')), route(world, 8858, 8860) as (edge, _):
            state = inventory(world, Ages.ADULT)
            self.decision(ER._reachable_as_age(world, state, edge, Ages.ADULT), False, 'initially blocked')
            state.collect(world.create_item('Iron Boots'), True)
            self.decision(ER._reachable_as_age(world, state, edge, Ages.ADULT), False, 'boots alone')
            state.collect(world.create_item('Swim'), True)
            self.decision(ER._reachable_as_age(world, state, edge, Ages.ADULT), True, 'boots plus received Swim')
            self.decision(reached(world, state, W + 'MAIN', Ages.ADULT), True, 'region cache updates')

    def test_dry_remap_never_keeps_a_previous_water_gate(self):
        world = self.world
        for target, expected in ((8860, False), (8858, True), (8863, False), (8859, True)):
            with arrivals(world, (Ages.CHILD, W + 'LOW_EMBLEM')), route(world, 8858, target) as (edge, _):
                state = inventory(world, Ages.CHILD)
                self.decision(ER._reachable_as_age(world, state, edge, Ages.CHILD), expected, target)

    def test_wet_pillar_arrival_does_not_establish_middle_control(self):
        world = self.world
        for flags, expected in (((), False), ((HIGH,), False), ((LOW,), True), ((MID,), True)):
            with arrivals(world, (Ages.ADULT, W + 'PILLAR_2F')), no_exits(world, W + 'PILLAR_2F'):
                state = inventory(world, Ages.ADULT, (*WET_TIME, *SONG), flags)
                self.decision(state.has(N.event_item(MID), 1), expected, ('actual Middle control', flags))
                self.decision(state.has(N.event_item('LOGIC_WATER_COULD_MIDDLE'), 1), expected,
                              ('dry Middle access', flags))

    def test_nonlocal_shortcuts_do_not_create_control_events(self):
        world = self.world
        names = (*WET_TIME, *SONG, 'Progressive Hookshot', 'Progressive Hookshot', 'Progressive Bow',
                 'Progressive Bomb Bag', 'Progressive Magic Meter', "Din's Fire", 'Grab / Power Bracelet',
                 *(['Water Temple Small Key'] * 6))
        for token in (W + 'ENTRANCE_LEDGE', W + 'MAIN', W + 'SIDE_TOWER_1F', W + 'RISING_TARGET_LEDGE'):
            with arrivals(world, (Ages.ADULT, token)), no_exits(world, token):
                state = inventory(world, Ages.ADULT, names)
                for flag in (LOW, MID, HIGH, 'LOGIC_WATER_COULD_MIDDLE',
                             'LOGIC_WATER_COULD_HIGH_FROM_MID', 'LOGIC_WATER_COULD_LOW_FROM_HIGH'):
                    self.decision(state.has(N.event_item(flag), 1), False, (token, flag))

    def test_water_level_helper_retains_vanilla_formulas_outside_room_shuffle(self):
        world = self.world
        old = world.options.shuffle_dungeon_doors.value
        try:
            state = inventory(world, Ages.ADULT, SONG,
                              ('LOGIC_WATER_COULD_MIDDLE', 'LOGIC_WATER_COULD_HIGH_FROM_MID'), sweep=False)
            for setting, expected in ((1, False), (0, True)):
                world.options.shuffle_dungeon_doors.value = setting
                rule = world._extreme_room_compiler.expr('WaterLevel(WL_HIGH)', W + 'MAIN').resolve(world)
                self.decision(rule(state), expected, ('High reset proof formula', setting))
        finally:
            world.options.shuffle_dungeon_doors.value = old

    def test_dry_middle_actions_require_low_or_middle_water(self):
        world = self.world
        native, _ = native_regions()
        for flags, expected in (((), False), ((HIGH,), False), ((LOW,), True), ((MID,), True)):
            state = inventory(world, Ages.ADULT, (*WET_TIME, 'Progressive Hookshot',
                                                'Progressive Hookshot', 'Progressive Bow', 'Pot Soul',
                                                'Master Sword'), flags, sweep=False)
            for source, target in ((W + '2F_CENTRAL_LM', W + 'PILLAR_2F'),
                                   (W + '2F_CENTRAL_LM', W + '3F_CENTRAL_LM'),
                                   (W + '2F_CENTRAL_LM', W + 'BLOCK_LOOP')):
                condition = next(row['condition'] for row in native[source]['exits'] if row['target'] == target)
                rule = world._extreme_room_compiler.expr(condition, source).resolve(world)
                self.decision(rule(state), expected, (source, target, flags))

    def test_pillar_high_must_approach_a_real_shuffled_door(self):
        world = self.world
        with arrivals(world, (Ages.ADULT, W + 'PILLAR_H')):
            state = inventory(world, Ages.ADULT, WET_TIME, sweep=False)
            for target, expected in ((W + 'MAIN', False), (W + '2F_CENTRAL_LM', False),
                                     (W + 'PILLAR_2F', True)):
                edges = [edge for edge in region(world, W + 'PILLAR_H').exits
                         if edge.connected_region is region(world, target)]
                # Constant-false option branches are retired by production
                # create_entrance, so the obsolete shortcut has no AP edge.
                self.decision(any(edge.access_rule(state) for edge in edges), expected, target)

    def test_pillar_basement_has_no_contracted_exit_to_main_room(self):
        world = self.world
        with arrivals(world, (Ages.ADULT, W + 'PILLAR_B1')):
            state = inventory(world, Ages.ADULT, WET_TIME, sweep=False)
            self.decision(any(edge.connected_region is region(world, W + 'MAIN')
                              for edge in region(world, W + 'PILLAR_B1').exits), False,
                          'basement cannot skip either mapped pillar door')
            self.decision(edge_rule(world, W + 'PILLAR_B1', W + 'PILLAR_1F')(state), True,
                          'basement returns to the same physical pillar')
        state = inventory(world, Ages.ADULT, WET_TIME, (HIGH,), sweep=False)
        self.decision(edge_rule(world, W + 'PILLAR_1F', W + 'PILLAR_H')(state), True,
                      'local flooded shaft remains traversable')
        state = inventory(world, Ages.ADULT, WET_TIME, (MID,), sweep=False)
        self.decision(edge_rule(world, W + 'PILLAR_1F', W + 'PILLAR_2F')(state), True,
                      'actual Mid arrival can ascend its own pillar without Farore setup')

    def test_dry_upper_ledges_stay_available_without_boots(self):
        world = self.world
        for endpoint in (8848, 8849, 8858, 8859, 8864, 8865, 8868, 8869, 8870, 8871, 8880, 8881):
            self.assertIsNone(ER._arrival_rule(world, ER.ENDPOINTS[endpoint]))
        tektite = next(entry for entry in ENEMY_DROP_LOCATIONS
                       if entry.region_token == W + '3F_CENTRAL_A' and 'Tektite 1' in entry.name)
        with arrivals(world, (Ages.CHILD, W + '3F_CENTRAL_A')):
            state = inventory(world, Ages.CHILD, ('Kokiri Sword', 'Tektite Soul'))
            self.decision(ER._reachable_as_age(world, state, world.water_checks[tektite.address], Ages.CHILD),
                          True, 'dry boots pickup Tektite')
        FACTS['dry_boots_pickup_check'] = tektite.address

    def test_dry_platform_drops_and_river_traversal_require_usable_boots(self):
        world = self.world
        for age in (Ages.CHILD, Ages.ADULT):
            for names in ((), ('Swim',), ('Iron Boots',), WET):
                state = inventory(world, age, (*names, 'Song of Time', 'Progressive Ocarina'), sweep=False)
                expected = age == Ages.ADULT and names == WET
                for source, target in ((W + '3F_CENTRAL_A', W + 'MAIN'),
                                       (W + 'SOT_PIT_ROOM', W + 'RIVER')):
                    self.decision(edge_rule(world, source, target)(state), expected, (source, age, names))
            state = inventory(world, age, flags=(LOW,), sweep=False)
            self.decision(edge_rule(world, W + '3F_CENTRAL_A', W + 'MAIN')(state), True, 'dry Low drop')

    def test_nine_underwater_enemies_require_real_local_combat(self):
        world = self.world
        ordinary = ('Shell Blade Soul', 'Song of Time', 'Progressive Ocarina', 'Zora Tunic')
        matrix = (
            (Ages.CHILD, ('Kokiri Sword',), (), False, False, False),
            (Ages.ADULT, ('Master Sword',), (), False, False, False),
            (Ages.ADULT, ('Master Sword', 'Iron Boots'), (), False, False, False),
            (Ages.ADULT, ('Master Sword', *WET), (), False, False, False),
            (Ages.ADULT, ('Progressive Hookshot', *WET), (), True, True, True),
            (Ages.CHILD, ('Kokiri Sword',), (LOW,), False, False, True),
            (Ages.ADULT, ('Master Sword',), (LOW,), False, False, True),
        )
        for address, entry in SHELLS.items():
            self.assertIn(entry.encounter_gate, ('gtg_underwater', 'water_pillar_bottom', 'water_torch_room'))
            index = ('gtg_underwater', 'water_pillar_bottom', 'water_torch_room').index(entry.encounter_gate)
            for age, names, flags, *results in matrix:
                with self.subTest(address=address, age=age, names=names, flags=flags), arrivals(world, (age, entry.region_token)):
                    state = inventory(world, age, (*ordinary, *names), flags)
                    self.decision(ER._reachable_as_age(world, state, world.water_checks[address], age),
                                  results[index], (address, age, names, flags))
        with arrivals(world, (Ages.ADULT, GTG)):
            for missing in ('Shell Blade Soul', 'Song of Time', 'Progressive Ocarina', 'Zora Tunic',
                            'Iron Boots', 'Swim', 'Progressive Hookshot'):
                names = (*ordinary, *WET, 'Progressive Hookshot')
                state = inventory(world, Ages.ADULT, tuple(item for item in names if item != missing))
                self.decision(ER._reachable_as_age(world, state, world.water_checks[9800443], Ages.ADULT),
                              False, ('GTG missing', missing))

    def test_gtg_dry_door_and_chest_do_not_inherit_pool_bottom_gate(self):
        world = self.world
        with arrivals(world, (Ages.CHILD, GTG)):
            state = inventory(world, Ages.CHILD, ('Open Chest', *(['Training Ground Silver: Water'] * 5)))
            check = world.water_checks[372]
            self.decision(ER._reachable_as_age(world, state, check, Ages.CHILD), True, 'dry ledge chest')
            return_door = next(row for row in ER.CATALOG if row['source'] == GTG)
            self.decision(ER._source_rule(world, return_door)(state), True, 'dry exit door')

    def test_native_finder_encounter_tags_match_exact_ap_ids(self):
        text = (SOURCE / 'soh/Network/Archipelago/ArchipelagoEnemyFinderMap.inc').read_text()
        for address, entry in SHELLS.items():
            row = next(line for line in text.splitlines() if f'{{ {address}LL,' in line)
            self.assertIn('EFG_' + entry.encounter_gate.upper(), row)
            self.assertIn(entry.region_token, row)
        self.assertEqual(len(SHELLS), 9)

    def test_both_gerudo_vine_ascents_need_climb_or_usable_hookshot(self):
        world = self.world
        for source, target in (('GF_BOTTOM_OF_LOWER_VINES', 'GF_TOP_OF_LOWER_VINES'),
                               ('GF_BOTTOM_OF_UPPER_VINES', 'GF_TOP_OF_UPPER_VINES')):
            rule = edge_rule(world, source, target)
            for age in (Ages.CHILD, Ages.ADULT):
                for names, expected in (((), False), (('Climb',), True),
                                         (('Progressive Hookshot',), age == Ages.ADULT)):
                    with arrivals(world, (age, source)):
                        state = inventory(world, age, names)
                        self.decision(rule(state), expected, (source, age, names))

    def test_richard_fixed_delivery_route_and_interactions(self):
        world = self.world
        route_pairs = {('MARKET', 'MARKET_BACK_ALLEY'), ('MARKET_BACK_ALLEY', 'MARKET'),
                       ('MARKET_BACK_ALLEY', 'MARKET_DOG_LADY_HOUSE'),
                       ('MARKET_DOG_LADY_HOUSE', 'MARKET_BACK_ALLEY')}
        self.assertFalse(any((row['source'], row['target']) in route_pairs for row in ER.CATALOG))
        self.assertTrue({908, 920}.isdisjoint(ER.ENDPOINTS))
        checks = {row['id'] for row in SceneTransitions.CATALOG}
        self.assertTrue({11000908, 11000920} <= checks)
        old_phase = world.options.frozen_starting_time.value
        full = ('Dog Soul', 'NPC Soul', 'Speak Hylian', "Richard's House Key")
        try:
            for phase, age, missing in ((4, Ages.CHILD, None), (2, Ages.CHILD, None),
                                       (4, Ages.ADULT, None),
                                       *((4, Ages.CHILD, item) for item in full)):
                world.options.frozen_starting_time.value = phase
                with arrivals(world, (age, 'MARKET')):
                    state = inventory(world, age, tuple(item for item in full if item != missing))
                    expected = phase == 4 and age == Ages.CHILD and missing is None
                    self.decision(ER._reachable_as_age(world, state, world.water_checks[46], age), expected,
                                  ('Richard delivery', phase, age, missing))
        finally:
            world.options.frozen_starting_time.value = old_phase

    def test_saved_exact_map_restores_all_connections_with_new_arrival_rules(self):
        evidence = self.evidence
        self.assertEqual(evidence['status'], 'exactly_reproduced')
        self.assertTrue(evidence['all_placements_match_uploaded_spoiler'])
        self.assertEqual((evidence['matching_placements'], evidence['mismatched_placements']), (4036, 0))
        world = build_world(evidence, simplified_songs=False)
        world.using_ut = True
        world.passthrough = {'entrance_randomizer': {
            'revision': ER.REVISION, 'destination_policy_revision': ER.Safety.POLICY_REVISION,
            'pool_policy_revision': ER.POOL_POLICY_REVISION, 'connections': evidence['mapping']}}
        ER.connect(world)
        self.assertEqual(world._er_mapping, {int(key): value for key, value in evidence['mapping'].items()})
        wet_routes = []
        for source, target in world._er_mapping.items():
            if target not in ER.WATER_ARRIVAL_LEVELS:
                continue
            edge = world.get_entrance('EXTREME Shuffled Entrance ' + str(source))
            self.assertEqual(edge.connected_region, region(world, ER.ENDPOINTS[target]['target']))
            check = world.water_checks.get(ER.ENDPOINTS[source]['check_id'])
            if check is not None:
                self.assertIsNot(edge.access_rule, check.access_rule)
            wet_routes.append([source, target])
        self.assertTrue(wet_routes)
        FACTS['saved_map_restoration'] = {'connections': len(world._er_mapping), 'wet_routes': wet_routes,
                                         'all_connections_unchanged': True,
                                         'same_uploaded_placements_certified_by_input_report': 4036,
                                         'scope': 'Actual UT connect and route restoration; no new fill or placement replay.'}

    def test_ordinary_unshuffled_water_entry_also_requires_usable_boots(self):
        world = build_world(self.evidence, entrances=False)
        rule = edge_rule(world, 'WATER_TEMPLE_ENTRYWAY', 'WATER_TEMPLE_LOBBY')
        for age in (Ages.CHILD, Ages.ADULT):
            for names in ((), ('Swim',), ('Iron Boots',), WET):
                with arrivals(world, (age, 'WATER_TEMPLE_ENTRYWAY')):
                    state = inventory(world, age, names)
                    self.decision(rule(state), age == Ages.ADULT and names == WET,
                                  ('ordinary wet dungeon entry', age, names))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exact-seed', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    started = time.monotonic()
    evidence_bytes = args.exact_seed.read_bytes()
    WaterArrivalTests.evidence = json.loads(evidence_bytes)
    before = {name: sha256((SOURCE / name).read_bytes()).hexdigest() for name in SOURCE_FILES}
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(WaterArrivalTests))
    print(stream.getvalue())
    after = {name: sha256((SOURCE / name).read_bytes()).hexdigest() for name in SOURCE_FILES}
    report = {'status': 'passed' if result.wasSuccessful() and before == after else 'failed',
              'test_methods': result.testsRun, 'behavior_decisions': WaterArrivalTests.cases,
              'failures': len(result.failures), 'errors': len(result.errors),
              'skipped': len(result.skipped), 'archipelago_version': str(Utils.__version__),
              'world_version': TrackerMirror.VERSION, 'elapsed_seconds': round(time.monotonic() - started, 3),
              'source_unchanged_during_run': before == after, 'source_sha256': after,
              'input_evidence_path': str(args.exact_seed.resolve()),
              'input_evidence_sha256': sha256(evidence_bytes).hexdigest(),
              'probe_song_options': {'song_note_shuffle': 0, 'shuffle_ocarina_buttons': 0},
              'saved_map_options': 'All verified uploaded-seed resolved options, with original note/button settings',
              'facts': FACTS, 'test_output': stream.getvalue(),
              'limits': ['Controlled AP logic and source-parity tests; no native gameplay claim.',
                         'Actual higher-water control/reset access is conservative under room shuffle.',
                         'Independent basement ledges are not classified by the main water-box height.']}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({key: report[key] for key in ('status', 'test_methods', 'behavior_decisions',
                                                  'failures', 'errors', 'archipelago_version', 'world_version')}))
    return int(report['status'] != 'passed')


if __name__ == '__main__':
    raise SystemExit(main())
