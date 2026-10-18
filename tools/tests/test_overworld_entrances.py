"""Overworld pool and saved-map regressions against the real AP/SoH graph.

Run with Archipelago 0.6.7 source and dependencies on PYTHONPATH.
"""
import random
import unittest
from unittest.mock import patch

import ModuleUpdate
ModuleUpdate.update_ran = True
import settings
settings.no_gui = True
settings.skip_autosave = True

from BaseClasses import CollectionState, Item, ItemClassification
from Options import OptionError
from test.general import setup_multiworld
from worlds.AutoWorld import call_all
from worlds.soh_extreme import SohExtremeWorld
from worlds.soh_extreme import EntranceRandomizer as ER
from worlds.soh_extreme._vendor_oot_soh.Enums import Ages


def exchange_pairs(mapping, first, second):
    a, b = mapping[first], mapping[second]
    mapping[first], mapping[second] = b, a
    mapping[ER.ENDPOINTS[b]['reverse']] = ER.ENDPOINTS[first]['reverse']
    mapping[ER.ENDPOINTS[a]['reverse']] = ER.ENDPOINTS[second]['reverse']


def shuffled_edges(world):
    prefix = 'EXTREME Shuffled Entrance '
    return {int(edge.name.removeprefix(prefix)): edge
            for region in world.get_regions() for edge in region.exits
            if edge.name.startswith(prefix)}


class OverworldPoolTests(unittest.TestCase):
    def world(self, **options):
        return setup_multiworld(SohExtremeWorld, steps=(), seed=1802, options=options).worlds[1]

    def test_default_is_off_and_overworld_toggle_selects_all_52_endpoints(self):
        world = self.world()
        self.assertNotIn('overworld', ER.enabled_categories(world))
        self.assertEqual(ER._eligible(world), [])
        world.options.shuffle_overworld_entrances.value = 1
        rows = ER._eligible(world)
        self.assertEqual(len(rows), 52)
        self.assertEqual({row['category'] for row in rows}, {'overworld'})
        ids = {row['id'] for row in rows}
        # Trail/City, summit/Crater, Darunia/Crater, and Woods/City.
        self.assertTrue({333, 441, 327, 445, 582, 449, 1250, 1238} <= ids)

    def test_overworld_candidates_keep_every_return_paired(self):
        world = self.world(shuffle_overworld_entrances=1)
        for seed in range(10):
            world.random = random.Random(seed)
            mapping = ER._candidate(world)
            ER.validate_mapping(world, mapping)
            self.assertTrue(any(source != target for source, target in mapping.items()))
            for source, target in mapping.items():
                self.assertEqual(ER.ENDPOINTS[target]['category'], 'overworld')
                self.assertEqual(mapping[ER.ENDPOINTS[target]['reverse']], ER.ENDPOINTS[source]['reverse'])

    def test_overworld_and_interiors_stay_separate_unless_mixed(self):
        world = self.world(shuffle_overworld_entrances=1, shuffle_interior_entrances=1)
        mapping = ER._candidate(world)
        for source, target in mapping.items():
            self.assertEqual(ER.ENDPOINTS[source]['category'], ER.ENDPOINTS[target]['category'])
        mapping = {row['id']: row['id'] for row in ER._eligible(world)}
        exchange_pairs(mapping, 333, 626)  # Trail/City <-> Kokiri Forest/Link's House.
        with self.assertRaises(OptionError):
            ER.validate_mapping(world, mapping)
        world.options.mixed_entrance_pools.value = {'overworld', 'interiors'}
        ER.validate_mapping(world, mapping)
        self.assertEqual(mapping[529], 441)  # Leaving the reached house returns to DMT.

    def test_native_overworld_flag_covers_paired_and_one_way_routes(self):
        for overworld, one_ways in ((0, 0), (1, 0), (0, 1), (1, 1)):
            world = self.world(shuffle_overworld_entrances=overworld,
                               shuffle_one_way_entrances=one_ways)
            native = ER.native_settings(world)
            self.assertEqual(native['ShuffleOverworldEntrances'], int(bool(overworld or one_ways)))
            self.assertEqual(native['DecoupleEntrances'], 0)

    def test_old_slot_without_entrance_data_disables_new_pool_too(self):
        world = self.world(shuffle_overworld_entrances=1, shuffle_interior_entrances=1,
                           mixed_entrance_pools={'overworld', 'interiors'})
        world.using_ut = True
        world.passthrough = {}
        ER.restore_legacy_defaults(world)
        self.assertFalse(ER.enabled(world))
        self.assertFalse(world.options.mixed_entrance_pools.value)

    def test_missing_overworld_option_defaults_off_for_an_old_mapped_slot(self):
        world = self.world(shuffle_overworld_entrances=1, shuffle_interior_entrances=1)
        world.using_ut = True
        world.passthrough = {'entrance_randomizer': {'revision': 1, 'connections': {}},
                             'extreme_all_options': {'shuffle_interior_entrances': 1}}
        ER.restore_legacy_defaults(world)
        self.assertFalse(world.options.shuffle_overworld_entrances.value)
        self.assertTrue(world.options.shuffle_interior_entrances.value)

    def test_explicit_saved_overworld_option_is_preserved(self):
        for nested in (True, False):
            world = self.world(shuffle_overworld_entrances=1)
            world.using_ut = True
            world.passthrough = {'entrance_randomizer': {'revision': 1, 'connections': {}}}
            if nested:
                world.passthrough['extreme_all_options'] = {'shuffle_overworld_entrances': 1}
            else:
                world.passthrough['shuffle_overworld_entrances'] = 1
            ER.restore_legacy_defaults(world)
            self.assertTrue(world.options.shuffle_overworld_entrances.value)


class OverworldGraphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.multiworld = setup_multiworld(SohExtremeWorld, seed=1802, options={
            'shuffle_overworld_entrances': 1, 'shuffle_interior_entrances': 1,
            'mixed_entrance_pools': {'overworld', 'interiors'}, 'shuffle_grab': 1,
        }, steps=('generate_early', 'create_regions', 'create_items', 'set_rules'))
        cls.world = cls.multiworld.worlds[1]
        cls.mapping = {row['id']: row['id'] for row in ER._eligible(cls.world)}
        exchange_pairs(cls.mapping, 333, 626)
        exchange_pairs(cls.mapping, 582, 327)
        cls.world.using_ut = True
        cls.world.passthrough = {'entrance_randomizer': {
            'revision': 1, 'connections': {str(k): v for k, v in cls.mapping.items()},
        }}
        cls.rng_before = cls.world.random.getstate()
        ER.connect(cls.world)
        cls.edges = shuffled_edges(cls.world)

    def test_goron_city_and_crater_routes_use_the_saved_destinations(self):
        for source in (333, 441, 327, 445, 582, 449, 626, 529):
            expected = ER.region_name(ER.ENDPOINTS[self.mapping[source]]['target'])
            self.assertEqual(self.edges[source].connected_region.name, expected)
        self.assertEqual(self.edges[333].connected_region.name, ER.region_name('KF_LINKS_HOUSE'))
        self.assertEqual(self.edges[529].connected_region.name, ER.region_name('DEATH_MOUNTAIN_TRAIL'))

    def test_no_vanilla_overworld_edge_bypasses_the_saved_shuffle(self):
        for row in ER._eligible(self.world):
            if row['category'] != 'overworld':
                continue
            source = self.world.get_region(ER.region_name(row['source']))
            target_name = ER.region_name(row['target'])
            bypasses = [edge for edge in source.exits
                        if edge.connected_region and edge.connected_region.name == target_name
                        and not edge.name.startswith('EXTREME Shuffled Entrance ')]
            self.assertEqual(bypasses, [], row['name'])

    def test_source_age_and_grab_gate_survives_a_new_destination(self):
        state = CollectionState(self.multiworld)
        state._soh_extreme_age[1] = Ages.CHILD
        self.assertFalse(self.edges[582].access_rule(state))
        state._soh_extreme_age[1] = Ages.ADULT
        self.assertFalse(self.edges[582].access_rule(state))
        state.collect(Item('Grab / Power Bracelet', ItemClassification.progression, 9500001, 1), True)
        self.assertTrue(self.edges[582].access_rule(state))

    def test_saved_connections_replay_exactly_without_consuming_rng(self):
        self.assertEqual(self.world._er_mapping, self.mapping)
        self.assertEqual(self.world.random.getstate(), self.rng_before)
        self.assertEqual(ER.slot_data(self.world)['revision'], 1)
        ER.validate_mapping(self.world, self.mapping)


class AllMixedPoolTests(unittest.TestCase):
    def world(self, **options):
        return setup_multiworld(SohExtremeWorld, steps=(), seed=1802, options=options).worlds[1]

    def test_all_matches_an_explicit_list_for_every_enabled_pool(self):
        options = {option: 1 for option in ER.CATEGORIES.values()}
        all_world = self.world(**options, mixed_entrance_pools={'all'})
        explicit_world = self.world(**options, mixed_entrance_pools=set(ER.CATEGORIES))
        self.assertEqual(ER.mixed_categories(all_world), ER.mixed_categories(explicit_world))
        mapping = ER._candidate(all_world)
        self.assertEqual(mapping, ER._candidate(explicit_world))
        ER.validate_mapping(all_world, mapping)
        self.assertEqual(ER.native_settings(all_world), ER.native_settings(explicit_world))
        self.assertEqual(all_world.options.mixed_entrance_pools.value, {'all'})

    def test_all_and_explicit_keys_do_not_enable_disabled_categories(self):
        world = self.world(shuffle_overworld_entrances=1, shuffle_one_way_entrances=1,
                           mixed_entrance_pools={'all', 'interiors', 'dungeon_doors'})
        self.assertEqual(ER.mixed_categories(world), {'overworld', 'one_ways'})
        mapping = ER._candidate(world)
        ER.validate_mapping(world, mapping)
        self.assertEqual({ER.ENDPOINTS[source]['category'] for source in mapping}, {'overworld', 'one_ways'})
        self.assertTrue({ER.ENDPOINTS[target]['category'] for target in mapping.values()}
                        <= {'overworld', 'one_ways'})
        native = ER.native_settings(world)
        self.assertEqual(native['ShuffleInteriorsEntrances'], 0)
        self.assertEqual(native['ShuffleDungeonDoors'], 0)

    def test_switching_a_toggle_off_removes_it_from_all(self):
        world = self.world(shuffle_overworld_entrances=1, shuffle_interior_entrances=1,
                           mixed_entrance_pools={'all'})
        self.assertEqual(ER.mixed_categories(world), {'overworld', 'interiors'})
        world.options.shuffle_overworld_entrances.value = 0
        self.assertEqual(ER.mixed_categories(world), {'interiors'})
        mapping = ER._candidate(world)
        ER.validate_mapping(world, mapping)
        self.assertEqual({ER.ENDPOINTS[source]['category'] for source in mapping}, {'interiors'})
        self.assertEqual(ER.native_settings(world)['ShuffleOverworldEntrances'], 0)
        self.assertEqual(world.options.mixed_entrance_pools.value, {'all'})

    def test_all_with_every_shuffle_disabled_is_empty(self):
        world = self.world(mixed_entrance_pools={'all'})
        self.assertFalse(ER.enabled(world))
        self.assertEqual(ER.mixed_categories(world), set())
        self.assertEqual(ER._candidate(world), {})
        self.assertEqual(ER.native_settings(world)['MixedEntrances'], 0)

    def test_all_expands_after_legacy_overworld_default_is_restored(self):
        world = self.world(shuffle_overworld_entrances=1, shuffle_interior_entrances=1,
                           mixed_entrance_pools={'all'})
        world.using_ut = True
        world.passthrough = {'entrance_randomizer': {'revision': 1, 'connections': {}},
                             'extreme_all_options': {'shuffle_interior_entrances': 1}}
        ER.restore_legacy_defaults(world)
        self.assertEqual(ER.mixed_categories(world), {'interiors'})
        mapping = ER._candidate(world)
        ER.validate_mapping(world, mapping)
        self.assertEqual({ER.ENDPOINTS[source]['category'] for source in mapping}, {'interiors'})
        self.assertEqual(world.options.mixed_entrance_pools.value, {'all'})


class LegacyGraphReplayTests(unittest.TestCase):
    def test_old_non_overworld_map_replays_with_new_local_toggle_enabled(self):
        multiworld = setup_multiworld(SohExtremeWorld, steps=(), seed=1802, options={
            'shuffle_overworld_entrances': 1, 'shuffle_interior_entrances': 1, 'shuffle_child_spawn': 1,
            'mixed_entrance_pools': {'all'},
        })
        world = multiworld.worlds[1]
        old_rows = [row for row in ER.CATALOG if row['category'] == 'interiors']
        mapping = {row['id']: row['id'] for row in old_rows}
        mapping[187] = 626  # An older seed may legitimately start at Link's House.
        primary = [row['id'] for row in old_rows if row['primary']]
        exchange_pairs(mapping, primary[0], primary[1])
        multiworld.re_gen_passthrough = {'SOH-EXTREME': {
            'extreme_all_options': {'shuffle_interior_entrances': 1, 'shuffle_child_spawn': 1,
                                    'mixed_entrance_pools': ['interiors', 'child_spawn']},
            'entrance_randomizer': {'revision': 1, 'connections': {str(k): v for k, v in mapping.items()}},
        }}
        for step in ('generate_early', 'create_regions', 'create_items', 'set_rules'):
            call_all(multiworld, step)
        self.assertTrue(world.using_ut)
        self.assertFalse(world.options.shuffle_overworld_entrances.value)
        rng_before = world.random.getstate()
        ER.connect(world)
        self.assertEqual(world._er_mapping, mapping)
        self.assertEqual(world.random.getstate(), rng_before)
        self.assertFalse({row['id'] for row in ER.CATALOG if row['category'] == 'overworld'}
                         & shuffled_edges(world).keys())


class AlternateSpawnTests(unittest.TestCase):
    def world(self, **options):
        return setup_multiworld(SohExtremeWorld, steps=(), seed=1802, options=options).worlds[1]

    def test_child_and_adult_home_aliases_are_all_default_destinations(self):
        for source, defaults in ((187, (187, 626)), (642, (642, 83, 1524))):
            for target in defaults:
                self.assertTrue(ER._is_default_spawn(ER.ENDPOINTS[source], target))
            self.assertFalse(ER._is_default_spawn(ER.ENDPOINTS[source], 1119))

    def test_all_with_only_one_spawn_enabled_has_no_alternate_pool(self):
        for option in ('shuffle_child_spawn', 'shuffle_adult_spawn'):
            world = self.world(**{option: 1}, mixed_entrance_pools={'all'})
            with self.assertRaisesRegex(OptionError, 'No alternate .* spawn destination'):
                ER._validate_spawn_pools(world, ER._eligible(world))
            self.assertEqual(ER.enabled_categories(world), {option.removeprefix('shuffle_')})

    def test_separate_spawn_pool_has_normal_overworld_alternatives(self):
        world = self.world(shuffle_child_spawn=1)
        ER._validate_spawn_pools(world, ER._eligible(world))
        result = ER._place_one_way(world, {187: 187}, ER.ENDPOINTS[187], lambda mapping: True)
        self.assertFalse(ER._is_default_spawn(ER.ENDPOINTS[187], result[187]))
        ER.validate_mapping(world, result)

    def test_default_aliases_are_skipped_before_a_viable_alternate_is_accepted(self):
        for source, defaults in ((187, (187, 626)), (642, (642, 83, 1524))):
            option = 'shuffle_' + ER.ENDPOINTS[source]['category']
            world = self.world(**{option: 1}, shuffle_interior_entrances=1, shuffle_warp_songs=1,
                               mixed_entrance_pools={'all'})
            checked = []
            def viable(mapping):
                checked.append(mapping[source])
                return True
            targets = [ER.ENDPOINTS[target] for target in (*defaults, 1119)]
            with patch.object(ER, '_one_way_targets', return_value=targets):
                result = ER._place_one_way(world, {source: source}, ER.ENDPOINTS[source], viable)
            self.assertEqual(result[source], 1119)
            self.assertEqual(checked, [1119])

    def test_no_viable_alternate_fails_instead_of_leaving_identity(self):
        world = self.world(shuffle_child_spawn=1)
        original = {187: 187}
        with patch.object(ER, '_one_way_targets', return_value=[ER.ENDPOINTS[333]]):
            with self.assertRaisesRegex(OptionError, 'No playable alternate child spawn.*all 1 allowed'):
                ER._place_one_way(world, original, ER.ENDPOINTS[187], lambda mapping: False)
        self.assertEqual(original, {187: 187})

    def test_fixed_seed_produces_the_same_nondefault_spawn_and_rng_state(self):
        options = {option: 1 for option in ER.CATEGORIES.values()}
        first = self.world(**options, mixed_entrance_pools={'all'})
        second = self.world(**options, mixed_entrance_pools={'all'})
        identity = {row['id']: row['id'] for row in ER._eligible(first)}
        left = ER._place_one_way(first, identity, ER.ENDPOINTS[187], lambda mapping: True)
        right = ER._place_one_way(second, identity, ER.ENDPOINTS[187], lambda mapping: True)
        self.assertEqual(left, right)
        self.assertFalse(ER._is_default_spawn(ER.ENDPOINTS[187], left[187]))
        self.assertEqual(first.random.getstate(), second.random.getstate())

    def test_only_playable_destination_after_fifty_is_found_without_repeated_probes(self):
        options = {option: 1 for option in ER.CATEGORIES.values()}
        world = self.world(**options, mixed_entrance_pools={'all'})
        source = ER.ENDPOINTS[187]
        allowed = [target['id'] for target in ER._one_way_targets(world, source)
                   if not ER._is_default_spawn(source, target['id'])]
        self.assertGreater(len(allowed), 50)
        checked = []
        original = {row['id']: row['id'] for row in ER._eligible(world)}
        def viable(mapping):
            checked.append(mapping[187])
            return mapping[187] == allowed[-1]
        with patch.object(world.random, 'shuffle', side_effect=lambda values: None), \
                patch.object(ER, '_candidate', side_effect=AssertionError('Unrelated mapping generated')):
            result = ER._place_one_way(world, original, source, viable)
        self.assertEqual(checked, allowed)
        self.assertEqual(len(checked), len(set(checked)))
        self.assertEqual(result[187], allowed[-1])
        self.assertEqual(original[187], 187)
        ER.validate_mapping(world, result)

    def test_exhausted_pool_checks_every_unique_nonhome_destination(self):
        world = self.world(shuffle_child_spawn=1, shuffle_interior_entrances=1,
                           mixed_entrance_pools={'all'})
        source = ER.ENDPOINTS[187]
        targets = [ER.ENDPOINTS[target] for target in (187, 626, 126, 1119, 126)]
        checked = []
        def viable(mapping):
            checked.append(mapping[187])
            return False
        with patch.object(ER, '_one_way_targets', return_value=targets):
            with self.assertRaisesRegex(OptionError, 'all 2 allowed destinations'):
                ER._place_one_way(world, {187: 187}, source, viable)
        self.assertCountEqual(checked, [126, 1119])
        self.assertEqual(len(checked), 2)

    def test_optional_base_topology_probe_can_fail_without_accepting_home(self):
        world = self.world(shuffle_child_spawn=1)
        original = {187: 187}
        checked = []
        def viable(mapping):
            checked.append(mapping[187])
            return False
        with patch.object(ER, '_one_way_targets', return_value=[ER.ENDPOINTS[333]]):
            result = ER._place_one_way(world, original, ER.ENDPOINTS[187], viable, allow_failure=True)
        self.assertIsNone(result)
        self.assertEqual(checked, [333])
        self.assertEqual(original, {187: 187})

    def test_nonspawn_one_way_preserves_existing_route_when_no_target_is_viable(self):
        world = self.world(shuffle_owl_drops=1)
        original = {638: 638, 1364: 1364}
        with patch.object(ER, '_one_way_targets', return_value=[ER.ENDPOINTS[333]]):
            result = ER._place_one_way(world, original, ER.ENDPOINTS[638], lambda mapping: False)
        self.assertIsNone(result)
        self.assertEqual(original, {638: 638, 1364: 1364})


if __name__ == '__main__':
    unittest.main(verbosity=2)
