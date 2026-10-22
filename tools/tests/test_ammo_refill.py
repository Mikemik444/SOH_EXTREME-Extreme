"""Exercise live-ammo refill proofs against the actual SOH-EXTREME AP world.

Controlled arrivals isolate physical source access; no AP reward fill or game
playthrough is claimed. Runtime observations in these cases are explicit input
fixtures; their native parameter classification is tested by the C/C++ suite.
"""
from contextlib import contextmanager
from hashlib import sha256
import argparse
import copy
import io
import json
from pathlib import Path
import time
import unittest

from test_entrance_blockers import SOURCE, Ages, Regions, ER, Item, ItemClassification, arrivals, inventory
from test_water_arrival_logic import build_world, no_exits
from test_zora_river_paths import full_identity, restore, add_blue_warps
from worlds.soh_extreme import AmmoRefillRules as A
from worlds.soh_extreme._vendor_oot_soh import LogicHelpers as H
from worlds.soh_extreme._vendor_oot_soh.Enums import Items, Locations, Events
from worlds.soh_extreme._vendor_oot_soh.Locations import SohLocation
from worlds.soh_extreme._vendor_oot_soh.ShopItems import all_shop_locations, fill_shop_items, vanilla_shop_prices

SOURCE_FILES = (
    'archipelago/soh_extreme/AmmoRefillRules.py',
    'archipelago/soh_extreme/AmmoRefillSources.json',
    'archipelago/soh_extreme/__init__.py',
    'archipelago/soh_extreme/EnemyRoomLogic.py',
    'archipelago/soh_extreme/EnemyRoomGraph.json',
    'archipelago/soh_extreme/EnemyRoomMap.json',
    'archipelago/soh_extreme/EnemyDropLocations.py',
    'archipelago/soh_extreme/EnemyDropRules.py',
    'archipelago/soh_extreme/EntranceRandomizer.py',
    'archipelago/soh_extreme/EntranceCatalog.json',
    'archipelago/soh_extreme/DungeonLocationRoutes.json',
    'archipelago/soh_extreme/_vendor_oot_soh/LogicHelpers.py',
    'archipelago/soh_extreme/_vendor_oot_soh/Enums.py',
    'archipelago/soh_extreme/_vendor_oot_soh/Locations.py',
    'archipelago/soh_extreme/_vendor_oot_soh/Items.py',
    'archipelago/soh_extreme/_vendor_oot_soh/ShopItems.py',
    'archipelago/soh_extreme/_vendor_oot_soh/location_access/overworld/kokiri_forest.py',
    'archipelago/soh_extreme/_vendor_oot_soh/location_access/overworld/lost_woods.py',
    'archipelago/soh_extreme/_vendor_oot_soh/location_access/overworld/haunted_wasteland.py',
    'soh/Enhancements/randomizer/location_list.cpp',
    'soh/Enhancements/randomizer/MegaSouls.cpp',
    'soh/Enhancements/randomizer/EnemyDropPolicy.h',
    'soh/Enhancements/randomizer/hook_handlers.cpp',
    'src/overlays/actors/ovl_En_Dns/z_en_dns.c',
    'src/overlays/actors/ovl_En_Js/z_en_js.c',
    'src/overlays/actors/ovl_En_Karebaba/z_en_karebaba.c',
    'src/overlays/actors/ovl_En_Tite/z_en_tite.c',
    'src/code/z_en_item00.c',
    'soh/Network/Archipelago/ArchipelagoLocationMap.inc',
)
TEST_FILES = ('tools/tests/test_ammo_refill.py', 'tools/tests/test_entrance_blockers.py',
              'tools/tests/test_water_arrival_logic.py', 'tools/tests/test_zora_river_paths.py',
              'tools/tests/test_overworld_entrances.py', 'tools/generate_ammo_refill_sources.py')
FACTS = {}


def observed(address, raw, kind=1, age=1):
    return (address, raw | (kind << 6) | (age << 8))


def clear_sources(world):
    for name in ('_extreme_ammo_sources', '_extreme_ammo_locations'):
        if hasattr(world, name):
            delattr(world, name)


@contextmanager
def one_room(world, age, token):
    with arrivals(world, (age, token)), no_exits(world, token):
        yield


class AmmoTests(unittest.TestCase):
    evidence = None
    decisions = 0
    probes = 0

    @classmethod
    def setUpClass(cls):
        cls.world = build_world(cls.evidence)
        mapping = full_identity(cls.world)
        add_blue_warps(mapping)
        restore(cls.world, mapping, 1)
        ordinary = copy.deepcopy(cls.evidence)
        cls.overrides = {'shuffle_scrubs': 0, 'shuffle_pots': 0, 'shuffle_crates': 0,
                         'shuffle_pot_soul': 0, 'shuffle_crate_soul': 0,
                         'npc_speech_sanity': 0}
        for name, value in cls.overrides.items():
            ordinary['resolved_options'][name]['value'] = value
        cls.ordinary = build_world(ordinary)
        mapping = full_identity(cls.ordinary)
        add_blue_warps(mapping)
        restore(cls.ordinary, mapping, 1)
        FACTS['worlds'] = {'actual_catalog_entries': len(ER.CATALOG),
                          'fresh_item_fill': False, 'controlled_identity_maps': True,
                          'ordinary_source_variant_overrides': cls.overrides,
                          'captured_ordinary_source_rules': len(cls.world._extreme_refill_source_rules)}

    def setUp(self):
        for world in (self.world, self.ordinary):
            world._extreme_live_ammo = None
            world._extreme_live_shields = None
            clear_sources(world)

    def check(self, actual, expected, label):
        type(self).decisions += 1
        self.assertEqual(actual, expected, label)

    def probe(self, world, state, *, ammo, owned=None, rupees=0, flags=0, checked=(), facts=(), age=1):
        type(self).probes += 1
        before = (copy.deepcopy(state.prog_items), set(state.advancements), set(state.locations_checked))
        prior_ammo = getattr(world, '_extreme_live_ammo', None)
        before_prices = dict(world.shop_prices)
        answer = A.refill_mask(world, state, live_ammo=ammo, owned=ammo if owned is None else owned,
                               rupees=rupees, flags=flags, checked=checked, observed=facts, live_age=age)
        self.check((state.prog_items, state.advancements, state.locations_checked), before,
                   'probe preserves authoritative input state')
        self.check(world._extreme_live_ammo, prior_ammo, 'probe restores actual live ammunition')
        self.check(world.shop_prices, before_prices, 'refill proof does not alter AP shelf prices')
        return answer

    def test_01_carried_ammo_and_capacity_aliases(self):
        world = self.world
        with one_room(world, Ages.ADULT, 'KF_LINKS_HOUSE'):
            names = ('Progressive Bomb Bag',) * 4 + ('Progressive Bow',) * 4 + ('Bombchu Bag',)
            state = inventory(world, Ages.ADULT, names)
            bundle = (Regions.KF_LINKS_HOUSE, world)
            aliases = {4: (Items.PROGRESSIVE_BOMB_BAG, Items.BOMB_BAG, Items.BIG_BOMB_BAG,
                           Items.BIGGEST_BOMB_BAG, Items.BOMB_BAG_INF),
                       16: (Items.PROGRESSIVE_BOW, Items.FAIRY_BOW, Items.BIG_QUIVER,
                            Items.BIGGEST_QUIVER, Items.QUIVER_INF),
                       8: (Items.BOMBCHU_BAG, Items.BOMBCHUS_5, Items.BOMBCHUS_10, Items.BOMBCHUS_20)}
            for bit, items in aliases.items():
                for item in items:
                    # Capacity names have no progressive expansion in the
                    # stock table. Give their literal legacy rule ownership
                    # as well as the ordinary progressive container.
                    state.collect(Item(str(item), ItemClassification.progression, None, 1), True)
                    rule = H.can_use(item, bundle).resolve(world)
                    world._extreme_live_ammo = bit
                    self.check(rule(state), True, ('carried last unit is usable', item))
                    world._extreme_live_ammo = 0
                    self.check(rule(state), False, ('empty owned container is not usable', item))
                    self.check(state.has('Progressive Bomb Bag', 1), True, 'bomb bag remains owned')
            world._extreme_live_ammo = None
            self.check(H.can_use(Items.BOMB_BAG, bundle).resolve(world)(state), True,
                       'generation fallback unchanged')
        with one_room(world, Ages.CHILD, 'KF_LINKS_HOUSE'):
            state = inventory(world, Ages.CHILD, ('Progressive Stick Capacity', 'Progressive Nut Capacity'))
            for bit, item in ((1, Items.STICKS), (2, Items.NUTS)):
                world._extreme_live_ammo = bit
                self.check(H.can_use(item, (Regions.KF_LINKS_HOUSE, world)).resolve(world)(state), True,
                           'positive protected stick/nut does not need a preexisting farm event')
                world._extreme_live_ammo = 0
                self.check(H.can_use(item, (Regions.KF_LINKS_HOUSE, world)).resolve(world)(state), False,
                           'empty stick/nut bag does not become ammo')

    def test_02_observed_pot_first_check_soul_break_method_and_age(self):
        world = self.world
        with one_room(world, Ages.CHILD, 'KF_LINKS_HOUSE'):
            world._extreme_live_ammo = 2
            state = inventory(world, Ages.CHILD, ('Progressive Nut Capacity', 'Pot Soul', 'Grab / Power Bracelet'))
            fact = (observed(794, 2),)
            for checked, facts, expected in (((), fact, 0), ((794,), (), 0), ((794,), fact, 2)):
                self.check(self.probe(world, state, ammo=2, checked=checked, facts=facts), expected,
                           ('active pot first check and native proof', checked, facts))
            self.check(self.probe(world, state, ammo=2, checked=(794,), facts=fact, age=2), 0,
                       'current adult cannot use an old child source result')
            for names in (('Progressive Nut Capacity', 'Grab / Power Bracelet'),
                          ('Progressive Nut Capacity', 'Pot Soul', 'Kokiri Sword')):
                no = inventory(world, Ages.CHILD, names)
                self.check(self.probe(world, no, ammo=2, checked=(794,), facts=fact), 0,
                           'missing Soul or reusable physical break method')
            self.check(self.probe(world, state, ammo=0, owned=0, checked=(794,), facts=fact), 0,
                       'no owned container never gains a refill capability')
            self.check(self.probe(world, state, ammo=0, owned=2, checked=(794,), facts=fact), 2,
                       'empty owned bag may know a refill, but native guard never creates a unit')

    def test_03_raw_drop_age_conversion_and_bombchu_only_bag(self):
        world = self.world
        names = ('Progressive Stick Capacity', 'Progressive Nut Capacity', 'Progressive Bomb Bag',
                 'Progressive Bow', 'Bombchu Bag', 'Pot Soul', 'Kokiri Sword', 'Master Sword',
                 'Grab / Power Bracelet')
        for age, native_age in ((Ages.CHILD, 1), (Ages.ADULT, 2)):
            with one_room(world, age, 'KF_LINKS_HOUSE'):
                state = inventory(world, age, names)
                for raw, expected in ((1, 1 if native_age == 1 else 0), (2, 2), (4, 4),
                                      (16, 16 if native_age == 2 else 0), (32, 16 if native_age == 2 else 0)):
                    self.check(self.probe(world, state, ammo=31, flags=1, checked=(794,),
                                         facts=(observed(794, raw, age=native_age),), age=native_age), expected,
                               ('ordinary age conversion; NoRandomDrops leaves fixed drops', native_age, raw))
                self.check(self.probe(world, state, ammo=31, flags=2, checked=(794,),
                                     facts=(observed(794, 1, age=native_age),), age=native_age), 1,
                           'TreesDropSticks permits adult ordinary stick drops')
                chu_only = inventory(world, age, tuple(name for name in names
                                                     if name != 'Progressive Bomb Bag'))
                self.check(self.probe(world, chu_only, ammo=8, owned=8, checked=(794,),
                                     facts=(observed(794, 4, age=native_age),), age=native_age), 8,
                           'Bombchu-only bag converts native bomb refills')
                self.check(self.probe(world, state, ammo=12, owned=12, checked=(794,),
                                     facts=(observed(794, 4, age=native_age),), age=native_age), 4,
                           'owning both bags retains bomb drops; no false Bombchu refill')

    def test_04_inactive_sources_keep_their_real_access_rules(self):
        world = self.ordinary
        with one_room(world, Ages.CHILD, 'KF_LINKS_HOUSE'):
            state = inventory(world, Ages.CHILD, ('Progressive Nut Capacity', 'Grab / Power Bracelet'))
            self.check(794 in {location.address for location in world.get_locations()}, False,
                       'ordinary pot is not an active AP location')
            self.check(self.probe(world, state, ammo=2, facts=(observed(794, 2),)), 2,
                       'unshuffled flag0 pot supports a repeatable refill')
        with one_room(world, Ages.CHILD, 'KF_MIDOS_HOUSE'):
            state = inventory(world, Ages.CHILD, ('Progressive Nut Capacity', 'Grab / Power Bracelet'))
            self.check(self.probe(world, state, ammo=2, facts=(observed(794, 2),)), 0,
                       'an observed actor is not proof of current AP access')
        # An inactive dungeon source still inherits its exact native room route.
        address = 995  # Bottom of the Well perimeter pot, from DungeonLocationRoutes
        with one_room(world, Ages.CHILD, 'RR_BOTW_PERIMETER'):
            state = inventory(world, Ages.CHILD, ('Progressive Nut Capacity', 'Pot Soul', 'Kokiri Sword'))
            self.check(self.probe(world, state, ammo=2, facts=(observed(address, 2),)), 2,
                       'inactive dungeon pot uses actual native room')
        with one_room(world, Ages.CHILD, 'RR_BOTW_SKULL_WALL_ROOM'):
            state = inventory(world, Ages.CHILD, ('Progressive Nut Capacity', 'Pot Soul', 'Kokiri Sword'))
            self.check(self.probe(world, state, ammo=2, facts=(observed(address, 2),)), 0,
                       'inactive dungeon pot cannot leak across a disconnected room')

    def test_05_target_ammo_events_are_reswept_without_losing_bag(self):
        world = self.world
        root = world.get_region(str(Regions.ROOT))
        event = SohLocation(1, 'Ammo fixture bomb switch', None, root)
        event.place_locked_item(Item('Ammo fixture bomb switch opened', ItemClassification.progression, None, 1))
        event.access_rule = H.can_use(Items.BOMB_BAG, (Regions.ROOT, world)).resolve(world)
        root.locations.append(event)
        try:
            with one_room(world, Ages.CHILD, 'KF_LINKS_HOUSE'):
                gate = root.exits[0]
                gate.access_rule = lambda state: (state._soh_extreme_age[1] == Ages.CHILD
                                                  and state.has('Ammo fixture bomb switch opened', 1))
                world._extreme_live_ammo = 4
                state = inventory(world, Ages.CHILD, ('Progressive Bomb Bag', 'Pot Soul', 'Grab / Power Bracelet'))
                self.check(state.has('Ammo fixture bomb switch opened', 1), True,
                           'original live state derived a switch using carried bomb')
                self.check(self.probe(world, state, ammo=4, checked=(794,), facts=(observed(794, 4),)), 0,
                           'target-ammo switch cannot survive into its own refill proof')
                self.check(state.has('Progressive Bomb Bag', 1), True, 'the physical bomb bag remains owned')
                gate.access_rule = lambda state: state._soh_extreme_age[1] == Ages.CHILD
                self.check(self.probe(world, state, ammo=4, checked=(794,), facts=(observed(794, 4),)), 4,
                           'same pot qualifies when the independent actual route is open')
        finally:
            root.locations.remove(event)

    def test_06_consumptive_custom_lost_woods_route(self):
        world = self.world
        with arrivals(world, (Ages.CHILD, 'GC_WOODS_WARP')):
            b = world.get_region(str(Regions.GC_WOODS_WARP))
            edges = [edge for edge in b.exits if edge.connected_region and
                     edge.connected_region.name == str(Regions.LOST_WOODS)]
            self.check(bool(edges), True, 'actual GC to Lost Woods custom physical route exists')
            state = inventory(world, Ages.CHILD, ('Progressive Bomb Bag', 'Rock / Boulder Soul'))
            for ammo, expected in ((4, True), (0, False)):
                world._extreme_live_ammo = ammo
                self.check(any(edge.access_rule(state) for edge in edges), expected,
                           'direct Has(Bomb Bag) custom route obeys actual live ammo')

    def test_07_native_repeat_loot_requires_checked_exact_enemy_and_reusable_kill(self):
        world = self.world
        for age, native_age, sword in ((Ages.CHILD, 1, 'Kokiri Sword'), (Ages.ADULT, 2, 'Master Sword')):
            with one_room(world, age, 'DEATH_MOUNTAIN_TRAIL'):
                names = (sword, 'Tektite Soul', 'Progressive Nut Capacity', 'Progressive Bomb Bag', 'Progressive Bow')
                state = inventory(world, age, names)
                checks = (9800558,) if native_age == 1 else (9800697,)
                expected = 6 if native_age == 1 else 22
                self.check(self.probe(world, state, ammo=22, checked=checks, age=native_age), expected,
                           'audited repeat Red Tektite loot after exact first check')
                self.check(self.probe(world, state, ammo=22, checked=(), age=native_age), 0,
                           'assigned first enemy reward is not renewable ammo')
                self.check(self.probe(world, state, ammo=22, checked=checks, flags=1, age=native_age), 0,
                           'NoRandomDrops suppresses generic loot')
                finite_only = inventory(world, age, names[1:])
                self.check(self.probe(world, finite_only, ammo=22, checked=checks, age=native_age), 0,
                           'a random farm cannot consume another finite ammo supply to kill')
        with one_room(world, Ages.CHILD, 'KF_OUTSIDE_DEKU_TREE'):
            state = inventory(world, Ages.CHILD, ('Kokiri Sword', 'Deku Baba Soul', 'Progressive Stick Capacity'))
            self.check(self.probe(world, state, ammo=1, flags=1), 1,
                       'regrowing withered Baba retains its direct guaranteed stick reward')

    def test_08_unshuffled_scrubs_and_carpet_real_prices(self):
        world = self.ordinary
        with one_room(world, Ages.CHILD, 'LW_BEYOND_MIDO'):
            names = ('Progressive Nut Capacity', 'Progressive Stick Capacity', 'Deku Shield',
                     'Scrub Soul', 'NPC Soul', 'Speak Deku', 'Progressive Wallet')
            state = inventory(world, Ages.CHILD, names)
            world._extreme_live_shields = 1
            ordinary_price = H.can_afford_slot(Locations.LW_DEKU_SCRUB_NEAR_DEKU_THEATER_LEFT,
                                              (Regions.LW_BEYOND_MIDO, world)).resolve(world)
            self.check(ordinary_price(state), False,
                       'inactive stock AP predicate has its ordinary 500-rupee fallback')
            for rupees, expected in ((14, 0), (15, 1), (19, 1), (20, 3)):
                self.check(self.probe(world, state, ammo=3, rupees=rupees), expected,
                           'ordinary scrub refill checks real 15/20 rupee price')
            for missing in ('Deku Shield', 'Scrub Soul', 'NPC Soul', 'Speak Deku'):
                world._extreme_live_shields = 0 if missing == 'Deku Shield' else 1
                state = inventory(world, Ages.CHILD, tuple(name for name in names if name != missing))
                self.check(self.probe(world, state, ammo=3, rupees=99), 0,
                           ('scrub refill missing physical requirement', missing))
            self.check(ordinary_price(inventory(world, Ages.CHILD, names)), False,
                       'stock-price proxy never changes the authored AP price predicate')
        world = self.world
        with one_room(world, Ages.ADULT, 'HAUNTED_WASTELAND'):
            names = ('Bombchu Bag', 'Progressive Wallet', 'Progressive Wallet', 'NPC Soul', 'Speak Hylian', 'Master Sword')
            state = inventory(world, Ages.ADULT, names)
            address = world.location_name_to_id[str(Locations.WASTELAND_CARPET_SALESMAN)]
            for rupees, checked, expected in ((199, (address,), 0), (200, (), 0), (200, (address,), 8)):
                self.check(self.probe(world, state, ammo=8, rupees=rupees, checked=checked, age=2), expected,
                           'Carpet refill is after its first AP check and costs vanilla200')

    def test_09_retained_shop_stock_is_repeatable_but_assigned_reward_is_not(self):
        world = self.world
        parent = Regions.KF_KOKIRI_SHOP
        slots = (Locations.KF_SHOP_ITEM1, Locations.KF_SHOP_ITEM2, Locations.KF_SHOP_ITEM3,
                 Locations.KF_SHOP_ITEM4, Locations.KF_SHOP_ITEM5)
        stock = (Items.BUY_DEKU_STICK1, Items.BUY_DEKU_NUTS5, Items.BUY_BOMBS525,
                 Items.BUY_BOMBCHUS10, Items.BUY_ARROWS10)
        original = [(world.get_location(str(name)), world.get_location(str(name)).address,
                     world.get_location(str(name)).item, world.get_location(str(name)).locked,
                     world.shop_prices.get(name)) for name in slots]
        old_pass = world.passthrough
        try:
            world.passthrough = dict(old_pass, shop_vanilla_items={str(name): str(item) for name, item in zip(slots, stock)})
            fill_shop_items(world)  # actual UT restoration of retained native shelf stock
            for name, item in zip(slots, stock):
                world.shop_prices[name] = vanilla_shop_prices[item]
            clear_sources(world)
            with one_room(world, Ages.CHILD, 'KF_KOKIRI_SHOP'):
                names = ('Progressive Stick Capacity', 'Progressive Nut Capacity', 'Progressive Bomb Bag',
                         'Bombchu Bag', 'Progressive Bow', 'Progressive Wallet', 'NPC Soul', 'Speak Kokiri')
                state = inventory(world, Ages.CHILD, names)
                self.check(self.probe(world, state, ammo=31, rupees=99), 31,
                           'retained real shop stock refills each of the five owned ammo types')
                self.check(self.probe(world, state, ammo=31, rupees=0), 0,
                           'wallet capacity does not invent cash')
                for location, address, _, _, _ in original:
                    location.address = address
                clear_sources(world)
                self.check(self.probe(world, state, ammo=31, rupees=999, checked=tuple(x[1] for x in original)), 0,
                           'an AP shelf remains one-time even assigned a BuyAmmo item')
        finally:
            world.passthrough = old_pass
            for location, address, item, locked, price in original:
                location.address, location.item, location.locked = address, item, locked
                if price is None:
                    world.shop_prices.pop(location.name, None)
                else:
                    world.shop_prices[location.name] = price
            clear_sources(world)

    def test_10_observation_validation_and_unknown_identity(self):
        valid = observed(794, 2)
        self.check(A.validate_observed_sources([valid]), (valid,), 'valid exact source observation')
        for invalid in (None, [valid, valid], [[0, valid[1]]], [[794, 8 | 64 | 256]],
                        [[794, 2]], [[794, 2 | 64 | 768]], [[794, True]], [valid] * 2049):
            with self.assertRaises(ValueError):
                A.validate_observed_sources(invalid)
            type(self).decisions += 1
        world = self.world
        with one_room(world, Ages.CHILD, 'KF_LINKS_HOUSE'):
            state = inventory(world, Ages.CHILD, ('Progressive Nut Capacity', 'Pot Soul', 'Kokiri Sword'))
            for fact in (observed(999999999, 2), observed(794, 2, kind=3)):
                self.check(self.probe(world, state, ammo=2, facts=(fact,), checked=(794,)), 0,
                           'unknown identity or mismatched actor class retains protection')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--settings-report', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    before = {name: sha256((SOURCE / name).read_bytes()).hexdigest() for name in SOURCE_FILES}
    tests = {name: sha256((SOURCE / name).read_bytes()).hexdigest() for name in TEST_FILES}
    AmmoTests.evidence = json.loads(args.settings_report.read_text())
    start = time.monotonic()
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(AmmoTests))
    output = stream.getvalue()
    print(output)
    unchanged = before == {name: sha256((SOURCE / name).read_bytes()).hexdigest() for name in SOURCE_FILES}
    report = {'status': 'passed' if result.wasSuccessful() and unchanged else 'failed',
              'tests': result.testsRun, 'decisions': AmmoTests.decisions, 'refill_probes': AmmoTests.probes,
              'elapsed_seconds': round(time.monotonic() - start, 3), 'source_unchanged_during_tests': unchanged,
              'source_sha256': before, 'test_sha256': tests,
              'inputs': {'settings_report': {'name': args.settings_report.name,
                         'sha256': sha256(args.settings_report.read_bytes()).hexdigest()}},
              'facts': FACTS, 'test_output': output,
              'scope': 'Actual AP rule/event/topology evaluation; controlled sources/ingress; no item fill or game playthrough'}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    if report['status'] != 'passed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
