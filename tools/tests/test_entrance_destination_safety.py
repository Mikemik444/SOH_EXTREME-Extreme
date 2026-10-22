"""Destination policy and age regressions using the real AP/SoH region graph.

Run with the supported Archipelago runtime and this source world on PYTHONPATH.
The small graphs isolate physical entrances; they do not simulate native scene
geometry or claim that a compiled game was launched.
"""
from copy import deepcopy
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
from worlds.soh_extreme import SohExtremeWorld
from worlds.soh_extreme import EntranceRandomizer as ER
from worlds.soh_extreme import EntranceSafety as Safety
from worlds.soh_extreme._vendor_oot_soh.Enums import Ages, Events, Items, Regions
from worlds.soh_extreme._vendor_oot_soh.Locations import SohLocation
from worlds.soh_extreme._vendor_oot_soh.Regions import SohRegion


class DestinationPolicyTests(unittest.TestCase):
    def test_every_catalog_endpoint_has_reviewed_normal_layers(self):
        Safety.validate_catalog(ER.CATALOG)
        self.assertEqual(len(ER.CATALOG), 721)
        self.assertEqual(set(Safety.POLICIES), set(ER.ENDPOINTS))
        for row in ER.CATALOG:
            with self.subTest(endpoint=row['id']):
                policy = Safety.POLICIES[row['id']]
                self.assertEqual(len(policy['normal_layers']), 4)
                self.assertIn(policy['source_age_mask'], (1, 2, 3))
                self.assertIn(policy['arrival_age_mask'], (1, 2, 3))
                self.assertTrue(Safety.allowed_route(row['id'], row['id']))

    def test_age_masks_are_explicit_and_only_grounded_arrivals_are_restricted(self):
        self.assertEqual((Safety.CHILD, Safety.ADULT, Safety.BOTH), (1, 2, 3))
        self.assertEqual({key: Safety.arrival_age_mask(key) for key in Safety.POLICIES
                          if Safety.arrival_age_mask(key) != Safety.BOTH},
                         {781: Safety.ADULT, 832: Safety.CHILD, 1000: Safety.ADULT, 2060: Safety.CHILD})
        self.assertEqual({key: Safety.source_age_mask(key) for key in Safety.POLICIES
                          if Safety.source_age_mask(key) != Safety.BOTH},
                         {187: Safety.CHILD, 638: Safety.CHILD,
                          642: Safety.ADULT, 781: Safety.ADULT, 1364: Safety.CHILD})
        for endpoint in (832, 1000, 2060):
            # Mixing can place either age inside the shared return scene.
            # Its original exterior approach does not constrain the return actor.
            self.assertEqual(Safety.source_age_mask(endpoint), Safety.BOTH)

    def test_hard_spawn_and_owl_age_conflicts_are_rejected(self):
        self.assertFalse(Safety.allowed_route(642, 832))
        self.assertFalse(Safety.allowed_route(642, 2060))
        for child_source in (187, 638, 1364):
            self.assertFalse(Safety.allowed_route(child_source, 1000))
            self.assertTrue(Safety.allowed_route(child_source, 832))
        self.assertTrue(Safety.allowed_route(642, 1000))
        self.assertFalse(Safety.allowed_age(832, Safety.ADULT))
        self.assertFalse(Safety.allowed_age(1000, Safety.CHILD))
        self.assertFalse(Safety.allowed_age(832, Safety.BOTH))

    def test_unknown_and_non_concrete_ages_are_rejected(self):
        for endpoint in (-1, 2147483647):
            self.assertEqual(Safety.source_age_mask(endpoint), 0)
            self.assertEqual(Safety.arrival_age_mask(endpoint), 0)
            self.assertFalse(Safety.allowed_route(187, endpoint))
            self.assertFalse(Safety.allowed_route(endpoint, 187))
            self.assertFalse(Safety.allowed_age(endpoint, Safety.CHILD))
        for age in (-1, 0, 3, 4):
            self.assertFalse(Safety.allowed_age(12, age))

    def test_dungeon_boss_door_and_warp_arrivals_keep_both_ages(self):
        categories = {'dungeons', 'bosses', 'dungeon_doors', 'blue_warps', 'warp_songs'}
        for row in ER.CATALOG:
            if row['category'] not in categories:
                continue
            with self.subTest(endpoint=row['id'], category=row['category']):
                self.assertEqual(Safety.arrival_age_mask(row['id']), Safety.BOTH)
                self.assertTrue(Safety.allowed_route(187, row['id']))
                self.assertTrue(Safety.allowed_route(642, row['id']))

    def test_unreviewed_cutscene_layer_catalog_id_is_rejected(self):
        catalog = deepcopy(list(ER.CATALOG))
        row = next(row for row in catalog if row['id'] == 12)
        row['id'] = 20
        with self.assertRaises(OptionError):
            Safety.validate_catalog(catalog)

    def test_changed_scene_anchor_and_room_metadata_are_rejected(self):
        for endpoint, key, value in ((12, 'scene', 108), (12, 'scene', 110),
                                     (4096, 'anchor', 20), (4096, 'room', 127)):
            catalog = deepcopy(list(ER.CATALOG))
            # The first physical door supplies the representative room/anchor
            # row independently of its generated numeric endpoint.
            row = (next(row for row in catalog if row['door'] >= 0) if endpoint == 4096 else
                   next(row for row in catalog if row['id'] == endpoint))
            with self.subTest(endpoint=row['id'], key=key):
                row[key] = value
                with self.assertRaises(OptionError):
                    Safety.validate_catalog(catalog)

    def test_missing_duplicate_and_unreviewed_endpoints_are_rejected(self):
        duplicate = deepcopy(list(ER.CATALOG))
        duplicate.append(deepcopy(duplicate[0]))
        unreviewed = deepcopy(list(ER.CATALOG))
        new_row = deepcopy(unreviewed[0])
        new_row['id'] = 2147483647
        unreviewed.append(new_row)
        for catalog in (ER.CATALOG[:-1], duplicate, unreviewed):
            with self.subTest(size=len(catalog)):
                with self.assertRaises(OptionError):
                    Safety.validate_catalog(catalog)

    def test_malformed_policy_is_rejected(self):
        mutations = {
            'revision': lambda p: p.update(revision=Safety.POLICY_REVISION + 1),
            'missing_row': lambda p: p['endpoints'].pop(),
            'duplicate_row': lambda p: p['endpoints'].append(deepcopy(p['endpoints'][0])),
            'source_mask': lambda p: p['endpoints'][0].update(source_age_mask=0),
            'arrival_mask': lambda p: p['endpoints'][0].update(arrival_age_mask=4),
            'boolean_mask': lambda p: p['endpoints'][0].update(arrival_age_mask=True),
            'missing_layer': lambda p: p['endpoints'][0]['normal_layers'].pop(),
            'debug_scene': lambda p: p['endpoints'][0]['normal_layers'][0].update(scene=108),
            'unused_scene': lambda p: p['endpoints'][0]['normal_layers'][0].update(scene=110),
            'negative_spawn': lambda p: p['endpoints'][0]['normal_layers'][0].update(spawn=-1),
            'boolean_spawn': lambda p: p['endpoints'][0]['normal_layers'][0].update(spawn=True),
            'negative_index': lambda p: p['endpoints'][0].update(native_index=-1),
            'unknown_kind': lambda p: p['endpoints'][0].update(kind='cutscene'),
        }
        for name, mutate in mutations.items():
            with self.subTest(mutation=name):
                policy = deepcopy(Safety.POLICY)
                mutate(policy)
                with self.assertRaises(OptionError):
                    Safety.validate_catalog(ER.CATALOG, policy)

    def test_policy_native_base_cannot_be_changed_to_cutscene_layer(self):
        policy = deepcopy(Safety.POLICY)
        row = next(row for row in policy['endpoints'] if row['id'] == 12)
        row['native_index'] = 20
        with self.assertRaises(OptionError):
            Safety.validate_catalog(ER.CATALOG, policy)

    def test_one_way_targets_apply_known_source_age_before_placement(self):
        options = {key: 1 for key in ER.ENTRANCE_OPTIONS if key != 'mixed_entrance_pools'}
        options['mixed_entrance_pools'] = {'all'}
        world = setup_multiworld(SohExtremeWorld, steps=(), seed=187, options=options).worlds[1]
        for source in (187, 642, 638, 1364):
            targets = ER._one_way_targets(world, ER.ENDPOINTS[source])
            self.assertTrue(targets)
            self.assertTrue(all(Safety.allowed_route(source, target['id']) for target in targets))

        # Exercise a hard arrival restriction on an otherwise eligible one-way
        # destination, independent of the catalog's dynamic shared-room rules.
        policies = deepcopy(Safety.POLICIES)
        policies[1400]['arrival_age_mask'] = Safety.CHILD
        with patch.object(Safety, 'POLICIES', policies):
            child_targets = {row['id'] for row in ER._one_way_targets(world, ER.ENDPOINTS[187])}
            adult_targets = {row['id'] for row in ER._one_way_targets(world, ER.ENDPOINTS[642])}
        self.assertIn(1400, child_targets)
        self.assertNotIn(1400, adult_targets)


class DestinationAgeGraphTests(unittest.TestCase):
    def setUp(self):
        self.multiworld = setup_multiworld(SohExtremeWorld, steps=(), seed=187, options={
            'starting_age': 'child', 'shuffle_child_spawn': 1, 'shuffle_adult_spawn': 1,
            'shuffle_interior_entrances': 0, 'shuffle_grotto_entrances': 0,
            'mixed_entrance_pools': {'all'},
        })
        self.world = self.multiworld.worlds[1]
        names = {str(Regions.ROOT)}
        for row in ER.CATALOG:
            names.update((ER.region_name(row['source']), ER.region_name(row['target'])))
        self.regions = {}
        for name in sorted(names):
            region = SohRegion(name, 1, self.multiworld)
            self.multiworld.regions.append(region)
            self.regions[name] = region
        self.root = self.regions[str(Regions.ROOT)]
        self.edges = {}
        self.physical = {}
        self.mapping = {}
        # Disabled pools still contain physical identity returns. The validator
        # must discover these original source edges without a shuffled entry.
        for endpoint in (781, 832, 1000, 2060):
            self.route(endpoint, endpoint, exposed=False)

    def region_for(self, endpoint, side):
        return self.regions[ER.region_name(ER.ENDPOINTS[endpoint][side])]

    def approach(self, endpoint, age=None, rule=None):
        edge = self.root.create_exit(f'Test approach {endpoint} {len(self.root.exits)}')
        edge.access_rule = rule or (lambda state: age is None or state._soh_extreme_age[1] == age)
        edge.connect(self.region_for(endpoint, 'source'))
        return edge

    def route(self, source, target, rule=lambda state: True, exposed=True):
        edge = self.physical.get(source)
        if edge is None:
            edge = self.region_for(source, 'source').create_exit(f'Test physical source {source}')
            self.physical[source] = edge
        elif edge.connected_region is not None:
            edge.connected_region.entrances.remove(edge)
        edge.access_rule = rule
        edge.connect(self.region_for(target, 'target'))
        if exposed:
            self.edges[source] = edge
            self.mapping[source] = target
        return edge

    def spawn(self, source, target):
        age = Ages.CHILD if source == 187 else Ages.ADULT
        self.approach(source, age)
        return self.route(source, target)

    def state(self, *items):
        state = CollectionState(self.multiworld)
        for name in items:
            state.collect(Item(name, ItemClassification.progression, 123, 1), True)
        state.sweep_for_advancements()
        return state

    def safe(self, state=None):
        return ER._age_routes_are_safe(self.world, self.mapping, self.edges,
                                       self.state() if state is None else state)

    def can_reach_as(self, state, region, age):
        previous = state._soh_extreme_age[1]
        try:
            state._soh_extreme_age[1] = age
            return region.can_reach(state)
        finally:
            state._soh_extreme_age[1] = previous

    def test_vanilla_age_specific_identity_exits_are_valid(self):
        for endpoint, age in ((832, Ages.CHILD), (1000, Ages.ADULT), (2060, Ages.CHILD)):
            self.approach(endpoint, age)
        self.assertTrue(self.safe())

    def test_adult_spawn_into_hc_fairy_rejects_unshuffled_wrong_age_return(self):
        self.spawn(642, 1400)
        self.assertNotIn(832, self.mapping)
        self.assertFalse(self.world.options.shuffle_interior_entrances.value)
        self.assertFalse(self.safe())

    def test_child_spawn_into_ogc_fairy_rejects_unshuffled_wrong_age_return(self):
        self.spawn(187, 1218)
        self.assertNotIn(1000, self.mapping)
        self.assertFalse(self.safe())

    def test_adult_spawn_into_hc_storms_rejects_unshuffled_wrong_age_return(self):
        self.spawn(642, 1804)
        self.assertNotIn(2060, self.mapping)
        self.assertFalse(self.world.options.shuffle_grotto_entrances.value)
        self.assertFalse(self.safe())

    def test_correct_age_can_use_the_same_interior_arrival(self):
        self.spawn(187, 1400)
        self.spawn(642, 1218)
        self.assertTrue(self.safe())

    def test_rejection_does_not_add_fake_destination_or_return_age_gates(self):
        self.spawn(642, 1400)
        state = self.state()
        outside = self.region_for(832, 'target')
        physical_rule = self.physical[832].access_rule
        self.assertTrue(self.can_reach_as(state, outside, Ages.ADULT))
        self.assertFalse(self.safe(state))
        self.assertIs(self.physical[832].access_rule, physical_rule)
        self.assertTrue(self.can_reach_as(state, outside, Ages.ADULT))

    def test_rerouted_shared_interior_can_safely_be_used_by_both_ages(self):
        self.spawn(642, 1400)
        self.spawn(187, 1400)
        self.route(832, 529)
        self.assertTrue(self.safe())

    def test_mapped_child_only_destination_rejects_both_age_source(self):
        self.approach(529)
        self.route(529, 832)
        self.assertFalse(self.safe())

    def test_original_source_age_predicate_is_honored(self):
        self.approach(529)
        self.route(529, 832, lambda state: state._soh_extreme_age[1] == Ages.CHILD)
        self.assertTrue(self.safe())

    def test_blue_warp_physical_return_is_included(self):
        self.approach(1544, Ages.ADULT)
        self.route(1544, 832)
        self.assertFalse(self.safe())

    def test_warp_song_and_one_way_sources_are_included(self):
        for source in (1536, 537):
            with self.subTest(source=source):
                self.approach(source, Ages.ADULT)
                self.route(source, 832)
                self.assertFalse(self.safe())

    def test_full_inventory_exposes_a_later_wrong_age_path(self):
        self.approach(832, rule=lambda state: state._soh_extreme_age[1] == Ages.ADULT
                      and state.has('Climb', 1))
        self.assertTrue(self.safe(self.state()))
        self.assertFalse(self.safe(self.state('Climb')))

    def test_each_age_is_checked_and_callers_context_is_restored(self):
        self.spawn(642, 1400)
        for current_age in (Ages.null, Ages.CHILD, Ages.ADULT):
            with self.subTest(current_age=current_age):
                state = self.state()
                state._soh_extreme_age[1] = current_age
                self.assertFalse(self.safe(state))
                self.assertEqual(state._soh_extreme_age[1], current_age)

    def test_returning_to_a_safe_candidate_uses_a_fresh_state(self):
        self.spawn(642, 1400)
        self.assertFalse(self.safe())
        self.route(642, 626)
        self.assertTrue(self.safe())
        self.route(642, 1400)
        self.assertFalse(self.safe())

    def test_both_ages_can_still_reach_an_ordinary_mixed_boss(self):
        self.spawn(187, 12)
        self.spawn(642, 12)
        self.assertTrue(self.safe())
        state = self.state()
        boss = self.region_for(12, 'target')
        self.assertTrue(self.can_reach_as(state, boss, Ages.CHILD))
        self.assertTrue(self.can_reach_as(state, boss, Ages.ADULT))


class OppositeAgeSpawnTests(unittest.TestCase):
    """A viable selected age must not conceal the other save/spawn's trap."""
    def setUp(self):
        self.multiworld = setup_multiworld(SohExtremeWorld, steps=(), seed=187, options={
            'starting_age': 'child', 'shuffle_child_spawn': 1, 'shuffle_adult_spawn': 1,
            'shuffle_interior_entrances': 1, 'shuffle_swim': 1,
            'mixed_entrance_pools': {'all'},
        })
        self.world = self.multiworld.worlds[1]
        names = {str(Regions.ROOT), str(Regions.KOKIRI_FOREST), str(Regions.HYRULE_FIELD)}
        for endpoint in (187, 642, 626, 529, 769, 1031):
            row = ER.ENDPOINTS[endpoint]
            names.update((ER.region_name(row['source']), ER.region_name(row['target'])))
        self.regions = {}
        for name in sorted(names):
            region = SohRegion(name, 1, self.multiworld)
            self.multiworld.regions.append(region)
            self.regions[name] = region
        root = self.regions[str(Regions.ROOT)]
        self.house = self.regions[str(Regions.KF_LINKS_HOUSE)]
        self.forest = self.regions[str(Regions.KOKIRI_FOREST)]
        self.field = self.regions[str(Regions.HYRULE_FIELD)]
        self.spawn_edges = {}
        for endpoint, age in ((187, Ages.CHILD), (642, Ages.ADULT)):
            row = ER.ENDPOINTS[endpoint]
            spawn = self.regions[ER.region_name(row['source'])]
            approach = root.create_exit(f'Test root to {age} spawn')
            approach.access_rule = lambda state, age=age: (
                state._soh_extreme_age[1] == age and
                (age == Ages.CHILD or state.has(str(Events.TIME_TRAVEL), 1)))
            approach.connect(spawn)
            edge = spawn.create_exit(f'Test {age} physical spawn')
            edge.connect(self.house)
            self.spawn_edges[endpoint] = edge
        self.return_edge = self.house.create_exit('Test both-age house return')
        self.return_edge.connect(self.forest)
        self.field_edge = self.forest.create_exit('Test physical field route')
        self.field_edge.connect(self.field)
        self.check = SohLocation(1, 'Test real starting check', 12345100, self.house)
        self.house.locations.append(self.check)
        self.mapping = {187: 626, 642: 626}
        self.edges = {529: self.return_edge}

    def viable(self):
        return ER._starting_state_is_viable(self.world, self.mapping, self.edges, [self.check])

    def grant(self, name):
        self.multiworld.push_precollected(Item(name, ItemClassification.progression, 123, 1))

    def test_safe_other_age_is_tested_without_granting_real_time_travel(self):
        before = list(self.multiworld.precollected_items[1])
        self.assertFalse(CollectionState(self.multiworld).has(str(Events.TIME_TRAVEL), 1))
        self.assertTrue(self.viable())
        self.assertEqual(self.multiworld.precollected_items[1], before)
        self.assertFalse(CollectionState(self.multiworld).has(str(Events.TIME_TRAVEL), 1))
        self.assertEqual(self.world.options.starting_age.current_key, 'child')

    def test_child_start_does_not_certify_adult_barinade_spawn_without_return(self):
        self.mapping[642] = 769
        edge = self.spawn_edges[642]
        edge.connected_region.entrances.remove(edge)
        edge.connect(self.regions[ER.region_name(ER.ENDPOINTS[769]['target'])])
        self.assertFalse(self.viable())

    def test_other_age_reverse_gate_is_checked_at_its_own_age(self):
        self.return_edge.access_rule = lambda state: state._soh_extreme_age[1] == Ages.CHILD
        self.assertFalse(self.viable())

    def test_other_age_locked_reverse_needs_actual_starting_inventory(self):
        self.return_edge.access_rule = lambda state: (state._soh_extreme_age[1] == Ages.CHILD
                                                     or state.has('Climb', 1))
        self.assertFalse(self.viable())
        self.grant('Climb')
        self.assertTrue(self.viable())

    def test_future_full_inventory_does_not_certify_other_age_start(self):
        self.return_edge.access_rule = lambda state: (state._soh_extreme_age[1] == Ages.CHILD
                                                     or state.has('Climb', 1))
        self.multiworld.itempool.append(Item('Climb', ItemClassification.progression, 123, 1))
        full = self.multiworld.get_all_state(False, perform_sweep=False)
        self.assertTrue(full.has('Climb', 1))
        self.assertFalse(self.viable())

    def test_local_prefilled_other_age_key_can_open_its_return(self):
        self.return_edge.access_rule = lambda state: (state._soh_extreme_age[1] == Ages.CHILD
                                                     or state.has('Climb', 1))
        key = SohLocation(1, 'Test adult-only local return key', 12345101, self.house)
        key.access_rule = lambda state: state._soh_extreme_age[1] == Ages.ADULT
        key.place_locked_item(Item('Climb', ItemClassification.progression, 123, 1))
        self.house.locations.append(key)
        self.assertTrue(self.viable())
        self.assertFalse(CollectionState(self.multiworld).has('Climb', 1))

    def test_other_age_needs_its_own_physical_field_route(self):
        self.field_edge.access_rule = lambda state: state._soh_extreme_age[1] == Ages.CHILD
        self.assertFalse(self.viable())

    def test_disabled_other_age_spawn_keeps_existing_vanilla_start_policy(self):
        self.world.options.shuffle_adult_spawn.value = 0
        del self.mapping[642]
        self.return_edge.access_rule = lambda state: state._soh_extreme_age[1] == Ages.CHILD
        self.assertTrue(self.viable())

    def test_other_age_physical_probe_cannot_escape_only_by_ocarina(self):
        instrument = str(Items.PROGRESSIVE_OCARINA)
        self.field_edge.access_rule = lambda state: state._soh_extreme_age[1] == Ages.CHILD
        warp = self.regions[str(Regions.ROOT)].create_exit('Test adult instrument warp')
        warp.access_rule = lambda state: state._soh_extreme_age[1] == Ages.ADULT and state.has(instrument, 1)
        warp.connect(self.field)
        refill = SohLocation(1, 'Test adult prefilled instrument', 12345102, self.house)
        refill.access_rule = lambda state: state._soh_extreme_age[1] == Ages.ADULT
        refill.place_locked_item(Item(instrument, ItemClassification.progression, 123, 1))
        self.house.locations.append(refill)
        inventory = CollectionState(self.multiworld)
        inventory.collect(Item(instrument, ItemClassification.progression, 123, 1), True)
        before = deepcopy(inventory.prog_items)
        self.assertTrue(ER._physical_start_is_connected(self.world, inventory, Ages.CHILD))
        self.assertFalse(ER._physical_start_is_connected(self.world, inventory, Ages.ADULT))
        self.assertEqual(inventory.prog_items, before)
        self.assertFalse(inventory.has(str(Events.TIME_TRAVEL), 1))
        self.field_edge.access_rule = lambda state: True
        self.assertTrue(ER._physical_start_is_connected(self.world, inventory, Ages.ADULT))
        self.assertEqual(inventory.prog_items, before)


if __name__ == '__main__':
    unittest.main(verbosity=2)
