"""Actual AP rules for Dodongo's Cavern's two temporary-switch room exits.

Controlled arrivals isolate the switch and a physical-door bypass regression.
The exact uploaded seed is restored through UT without changing its mapping;
this suite does not generate a seed or claim a complete gameplay simulation.
"""
from contextlib import ExitStack
from hashlib import sha256
import argparse
import io
import json
from pathlib import Path
import re
import time
import unittest

from test_entrance_blockers import (
    SOURCE, Ages, Regions, ER, N, CollectionState, Utils, arrivals, inventory,
    reached, region, redirect_source,
)
from test_water_arrival_logic import build_world, no_exits
from worlds.soh_extreme import TrackerMirror


DC = 'RR_DODONGOS_CAVERN_'
ARMOS = DC + 'ARMOS_ROOM'
STAIRS = DC + 'STAIRS_UPPER'
BRIDGE = DC + 'ENTRANCE_SIDE_BRIDGE'
BOMBS = DC + 'BOMB_ROOM_LOWER'
MOVEMENT = ('Grab / Power Bracelet', 'Climb')
SOURCES = (8355, 8357)
FACTS = {}
SOURCE_FILES = (
    'archipelago/soh_extreme/__init__.py',
    'archipelago/soh_extreme/EntranceRandomizer.py',
    'archipelago/soh_extreme/EntranceCatalog.json',
    'archipelago/soh_extreme/EntranceDestinationPolicy.json',
    'archipelago/soh_extreme/SceneTransitions.py',
    'archipelago/soh_extreme/DungeonDoorCatalog.json',
    'archipelago/soh_extreme/EnemyRoomLogic.py',
    'archipelago/soh_extreme/EnemyRoomGraph.json',
    'archipelago/soh_extreme/NativeLogic.py',
    'archipelago/soh_extreme/NativeLogicAlternatives.py',
    'archipelago/soh_extreme/_vendor_oot_soh/LogicHelpers.py',
    'archipelago/soh_extreme/_vendor_oot_soh/location_access/dungeons/dodongos_cavern.py',
    'soh/Enhancements/randomizer/location_access/dungeons/dodongos_cavern.cpp',
    'soh/Enhancements/randomizer/logic.cpp',
    'soh/Enhancements/randomizer/hook_handlers.cpp',
    'soh/Enhancements/randomizer/MegaSouls.cpp',
    'src/code/z_actor.c',
    'src/overlays/actors/ovl_Door_Shutter/z_door_shutter.c',
    'src/overlays/actors/ovl_En_Am/z_en_am.c',
    'src/overlays/actors/ovl_player_actor/z_player.c',
)
TEST_FILES = (
    'tools/tests/test_dodongo_armos_logic.py',
    'tools/tests/test_entrance_blockers.py',
    'tools/tests/test_water_arrival_logic.py',
)


def checks(world):
    return {location.address: location for location in world.get_locations()
            if location.address is not None}


class DodongoArmosTests(unittest.TestCase):
    evidence = None
    cases = 0

    @classmethod
    def setUpClass(cls):
        cls.world = build_world(cls.evidence, simplified_songs=False)
        cls.locations = checks(cls.world)

    def decision(self, actual, expected, label):
        type(self).cases += 1
        self.assertEqual(bool(actual), bool(expected), label)

    def test_source_and_graph_bind_both_switch_barred_sides(self):
        native = (SOURCE / SOURCE_FILES[12]).read_text()
        body = native.split('areaTable[' + ARMOS + '] = Region(', 1)[1].split('\n    });', 1)[0]
        compact = lambda text: ''.join(text.split())
        door_catalog = {row['id']: row for row in json.loads(
            (SOURCE / 'archipelago/soh_extreme/DungeonDoorCatalog.json').read_bytes())}
        graph = N.GRAPH[ARMOS]
        self.assertEqual({row['target'] for row in graph['exits']}, {STAIRS, BRIDGE})
        self.assertEqual(graph['events'], [])
        for endpoint in SOURCES:
            row = ER.ENDPOINTS[endpoint]
            physical = door_catalog[row['check_id']]
            self.assertEqual((row['side'], row['from_room'], row['params']), (1, 5, 162))
            self.assertEqual((physical['side'], physical['room_from'], physical['params']), (1, 5, 162))
            self.assertEqual(((row['params'] >> 6) & 15, row['params'] & 63), (2, 0x22))
            condition = next(edge['condition'] for edge in graph['exits'] if edge['target'] == row['target'])
            self.assertIn(compact('ENTRANCE(' + row['target'] + ',' + condition + ')'), compact(body))
        FACTS['physical_switch'] = {'scene': 1, 'room': 5, 'switch': 0x22,
                                   'barred_sources': list(SOURCES),
                                   'free_inward_sources': [8354, 8356],
                                   'temporary_scene_switch': True,
                                   'permanent_or_cross_age_event_added': False}

    def test_both_source_checks_need_the_current_age_switch_action(self):
        world = self.world
        rules = {endpoint: ER._source_rule(world, ER.ENDPOINTS[endpoint]) for endpoint in SOURCES}
        for age in (Ages.CHILD, Ages.ADULT):
            with arrivals(world, (age, ARMOS)):
                for grab in (False, True):
                    for climb in (False, True):
                        for hookshot in (False, True):
                            for soul in (False, True):
                                names = tuple(name for name, present in (
                                    ('Grab / Power Bracelet', grab), ('Climb', climb),
                                    ('Progressive Hookshot', hookshot), ('Armos Soul', soul)) if present)
                                state = inventory(world, age, names)
                                expected = age == Ages.ADULT or (grab and climb)
                                for endpoint in SOURCES:
                                    location = self.locations[ER.ENDPOINTS[endpoint]['check_id']]
                                    label = (age, endpoint, names)
                                    self.decision(rules[endpoint](state), expected, ('source rule', label))
                                    self.decision(location.access_rule(state), expected, ('check rule', label))
                                    self.decision(ER._reachable_as_age(world, state, location, age),
                                                  expected, ('actual reachable check', label))

    def test_unrelated_combat_and_souls_do_not_move_the_structural_statue(self):
        world = self.world
        with arrivals(world, (Ages.CHILD, ARMOS)):
            names = ('Armos Soul', 'Rock / Boulder Soul', 'Kokiri Sword',
                     'Progressive Bomb Bag', 'Progressive Slingshot', 'Keese Soul')
            state = inventory(world, Ages.CHILD, names)
            for endpoint in SOURCES:
                self.decision(ER._source_rule(world, ER.ENDPOINTS[endpoint])(state), False,
                              ('combat cannot reach pillar switch', endpoint))
            state = inventory(world, Ages.CHILD, MOVEMENT)
            for endpoint in SOURCES:
                self.decision(ER._source_rule(world, ER.ENDPOINTS[endpoint])(state), True,
                              ('structural statue requires no enemy or rock soul', endpoint))

    def test_an_adult_visit_does_not_latch_the_child_switch(self):
        world = self.world
        with arrivals(world, (Ages.CHILD, ARMOS), (Ages.ADULT, ARMOS)):
            state = inventory(world, Ages.ADULT)
            for endpoint in SOURCES:
                rule = ER._source_rule(world, ER.ENDPOINTS[endpoint])
                self.decision(rule(state), True, ('adult can perform pillar action', endpoint))
            state.sweep_for_advancements()
            state._soh_extreme_age[1] = Ages.CHILD
            for endpoint in SOURCES:
                rule = ER._source_rule(world, ER.ENDPOINTS[endpoint])
                self.decision(rule(state), False, ('child must perform own temporary action', endpoint))

    def test_outside_door_checks_keep_their_physical_source_credit(self):
        world = self.world
        for endpoint in (8354, 8356):
            row = ER.ENDPOINTS[endpoint]
            with arrivals(world, (Ages.CHILD, row['source'])):
                state = inventory(world, Ages.CHILD)
                self.decision(ER._source_rule(world, row)(state), True, ('unbarred inward side', endpoint))
                self.decision(ER._reachable_as_age(world, state, self.locations[row['check_id']], Ages.CHILD),
                              True, ('inward crossing check still awarded', endpoint))

    def test_remapped_exits_cannot_leave_a_vanilla_bomb_room_bypass(self):
        world = self.world
        dead_end = 'RR_DEKU_TREE_LOBBY'
        with ExitStack() as stack:
            stack.enter_context(arrivals(world, (Ages.CHILD, ARMOS)))
            stack.enter_context(no_exits(world, dead_end))
            for endpoint in SOURCES:
                stack.enter_context(redirect_source(world, endpoint, dead_end))
            state = inventory(world, Ages.CHILD, MOVEMENT)
            self.decision(reached(world, state, dead_end, Ages.CHILD), True, 'takes actual remapped exit')
            self.decision(reached(world, state, BOMBS, Ages.CHILD), False,
                          'no contracted route through the unmapped bridge door')

    def test_unshuffled_stock_routes_obey_the_same_switch(self):
        world = build_world(self.evidence, simplified_songs=False, entrances=False)
        token = 'DODONGOS_CAVERN_ARMOS_ROOM'
        rules = {edge.connected_region.name: edge.access_rule for edge in region(world, token).exits
                 if edge.connected_region is not None}
        for age in (Ages.CHILD, Ages.ADULT):
            with arrivals(world, (age, token)):
                for names in ((), ('Climb',), ('Grab / Power Bracelet',), MOVEMENT):
                    state = inventory(world, age, names)
                    expected = age == Ages.ADULT or names == MOVEMENT
                    for target in (Regions.DODONGOS_CAVERN_STAIRS_UPPER,
                                   Regions.DODONGOS_CAVERN_BOMB_ROOM_LOWER):
                        self.decision(rules[str(target)](state), expected, ('ordinary stock route', age, names, target))

    def test_exact_saved_mapping_restores_and_rejects_this_initial_spawn(self):
        evidence = self.evidence
        self.assertEqual(evidence['status'], 'exactly_reproduced')
        self.assertTrue(evidence['all_placements_match_uploaded_spoiler'])
        self.assertEqual((evidence['matching_placements'], evidence['mismatched_placements']), (4036, 0))
        self.assertEqual(evidence['child_spawn']['id'], 8354)
        world = build_world(evidence, simplified_songs=False)
        world.using_ut = True
        world.passthrough = {'entrance_randomizer': {
            'revision': ER.REVISION, 'destination_policy_revision': ER.Safety.POLICY_REVISION,
            'pool_policy_revision': ER.POOL_POLICY_REVISION, 'connections': evidence['mapping']}}
        ER.connect(world)
        mapping = {int(key): value for key, value in evidence['mapping'].items()}
        self.assertEqual(world._er_mapping, mapping)
        for name in evidence['starting_items']:
            world.multiworld.push_precollected(world.create_item(name))
        network = checks(world)
        for row in evidence['placements']:
            if row['id'] not in (1, 12):
                continue
            network[row['id']].item = world.create_item(row['item']['name'])
        prefix = 'EXTREME Shuffled Entrance '
        edges = {int(edge.name[len(prefix):]): edge for parent in world.get_regions()
                 for edge in parent.exits if edge.name.startswith(prefix)}
        target = ER.ENDPOINTS[evidence['child_spawn']['id']]
        state = ER._initial_state_for_age(world, Ages.CHILD)
        self.decision(ER._spawn_return_is_usable(world, state, target, edges, Ages.CHILD), False,
                      'saved child spawn cannot use its barred physical return')
        self.decision(ER._starting_state_is_viable(world, mapping, edges, []), False,
                      'production start validator rejects this spawn')
        for endpoint in SOURCES:
            location = network[ER.ENDPOINTS[endpoint]['check_id']]
            self.decision(ER._reachable_as_age(world, state, location, Ages.CHILD), False,
                          ('restored source check blocked', endpoint))
        self.decision(reached(world, state, 'HYRULE_FIELD', Ages.CHILD), False,
                      'no phantom opening route to Hyrule Field')
        self.decision(reached(world, state, ARMOS, Ages.ADULT), False,
                      'starting child cannot borrow adult reachability')
        for name in MOVEMENT:
            state.collect(world.create_item(name), True)
        state.sweep_for_advancements()
        self.decision(ER._spawn_return_is_usable(world, state, target, edges, Ages.CHILD), True,
                      'control equipment restores the actual mapped exit')
        self.decision(reached(world, state, 'HYRULE_FIELD', Ages.CHILD), True,
                      'switch-capable child reaches the mapped Hyrule Field exit')
        FACTS['exact_saved_map'] = {
            'connections': len(mapping), 'all_connections_unchanged': True,
            'uploaded_seed': evidence['seed'], 'verified_placements': 4036,
            'child_spawn': target['id'], 'barred_return_source': 8355,
            'mapped_return_destination': mapping[8355],
            'starting_return_usable': False, 'starting_state_viable': False,
            'movement_control_return_usable': True,
            'scope': 'UT restoration and starting-state/source-rule checks; no new fill or full placement replay',
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exact-seed', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    started = time.monotonic()
    evidence = args.exact_seed.read_bytes()
    DodongoArmosTests.evidence = json.loads(evidence)
    digest = lambda name: sha256((SOURCE / name).read_bytes()).hexdigest()
    before = {name: digest(name) for name in SOURCE_FILES}
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(DodongoArmosTests))
    after = {name: digest(name) for name in SOURCE_FILES}
    report = {
        'status': 'passed' if result.wasSuccessful() and before == after else 'failed',
        'test_methods': result.testsRun, 'behavior_decisions': DodongoArmosTests.cases,
        'failures': len(result.failures), 'errors': len(result.errors), 'skipped': len(result.skipped),
        'archipelago_version': str(Utils.__version__), 'world_version': TrackerMirror.VERSION,
        'source_unchanged_during_run': before == after, 'source_sha256': after,
        'test_sha256': {name: digest(name) for name in TEST_FILES},
        'input_evidence_path': str(args.exact_seed.resolve()),
        'input_evidence_sha256': sha256(evidence).hexdigest(),
        'elapsed_seconds': round(time.monotonic() - started, 3),
        'facts': FACTS, 'test_output': stream.getvalue(),
        'limits': ['Actual AP rules with controlled arrivals; no native collision or gameplay simulation.',
                   'Adult, usable Hookshot and explicit native trick alternatives retain the authored path rules.',
                   'Temporary switch state is not granted or converted to a permanent AP event.'],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    print(stream.getvalue())
    print(json.dumps({key: report[key] for key in ('status', 'test_methods', 'behavior_decisions',
                                                  'failures', 'errors', 'skipped')}))
    return int(report['status'] != 'passed')


if __name__ == '__main__':
    raise SystemExit(main())
