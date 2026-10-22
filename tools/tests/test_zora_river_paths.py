"""Verify separate river land/water routes through the actual AP world.

Runs source/arrival and item-receipt decisions, restores an exact older map,
and generates one fresh all-pool entrance map. No item fill or gameplay run
is claimed. Inputs are the previous reproduction report and resolved options.
"""
from hashlib import sha256
import argparse
import io
import json
from pathlib import Path
import time
import unittest

from test_entrance_blockers import (
    SOURCE, Ages, ER, Utils, arrivals, inventory, setup_multiworld, SohExtremeWorld,
)
from test_water_arrival_logic import build_world
from test_overworld_entrances import exchange_pairs, shuffled_edges
from Options import OptionError


RIVER_IDS = (234, 385, 473, 785)
WATER_IDS = (473, 785)
SOURCE_FILES = (
    'archipelago/soh_extreme/__init__.py',
    'archipelago/soh_extreme/EntranceRandomizer.py',
    'archipelago/soh_extreme/EntranceCatalog.json',
    'archipelago/soh_extreme/EntranceSafety.py',
    'archipelago/soh_extreme/EntranceDestinationPolicy.json',
    'archipelago/soh_extreme/NativeSettings.py',
    'archipelago/soh_extreme/SceneTransitions.py',
    'archipelago/soh_extreme/SceneTransitionCatalog.json',
    'archipelago/soh_extreme/CheckDescriptions.py',
    'archipelago/soh_extreme/CheckDescriptions.json',
    'archipelago/soh_extreme/_vendor_oot_soh/LogicHelpers.py',
    'archipelago/soh_extreme/_vendor_oot_soh/location_access/overworld/hyrule_field.py',
    'archipelago/soh_extreme/_vendor_oot_soh/location_access/overworld/zoras_river.py',
)
TEST_FILES = (
    'tools/tests/test_zora_river_paths.py',
    'tools/tests/test_overworld_entrances.py',
    'tools/tests/test_water_arrival_logic.py',
    'tools/tests/test_entrance_blockers.py',
)
FACTS = {}


def full_identity(world):
    mapping = {row['id']: row['id'] for row in ER._eligible(world)}
    for row in ER.CATALOG:
        if row['category'] == 'blue_warps':
            mapping[row['id']] = row['id']
    return mapping


def add_blue_warps(mapping):
    for row in ER.CATALOG:
        if row['category'] != 'blue_warps':
            continue
        boss = next((candidate for candidate in ER.CATALOG
                     if candidate['category'] == 'bosses' and candidate['primary']
                     and candidate['target'] == row['source']), None)
        mapping[row['id']] = (mapping[boss['reverse']]
                              if boss and boss['reverse'] in mapping else row['id'])


def restore(world, mapping, river_revision):
    world.using_ut = True
    saved = {
        'revision': ER.REVISION,
        'destination_policy_revision': ER.Safety.POLICY_REVISION,
        'pool_policy_revision': ER.POOL_POLICY_REVISION,
        'connections': {str(key): value for key, value in mapping.items()},
    }
    if river_revision is not None:
        saved['river_path_revision'] = river_revision
    world.passthrough = {'song_note_catalog_revision': 1, 'entrance_randomizer': saved}
    rng = world.random.getstate()
    ER.connect(world)
    assert world.random.getstate() == rng
    assert world._er_mapping == mapping
    return shuffled_edges(world)


class RiverTests(unittest.TestCase):
    evidence = None
    legacy_report = None
    decisions = 0

    @classmethod
    def setUpClass(cls):
        cls.world = build_world(cls.evidence, simplified_songs=False)
        cls.mapping = full_identity(cls.world)
        exchange_pairs(cls.mapping, 234, 333)  # Land path <-> DMT/Goron City.
        exchange_pairs(cls.mapping, 473, 626)  # Water path <-> Link's House.
        cls.mapping[187] = 1806
        add_blue_warps(cls.mapping)
        cls.edges = restore(cls.world, cls.mapping, 1)
        cls.checks = {location.address: location for location in cls.world.get_locations()
                      if location.address is not None}
        FACTS['controlled_map'] = {
            'entries': len(cls.mapping),
            'river_routes': {str(key): cls.mapping[key] for key in RIVER_IDS},
            'dry_source_to_water': {str(key): cls.mapping[key] for key in (626, 529)},
            'restored_by_production_connect': True,
            'claimed_to_be_uploaded_seed': False,
        }

    def decision(self, actual, expected, label):
        type(self).decisions += 1
        self.assertEqual(actual, expected, label)

    def test_four_physical_endpoints_are_distinct_and_coupled(self):
        self.decision(len(ER.CATALOG), 721, 'full catalog')
        self.decision(sum(row['category'] == 'overworld' for row in ER.CATALOG), 54, 'overworld catalog')
        for source in RIVER_IDS:
            target = self.mapping[source]
            self.decision(self.mapping[ER.ENDPOINTS[target]['reverse']],
                          ER.ENDPOINTS[source]['reverse'], ('coupled return', source))
            self.decision(ER.ENDPOINTS[source]['check_id'], 11000000 + source,
                          ('unchanged physical check', source))
            self.decision(self.edges[source].connected_region.name,
                          ER.region_name(ER.ENDPOINTS[target]['target']), ('actual graph target', source))
            for age in (ER.Safety.CHILD, ER.Safety.ADULT):
                self.decision(ER.Safety.allowed_age(source, age), True, ('ordinary age', source, age))
        self.decision(self.mapping[234] != self.mapping[473], True, 'different forward destinations')
        self.decision(self.mapping[385] != self.mapping[785], True, 'different backward destinations')

    def test_water_crossing_needs_swim_but_land_crossing_does_not(self):
        world = self.world
        for age in (Ages.CHILD, Ages.ADULT):
            for source in RIVER_IDS:
                row = ER.ENDPOINTS[source]
                with arrivals(world, (age, row['source'])):
                    for owned in ((), ('Swim',), ('Progressive Scale',)):
                        state = inventory(world, age, owned)
                        expected = source not in WATER_IDS or bool(owned)
                        check = self.checks[row['check_id']]
                        self.decision(check.access_rule(state), expected, ('source gate', age, source, owned))
                        self.decision(ER._reachable_as_age(world, state, check, age), expected,
                                      ('physical crossing check', age, source, owned))
                        self.decision(self.edges[source].access_rule(state), expected,
                                      ('outbound routed edge', age, source, owned))
                        if owned == ('Progressive Scale',):
                            self.decision(state.has('Swim', world.player), True,
                                          'first Progressive Scale grants basic Swim')

    def test_dry_source_to_water_arrival_keeps_the_source_check_separate(self):
        world = self.world
        for age in (Ages.CHILD, Ages.ADULT):
            for source, target in ((626, 473), (529, 785)):
                with arrivals(world, (age, ER.ENDPOINTS[source]['source'])):
                    # Reaching Link's elevated house door requires Climb; this
                    # independently preserved source gate must be supplied to
                    # isolate the destination's missing Swim requirement.
                    state = inventory(world, age, ('Climb',))
                    check = self.checks[ER.ENDPOINTS[source]['check_id']]
                    edge = self.edges[source]
                    self.decision(check.access_rule(state), True, ('dry source check', age, source))
                    self.decision(edge.access_rule(state), False, ('wet destination', age, target))
                    # Use the real collect/remove dependency invalidation, including
                    # the virtual Swim granted by the first physical scale.
                    item = world.create_item('Progressive Scale')
                    state.collect(item, True)
                    state.sweep_for_advancements()
                    state._soh_extreme_age[world.player] = age
                    self.decision(edge.access_rule(state), True, ('received Swim', age, target))
                    state.remove(item)
                    state._soh_extreme_age[world.player] = age
                    self.decision(edge.access_rule(state), False, ('removed Swim', age, target))
                    self.decision(check.access_rule(state), True, 'source check does not inherit destination water')

    def test_new_metadata_rejects_missing_or_uncoupled_water_paths(self):
        world = self.world
        eligible = {row['id'] for row in ER._eligible(world)}
        mapping = {key: value for key, value in self.mapping.items() if key in eligible}
        ER.validate_mapping(world, mapping)
        for source in WATER_IDS:
            broken = dict(mapping)
            del broken[source]
            with self.assertRaises(OptionError):
                ER.validate_mapping(world, broken)
            self.decision(source in eligible, True, 'required independent water source')
        broken = dict(mapping)
        broken[473] = 234
        with self.assertRaises(OptionError):
            ER.validate_mapping(world, broken)
        self.decision(ER.slot_data(world)['river_path_revision'], 1, 'UT marker')
        self.decision(ER.native_settings(world)['EntranceRiverPathsRevision'], 1, 'native marker')
        self.decision(ER.native_settings(world)['EntranceMap.473'], self.mapping[473], 'native water route')

    def test_old_719_route_map_replays_exactly_with_physical_water_checks(self):
        world = build_world(self.evidence, simplified_songs=False)
        mapping = {int(key): value for key, value in self.legacy_report['mapping'].items()}
        self.decision(len(mapping), 719, 'actual earlier map size')
        self.decision(any(source in mapping for source in WATER_IDS), False, 'older map has no explicit water sources')
        edges = restore(world, mapping, None)
        self.decision(world._er_mapping, mapping, 'every saved route restored unchanged')
        self.decision(ER.slot_data(world)['connections'], {str(k): v for k, v in sorted(mapping.items())},
                      'exported saved map unchanged')
        self.decision(ER.slot_data(world)['river_path_revision'], 0, 'old UT marker')
        self.decision(ER.native_settings(world)['EntranceRiverPathsRevision'], 0, 'old native marker')
        checks = {location.address: location for location in world.get_locations()
                  if location.address is not None}
        for water, land in ER.RIVER_WATER_ALIASES.items():
            self.decision(edges[water].connected_region.name,
                          ER.region_name(ER.ENDPOINTS[mapping[land]]['target']), 'old aliased water destination')
            for age in (Ages.CHILD, Ages.ADULT):
                for owned in ((), ('Progressive Scale',)):
                    state = inventory(world, age, owned, sweep=False)
                    self.decision(checks[11000000 + water].access_rule(state), bool(owned),
                                  ('old map physical water check', water, age, owned))
        FACTS['legacy_map_replay'] = {
            'source_report_status': self.legacy_report['status'],
            'official_output_name': self.legacy_report['official_output_name'],
            'entries': len(mapping), 'mismatched_routes': 0,
            'rng_unchanged': True,
            'water_destinations': {str(w): mapping[l] for w, l in ER.RIVER_WATER_ALIASES.items()},
            'item_placement_regenerated': False,
        }

    def test_z_fresh_generation_has_all_721_routes_and_independent_pairs(self):
        # Retain actual starting items/prefill for the real generation guards.
        options = {key: row['value'] for key, row in self.evidence['resolved_options'].items()}
        mw = setup_multiworld(SohExtremeWorld, seed=self.evidence['seed'], options=options,
                              steps=('generate_early', 'create_regions', 'create_items', 'set_rules'))
        world = mw.worlds[1]
        self.decision(world.using_ut, False, 'fresh generation path')
        start = time.monotonic()
        ER.connect(world)
        elapsed = time.monotonic() - start
        mapping = world._er_mapping
        edges = shuffled_edges(world)
        self.decision(len(mapping), 721, 'fresh complete map')
        self.decision(set(mapping), set(ER.ENDPOINTS), 'no missing endpoint')
        for source, target in mapping.items():
            row = ER.ENDPOINTS[source]
            if row['reverse'] >= 0:
                self.decision(mapping[ER.ENDPOINTS[target]['reverse']], row['reverse'], ('fresh coupling', source))
        self.decision(mapping[234] != mapping[473], True, 'fresh land/water destinations differ')
        self.decision(mapping[385] != mapping[785], True, 'fresh land/water reverse destinations differ')
        eligible = {row['id'] for row in ER._eligible(world)}
        ER.validate_mapping(world, {key: value for key, value in mapping.items() if key in eligible})
        fill_locations = [loc for loc in world.get_locations() if loc.address is not None and loc.item is None]
        self.decision(ER._starting_state_is_viable(world, mapping, edges, fill_locations), True,
                      'actual starting inventory, age and escape guard')
        # Exercise the official wire data builder, not just the ER helper.
        slot = world.fill_slot_data()
        self.decision(slot['entrance_randomizer']['river_path_revision'], 1, 'official AP slot marker')
        native = slot['extreme_soh_cvars']
        if isinstance(native, str):
            native = json.loads(native)
        self.decision(native['EntranceRiverPathsRevision'], 1, 'official native snapshot marker')
        for endpoint in RIVER_IDS:
            self.decision(native['EntranceMap.' + str(endpoint)], mapping[endpoint], 'official native route')
        FACTS['fresh_generation'] = {
            'seed': self.evidence['seed'], 'entries': len(mapping),
            'generation_seconds': round(elapsed, 3),
            'river_routes': {str(key): mapping[key] for key in RIVER_IDS},
            'accepted_changes': world._er_generation_attempts,
            'starting_state_viable': True,
            'official_slot_metadata_verified': True,
            'mapping': {str(key): value for key, value in sorted(mapping.items())},
            'item_fill_performed': False,
        }


def hashes(paths):
    return {relative: sha256((SOURCE / relative).read_bytes()).hexdigest() for relative in paths}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--settings-report', type=Path, required=True)
    parser.add_argument('--legacy-report', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    RiverTests.evidence = json.loads(args.settings_report.read_bytes())
    RiverTests.legacy_report = json.loads(args.legacy_report.read_bytes())
    before = hashes(SOURCE_FILES)
    started = time.monotonic()
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(RiverTests))
    print(stream.getvalue(), end='')
    after = hashes(SOURCE_FILES)
    assert before == after, 'Production source changed during AP regression run'
    report = {
        'status': 'passed' if result.wasSuccessful() else 'failed',
        'tests': result.testsRun, 'decisions': RiverTests.decisions,
        'world_version': RiverTests.world.world_version.as_simple_string(),
        'archipelago_version': Utils.__version__,
        'source_sha256': before, 'test_sha256': hashes(TEST_FILES),
        'source_unchanged_during_run': True,
        'settings_report_sha256': sha256(args.settings_report.read_bytes()).hexdigest(),
        'legacy_report_sha256': sha256(args.legacy_report.read_bytes()).hexdigest(),
        'elapsed_seconds': round(time.monotonic() - started, 3),
        'facts': FACTS,
        'scope': 'Actual AP rule evaluation, exact older-map restore, and one fresh entrance generation. No item fill or gameplay run.',
        'failures': [str(case) + '\n' + detail for case, detail in result.failures + result.errors],
    }
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    if not result.wasSuccessful():
        raise SystemExit(1)


if __name__ == '__main__':
    main()
