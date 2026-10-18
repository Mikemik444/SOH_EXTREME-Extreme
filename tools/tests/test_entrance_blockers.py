"""Exercise actual AP room, source-door, age and shortcut predicates.

The supplied YAML builds the real world through set_rules. Controlled ingress
edges then isolate alternate arrivals; event sweeps and item checks are the
production implementations. An optional exactly reproduced saved map is
restored through production ER.connect. No new fill or in-game collision
playthrough is claimed.
"""
from contextlib import contextmanager, ExitStack
from hashlib import sha256
import argparse
import io
import json
from pathlib import Path
import random
import time
import unittest
from unittest.mock import patch

import ModuleUpdate
ModuleUpdate.update_ran = True
import settings
settings.no_gui = True
settings.skip_autosave = True

import Utils
import yaml
from BaseClasses import CollectionState, Item, ItemClassification
from Generate import roll_settings
from Options import OptionError
from test.general import setup_multiworld
from worlds.AutoWorld import call_all
from worlds.soh_extreme import SohExtremeWorld
from worlds.soh_extreme import EntranceRandomizer as ER
from worlds.soh_extreme import EnemyRoomLogic as N
from worlds.soh_extreme._vendor_oot_soh.Enums import Ages, Regions
from worlds.soh_extreme._vendor_oot_soh.Regions import SohRegion


SOURCE = Path(__file__).resolve().parents[2]
J = 'RR_JABU_JABUS_BELLY_'
W = 'RR_WATER_TEMPLE_'
F = 'RR_FIRE_TEMPLE_'
S = 'RR_SPIRIT_TEMPLE_'
SH = 'RR_SHADOW_TEMPLE_'
SOURCE_FILES = (
    'archipelago/soh_extreme/__init__.py',
    'archipelago/soh_extreme/EnemyRoomLogic.py',
    'archipelago/soh_extreme/EnemyRoomGraph.json',
    'archipelago/soh_extreme/EnemyRoomMap.json',
    'archipelago/soh_extreme/EnemyDropLocations.py',
    'archipelago/soh_extreme/SceneTransitions.py',
    'archipelago/soh_extreme/EntranceRandomizer.py',
    'archipelago/soh_extreme/EntranceCatalog.json',
    'archipelago/soh_extreme/DungeonDoorCatalog.json',
    'archipelago/soh_extreme/DungeonLocationRoutes.json',
    'archipelago/soh_extreme/_vendor_oot_soh/LogicHelpers.py',
    'archipelago/soh_extreme/_vendor_oot_soh/Regions.py',
    'archipelago/soh_extreme/_vendor_oot_soh/Locations.py',
    'soh/Enhancements/randomizer/location_access/dungeons/jabujabus_belly.cpp',
    'soh/Enhancements/randomizer/location_access/dungeons/water_temple.cpp',
    'soh/Enhancements/randomizer/location_access/dungeons/fire_temple.cpp',
    'soh/Enhancements/randomizer/location_access/dungeons/shadow_temple.cpp',
    'soh/Enhancements/randomizer/location_access/dungeons/spirit_temple.cpp',
    'soh/Enhancements/randomizer/location_access.h',
    'soh/Enhancements/randomizer/logic.cpp',
    'soh/Enhancements/randomizer/MegaSouls.cpp',
    'src/overlays/actors/ovl_En_Ba/z_en_ba.c',
    'src/overlays/actors/ovl_En_Bili/z_en_bili.c',
    'src/overlays/actors/ovl_En_Bx/z_en_bx.c',
    'src/overlays/actors/ovl_Door_Shutter/z_door_shutter.c',
    'src/code/z_actor.c',
    'tools/tests/test_entrance_blockers.py',
)


def build_world(yaml_path, seed=188):
    random.seed(seed)
    rolled = roll_settings(yaml.safe_load(yaml_path.read_text(encoding='utf-8-sig')))
    options = {name: getattr(rolled, name).value
               for name in SohExtremeWorld.options_dataclass.type_hints}
    options = {name: dict(value) if isinstance(value, dict) else value
               for name, value in options.items()}
    options['starting_age'] = 'adult'
    mw = setup_multiworld(SohExtremeWorld, steps=(), seed=seed, options=options)
    for step in ('generate_early', 'create_regions', 'create_items', 'set_rules'):
        print(step, flush=True)
        call_all(mw, step)
    mw.precollected_items[1].clear()
    world = mw.worlds[1]
    # Probe inventories are explicit. Keep native event locations, but do not
    # obtain a random locked Pocket reward or other addressed reward for free.
    for loc in world.get_locations():
        if loc.address is not None:
            loc.item = None
    world.blocker_checks = {loc.address: loc for loc in world.get_locations()
                            if loc.address is not None}
    return world


def region(world, token):
    return world.get_region(ER.region_name(token)) if isinstance(token, str) else token


@contextmanager
def arrivals(world, *entries):
    """Each entry is (age, exact region); no inventory action is substituted."""
    root = world.get_region(str(Regions.ROOT))
    original = list(root.exits)
    for edge in original:
        if edge.connected_region is not None:
            edge.connected_region.entrances.remove(edge)
    root.exits.clear()
    for index, (age, target) in enumerate(entries):
        edge = root.create_exit(f'Blocker fixture arrival {index}')
        edge.access_rule = lambda state, age=age: state._soh_extreme_age[1] == age
        edge.connect(region(world, target))
    try:
        yield
    finally:
        for edge in list(root.exits):
            edge.connected_region.entrances.remove(edge)
        root.exits.clear()
        root.exits.extend(original)
        for edge in original:
            if edge.connected_region is not None:
                edge.connected_region.entrances.append(edge)


def inventory(world, age, names=(), flags=(), sweep=True):
    state = CollectionState(world.multiworld)
    for name in names:
        state.collect(world.create_item(name), True)
    for flag in flags:
        state.collect(Item(N.event_item(flag), ItemClassification.progression, None, 1), True)
    state._soh_extreme_age[1] = age
    if sweep:
        state.sweep_for_advancements()
        state._soh_extreme_age[1] = age
    return state


def reached(world, state, token, age):
    old = state._soh_extreme_age[1]
    try:
        state._soh_extreme_age[1] = age
        return region(world, token).can_reach(state)
    finally:
        state._soh_extreme_age[1] = old


def physical_edge(world, endpoint):
    row = ER.ENDPOINTS[endpoint]
    return next(edge for edge in region(world, row['source']).exits
                if edge.connected_region and
                edge.connected_region.name == ER.region_name(row['target']))


@contextmanager
def redirect_source(world, endpoint, target):
    """Rewire the actual physical edge using ER's actual source predicate."""
    rule = ER._source_rule(world, ER.ENDPOINTS[endpoint])
    edge = physical_edge(world, endpoint)
    old_target, old_rule = edge.connected_region, edge.access_rule
    old_target.entrances.remove(edge)
    edge.connect(region(world, target))
    edge.access_rule = rule
    for dependency in getattr(rule, '_er_dependencies', ()):
        world._register_rule_indirects(dependency, edge)
    try:
        yield edge
    finally:
        edge.connected_region.entrances.remove(edge)
        edge.connect(old_target)
        edge.access_rule = old_rule


class EntranceBlockerTests(unittest.TestCase):
    world = None
    reported_seed = None
    restored_seed_results = None

    def check_door(self, endpoint, state, expected, source_rule=None):
        world = self.world
        row = ER.ENDPOINTS[endpoint]
        age = state._soh_extreme_age[1]
        if source_rule is None:
            source_rule = ER._source_rule(world, row)
        self.assertEqual(bool(source_rule(state)), expected)
        location = world.blocker_checks[row['check_id']]
        self.assertEqual(bool(location.access_rule(state)), expected)
        self.assertEqual(ER._reachable_as_age(world, state, location, age), expected)

    def test_native_export_and_exact_barred_sides(self):
        for endpoint, file in ((8461, 'jabujabus_belly.cpp'), (8877, 'water_temple.cpp')):
            row = ER.ENDPOINTS[endpoint]
            native = (SOURCE / 'soh/Enhancements/randomizer/location_access/dungeons' / file).read_text()
            body = native.split('areaTable[' + row['source'] + '] = Region(', 1)[1].split('\n    areaTable[', 1)[0]
            condition = next(edge['condition'] for edge in N.GRAPH[row['source']]['exits']
                             if edge['target'] == row['target'])
            compact = lambda text: ''.join(text.split())
            self.assertIn(compact('ENTRANCE(' + row['target'] + ',' + condition + ')'), compact(body))
            self.assertEqual(row['side'], 1)
        self.assertEqual((ER.ENDPOINTS[8461]['from_room'], ER.ENDPOINTS[8461]['params']), (8, 127))
        self.assertEqual((ER.ENDPOINTS[8877]['from_room'], ER.ENDPOINTS[8877]['params']), (15, 190))
        native = (SOURCE / 'soh/Enhancements/randomizer/location_access/dungeons/jabujabus_belly.cpp').read_text()
        for direction in ('NORTH_WEST', 'NORTH', 'NORTH_EAST'):
            token = J + 'TO_FORK_' + direction
            body = native.split('areaTable[' + token + '] = Region(', 1)[1].split('\n    areaTable[', 1)[0]
            condition = next(e['condition'] for e in N.GRAPH[token]['exits'] if e['target'] == J + 'FORKED_CORRIDOR')
            self.assertNotIn('TakeDamage', condition)
            self.assertIn(compact('ENTRANCE(' + J + 'FORKED_CORRIDOR,' + condition + ')'), compact(body))

    def test_jabu_corridor_cannot_bootstrap_any_tentacle(self):
        world = self.world
        for age in (Ages.CHILD, Ages.ADULT):
            with self.subTest(age=age), arrivals(world, (age, J + 'FORKED_CORRIDOR')):
                state = inventory(world, age, ('Boomerang', 'Jabu Jabu Tentacle Soul', 'Biri and Bari Soul', 'Shabom Soul'))
                for direction in ('WEST', 'EAST', 'NORTH'):
                    self.assertFalse(state.has(N.event_item('LOGIC_JABU_' + direction + '_TENTACLE'), 1))
                for endpoint in (8458, 8460, 8462):
                    self.check_door(endpoint, state, False)
                self.assertFalse(reached(world, state, J + 'FORK_NORTH_WEST', age))
                self.assertFalse(reached(world, state, J + 'FORK_NORTH', age))
                self.assertFalse(world.blocker_checks[9800115].can_reach(state))
                self.assertFalse(world.blocker_checks[9800103].can_reach(state))

    def test_jabu_real_child_action_can_persist_but_adult_boomerang_cannot(self):
        world = self.world
        for age in (Ages.CHILD, Ages.ADULT):
            for names in ((), ('Boomerang',), ('Boomerang', 'Jabu Jabu Tentacle Soul')):
                with self.subTest(age=age, names=names), arrivals(world, (age, J + 'FORK_WEST')):
                    state = inventory(world, age, names)
                    self.assertEqual(state.has(N.event_item('LOGIC_JABU_WEST_TENTACLE'), 1),
                                     age == Ages.CHILD and len(names) == 2)
        with arrivals(world, (Ages.CHILD, J + 'FORK_WEST'), (Ages.ADULT, J + 'FORKED_CORRIDOR')):
            state = inventory(world, Ages.ADULT, ('Boomerang', 'Jabu Jabu Tentacle Soul'))
            self.assertTrue(state.has(N.event_item('LOGIC_JABU_WEST_TENTACLE'), 1))
            self.check_door(8458, state, True)
            self.check_door(8462, state, True)
            # Child can now physically enter the newly opened northeast room
            # and defeat its tentacle too; that second permanent action is real.
            self.assertTrue(state.has(N.event_item('LOGIC_JABU_EAST_TENTACLE'), 1))
            self.check_door(8460, state, True)

    def test_jabu_each_permanent_switch_opens_only_its_actual_paths(self):
        world = self.world
        for age in (Ages.CHILD, Ages.ADULT):
            for flag, allowed in (('WEST', {8458, 8462}), ('EAST', {8460}), ('NORTH', set())):
                with self.subTest(age=age, flag=flag), arrivals(world, (age, J + 'FORKED_CORRIDOR')):
                    state = inventory(world, age, flags=('LOGIC_JABU_' + flag + '_TENTACLE',))
                    for endpoint in (8458, 8460, 8462):
                        self.check_door(endpoint, state, endpoint in allowed)

    def test_jabu_north_clear_requires_biri_soul_at_actual_action_site(self):
        world = self.world
        with arrivals(world, (Ages.CHILD, J + 'FORK_NORTH')):
            names = ('Boomerang', 'Jabu Jabu Tentacle Soul')
            state = inventory(world, Ages.CHILD, names)
            self.assertTrue(state.has(N.event_item('LOGIC_JABU_NORTH_TENTACLE'), 1))
            self.check_door(8461, state, False)
            state.collect(world.create_item('Biri and Bari Soul'), True)
            state.sweep_for_advancements()
            state._soh_extreme_age[1] = Ages.CHILD
            self.check_door(8461, state, True)
        with arrivals(world, (Ages.ADULT, J + 'FORK_NORTH')):
            for names, expected in (((), False), (('Biri and Bari Soul',), False),
                                    (('Biri and Bari Soul', 'Progressive Bow'), True)):
                state = inventory(world, Ages.ADULT, names, ('LOGIC_JABU_NORTH_TENTACLE',))
                self.check_door(8461, state, expected)

    def test_jabu_biri_clear_does_not_claim_tentacle_death(self):
        world = self.world
        with arrivals(world, (Ages.ADULT, J + 'FORK_NORTH')):
            state = inventory(world, Ages.ADULT, ('Biri and Bari Soul', 'Progressive Bow'))
            self.assertFalse(state.has(N.event_item('LOGIC_JABU_NORTH_TENTACLE'), 1))
            self.check_door(8461, state, False)
            self.assertTrue(ER._reachable_as_age(world, state, world.blocker_checks[9800103], Ages.ADULT))

    def test_jabu_shuffled_exit_keeps_clear_gate(self):
        world = self.world
        target = self.fresh_target('Jabu reverse destination')
        with redirect_source(world, 8461, target) as edge, arrivals(world, (Ages.CHILD, J + 'FORK_NORTH')):
            state = inventory(world, Ages.CHILD, ('Boomerang', 'Jabu Jabu Tentacle Soul'))
            self.assertFalse(reached(world, state, target, Ages.CHILD))
            self.check_door(8461, state, False, edge.access_rule)
            state.collect(world.create_item('Biri and Bari Soul'), True)
            state.sweep_for_advancements()
            self.assertTrue(reached(world, state, target, Ages.CHILD))

    def test_jabu_reported_lower_ledge_door_is_its_own_unblocked_route(self):
        world = self.world
        with arrivals(world, (Ages.ADULT, J + 'HOLES_BASEMENT')):
            state = inventory(world, Ages.ADULT)
            self.check_door(8473, state, True)
            self.assertFalse(reached(world, state, J + 'FORK_NORTH', Ages.ADULT))
            self.assertFalse(reached(world, state, J + 'FORK_NORTH_WEST', Ages.ADULT))

    def test_jabu_barrier_arrivals_cannot_damage_their_way_to_open_chest(self):
        world = self.world
        self.assertEqual(world.options.starting_hearts.value, 1)
        for age in (Ages.CHILD, Ages.ADULT):
            for direction, clear in (('NORTH_WEST', 'WEST'), ('NORTH', 'EAST'), ('NORTH_EAST', 'WEST')):
                token = J + 'TO_FORK_' + direction
                with self.subTest(age=age, target=token), arrivals(world, (age, token)):
                    state = inventory(world, age)
                    self.assertFalse(reached(world, state, J + 'FORKED_CORRIDOR', age))
                    self.assertFalse(ER._reachable_as_age(world, state,
                        world.blocker_checks[ER.ENDPOINTS[8473]['check_id']], age))
                    self.assertFalse(state.has(N.event_item('LOGIC_JABU_RUTO_IN_B1'), 1))
                    state = inventory(world, age, flags=('LOGIC_JABU_' + clear + '_TENTACLE',))
                    self.assertTrue(reached(world, state, J + 'FORKED_CORRIDOR', age))
                    self.check_door(8473, state, True)

    def test_reported_8459_arrival_detects_original_damage_only_false_positive(self):
        world = self.world
        target = ER.ENDPOINTS[8459]['target']
        self.assertEqual(target, J + 'TO_FORK_NORTH_WEST')
        edge = next(e for e in region(world, target).exits
                    if e.connected_region.name == ER.region_name(J + 'FORKED_CORRIDOR'))
        old_expression = 'logic->Get(LOGIC_JABU_WEST_TENTACLE) || logic->TakeDamage()'
        old_rule = world._extreme_room_compiler.expr(old_expression, target).resolve(world)
        check = world.blocker_checks[ER.ENDPOINTS[8473]['check_id']]
        with arrivals(world, (Ages.ADULT, target)):
            # This explicit historical-condition control demonstrates that the
            # regression reaches the reported Open Chest check with no items.
            with patch.object(edge, 'access_rule', old_rule):
                prior = inventory(world, Ages.ADULT)
                self.assertTrue(ER._reachable_as_age(world, prior, check, Ages.ADULT))
            fixed = inventory(world, Ages.ADULT)
            self.assertFalse(ER._reachable_as_age(world, fixed, check, Ages.ADULT))

    def test_water_direct_arrival_needs_a_real_switch_approach(self):
        world = self.world
        for age in (Ages.CHILD, Ages.ADULT):
            with self.subTest(age=age), arrivals(world, (age, W + '3_JETS_NO_SWITCH')):
                state = inventory(world, age)
                self.check_door(8877, state, False)
                self.assertFalse(reached(world, state, W + 'CANAL_ALCOVE', age))
                state.collect(world.create_item('Progressive Hookshot'), True)
                state.sweep_for_advancements()
                state._soh_extreme_age[1] = age
                self.check_door(8877, state, age == Ages.ADULT)

    def test_water_walk_on_switch_approach_preserves_free_forward_route(self):
        world = self.world
        for age in (Ages.CHILD, Ages.ADULT):
            with self.subTest(age=age), arrivals(world, (age, W + '3_JETS_SWITCH')):
                state = inventory(world, age)
                self.check_door(8857, state, True)
                self.check_door(8877, state, True)
                self.assertTrue(reached(world, state, W + 'CANAL_ALCOVE', age))
        with arrivals(world, (Ages.ADULT, W + 'CANAL_ALCOVE')):
            state = inventory(world, Ages.ADULT)
            self.check_door(8876, state, True)
            self.check_door(8877, state, False)

    def test_water_child_switch_is_not_an_adult_timed_switch(self):
        world = self.world
        with arrivals(world, (Ages.CHILD, W + '3_JETS_SWITCH'),
                      (Ages.ADULT, W + '3_JETS_NO_SWITCH')):
            state = inventory(world, Ages.CHILD)
            self.check_door(8877, state, True)
            state._soh_extreme_age[1] = Ages.ADULT
            self.check_door(8877, state, False)
            self.assertFalse(reached(world, state, W + 'CANAL_ALCOVE', Ages.ADULT))
            state._soh_extreme_age[1] = Ages.CHILD
            self.check_door(8877, state, True)

    def test_water_same_age_switch_retries_previously_blocked_exit(self):
        world = self.world
        hops = [self.fresh_target('Water approach ' + str(i)) for i in range(3)]
        for a, b in zip(hops, [*hops[1:], region(world, W + '3_JETS_SWITCH')]):
            a.connect(b)
        gate = physical_edge(world, 8877)
        original = gate.access_rule
        evaluations = []
        def observed(state):
            result = original(state)
            evaluations.append((state._soh_extreme_age[1], result))
            return result
        gate.access_rule = observed
        try:
            with arrivals(world, (Ages.ADULT, W + '3_JETS_NO_SWITCH'), (Ages.ADULT, hops[0])):
                state = inventory(world, Ages.ADULT, sweep=False)
                self.assertTrue(reached(world, state, W + 'CANAL_ALCOVE', Ages.ADULT))
                actual = [yes for age, yes in evaluations if age == Ages.ADULT]
                self.assertIn(False, actual)
                self.assertIn(True, actual)
                self.assertLess(actual.index(False), actual.index(True))
        finally:
            gate.access_rule = original

    def test_water_rewired_source_does_not_gain_temporary_flag(self):
        world = self.world
        target = self.fresh_target('Water shuffled destination')
        with redirect_source(world, 8877, target) as edge, arrivals(world, (Ages.ADULT, W + '3_JETS_NO_SWITCH')):
            state = inventory(world, Ages.ADULT, flags=('LOGIC_JABU_NORTH_TENTACLE',))
            self.assertFalse(reached(world, state, target, Ages.ADULT))
            self.check_door(8877, state, False, edge.access_rule)
            state.collect(world.create_item('Progressive Hookshot'), True)
            state.sweep_for_advancements()
            self.assertTrue(reached(world, state, target, Ages.ADULT))

    def test_age_region_rule_is_nonlatching_and_restores_age(self):
        world = self.world
        compiler = world._extreme_room_compiler
        before = dict(compiler.events)
        rule = compiler.expr('areaTable[' + W + '3_JETS_SWITCH].Child()', W + '3_JETS_NO_SWITCH').resolve(world)
        self.assertEqual(before, compiler.events)
        self.assertIn(ER.region_name(W + '3_JETS_SWITCH'), rule.region_dependencies())
        self.assertFalse(rule.caching_enabled)
        state = inventory(world, Ages.ADULT, sweep=False)
        with patch.object(state, 'can_reach_region', side_effect=RuntimeError('fixture')):
            with self.assertRaisesRegex(RuntimeError, 'fixture'):
                rule(state)
        self.assertEqual(state._soh_extreme_age[1], Ages.ADULT)
        for bad in ('areaTable[RR_NOT_A_REAL_ROOM].Child()', 'RegionAdult()', 'RegionChild(true)'):
            with self.assertRaises(OptionError):
                compiler.expr(bad, W + '3_JETS_NO_SWITCH')

    def test_fire_shortcut_requires_reachable_upper_opening_action(self):
        world = self.world
        event = N.event_item('LOGIC_FIRE_OPENED_UPPER_SHORTCUT')
        with arrivals(world, (Ages.ADULT, F + 'SHORTCUT_ROOM')):
            state = inventory(world, Ages.ADULT)
            self.assertFalse(state.has(event, 1))
            self.assertFalse(reached(world, state, F + 'SHORTCUT_CLIMB', Ages.ADULT))
        with arrivals(world, (Ages.ADULT, F + 'BOULDER_MAZE_UPPER')):
            state = inventory(world, Ages.ADULT)
            self.assertFalse(state.has(event, 1))
            state.collect(world.create_item('Bombchu Bag'), True)
            state.sweep_for_advancements()
            self.assertTrue(state.has(event, 1))
            self.assertTrue(reached(world, state, F + 'SHORTCUT_ROOM', Ages.ADULT))

    def test_shadow_shortcut_requires_dock_action_and_climb_to_return(self):
        world = self.world
        strength = ('Strength Upgrade',) * 2
        event = N.event_item('LOGIC_SHADOW_SHORTCUT_BLOCK')
        with arrivals(world, (Ages.ADULT, SH + 'SPINNING_BLADES')):
            state = inventory(world, Ages.ADULT, strength)
            self.assertFalse(state.has(event, 1))
            self.assertFalse(reached(world, state, SH + 'DOCK', Ages.ADULT))
        with arrivals(world, (Ages.ADULT, SH + 'DOCK')):
            state = inventory(world, Ages.ADULT, strength)
            self.assertTrue(state.has(event, 1))
            self.assertFalse(reached(world, state, SH + 'SPINNING_BLADES', Ages.ADULT))
            state.collect(world.create_item('Climb'), True)
            self.assertTrue(reached(world, state, SH + 'SPINNING_BLADES', Ages.ADULT))

    def test_spirit_shortcut_does_not_get_remote_hammer_action_for_free(self):
        world = self.world
        event = N.event_item('LOGIC_SPIRIT_STATUE_SOUTH_DOOR')
        with arrivals(world, (Ages.ADULT, S + 'STATUE_ROOM')):
            state = inventory(world, Ages.ADULT, ('Megaton Hammer',))
            self.assertFalse(state.has(event, 1))
            self.check_door(9007, state, False)
        for age in (Ages.CHILD, Ages.ADULT):
            with self.subTest(age=age), arrivals(world, (age, S + 'SHORTCUT_SWITCH')):
                state = inventory(world, age, ('Megaton Hammer',))
                self.assertEqual(state.has(event, 1), age == Ages.ADULT)
        with arrivals(world, (Ages.ADULT, S + 'SHORTCUT')):
            state = inventory(world, Ages.ADULT)
            self.check_door(9006, state, True)

    def test_crawl_routes_stay_child_only_with_crawl_owned(self):
        world = self.world
        for age in (Ages.CHILD, Ages.ADULT):
            with self.subTest(age=age), arrivals(world, (age, 'RR_BOTW_ENTRYWAY')):
                state = inventory(world, age, ('Crawl',))
                self.assertEqual(reached(world, state, 'RR_BOTW_CORRIDOR', age), age == Ages.CHILD)

    def test_existing_shortcut_endpoints_remain_in_all_enabled_pools(self):
        world = self.world
        selected = {row['id'] for row in ER._eligible(world)}
        for a, b in ((1238, 1250), (477, 1242), (808, 1376)):
            self.assertEqual(ER.ENDPOINTS[a]['reverse'], b)
            self.assertEqual(ER.ENDPOINTS[b]['reverse'], a)
            self.assertEqual(ER.ENDPOINTS[a]['category'], 'overworld')
            self.assertTrue({a, b} <= selected)
        for endpoint in (8716, 8717, 8758, 8759, 9006, 9007):
            self.assertIn(endpoint, selected)
        self.assertEqual(ER.mixed_categories(world), ER.enabled_categories(world))
        self.assertFalse(any('shortcut' in name for name in world.options_dataclass.type_hints))

    def test_z_restore_reported_map_removes_damage_only_starting_progression(self):
        if self.reported_seed is None:
            self.skipTest('No exactly reproduced user entrance map supplied')
        world = self.world
        evidence = self.reported_seed
        self.assertTrue(evidence['all_placements_match_uploaded_spoiler'])
        self.assertEqual(evidence['matching_placements'], 4036)
        self.assertEqual(evidence['seed'], 75502037396837836795)
        mapping = {int(key): value for key, value in evidence['mapping'].items()}
        self.assertEqual(len(mapping), 719)
        self.assertEqual(mapping[606], 8459)
        self.assertEqual(mapping[642], 896)
        world.using_ut = True
        world.passthrough = {'entrance_randomizer': {
            'revision': ER.REVISION,
            'destination_policy_revision': ER.Safety.POLICY_REVISION,
            'connections': evidence['mapping'],
        }}
        ER.connect(world)
        self.assertEqual(world._er_mapping, mapping)
        # The immutable release reproduction swept only local events; its
        # starting inventory was these two explicitly listed quest items.
        names = ("Zelda's Letter", 'Weird Egg')
        check = world.blocker_checks[ER.ENDPOINTS[8473]['check_id']]
        fixed = inventory(world, Ages.ADULT, names)
        fixed_open = ER._reachable_as_age(world, fixed, check, Ages.ADULT)
        self.assertFalse(fixed_open)
        target = J + 'TO_FORK_NORTH_WEST'
        self.assertTrue(reached(world, fixed, target, Ages.ADULT))
        self.assertFalse(reached(world, fixed, J + 'FORKED_CORRIDOR', Ages.ADULT))
        # Keep this exact saved map and all current rules; restoring only the
        # old three damage escape clauses must reproduce the initial overreach.
        with ExitStack() as patches:
            for direction, clear in (('NORTH_WEST', 'WEST'), ('NORTH', 'EAST'), ('NORTH_EAST', 'WEST')):
                token = J + 'TO_FORK_' + direction
                edge = next(e for e in region(world, token).exits
                            if e.connected_region.name == ER.region_name(J + 'FORKED_CORRIDOR'))
                expression = 'logic->Get(LOGIC_JABU_' + clear + '_TENTACLE) || logic->TakeDamage()'
                old_rule = world._extreme_room_compiler.expr(expression, token).resolve(world)
                patches.enter_context(patch.object(edge, 'access_rule', old_rule))
            prior = inventory(world, Ages.ADULT, names)
            prior_open = ER._reachable_as_age(world, prior, check, Ages.ADULT)
            self.assertTrue(prior_open)
        type(self).restored_seed_results = {
            'seed': evidence['seed'], 'mapping_entries': len(mapping),
            'saved_map_restored_by_production_er_connect': True,
            'adult_spawn_source': 642, 'adult_spawn_target': 896,
            'reported_corridor_source': 606, 'reported_corridor_target': 8459,
            'starting_age': 'adult', 'starting_hearts': world.options.starting_hearts.value,
            'starting_inventory': list(names),
            'open_chest_check': ER.ENDPOINTS[8473]['check_id'],
            'old_damage_clause_control_can_reach_open_chest': prior_open,
            'corrected_graph_can_reach_open_chest': fixed_open,
            'new_seed_required_for_corrected_placement': True,
            'scope': 'Restored the exactly reproduced719-entry map through production ER.connect; compared old versus corrected damage clauses. No new fill or game playthrough is claimed.',
        }

    def fresh_target(self, suffix):
        target = SohRegion('Blocker fixture ' + suffix, 1, self.world.multiworld)
        self.world.multiworld.regions.append(target)
        return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--yaml', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--reported-seed', type=Path,
                        help='Parent exact-reproduction report with matching placements and saved mapping')
    args = parser.parse_args()
    started = time.monotonic()
    if args.reported_seed:
        EntranceBlockerTests.reported_seed = json.loads(args.reported_seed.read_text())
    seed = EntranceBlockerTests.reported_seed['seed'] if EntranceBlockerTests.reported_seed else 188
    EntranceBlockerTests.world = build_world(args.yaml, seed)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(EntranceBlockerTests)
    output = io.StringIO()
    result = unittest.TextTestRunner(stream=output, verbosity=2).run(suite)
    print(output.getvalue(), end='')
    report = {
        'status': 'passed' if result.wasSuccessful() else 'failed',
        'scope': __doc__,
        'ap_version': Utils.__version__,
        'world_version': EntranceBlockerTests.world.world_version.as_simple_string(),
        'tests_run': result.testsRun,
        'failures': [(str(test), error) for test, error in result.failures],
        'errors': [(str(test), error) for test, error in result.errors],
        'skipped': [(str(test), why) for test, why in result.skipped],
        'elapsed_seconds': round(time.monotonic() - started, 3),
        'yaml_sha256': sha256(args.yaml.read_bytes()).hexdigest(),
        'source_hashes': {name: sha256((SOURCE / name).read_bytes()).hexdigest() for name in SOURCE_FILES},
        'runtime_output': output.getvalue(),
        'reported_seed_restoration': EntranceBlockerTests.restored_seed_results,
        'reported_seed_evidence_sha256': sha256(args.reported_seed.read_bytes()).hexdigest() if args.reported_seed else None,
        'evidence': {
            'Jabu8461': 'Room8 side1 FRONT_CLEAR params127; tentacle switch10 and four Biri room clear are separate actions.',
            'Jabu8459': 'Adult one-heart direct arrival at ToForkNorthWest cannot reach OpenChest8473 until its WEST tentacle switch clears; historical TakeDamage-only control reproduces the false positive.',
            'Water8877': 'Room15 side1 FRONT_SWITCH params190 flag62; same-age switch-side approach required on each visit.',
            'permanent_tentacles': {'north': 10, 'west': 11, 'east': 12},
            'shortcuts': 'Existing physical shortcut endpoints remain selected; open movement/crawl passages retain their source graph rules.',
            'user_spoiler': 'The separate immutable1.8.7 reproduction established all4036 placements; this suite accepts its saved mapping only when that exact-match evidence is supplied.',
        },
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
