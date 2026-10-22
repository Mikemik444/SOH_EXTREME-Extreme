"""Keep a physical bomb-hole opening separate from a shuffled grotto spawn.

The real AP world, item collection, event sweeps, source rules and saved-map
restore are exercised. The controlled map is explicitly a fixture, not a
reconstruction of any uploaded seed or a native gameplay simulation.
"""
from hashlib import sha256
import argparse
import io
import json
from pathlib import Path
import time
import unittest

from test_entrance_blockers import (
    SOURCE, Ages, ER, Utils, arrivals, inventory, reached,
)
from test_water_arrival_logic import build_world


GROTTO = 'HF_NEAR_KAK_GROTTO'
ENTRY = 1806
EXIT = 2062
CHILD_SPAWN = 187
ENEMY_CHECK = 9800499
SOURCE_FILES = (
    'archipelago/soh_extreme/__init__.py',
    'archipelago/soh_extreme/EnemyDropLocations.py',
    'archipelago/soh_extreme/EnemyDropRules.py',
    'archipelago/soh_extreme/EntranceRandomizer.py',
    'archipelago/soh_extreme/EntranceCatalog.json',
    'archipelago/soh_extreme/EntranceDestinationPolicy.json',
    'archipelago/soh_extreme/SceneTransitions.py',
    'archipelago/soh_extreme/_vendor_oot_soh/LogicHelpers.py',
    'archipelago/soh_extreme/_vendor_oot_soh/location_access/overworld/hyrule_field.py',
)
TEST_FILES = (
    'tools/tests/test_bomb_grotto_logic.py',
    'tools/tests/test_entrance_blockers.py',
    'tools/tests/test_water_arrival_logic.py',
)
FACTS = {}


def restore_controlled_spawn(world):
    """Use production validation/restore for a complete coupled fixture map."""
    mapping = {row['id']: row['id'] for row in ER._eligible(world)}
    mapping[CHILD_SPAWN] = ENTRY
    for row in ER.CATALOG:
        if row['category'] != 'blue_warps':
            continue
        boss = next((candidate for candidate in ER.CATALOG
                     if candidate['category'] == 'bosses' and candidate['primary']
                     and candidate['target'] == row['source']), None)
        mapping[row['id']] = (mapping[boss['reverse']]
                              if boss and boss['reverse'] in mapping else row['id'])
    world.using_ut = True
    world.passthrough = {
        'song_note_catalog_revision': 1,
        'entrance_randomizer': {
            'revision': ER.REVISION,
            'destination_policy_revision': ER.Safety.POLICY_REVISION,
            'pool_policy_revision': ER.POOL_POLICY_REVISION,
            'connections': mapping,
        },
    }
    ER.connect(world)
    assert world._er_mapping == mapping
    return mapping


class BombGrottoLogicTests(unittest.TestCase):
    evidence = None
    cases = 0

    @classmethod
    def setUpClass(cls):
        cls.world = build_world(cls.evidence, simplified_songs=False)
        cls.mapping = restore_controlled_spawn(cls.world)
        cls.checks = {location.address: location for location in cls.world.get_locations()
                      if location.address is not None}
        FACTS['controlled_saved_map'] = {
            'entries': len(cls.mapping),
            'child_spawn': [CHILD_SPAWN, cls.mapping[CHILD_SPAWN]],
            'outside_entry': [ENTRY, cls.mapping[ENTRY]],
            'return': [EXIT, cls.mapping[EXIT]],
            'restored_through_production_ER_connect': True,
            'claimed_to_be_uploaded_seed_map': False,
        }

    def decision(self, actual, expected, label):
        type(self).cases += 1
        self.assertEqual(bool(actual), bool(expected), label)

    def test_physical_surface_opening_needs_a_usable_attack(self):
        world = self.world
        rule = ER._source_rule(world, ER.ENDPOINTS[ENTRY])
        # Supply the existing non-attack prerequisites to isolate the reported
        # opening-tool issue. This test does not assert that a bare Door_Ana
        # physically has a Rock Soul gate or a liftable boulder.
        prerequisites = ('Shovel', 'Rock / Boulder Soul', 'Stone of Agony',
                         'Skulltula Soul', 'Kokiri Sword', 'Master Sword')
        rows = []
        for age in (Ages.CHILD, Ages.ADULT):
            with arrivals(world, (age, 'HYRULE_FIELD')):
                for tools in ((), ('Grab / Power Bracelet',), ('Megaton Hammer',),
                              ('Progressive Bomb Bag',), ('Bombchu Bag',),
                              ('Bombs (10)',), ('Bombchus (20)',)):
                    expected = (tools in (('Progressive Bomb Bag',), ('Bombchu Bag',))
                                or (age == Ages.ADULT and tools == ('Megaton Hammer',)))
                    state = inventory(world, age, prerequisites + tools)
                    label = (str(age), tools)
                    source = rule(state)
                    crossing = ER._reachable_as_age(
                        world, state, self.checks[ER.ENDPOINTS[ENTRY]['check_id']], age)
                    inside = reached(world, state, GROTTO, age)
                    enemy = ER._reachable_as_age(world, state, self.checks[ENEMY_CHECK], age)
                    self.decision(source, expected, ('physical source predicate', label))
                    self.decision(crossing, expected, ('actual source crossing check', label))
                    self.decision(inside, expected, ('entry reaches grotto', label))
                    self.decision(enemy, expected, ('enemy inherits the physical entry', label))
                    rows.append({'age': str(age), 'tools': list(tools), 'can_open': expected})
        FACTS['surface_attack_matrix'] = rows

    def test_spawn_has_interior_access_without_opening_the_surface_hole(self):
        world = self.world
        self.assertEqual(self.mapping[CHILD_SPAWN], ENTRY)
        self.assertEqual(self.checks[ENEMY_CHECK].parent_region.name, 'HF Near Kak Grotto')
        owned = ('Shovel', 'Skulltula Soul', 'Kokiri Sword')
        state = inventory(world, Ages.CHILD, owned)
        self.decision(reached(world, state, GROTTO, Ages.CHILD), True, 'spawn is already inside')
        self.decision(reached(world, state, 'HYRULE_FIELD', Ages.CHILD), True, 'exit leads to the field')
        self.decision(ER._reachable_as_age(world, state, self.checks[ENEMY_CHECK], Ages.CHILD),
                      True, 'spawned inside can defeat the actual Skulltula')
        self.decision(ER._reachable_as_age(world, state, self.checks[ER.ENDPOINTS[EXIT]['check_id']], Ages.CHILD),
                      True, 'grotto exit does not need surface explosives')
        self.decision(ER._reachable_as_age(world, state, self.checks[ER.ENDPOINTS[ENTRY]['check_id']], Ages.CHILD),
                      False, 'interior access does not credit opening the outside entry')
        for item in ('Progressive Bomb Bag', 'Bombchu Bag', 'Megaton Hammer',
                     'Grab / Power Bracelet', 'Rock / Boulder Soul', 'Stone of Agony'):
            self.decision(state.has(item, world.player), False, ('probe really lacks', item))
        FACTS['spawn_access'] = {'owned': list(owned), 'grotto_reachable': True,
                                 'enemy_reachable': True, 'exit_reachable': True,
                                 'outside_crossing_reachable': False}

    def test_source_gate_is_still_required_after_a_spawn_visit(self):
        world = self.world
        # Grant every non-attack source prerequisite. The completed interior
        # visit and event sweep must not fabricate an opened surface entrance.
        owned = ('Shovel', 'Skulltula Soul', 'Kokiri Sword',
                 'Rock / Boulder Soul', 'Stone of Agony')
        state = inventory(world, Ages.CHILD, owned)
        rule = ER._source_rule(world, ER.ENDPOINTS[ENTRY])
        self.decision(self.checks[ENEMY_CHECK].can_reach(state), True, 'inside is reachable')
        self.decision(rule(state), False, 'outside source remains closed after interior visit')
        state.collect(world.create_item('Progressive Bomb Bag'), True)
        state.sweep_for_advancements()
        state._soh_extreme_age[world.player] = Ages.CHILD
        self.decision(rule(state), True, 'receiving usable bombs enables the source')
        self.decision(self.checks[ER.ENDPOINTS[ENTRY]['check_id']].can_reach(state), True,
                      'live item receipt invalidates the source dependency')

    def test_source_shovel_requirement_is_independent_of_explosives(self):
        world = self.world
        with arrivals(world, (Ages.CHILD, 'HYRULE_FIELD')):
            owned = ('Progressive Bomb Bag', 'Rock / Boulder Soul', 'Stone of Agony')
            state = inventory(world, Ages.CHILD, owned)
            rule = ER._source_rule(world, ER.ENDPOINTS[ENTRY])
            self.decision(rule(state), False, 'bombs alone do not bypass shuffled Shovel')
            self.decision(reached(world, state, GROTTO, Ages.CHILD), False,
                          'surface ingress is blocked without Shovel')
            state.collect(world.create_item('Shovel'), True)
            state.sweep_for_advancements()
            state._soh_extreme_age[world.player] = Ages.CHILD
            self.decision(rule(state), True, 'Shovel and usable explosives enable source')
            self.decision(reached(world, state, GROTTO, Ages.CHILD), True,
                          'receiving Shovel updates region reachability')


def hashes(paths):
    return {relative: sha256((SOURCE / relative).read_bytes()).hexdigest() for relative in paths}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--settings-report', type=Path, required=True,
                        help='A report containing resolved_options and seed; its map is not used.')
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    evidence = json.loads(args.settings_report.read_bytes())
    BombGrottoLogicTests.evidence = evidence
    before = hashes(SOURCE_FILES)
    started = time.monotonic()
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(BombGrottoLogicTests))
    print(stream.getvalue(), end='')
    after = hashes(SOURCE_FILES)
    assert before == after, 'Production AP source changed during regression validation'
    report = {
        'status': 'passed' if result.wasSuccessful() else 'failed',
        'tests': result.testsRun, 'decisions': BombGrottoLogicTests.cases,
        'world_version': BombGrottoLogicTests.world.world_version.as_simple_string(),
        'archipelago_version': Utils.__version__,
        'source_sha256': before, 'test_sha256': hashes(TEST_FILES),
        'source_unchanged_during_run': True,
        'settings_report_sha256': sha256(args.settings_report.read_bytes()).hexdigest(),
        'configured_seed': evidence['seed'],
        'elapsed_seconds': round(time.monotonic() - started, 3),
        'facts': FACTS,
        'scope': ('Controlled saved-map restore and real AP/UT rule evaluation. '
                  'No seed-map attribution, item fill, native collision or in-game playthrough claim.'),
        'failures': [str(case) + '\n' + detail for case, detail in result.failures + result.errors],
    }
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    if not result.wasSuccessful():
        raise SystemExit(1)


if __name__ == '__main__':
    main()
