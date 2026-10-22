"""Real AP generation/UT graphs for courtyard guards and adult-only Dampé access.

Controlled ingress isolates physical sides; production rules, source predicates,
item collection, event sweeps and saved-map age validation remain in use. This
is not a scene-geometry simulation, full seed fill, or game playthrough.
"""
from hashlib import sha256
import argparse
import io
import json
from pathlib import Path
import re
import time
import unittest
import zipfile

from test_entrance_blockers import (
    SOURCE, Ages, ER, Utils, SohExtremeWorld, arrivals, inventory, reached,
    region, redirect_source, setup_multiworld, call_all,
)
from Options import OptionError
from worlds.soh_extreme import EntranceSafety as Safety

IDS = (11000122, 11000662, 11001024, 11683197)
DRAIN, GUARDS, ZELDA = 'HC_DRAIN_LEDGE', 'HC_COURTYARD_GUARDS', 'HC_GARDEN'
HUT, GRAVEYARD = 'GRAVEYARD_DAMPES_HOUSE', 'THE_GRAVEYARD'
KEY = "Dampe's Hut Key"
FACTS = {}


def build_world(evidence, *, entrances, ut_world=None, original_songs=False):
    options = {key: row['value'] for key, row in evidence['resolved_options'].items()}
    if not original_songs:
        options.update(song_note_shuffle=0, shuffle_ocarina_buttons=0)
    if not entrances:
        options.update({option: 0 for option in ER.CATEGORIES.values()})
        options['mixed_entrance_pools'] = []
    mw = setup_multiworld(SohExtremeWorld, steps=(), seed=evidence['seed'], options=options)
    if ut_world is not None:
        mw.re_gen_passthrough = {SohExtremeWorld.game: {
            'extreme_all_options': options,
            'extreme_active_locations': list(ut_world.courtyard_checks),
            'shop_vanilla_items': dict(ut_world.shop_vanilla_items),
            'shop_prices': dict(ut_world.shop_prices),
            'triforce_hunt_pieces_required': ut_world.triforce_pieces_required,
            'song_note_catalog_revision': 1,
        }}
    for stage in ('generate_early', 'create_regions', 'create_items', 'set_rules'):
        call_all(mw, stage)
    mw.precollected_items[1].clear()
    world = mw.worlds[1]
    for location in world.get_locations():
        if location.address is not None:
            location.item = None
    world.courtyard_checks = {location.address: location for location in world.get_locations()
                              if location.address is not None}
    return world


def clock(world, value, phase=None):
    world._extreme_live_clock = value
    world._extreme_live_time = (0 if 0x4555 <= value <= 0xC000 else 1) if phase is None else phase


def accessible(world, state, check, age):
    return ER._reachable_as_age(world, state, world.courtyard_checks[check], age)


class CourtyardDampeTests(unittest.TestCase):
    cases = 0
    evidence = None
    baseline = None
    saved_map = None

    @classmethod
    def setUpClass(cls):
        cls.ordinary = build_world(cls.evidence, entrances=False)
        cls.shuffled = build_world(cls.evidence, entrances=True)
        cls.ut = build_world(cls.evidence, entrances=False,
                             ut_world=cls.ordinary)
        cls.worlds = (cls.ordinary, cls.shuffled, cls.ut)
        FACTS['world_modes'] = ['ordinary generation graph', 'ER-enabled generation graph',
                                'Universal Tracker regeneration with authoritative active IDs']

    def decision(self, actual, expected, label):
        type(self).cases += 1
        self.assertEqual(bool(actual), bool(expected), label)

    def test_catalog_physical_ids_and_native_data_do_not_change(self):
        relative = 'archipelago/soh_extreme/SceneTransitionCatalog.json'
        current = json.loads((SOURCE / relative).read_text())
        with zipfile.ZipFile(self.baseline) as archive:
            with zipfile.ZipFile(io.BytesIO(archive.read('soh_extreme.apworld'))) as apworld:
                original_bytes = apworld.read('soh_extreme/SceneTransitionCatalog.json')
                original = json.loads(original_bytes)
        self.assertEqual([row['id'] for row in current], [row['id'] for row in original])
        bindings = {
            11000122: (DRAIN, GUARDS), 11000662: (ZELDA, GUARDS),
            11001024: (GUARDS, ZELDA), 11683197: (GUARDS, DRAIN),
        }
        native = (SOURCE / 'soh/Network/Archipelago/SceneTransitionData.inc').read_text()
        for old, new in zip(original, current):
            if new['id'] not in IDS:
                self.assertEqual(old, new)
                continue
            self.assertEqual((new['source'], new['target']), bindings[new['id']])
            self.assertNotIn('traversal_rule', new)
            physical = lambda row: {k: v for k, v in row.items()
                                    if k not in ('source', 'target', 'traversal_rule')}
            self.assertEqual(physical(old), physical(new))
            native_row = re.search(r'\{\s*' + str(new['id']) + r'LL, CrossingKind::Entrance,\s*(\d+),\s*(\d+),\s*(\d+),', native)
            self.assertIsNotNone(native_row)
            self.assertEqual(tuple(map(int, native_row.groups())),
                             (new['source_scene'], new['target_scene'], new['entrances'][0]))
        for world in self.worlds:
            for check, (source, _) in bindings.items():
                self.assertIs(world.courtyard_checks[check].parent_region, region(world, source))
        self.assertTrue(self.ut.using_ut)
        FACTS['stable_catalog'] = {'rows': len(current), 'changed_bindings': list(IDS),
                                  'physical_native_rows_unchanged': True,
                                  'baseline_catalog_sha256': sha256(original_bytes).hexdigest()}

    def test_exact_clock_boundaries_both_ages_all_graph_modes(self):
        for world in self.worlds:
            for age in (Ages.CHILD, Ages.ADULT):
                with arrivals(world, (age, DRAIN)):
                    for value in (0, 0x4554, 0x4555, 0x8000, 0xB888, 0xB889, 0xC000, 0xC001, 0xD000, 0xE000):
                        clock(world, value)
                        state = inventory(world, age, ('Crawl', 'NPC Soul'))
                        child = age == Ages.CHILD
                        pass_maze = child and 0x4555 <= value < 0xB889
                        for check, expected in ((11000122, child), (11683197, child),
                                                (11001024, pass_maze), (11000662, pass_maze)):
                            self.decision(accessible(world, state, check, age), expected,
                                          (world.using_ut, age, hex(value), check))
            # The engine phase is authoritative even if a captured clock is daytime.
            clock(world, 0x8000, phase=1)
            with arrivals(world, (Ages.CHILD, DRAIN)):
                state = inventory(world, Ages.CHILD, ('Crawl', 'NPC Soul'))
                self.decision(accessible(world, state, 11001024, Ages.CHILD), False, 'night flag')

    def test_crawl_and_reverse_zelda_side_are_independent(self):
        for world in self.worlds:
            clock(world, 0xD000)
            with arrivals(world, (Ages.CHILD, DRAIN)):
                state = inventory(world, Ages.CHILD)
                for check in IDS:
                    self.decision(accessible(world, state, check, Ages.CHILD), False, ('no Crawl', check))
            with arrivals(world, (Ages.CHILD, GUARDS)):
                state = inventory(world, Ages.CHILD, ('Crawl', 'NPC Soul'))
                self.decision(accessible(world, state, 11000662, Ages.CHILD), False,
                              'guard side cannot grant Zelda return check')
                self.decision(accessible(world, state, 11683197, Ages.CHILD), True, 'drain escape')
            with arrivals(world, (Ages.CHILD, ZELDA)):
                state = inventory(world, Ages.CHILD, ('Crawl', 'NPC Soul'))
                self.decision(accessible(world, state, 11000662, Ages.CHILD), True, 'legacy Zelda-side exit')
                self.decision(accessible(world, state, 11683197, Ages.CHILD), True, 'legacy onward drain exit')
            with arrivals(world, (Ages.ADULT, ZELDA)):
                state = inventory(world, Ages.ADULT)
                self.decision(accessible(world, state, 11000662, Ages.ADULT), True,
                              'existing adult on Zelda side can leave that scene')

    def test_flow_requires_waitable_route_and_song_requires_instrument(self):
        world = self.ordinary
        clock(world, 0xD000)
        with arrivals(world, (Ages.CHILD, GUARDS)):
            for names, expected in ((('Flow of Time',), False),
                                    (('Flow of Time', 'Crawl'), True),
                                    (("Sun's Song",), False),
                                    (("Sun's Song", 'Progressive Ocarina', 'Crawl'), True)):
                state = inventory(world, Ages.CHILD, names)
                self.decision(accessible(world, state, 11001024, Ages.CHILD), expected, names)

    def test_hut_is_adult_and_key_only_not_an_evening_child_route(self):
        for world in self.worlds:
            for age in (Ages.CHILD, Ages.ADULT):
                with arrivals(world, (age, GRAVEYARD)):
                    for value in (0, 0x4555, 0x8000, 0xC001, 0xD000, 0xDFFF, 0xE000):
                        clock(world, value)
                        for names in ((), (KEY,), (KEY, 'Flow of Time', "Sun's Song", 'Progressive Ocarina', 'NPC Soul')):
                            state = inventory(world, age, names)
                            expected = age == Ages.ADULT and KEY in names
                            self.decision(accessible(world, state, 11000781, age), expected,
                                          ('hut source check', world.using_ut, age, hex(value), names))
                            self.decision(reached(world, state, HUT, age), expected,
                                          ('hut region', world.using_ut, age, hex(value), names))
            for age in (Ages.CHILD, Ages.ADULT):
                with arrivals(world, (age, HUT)):
                    state = inventory(world, age)
                    self.decision(accessible(world, state, 11000853, age), True, 'already inside can leave')

    def test_shuffled_hut_source_keeps_physical_age_and_key(self):
        world = self.shuffled
        clock(world, 0xD000)
        with redirect_source(world, 781, 'TEMPLE_OF_TIME') as edge:
            for age in (Ages.CHILD, Ages.ADULT):
                with arrivals(world, (age, GRAVEYARD)):
                    for names in ((), (KEY,)):
                        state = inventory(world, age, names)
                        expected = age == Ages.ADULT and KEY in names
                        self.decision(ER._reachable_as_age(world, state, edge, age), expected,
                                      ('shuffled hut approach', age, names))
                        self.decision(accessible(world, state, 11000781, age), expected,
                                      ('physical source check stays with hut', age, names))

    def test_destination_policy_rejects_child_spawn_and_child_reachable_shared_source(self):
        world = self.shuffled
        self.assertEqual(Safety.source_age_mask(781), Safety.ADULT)
        self.assertEqual(Safety.arrival_age_mask(781), Safety.ADULT)
        self.assertEqual(Safety.arrival_age_mask(853), Safety.BOTH)
        self.assertFalse(Safety.allowed_route(187, 781))
        self.assertTrue(Safety.allowed_route(642, 781))
        mapping = {row['id']: row['id'] for row in ER._eligible(world)}
        mapping[187] = 781
        with self.assertRaisesRegex(OptionError, 'source age'):
            ER.validate_mapping(world, mapping)
        # Shared physical sources must also be tested by actual reachable age;
        # their BOTH mask is not a permission to send child Link into the hut.
        with redirect_source(world, 83, HUT) as edge:
            for age in (Ages.CHILD, Ages.ADULT):
                with arrivals(world, (age, 'TOT_ENTRANCE')):
                    state = inventory(world, age)
                    self.decision(ER._age_routes_are_safe(world, {83: 781}, {83: edge}, state),
                                  age == Ages.ADULT, ('shared source arrival safety', age))

    def test_saved_uploaded_map_is_evaluated_without_remapping(self):
        evidence = self.saved_map
        world = build_world(evidence, entrances=True, original_songs=True)
        mapping = {int(key): value for key, value in evidence['mapping'].items()}
        hut_sources = [source for source, target in mapping.items() if target == 781]
        world.using_ut = True
        world.passthrough = {'entrance_randomizer': {
            'revision': ER.REVISION, 'destination_policy_revision': Safety.POLICY_REVISION,
            'pool_policy_revision': ER.POOL_POLICY_REVISION, 'connections': evidence['mapping']}}
        try:
            ER.connect(world)
        except OptionError as exc:
            self.assertIn('age-incompatible arrival', str(exc))
            self.assertEqual(world._er_mapping, mapping)
            rejected = True
        else:
            self.assertEqual(world._er_mapping, mapping)
            rejected = False
        all_state = world.multiworld.get_all_state(False, perform_sweep=False).copy()
        all_state.sweep_for_advancements()
        child_sources = [source for source in hut_sources
                         if ER._reachable_as_age(world, all_state,
                             world.get_entrance('EXTREME Shuffled Entrance ' + str(source)), Ages.CHILD)]
        self.assertEqual(rejected, bool(child_sources))
        FACTS['historical_map'] = {
            'connections': len(mapping), 'connections_unchanged': True,
            'hut_sources': hut_sources, 'child_reachable_hut_sources': child_sources,
            'rejected_for_child_hut_arrival': rejected,
            'source_names': {source: ER.ENDPOINTS[source]['name'] for source in hut_sources},
            'scope': 'Production ER.connect with existing saved map and current rules; no new fill or remapping.',
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--options', type=Path, required=True)
    parser.add_argument('--saved-map', type=Path, required=True)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    CourtyardDampeTests.evidence = json.loads(args.options.read_bytes())
    CourtyardDampeTests.saved_map = json.loads(args.saved_map.read_bytes())
    CourtyardDampeTests.baseline = args.baseline
    # Bind every AP source/resource used by the real graph, not just edited rules.
    source_names = sorted(str(path.relative_to(SOURCE))
                          for path in (SOURCE / 'archipelago/soh_extreme').rglob('*')
                          if path.is_file() and path.suffix in ('.py', '.json'))
    source_names += ['soh/Network/Archipelago/SceneTransitionData.inc']
    test_names = ['tools/tests/test_courtyard_dampe_logic.py', 'tools/tests/test_entrance_blockers.py']
    hashes = lambda names: {name: sha256((SOURCE / name).read_bytes()).hexdigest() for name in names}
    source_before, tests_before = hashes(source_names), hashes(test_names)
    started = time.monotonic()
    output = io.StringIO()
    result = unittest.TextTestRunner(stream=output, verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(CourtyardDampeTests))
    print(output.getvalue())
    stable = source_before == hashes(source_names) and tests_before == hashes(test_names)
    report = {
        'status': 'passed' if result.wasSuccessful() and stable else 'failed',
        'archipelago_version': str(Utils.version_tuple),
        'tests_run': result.testsRun, 'decisions': CourtyardDampeTests.cases,
        'elapsed_seconds': round(time.monotonic() - started, 3),
        'source_sha256': source_before, 'test_sha256': tests_before,
        'source_unchanged_during_run': stable,
        'evidence': {path.name: {'path': str(path.resolve()), 'sha256': sha256(path.read_bytes()).hexdigest()}
                     for path in (args.options, args.saved_map, args.baseline)},
        'results': FACTS, 'unittest_output': output.getvalue(),
        'scope': __doc__,
    }
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    raise SystemExit(0 if report['status'] == 'passed' else 1)


if __name__ == '__main__':
    main()
