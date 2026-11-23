"""Focused regression tests for Goal Reachable + Full source-only optimization.

Runs with Python's standard library and exercises the production pruning
function extracted from SceneTransitions.py, not a reimplementation.
"""
import ast
import logging
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Classification:
    progression = 1
    useful = 2


class ProgressType:
    EXCLUDED = 99
    DEFAULT = 0


class OptionError(Exception):
    pass


class RegisteredLocations(list):
    def __init__(self, names, initial):
        super().__init__(initial)
        self.names = names

    def remove(self, obj):
        super().remove(obj)
        del self.names[obj.name]


class World:
    def __init__(self, *, goal=True, accessibility='full', fillers=4):
        self.player = 2
        self.using_ut = False
        self.options = types.SimpleNamespace(
            entrance_reachability=types.SimpleNamespace(value=int(goal)),
            accessibility=types.SimpleNamespace(current_key=accessibility),
        )
        self.cache = {}
        self.region = types.SimpleNamespace()
        self.region.locations = RegisteredLocations(self.cache, [])
        self.item_pool = []
        self.multiworld = types.SimpleNamespace()
        self.multiworld.itempool = []
        self.multiworld.get_all_state = lambda *args, **kwargs: object()
        self._scene_transition_entries = ({'name': 'Door [Child]', 'id': 1002},
                                          {'name': 'Door [Adult]', 'id': 1003})
        self.calls = 0
        self.location_list = []
        for index in range(fillers):
            self.multiworld.itempool.append(types.SimpleNamespace(
                name='Recovery Heart', player=2, classification=0, code=100+index))
        # An advancement item must never be taken to balance a check count.
        self.multiworld.itempool.append(types.SimpleNamespace(
            name='Climb', player=2, classification=Classification.progression, code=701))
        # Remote player's filler is unrelated to the SOH pool.
        self.multiworld.itempool.append(types.SimpleNamespace(
            name='Blue Rupee', player=1, classification=0, code=802))
        self.item_pool = list(self.multiworld.itempool)

    def add(self, name, address, reach, *, player=2, item=None, progress_type=0):
        loc = types.SimpleNamespace(name=name, address=address,
                                    item=item, progress_type=progress_type,
                                    parent_region=self.region,
                                    can_reach=lambda state: reach)
        self.location_list.append(loc)
        self.region.locations.append(loc)
        self.cache[name] = loc
        return loc

    def get_locations(self):
        return list(self.location_list) if False else list(self.cache.values())


# Do not depend on an installed Archipelago runtime for unit tests: compile
# the exact production function, with imports removed and injected stubs.
source = ROOT / 'SceneTransitions.py'
tree = ast.parse(source.read_text())
function = next(x for x in tree.body if isinstance(x, ast.FunctionDef)
                and x.name == 'retire_unreachable_goal_checks')
function = ast.fix_missing_locations(ast.FunctionDef(
    name=function.name, args=function.args, decorator_list=[], returns=None,
    type_comment=None,
    body=[x for x in function.body if not isinstance(x, (ast.ImportFrom, ast.Import))],
))
ns = dict(_is_goal_reachability=lambda w: bool(w.options.entrance_reachability.value),
          _is_full_accessibility=lambda w: w.options.accessibility.current_key == 'full',
          ItemClassification=Classification, LocationProgressType=ProgressType,
          OptionError=OptionError, logging=logging)
exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), 'exec'), ns)
prune = ns['retire_unreachable_goal_checks']


class GoalFullPruningTests(unittest.TestCase):
    def test_retire_only_unreachable_unfilled_own_checks(self):
        w = World(fillers=4)
        unreachable = w.add('Door [Child]', 1002, False)
        w.add('Door [Adult]', 1003, True)
        w.add('Regular Chest', 1004, False)
        w.add('Reachable Chest', 1005, True)
        w.add('Collected Event', None, False)
        w.add('Remote Check', 1500, False, player=1)  # not in SOH get_locations realistically
        w.add('Placed Check', 1006, False, item='already placed')
        w.add('Excluded Check', 1007, False, progress_type=ProgressType.EXCLUDED)
        # World.get_locations returns only this player's registry, like real AP.
        w.location_list.remove(next(loc for loc in w.location_list if loc.name == 'Remote Check'))
        w.region.locations.remove(next(loc for loc in w.region.locations if loc.name == 'Remote Check'))
        w.get_locations = lambda: list(w.location_list)
        self.assertEqual(prune(w), 2)
        self.assertNotIn('Door [Child]', w.cache)
        self.assertNotIn('Regular Chest', w.cache)
        self.assertIn('Door [Adult]', w.cache)
        self.assertIn('Reachable Chest', w.cache)
        self.assertIn('Placed Check', w.cache)
        self.assertIn('Excluded Check', w.cache)
        self.assertEqual([entry['name'] for entry in w._scene_transition_entries], ['Door [Adult]'])
        self.assertEqual(sum(i.name == 'Recovery Heart' for i in w.multiworld.itempool), 2)
        self.assertEqual(sum(i.name == 'Climb' for i in w.multiworld.itempool), 1)
        self.assertEqual(sum(i.player == 1 for i in w.multiworld.itempool), 1)

    def test_all_destinations_never_prunes(self):
        w = World(goal=False)
        w.add('Regular Chest', 42, False)
        self.assertEqual(prune(w), 0)
        self.assertIn('Regular Chest', w.cache)

    def test_goal_minimal_never_prunes(self):
        w = World(accessibility='minimal')
        w.add('Regular Chest', 42, False)
        self.assertEqual(prune(w), 0)
        self.assertIn('Regular Chest', w.cache)

    def test_filler_shortage_fails_without_mutating(self):
        w = World(fillers=0)
        w.add('Regular Chest', 42, False)
        before = list(w.multiworld.itempool)
        with self.assertRaises(OptionError):
            prune(w)
        self.assertEqual(before, w.multiworld.itempool)
        self.assertIn('Regular Chest', w.cache)

    def test_post_fill_does_not_repeat_expensive_simulation(self):
        text = (ROOT / '__init__.py').read_text()
        self.assertIn('SceneTransitions.retire_unreachable_goal_checks(self)', text)
        self.assertNotIn('validate_filled_world(self)', text)


if __name__ == '__main__':
    unittest.main()
