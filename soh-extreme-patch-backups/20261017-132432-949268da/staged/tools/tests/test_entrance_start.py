"""Focused regressions against the real AP 0.6.7 CollectionState and SoH classes."""
import random
import unittest

import ModuleUpdate
ModuleUpdate.update_ran = True
import settings
settings.no_gui = True
settings.skip_autosave = True

from BaseClasses import CollectionState, Item, ItemClassification, LocationProgressType
from test.general import setup_multiworld
from worlds.soh_extreme import SohExtremeWorld
from worlds.soh_extreme import EntranceRandomizer as ER
from worlds.soh_extreme._vendor_oot_soh.Enums import Ages, Regions
from worlds.soh_extreme._vendor_oot_soh.Locations import SohLocation
from worlds.soh_extreme._vendor_oot_soh.Regions import SohRegion


class EntranceStartTests(unittest.TestCase):
    def setUp(self):
        self.multiworld = setup_multiworld(SohExtremeWorld, steps=(), seed=44, options={
            'starting_age': 'child', 'shuffle_child_spawn': 1,
            'shuffle_interior_entrances': 1, 'shuffle_swim': 1,
            'mixed_entrance_pools': {'child_spawn', 'interiors'},
        })
        self.world = self.multiworld.worlds[1]
        self.root = self.region(str(Regions.ROOT))
        self.house = self.region(str(Regions.KF_LINKS_HOUSE))
        self.forest = self.region(str(Regions.KOKIRI_FOREST))
        self.spawn_edge = self.root.create_exit('Test starting age spawn')
        self.spawn_edge.access_rule = lambda state: state._soh_extreme_age[1] == Ages.CHILD
        self.spawn_edge.connect(self.house)
        self.return_edge = self.house.create_exit('Test physical return')
        self.return_edge.connect(self.forest)
        self.return_edge.access_rule = lambda state: True
        self.mapping = {187: 626}
        self.edges = {529: self.return_edge}

    def region(self, name):
        region = SohRegion(name, 1, self.multiworld)
        self.multiworld.regions.append(region)
        return region

    def location(self, name, parent, rule=lambda state: True):
        loc = SohLocation(1, name, 12345000 + len(self.world.get_locations()), parent)
        loc.access_rule = rule
        parent.locations.append(loc)
        return loc

    def grant(self, name):
        self.multiworld.push_precollected(Item(name, ItemClassification.progression, 123, 1))

    def viable(self, locations):
        return ER._starting_state_is_viable(self.world, self.mapping, self.edges, locations)

    def test_root_pocket_does_not_certify_playable_start(self):
        pocket = self.location('Test pocket', self.root)
        self.assertFalse(self.viable([pocket]))

    def test_real_initial_check_is_accepted(self):
        check = self.location('Test free check', self.forest)
        self.assertTrue(self.viable([check]))

    def test_excluded_check_cannot_bootstrap_progression(self):
        check = self.location('Test excluded check', self.forest)
        check.progress_type = LocationProgressType.EXCLUDED
        self.assertFalse(self.viable([check]))

    def test_full_inventory_route_does_not_certify_start(self):
        check = self.location('Test locked check', self.forest, lambda state: state.has('Crawl', 1))
        all_state = CollectionState(self.multiworld)
        all_state.collect(Item('Crawl', ItemClassification.progression, 123, 1), True)
        self.assertTrue(check.can_reach(all_state))
        self.assertFalse(self.viable([check]))

    def test_configured_starting_inventory_is_honored(self):
        check = self.location('Test crawl check', self.forest, lambda state: state.has('Crawl', 1))
        self.grant('Crawl')
        self.assertTrue(self.viable([check]))

    def test_locked_spawn_return_rejected_despite_free_item_inside(self):
        check = self.location('Test room check', self.house)
        self.return_edge.access_rule = lambda state: state.has('Climb', 1)
        self.assertFalse(self.viable([check]))
        self.grant('Climb')
        self.assertTrue(self.viable([check]))

    def test_wrong_age_check_cannot_certify_child_start(self):
        check = self.location('Test adult check', self.house,
                              lambda state: state._soh_extreme_age[1] == Ages.ADULT)
        self.assertFalse(self.viable([check]))

    def test_adult_spawn_uses_adult_rule_and_destination(self):
        self.world.options.starting_age.value = 1
        self.spawn_edge.access_rule = lambda state: state._soh_extreme_age[1] == Ages.ADULT
        self.mapping = {642: 626}
        check = self.location('Test adult check', self.house,
                              lambda state: state._soh_extreme_age[1] == Ages.ADULT)
        self.assertTrue(self.viable([check]))

    def test_prefilled_local_progression_can_open_start(self):
        key = self.location('Test free local key', self.house)
        key.place_locked_item(Item('Crawl', ItemClassification.progression, 123, 1))
        check = self.location('Test crawl check', self.forest, lambda state: state.has('Crawl', 1))
        self.assertTrue(self.viable([check]))

    def test_rejected_candidate_does_not_keep_swept_key(self):
        key = self.location('Test free key', self.house)
        key.place_locked_item(Item('Crawl', ItemClassification.progression, 123, 1))
        check = self.location('Test crawl check', self.forest, lambda state: state.has('Crawl', 1))
        self.assertTrue(self.viable([check]))
        key.access_rule = lambda state: False
        self.assertFalse(self.viable([check]))

    def test_water_spawn_needs_initial_swim(self):
        check = self.location('Test physical check', self.house)
        self.mapping = {187: 16}
        self.edges = {541: self.return_edge}
        self.assertFalse(self.viable([check]))
        self.grant('Progressive Scale')
        self.assertTrue(self.viable([check]))

    def test_boss_spawn_without_physical_return_is_rejected(self):
        check = self.location('Test physical check', self.house)
        boss_return = ER.ENDPOINTS[590]
        self.region(ER.region_name(boss_return['source']))
        self.mapping = {187: 12}
        self.edges = {}
        self.assertFalse(self.viable([check]))


class CoupledMappingTests(unittest.TestCase):
    def test_all_enabled_mixed_pools_preserve_every_reverse(self):
        options = {key: 1 for key in ER.ENTRANCE_OPTIONS if key != 'mixed_entrance_pools'}
        options['mixed_entrance_pools'] = set(ER.CATEGORIES)
        world = setup_multiworld(SohExtremeWorld, steps=(), seed=1801, options=options).worlds[1]
        for seed in range(100):
            world.random = random.Random(seed)
            mapping = ER._candidate(world)
            ER.validate_mapping(world, mapping)
            for source, target in mapping.items():
                a, b = ER.ENDPOINTS[source], ER.ENDPOINTS[target]
                if a['reverse'] >= 0:
                    self.assertEqual(mapping[b['reverse']], a['reverse'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
