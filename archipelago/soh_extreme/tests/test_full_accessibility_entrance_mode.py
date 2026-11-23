"""Regressions for Goal Reachable + Full accessibility incompatibility.

Run without Archipelago imports: only extract the production policy functions
from the exact EntranceRandomizer.py that will be shipped in the APWorld.
"""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'EntranceRandomizer.py'


def load_policy():
    program = ast.parse(SOURCE.read_text(encoding='utf-8'))
    wanted = {'_requested_goal_reachability', '_is_full_accessibility',
              '_is_goal_reachability', '_entrance_objective_met'}
    nodes = [node for node in program.body
             if isinstance(node, ast.FunctionDef) and node.name in wanted]
    assert {node.name for node in nodes} == wanted
    namespace = {}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), 'exec'), namespace)
    return namespace


def world(reachability, accessibility):
    return SimpleNamespace(options=SimpleNamespace(
        entrance_reachability=SimpleNamespace(value=reachability),
        accessibility=SimpleNamespace(current_key=accessibility)))


class EffectiveEntrancePolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = load_policy()

    def test_goal_plus_full_preserves_requested_goal_mode(self):
        check = self.policy['_is_goal_reachability']
        requested = self.policy['_requested_goal_reachability']
        setting = world(1, 'full')
        self.assertTrue(requested(setting))
        self.assertTrue(check(setting))
        self.assertEqual(setting.options.entrance_reachability.value, 1)

    def test_goal_plus_minimal_remains_goal_only(self):
        self.assertTrue(self.policy['_is_goal_reachability'](world(1, 'minimal')))

    def test_all_destinations_never_becomes_goal_only(self):
        check = self.policy['_is_goal_reachability']
        for access in ('full', 'minimal', 'items'):
            with self.subTest(access=access):
                self.assertFalse(check(world(0, access)))

    def test_full_policy_does_not_override_goal(self):
        self.assertTrue(self.policy['_is_goal_reachability'](world(1, 'FULL')))

    def test_strict_check_rejects_missing_optional_destination_even_if_goal_met(self):
        checks = [SimpleNamespace(can_reach=lambda s: True)]
        regions = [SimpleNamespace(can_reach=lambda s: False)]
        mw = SimpleNamespace(has_beaten_game=lambda s, p: True)
        w = SimpleNamespace(multiworld=mw, player=1)
        f = self.policy['_entrance_objective_met']
        self.assertFalse(f(w, object(), False, checks, regions))
        self.assertTrue(f(w, object(), True, checks, regions))

    def test_strict_check_rejects_missing_optional_location(self):
        checks = [SimpleNamespace(can_reach=lambda s: False)]
        mw = SimpleNamespace(has_beaten_game=lambda s, p: True)
        w = SimpleNamespace(multiworld=mw, player=1)
        self.assertFalse(self.policy['_entrance_objective_met'](
            w, object(), False, checks, []))

    def test_generation_and_slot_metadata_use_effective_mode(self):
        source = SOURCE.read_text(encoding='utf-8')
        self.assertIn('goal_only = _is_goal_reachability(world)', source)
        self.assertIn("'reachability_mode': 'goal_reachable' if _is_goal_reachability(world)", source)
        self.assertIn('if goal_only and _is_full_accessibility(world):', source)
        self.assertIn('required_probes = [] if goal_only else _distinct_reachability_probes(required)', source)


if __name__ == '__main__':
    unittest.main()
