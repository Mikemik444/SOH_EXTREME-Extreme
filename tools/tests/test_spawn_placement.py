"""Exercise spawn placement order and fallback through the real AP/SoH graph.

Run with Archipelago 0.6.7 source and dependencies on PYTHONPATH. These tests
run the production connect pipeline and rule/state evaluations. Instrumentation
observes its phases; only the explicitly named failure tests inject failures.
No item fill or native game execution is implied by this suite.
"""
import unittest
from unittest.mock import patch

import ModuleUpdate
ModuleUpdate.update_ran = True
import settings
settings.no_gui = True
settings.skip_autosave = True

from Options import OptionError
from BaseClasses import CollectionState, Item, ItemClassification
from test.general import setup_multiworld
from worlds.soh_extreme import SohExtremeWorld
from worlds.soh_extreme import EntranceRandomizer as ER
from worlds.soh_extreme._vendor_oot_soh.Enums import Ages, Regions
from worlds.soh_extreme._vendor_oot_soh.Locations import SohLocation
from worlds.soh_extreme._vendor_oot_soh.Regions import SohRegion


SPAWN_IDS = (187, 642)
STEPS = ('generate_early', 'create_regions', 'create_items', 'set_rules')


def shuffled_edges(world):
    prefix = 'EXTREME Shuffled Entrance '
    return {int(edge.name.removeprefix(prefix)): edge
            for region in world.get_regions() for edge in region.exits
            if edge.name.startswith(prefix)}


def actual_starting_state(world):
    state = CollectionState(world.multiworld)
    state.sweep_for_advancements(locations=[
        loc for loc in world.get_locations()
        if loc.item is not None and loc.item.player == world.player
    ])
    return state


class SpawnPlacementPipelineTests(unittest.TestCase):
    def make_world(self, age='child', seed=183, **changes):
        options = {
            'starting_age': age,
            'shuffle_overworld_entrances': 1,
            'shuffle_child_spawn': 1,
            'shuffle_adult_spawn': 1,
            'shuffle_owl_drops': 1,
            'mixed_entrance_pools': {'all'},
            'scene_transition_checks': 1,
            'shuffle_swim': 1,
        }
        options.update(changes)
        world = setup_multiworld(SohExtremeWorld, steps=STEPS, seed=seed,
                                 options=options).worlds[1]
        self.assertEqual(world.options.starting_age.current_key, age)
        return world

    def assert_playable_mapping(self, world, required):
        mapping = world._er_mapping
        ER.validate_mapping(world, mapping)
        for source in SPAWN_IDS:
            self.assertFalse(ER._is_default_spawn(ER.ENDPOINTS[source], mapping[source]))
        for source, target in mapping.items():
            reverse = ER.ENDPOINTS[source]['reverse']
            if reverse >= 0:
                self.assertEqual(mapping[ER.ENDPOINTS[target]['reverse']], reverse)
        edges = shuffled_edges(world)
        for source, target in mapping.items():
            if source in edges:
                self.assertEqual(edges[source].connected_region.name,
                                 ER.region_name(ER.ENDPOINTS[target]['target']))
        fill_locations = [loc for loc in world.get_locations()
                          if loc.address is not None and loc.item is None]
        self.assertTrue(ER._starting_state_is_viable(world, mapping, edges, fill_locations))
        self.assertTrue(ER._reachable_at_starting_age(
            world, actual_starting_state(world), world.get_region(str(Regions.HYRULE_FIELD))))
        inventory = world.multiworld.get_all_state(False, perform_sweep=False)
        self.assertTrue(ER._physical_start_is_connected(world, inventory))
        completed = world.multiworld.get_all_state(False)
        missing = [loc.name for loc in required if not loc.can_reach(completed)]
        self.assertEqual(missing, [])

    @staticmethod
    def originally_reachable(world):
        baseline = world.multiworld.get_all_state(False)
        return [loc for loc in world.get_locations()
                if loc.address is not None and loc.can_reach(baseline)]

    def test_both_ages_choose_spawns_before_protecting_them_in_every_pair_probe(self):
        for age in ('child', 'adult'):
            with self.subTest(age=age):
                world = self.make_world(age)
                required = self.originally_reachable(world)
                original_spawns = ER._place_spawns
                original_one_way = ER._place_one_way
                original_start = ER._starting_state_is_viable
                selected = {}
                phase = 'before_spawns'
                spawn_order = []
                pair_probes = 0
                nonspawn_sources = []
                spawn_calls = 0
                accepted_pair_probes = 0
                initial_pool = tuple(map(id, world.multiworld.itempool))
                initial_precollected = tuple(map(id, world.multiworld.precollected_items[1]))
                initial_state = world.multiworld.state.prog_items[1].copy()

                def observe_spawns(current_world, mapping, rows, viable, *, allow_failure=False):
                    nonlocal phase, spawn_calls
                    spawn_calls += 1
                    self.assertEqual(phase, 'before_spawns')
                    self.assertTrue(all(source == target for source, target in mapping.items()))
                    phase = 'spawns'
                    result = original_spawns(current_world, mapping, rows, viable,
                                             allow_failure=allow_failure)
                    self.assertIsNotNone(result)
                    selected.update((source, result[source]) for source in SPAWN_IDS)
                    for source in SPAWN_IDS:
                        self.assertFalse(ER._is_default_spawn(ER.ENDPOINTS[source], result[source]))
                    phase = 'pairs'
                    return result

                def observe_one_way(current_world, mapping, source, viable, *, allow_failure=False):
                    nonlocal phase
                    if source['id'] in SPAWN_IDS:
                        self.assertEqual(phase, 'spawns')
                        spawn_order.append(source['id'])
                    else:
                        self.assertGreater(pair_probes, 0)
                        self.assertTrue(selected)
                        for spawn, target in selected.items():
                            self.assertEqual(mapping[spawn], target)
                        nonspawn_sources.append(source['id'])
                        phase = 'nonspawn'
                    return original_one_way(current_world, mapping, source, viable,
                                            allow_failure=allow_failure)

                def observe_start(current_world, mapping, edges, fill_locations):
                    nonlocal pair_probes, accepted_pair_probes
                    self.assertNotEqual(phase, 'before_spawns')
                    if phase in ('pairs', 'nonspawn'):
                        for source, target in selected.items():
                            self.assertEqual(mapping[source], target)
                        ER.validate_mapping(current_world, mapping)
                        if phase == 'pairs':
                            pair_probes += 1
                    result = original_start(current_world, mapping, edges, fill_locations)
                    if result:
                        self.assertTrue(ER._reachable_at_starting_age(
                            current_world, actual_starting_state(current_world),
                            current_world.get_region(str(Regions.HYRULE_FIELD))))
                        if phase == 'pairs':
                            accepted_pair_probes += 1
                    return result

                with patch.object(ER, '_place_spawns', side_effect=observe_spawns), \
                     patch.object(ER, '_place_one_way', side_effect=observe_one_way), \
                     patch.object(ER, '_starting_state_is_viable', side_effect=observe_start):
                    ER.connect(world)

                expected_order = [187, 642] if age == 'child' else [642, 187]
                self.assertEqual(spawn_order, expected_order)
                self.assertEqual(spawn_calls, 1)
                self.assertGreater(pair_probes, 0)
                self.assertGreater(accepted_pair_probes, 0)
                self.assertEqual(set(nonspawn_sources), {638, 1364})
                self.assertTrue(any(source != target for source, target in world._er_mapping.items()
                                    if ER.ENDPOINTS[source]['reverse'] >= 0))
                self.assertEqual({source: world._er_mapping[source] for source in SPAWN_IDS}, selected)
                self.assert_playable_mapping(world, required)
                self.assertEqual(tuple(map(id, world.multiworld.itempool)), initial_pool)
                self.assertEqual(tuple(map(id, world.multiworld.precollected_items[1])), initial_precollected)
                self.assertEqual(world.multiworld.state.prog_items[1], initial_state)

    def test_partial_early_search_is_discarded_before_one_bounded_pair_fallback(self):
        world = self.make_world()
        required = self.originally_reachable(world)
        original_spawns = ER._place_spawns
        original_choice = world.random.choice
        original_start = ER._starting_state_is_viable
        calls = []
        discarded = {}
        identity_restored = False
        fallback_pair_probes = 0
        phase = 'initial'

        def observe_spawns(current_world, mapping, rows, viable, *, allow_failure=False):
            nonlocal phase
            calls.append(allow_failure)
            if len(calls) == 1:
                self.assertTrue(allow_failure)
                # Perform a real successful first-age search, then simulate
                # failure to place the second age. Its applied graph must not
                # leak into the fallback's identity starting point.
                child_only = [row for row in rows if row['category'] == 'child_spawn']
                partial = original_spawns(current_world, mapping, child_only, viable,
                                          allow_failure=True)
                self.assertIsNotNone(partial)
                self.assertNotEqual(partial[187], mapping[187])
                self.assertEqual(current_world._er_mapping, partial)
                discarded.update(partial)
                phase = 'before_fallback_pairs'
                return None
            self.assertEqual(len(calls), 2)
            self.assertFalse(allow_failure)
            self.assertTrue(identity_restored)
            self.assertGreater(fallback_pair_probes, 0)
            for source in SPAWN_IDS:
                self.assertEqual(mapping[source], source)
            phase = 'fallback_spawns'
            result = original_spawns(current_world, mapping, rows, viable,
                                     allow_failure=allow_failure)
            self.assertIsNotNone(result)
            phase = 'after_fallback'
            return result

        def observe_choice(pool):
            nonlocal phase, identity_restored
            if phase == 'before_fallback_pairs':
                # The first pair proposal draws its second endpoint only after
                # connect() has restored the accepted base topology.
                self.assertTrue(discarded)
                self.assertTrue(all(source == target for source, target in world._er_mapping.items()))
                for source, edge in shuffled_edges(world).items():
                    self.assertEqual(edge.connected_region.name,
                                     ER.region_name(ER.ENDPOINTS[source]['target']))
                identity_restored = True
                phase = 'fallback_pairs'
            return original_choice(pool)

        def observe_start(current_world, mapping, edges, fill_locations):
            nonlocal fallback_pair_probes
            if phase == 'fallback_pairs':
                fallback_pair_probes += 1
                for source in SPAWN_IDS:
                    self.assertEqual(mapping[source], source)
            return original_start(current_world, mapping, edges, fill_locations)

        with patch.object(ER, '_place_spawns', side_effect=observe_spawns), \
             patch.object(world.random, 'choice', side_effect=observe_choice), \
             patch.object(ER, '_starting_state_is_viable', side_effect=observe_start):
            ER.connect(world)

        self.assertEqual(calls, [True, False])
        self.assertTrue(identity_restored)
        self.assertGreater(fallback_pair_probes, 0)
        self.assert_playable_mapping(world, required)

    def test_failed_fallback_raises_instead_of_accepting_default_spawns(self):
        world = self.make_world(shuffle_overworld_entrances=0, shuffle_owl_drops=0,
                                mixed_entrance_pools=set())
        original_spawns = ER._place_spawns
        calls = []

        def observe_spawns(current_world, mapping, rows, viable, *, allow_failure=False):
            calls.append(allow_failure)
            return original_spawns(current_world, mapping, rows, viable, allow_failure=allow_failure)

        with patch.object(ER, '_place_spawns', side_effect=observe_spawns), \
             patch.object(ER, '_starting_state_is_viable', return_value=False), \
             patch.object(ER, '_physical_start_is_connected',
                          side_effect=AssertionError('Actual-start rejection must run first')) as physical:
            with self.assertRaisesRegex(OptionError, 'No playable alternate child spawn.*all'):
                ER.connect(world)
        physical.assert_not_called()
        self.assertEqual(calls, [True, False])


class StartConnectivityGraph(unittest.TestCase):
    """Small real SoH regions and AP states, with explicit physical edges."""

    def setUp(self):
        self.multiworld = setup_multiworld(SohExtremeWorld, steps=(), seed=183, options={
            'starting_age': 'child', 'shuffle_child_spawn': 1,
        })
        self.world = self.multiworld.worlds[1]
        self.root = self.region(str(Regions.ROOT))
        self.start = self.region('Physical-connectivity test start')
        self.field = self.region(str(Regions.HYRULE_FIELD))
        self.edge(self.root, self.start, 'Selected-age spawn', lambda state:
                  state._soh_extreme_age[1] == (
                      Ages.ADULT if self.world.options.starting_age == 'adult' else Ages.CHILD))
        self.address = 13100000

    def region(self, name):
        result = SohRegion(name, 1, self.multiworld)
        self.multiworld.regions.append(result)
        return result

    @staticmethod
    def edge(source, target, name, rule=lambda state: True):
        result = source.create_exit(name)
        result.access_rule = rule
        result.connect(target)
        return result

    def location(self, name, parent=None, rule=lambda state: True, *, event=False):
        self.address += 1
        result = SohLocation(1, name, None if event else self.address, parent or self.start)
        result.access_rule = rule
        result.parent_region.locations.append(result)
        return result

    @staticmethod
    def item(name):
        return Item(name, ItemClassification.progression, 13110000, 1)

    def inventory(self, *names):
        self.multiworld.itempool.extend(self.item(name) for name in names)
        return self.multiworld.get_all_state(False, perform_sweep=False)

    def add_ocarina_route(self):
        self.edge(self.start, self.field, 'Assumed musical escape',
                  lambda state: state.has('Progressive Ocarina', 1))


class ActualSpawnConnectivityTests(StartConnectivityGraph):
    """An unlocked return and free checks do not prove an actual hub route."""

    def setUp(self):
        super().setUp()
        self.return_region = self.region('Physical-connectivity test return')
        self.return_edge = self.edge(self.start, self.return_region, 'Free physical spawn return')
        self.check = self.location('Free physical starting check')
        self.arrival = next(row for row in ER.CATALOG if row['category'] == 'interiors'
                            and row['reverse'] >= 0 and row['scene'] != 5
                            and all(not ER._is_default_spawn(ER.ENDPOINTS[source], row['id'])
                                    for source in SPAWN_IDS))

    def selected_spawn(self):
        return 642 if self.world.options.starting_age == 'adult' else 187

    def viable(self, mapping=None, checks=None):
        if mapping is None:
            mapping = {self.selected_spawn(): self.arrival['id']}
        return ER._starting_state_is_viable(
            self.world, mapping, {self.arrival['reverse']: self.return_edge},
            [self.check] if checks is None else checks)

    def set_age(self, age):
        self.world.options.starting_age.value = (
            self.world.options.starting_age.option_adult if age == 'adult'
            else self.world.options.starting_age.option_child)

    def test_free_return_and_checks_cannot_use_future_escape_bundle_for_either_age(self):
        self.edge(self.return_region, self.field, 'Escape needs a future three-item bundle', lambda state:
                  state.has('Progressive Hookshot', 1, 2) and state.has('Goron Tunic', 1))
        inventory = self.inventory('Progressive Hookshot', 'Progressive Hookshot', 'Goron Tunic')
        initial_pool = tuple(map(id, self.multiworld.itempool))
        extra_checks = [self.location('Free starting check ' + str(index)) for index in range(2)]
        for age in ('child', 'adult'):
            with self.subTest(age=age):
                self.set_age(age)
                state = CollectionState(self.multiworld)
                self.assertTrue(ER._reachable_at_starting_age(self.world, state, self.return_edge))
                self.assertTrue(all(ER._reachable_at_starting_age(self.world, state, check)
                                    for check in [self.check] + extra_checks))
                self.assertTrue(ER._physical_start_is_connected(self.world, inventory))
                self.assertTrue(ER._reachable_at_starting_age(self.world, inventory.copy(), self.field))
                self.assertFalse(self.viable(checks=[self.check] + extra_checks))
                # Empty fill lists must not skip the actual hub route either.
                self.assertFalse(self.viable(checks=[]))
        self.assertEqual(tuple(map(id, self.multiworld.itempool)), initial_pool)
        self.assertFalse(self.multiworld.precollected_items[1])
        self.assertFalse(self.multiworld.state.prog_items[1])
        self.assertEqual(inventory.count('Progressive Hookshot', 1), 2)
        self.assertEqual(inventory.count('Goron Tunic', 1), 1)

    def test_configured_starting_inventory_opens_the_route_without_extra_grants(self):
        self.edge(self.return_region, self.field, 'Actual starting Crawl route',
                  lambda state: state.has('Crawl', 1))
        self.assertFalse(self.viable())
        starting_item = self.item('Crawl')
        self.multiworld.push_precollected(starting_item)
        initial_state = self.multiworld.state.prog_items[1].copy()
        for age in ('child', 'adult'):
            with self.subTest(age=age):
                self.set_age(age)
                self.assertTrue(self.viable())
                self.assertTrue(self.viable())
        self.assertEqual(self.multiworld.state.prog_items[1], initial_state)
        self.assertEqual(self.multiworld.state.count('Crawl', 1), 1)
        self.assertEqual(len(self.multiworld.precollected_items[1]), 1)
        self.assertIs(self.multiworld.precollected_items[1][0], starting_item)
        self.assertFalse(self.multiworld.itempool)

    def test_reachable_prefill_opens_the_route_but_cannot_survive_a_rejected_candidate(self):
        self.edge(self.return_region, self.field, 'Route requiring a real fixed Crawl reward',
                  lambda state: state.has('Crawl', 1))
        fixed = self.location('Reachable fixed starting Crawl')
        reward = self.item('Crawl')
        fixed.place_locked_item(reward)
        for age in ('child', 'adult'):
            with self.subTest(age=age):
                self.set_age(age)
                fixed.access_rule = lambda state: True
                self.assertTrue(self.viable())
                fixed.access_rule = lambda state: False
                self.assertFalse(self.viable())
                fixed.access_rule = lambda state: True
                self.assertTrue(self.viable())
        self.assertFalse(self.multiworld.state.has('Crawl', 1))
        self.assertFalse(self.multiworld.precollected_items[1])
        self.assertIs(fixed.item, reward)
        self.assertIs(reward.location, fixed)

    def test_other_age_hub_cannot_unlock_selected_age_prefill(self):
        self.edge(self.root, self.field, 'Hub accessible only at the other age', lambda state:
                  state._soh_extreme_age[1] != (
                      Ages.ADULT if self.world.options.starting_age == 'adult' else Ages.CHILD))
        self.edge(self.return_region, self.field, 'Hub via a fixed ability',
                  lambda state: state.has('Crawl', 1))
        fixed = self.location('Ability behind the selected-age escape', self.field)
        fixed.place_locked_item(self.item('Crawl'))
        # Keep the prefill age-specific too. Otherwise an intentionally
        # reachable other-age item would be a real reward rather than a grant.
        fixed.access_rule = lambda state: state._soh_extreme_age[1] == (
            Ages.ADULT if self.world.options.starting_age == 'adult' else Ages.CHILD)
        for age in ('child', 'adult'):
            with self.subTest(age=age):
                self.set_age(age)
                state = CollectionState(self.multiworld)
                self.assertTrue(self.field.can_reach(state))
                self.assertFalse(ER._reachable_at_starting_age(self.world, state, self.field))
                self.assertFalse(self.viable())
                self.assertEqual(state._soh_extreme_age[1], Ages.null)
        self.assertFalse(self.multiworld.state.has('Crawl', 1))

    def test_vanilla_selected_spawn_and_other_age_only_shuffle_keep_prior_start_rules(self):
        for age in ('child', 'adult'):
            with self.subTest(age=age):
                self.set_age(age)
                other_spawn = 187 if self.selected_spawn() == 642 else 642
                self.assertFalse(ER._reachable_at_starting_age(
                    self.world, CollectionState(self.multiworld), self.field))
                self.assertTrue(self.viable(mapping={}))
                self.assertTrue(self.viable(mapping={other_spawn: self.arrival['id']}))
                self.assertFalse(self.viable())
                # All-off and other-age-only maps still need a real free check.
                self.check.access_rule = lambda state: False
                self.assertFalse(self.viable(mapping={}))
                self.assertFalse(self.viable(mapping={other_spawn: self.arrival['id']}))
                self.check.access_rule = lambda state: True

    def test_other_age_water_arrivals_need_swim_even_if_selected_spawn_is_vanilla(self):
        self.edge(self.return_region, self.field, 'Free hub route for the selected age')
        water_targets = [row['id'] for row in ER.CATALOG if row['scene'] == 5]
        self.assertIn(16, water_targets)
        self.assertTrue(any(ER.ENDPOINTS[target]['door'] >= 0 for target in water_targets))
        self.world.options.shuffle_swim.value = 1
        for age in ('child', 'adult'):
            self.set_age(age)
            other_spawn = 187 if self.selected_spawn() == 642 else 642
            for selected_is_mapped in (False, True):
                mapping = {other_spawn: self.arrival['id']}
                if selected_is_mapped:
                    mapping[self.selected_spawn()] = self.arrival['id']
                with self.subTest(age=age, selected_is_mapped=selected_is_mapped, target='dry'):
                    self.assertTrue(self.viable(mapping=mapping))
                for target in water_targets:
                    with self.subTest(age=age, selected_is_mapped=selected_is_mapped, target=target):
                        mapping[other_spawn] = target
                        self.assertFalse(self.viable(mapping=mapping))
                        self.world.options.shuffle_swim.value = 0
                        self.assertTrue(self.viable(mapping=mapping))
                        self.world.options.shuffle_swim.value = 1
                        self.assertFalse(self.viable(mapping=mapping))
        self.assertFalse(self.multiworld.state.has('Swim', 1))
        self.assertFalse(self.multiworld.precollected_items[1])
        self.assertFalse(self.multiworld.itempool)

    def test_actual_first_scale_permits_other_age_water_spawn_without_an_extra_grant(self):
        self.edge(self.return_region, self.field, 'Free hub route for the selected age')
        self.world.options.shuffle_swim.value = 1
        future_scale = self.world.create_item('Progressive Scale')
        self.multiworld.itempool.append(future_scale)
        all_state = self.multiworld.get_all_state(False, perform_sweep=False)
        self.assertTrue(all_state.has('Swim', 1))
        for age in ('child', 'adult'):
            self.set_age(age)
            other_spawn = 187 if self.selected_spawn() == 642 else 642
            with self.subTest(age=age, inventory='unplaced scale'):
                self.assertFalse(self.viable(mapping={
                    self.selected_spawn(): self.arrival['id'], other_spawn: 16,
                }))

        starting_scale = self.world.create_item('Progressive Scale')
        self.multiworld.push_precollected(starting_scale)
        actual_counts = self.multiworld.state.prog_items[1].copy()
        self.assertEqual(self.multiworld.state.count('Progressive Scale', 1), 1)
        self.assertEqual(self.multiworld.state.count('Swim', 1), 1)
        for age in ('child', 'adult'):
            self.set_age(age)
            other_spawn = 187 if self.selected_spawn() == 642 else 642
            for selected_is_mapped in (False, True):
                mapping = {other_spawn: 16}
                if selected_is_mapped:
                    mapping[self.selected_spawn()] = self.arrival['id']
                with self.subTest(age=age, selected_is_mapped=selected_is_mapped,
                                  inventory='configured first scale'):
                    self.assertTrue(self.viable(mapping=mapping))
                    self.assertTrue(self.viable(mapping=mapping))
        self.assertEqual(self.multiworld.state.prog_items[1], actual_counts)
        self.assertEqual(len(self.multiworld.precollected_items[1]), 1)
        self.assertIs(self.multiworld.precollected_items[1][0], starting_scale)
        self.assertEqual(len(self.multiworld.itempool), 1)
        self.assertIs(self.multiworld.itempool[0], future_scale)
        self.assertIsNone(future_scale.location)

    def test_actual_instrument_is_permitted_while_structural_probe_still_needs_a_walk(self):
        self.add_ocarina_route()
        self.edge(self.return_region, self.field, 'Later physical escape requiring Crawl',
                  lambda state: state.has('Crawl', 1))
        inventory = self.inventory('Crawl', 'Progressive Ocarina')
        self.assertTrue(ER._physical_start_is_connected(self.world, inventory))
        self.assertFalse(self.viable())
        ocarina = self.item('Progressive Ocarina')
        self.multiworld.push_precollected(ocarina)
        for age in ('child', 'adult'):
            with self.subTest(age=age):
                self.set_age(age)
                self.assertTrue(self.viable())
                self.assertTrue(ER._physical_start_is_connected(self.world, inventory))
        self.assertEqual(self.multiworld.state.count('Progressive Ocarina', 1), 1)
        self.assertFalse(self.multiworld.state.has('Crawl', 1))
        self.assertEqual(len(self.multiworld.precollected_items[1]), 1)
        self.assertIs(self.multiworld.precollected_items[1][0], ocarina)

    def test_topology_change_cannot_keep_prior_hub_reach_or_swept_escape_item(self):
        route = self.edge(self.return_region, self.field, 'Initially free hub route')
        self.edge(self.return_region, self.field, 'Alternative route needs a hub reward',
                  lambda state: state.has('Crawl', 1))
        fixed = self.location('Crawl available only beyond the changed route', self.field)
        reward = self.item('Crawl')
        fixed.place_locked_item(reward)
        dead_end = self.region('Fresh-generation isolated component after a swap')
        for age in ('child', 'adult'):
            with self.subTest(age=age):
                self.set_age(age)
                self.assertTrue(self.viable())
                route.connected_region.entrances.remove(route)
                route.connect(dead_end)
                self.assertTrue(ER._reachable_at_starting_age(
                    self.world, CollectionState(self.multiworld), self.return_edge))
                self.assertFalse(self.viable())
                route.connected_region.entrances.remove(route)
                route.connect(self.field)
                self.assertTrue(self.viable())
        self.assertFalse(self.multiworld.state.has('Crawl', 1))
        self.assertFalse(self.multiworld.precollected_items[1])
        self.assertIs(fixed.item, reward)
        self.assertIs(reward.location, fixed)


class PhysicalStartConnectivityTests(StartConnectivityGraph):
    """Full-inventory connectivity excludes Ocarina in its separate probe."""

    def test_full_inventory_musical_route_does_not_certify_physical_connection(self):
        self.add_ocarina_route()
        inventory = self.inventory('Progressive Ocarina', 'Progressive Ocarina')
        self.assertTrue(ER._reachable_at_starting_age(self.world, inventory.copy(), self.field))

        self.assertFalse(ER._physical_start_is_connected(self.world, inventory))

        self.assertEqual(inventory.count('Progressive Ocarina', 1), 2)
        self.assertFalse(self.multiworld.state.has('Progressive Ocarina', 1))
        self.assertFalse(self.multiworld.precollected_items[1])

    def test_physical_route_uses_available_items_and_real_prefill_without_granting_them(self):
        self.edge(self.start, self.field, 'Physical route after two real abilities', lambda state:
                  state.has('Crawl', 1) and state.has('Roll', 1))
        fixed = self.location('Reachable fixed Roll reward', event=True)
        reward = self.item('Roll')
        fixed.place_locked_item(reward)
        inventory = self.inventory('Crawl', 'Progressive Ocarina')
        self.assertFalse(inventory.has('Roll', 1))

        self.assertTrue(ER._physical_start_is_connected(self.world, inventory))

        self.assertTrue(inventory.has('Crawl', 1))
        self.assertTrue(inventory.has('Progressive Ocarina', 1))
        self.assertFalse(inventory.has('Roll', 1))
        self.assertIs(fixed.item, reward)
        self.assertIs(reward.location, fixed)
        self.assertFalse(self.multiworld.state.has('Crawl', 1))
        self.assertFalse(self.multiworld.state.has('Roll', 1))
        self.assertFalse(self.multiworld.precollected_items[1])

    def test_only_other_age_reaching_the_hub_is_rejected_for_the_starting_age(self):
        self.edge(self.root, self.field, 'Adult-only hub access',
                  lambda state: state._soh_extreme_age[1] == Ages.ADULT)
        inventory = self.inventory()
        # An ordinary age-neutral query would incorrectly certify this child
        # start because the same state's adult region set contains the hub.
        self.assertTrue(self.field.can_reach(inventory.copy()))

        self.assertFalse(ER._physical_start_is_connected(self.world, inventory))

        self.world.options.starting_age.value = self.world.options.starting_age.option_adult
        self.assertTrue(ER._physical_start_is_connected(self.world, inventory))
        self.assertEqual(inventory._soh_extreme_age[1], Ages.null)

    def test_precollected_and_prefilled_ocarinas_cannot_reenter_the_private_probe(self):
        self.add_ocarina_route()
        starting_ocarina = self.item('Progressive Ocarina')
        self.multiworld.push_precollected(starting_ocarina)
        fixed = self.location('Reachable fixed Ocarina')
        fixed_ocarina = self.item('Progressive Ocarina')
        fixed.place_locked_item(fixed_ocarina)
        inventory = self.inventory('Progressive Ocarina', 'Progressive Ocarina')
        original_count = inventory.count('Progressive Ocarina', 1)
        self.assertGreaterEqual(original_count, 3)

        self.assertFalse(ER._physical_start_is_connected(self.world, inventory))

        self.assertEqual(inventory.count('Progressive Ocarina', 1), original_count)
        self.assertEqual(self.multiworld.state.count('Progressive Ocarina', 1), 1)
        self.assertEqual(len(self.multiworld.precollected_items[1]), 1)
        self.assertIs(self.multiworld.precollected_items[1][0], starting_ocarina)
        self.assertIs(fixed.item, fixed_ocarina)
        self.assertIs(fixed_ocarina.location, fixed)

    def test_rewiring_discards_prior_probe_regions_and_swept_events(self):
        route = self.edge(self.start, self.field, 'Initially physical route')
        self.edge(self.start, self.field, 'Alternative route needing a hub reward',
                  lambda state: state.has('Crawl', 1))
        known = self.location('Ability only obtainable at the hub', self.field, event=True)
        known.place_locked_item(self.item('Crawl'))
        self.add_ocarina_route()
        inventory = self.inventory('Progressive Ocarina')
        self.assertTrue(ER._physical_start_is_connected(self.world, inventory))
        self.assertFalse(inventory.has('Crawl', 1))
        dead_end = self.region('Rewired physical dead end')
        route.connected_region.entrances.remove(route)
        route.connect(dead_end)

        self.assertFalse(ER._physical_start_is_connected(self.world, inventory))

        self.assertFalse(inventory.has('Crawl', 1))
        self.assertFalse(inventory._soh_extreme_child_reachable_regions[1])
        self.assertFalse(inventory._soh_extreme_adult_reachable_regions[1])
        self.assertTrue(ER._reachable_at_starting_age(self.world, inventory.copy(), self.field))

    def test_full_inventory_connection_does_not_replace_actual_start_checks(self):
        route = self.edge(self.start, self.field, 'Physical route requiring future Crawl',
                          lambda state: state.has('Crawl', 1))
        check = self.location('Only initial physical check', rule=lambda state: state.has('Crawl', 1))
        inventory = self.inventory('Crawl')
        self.assertTrue(ER._physical_start_is_connected(self.world, inventory))
        self.assertFalse(ER._starting_state_is_viable(self.world, {}, {}, [check]))

        # A reachable check does not excuse an unusable shuffled spawn return.
        check.access_rule = lambda state: True
        arrival = next(row for row in ER.CATALOG if row['category'] == 'interiors'
                       and row['reverse'] >= 0 and row['scene'] != 5)
        mapping = {187: arrival['id']}
        self.assertFalse(ER._starting_state_is_viable(
            self.world, mapping, {arrival['reverse']: route}, [check]))

        # Nor can hypothetical full inventory bypass an unsafe water start.
        self.world.options.shuffle_swim.value = 1
        water = next(row for row in ER.CATALOG if row['scene'] == 5)
        self.assertFalse(ER._starting_state_is_viable(self.world, {187: water['id']}, {}, [check]))


if __name__ == '__main__':
    unittest.main(verbosity=2)
