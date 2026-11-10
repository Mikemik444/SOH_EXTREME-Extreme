"""Regression: tentative entrance maps must not reconnect unchanged physical doors.

Run with the rest of the SOH-EXTREME stdlib unittest suite; no Archipelago
runtime imports are necessary to verify the pure edge-selection helper.
"""
import ast
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / 'EntranceRandomizer.py'


def changed_route_ids():
    parsed = ast.parse(SOURCE.read_text(encoding='utf-8'))
    helper = next(n for n in parsed.body
                  if isinstance(n, ast.FunctionDef) and n.name == '_changed_route_ids')
    namespace = {}
    exec(compile(ast.Module(body=[helper], type_ignores=[]), str(SOURCE), 'exec'), namespace)
    return namespace['_changed_route_ids']


class IncrementalRoutingTests(unittest.TestCase):
    def test_first_install_reconnects_all_721_edges(self):
        current = {endpoint: endpoint for endpoint in range(721)}
        self.assertEqual(changed_route_ids()({}, current), list(current))

    def test_identical_candidate_reuses_every_edge(self):
        current = {endpoint: endpoint for endpoint in range(721)}
        self.assertEqual(changed_route_ids()(current, current.copy()), [])

    def test_pair_swap_reconnects_only_modified_edges(self):
        original = {endpoint: endpoint for endpoint in range(721)}
        candidate = dict(original)
        candidate[34], candidate[35], candidate[36], candidate[37] = 35, 34, 37, 36
        self.assertEqual(changed_route_ids()(original, candidate), [34, 35, 36, 37])
        self.assertEqual(changed_route_ids()(candidate, original), [34, 35, 36, 37])

    def test_rejected_candidate_is_compared_against_installed_not_accepted(self):
        accepted = {endpoint: endpoint for endpoint in range(721)}
        rejected = dict(accepted)
        rejected[20] = 99
        next_candidate = dict(accepted)
        next_candidate[21] = 55
        # The second candidate must restore door 20 *and* update door 21.
        self.assertEqual(changed_route_ids()(rejected, next_candidate), [20, 21])

    def test_full_validation_is_not_skipped(self):
        source = SOURCE.read_text(encoding='utf-8')
        self.assertIn('_starting_state_is_viable(world, candidate, edges, fill_locations)', source)
        self.assertIn('_physical_start_is_connected(world, inventory, age)', source)
        self.assertIn('_age_routes_are_safe(world, world._er_mapping, edges, state)', source)
        self.assertIn('assert_installed_topology()', source)
        self.assertIn('apply(mapping, update_labels=True)', source)


if __name__ == '__main__':
    unittest.main()
