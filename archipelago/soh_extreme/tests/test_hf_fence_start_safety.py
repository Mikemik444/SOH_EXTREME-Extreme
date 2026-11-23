"""Regression for the fenced Lake Hylia landing used by shuffled entrances.

The fence-side arrival ID 393 is not central Hyrule Field. A player with
shuffled Climb must never be stranded there by a shuffled entry or spawn.
These tests execute the production predicates extracted from their AST without
requiring an installed Archipelago runtime.
"""
import ast
from pathlib import Path
from collections import defaultdict
from random import Random
from types import SimpleNamespace
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'EntranceRandomizer.py'
CATALOG_SOURCE = Path(__file__).resolve().parents[1] / 'EntranceCatalog.json'


def load_functions(*names, **globals_):
    parsed = ast.parse(SOURCE.read_text(encoding='utf-8'))
    body = [node for node in parsed.body
            if isinstance(node, ast.FunctionDef) and node.name in names]
    assert len(body) == len(names), names
    namespace = dict(globals_)
    exec(compile(ast.Module(body=body, type_ignores=[]), str(SOURCE), 'exec'), namespace)
    return tuple(namespace[name] for name in names)


def world(climb=True, ut=False):
    return SimpleNamespace(options=SimpleNamespace(shuffle_climb=SimpleNamespace(value=climb)),
                           using_ut=ut, random=Random(17))


class FenceSafetyTests(unittest.TestCase):
    def test_pair_stays_vanilla_when_climb_is_shuffled(self):
        fence_locked, = load_functions('_fence_pair_must_stay_vanilla')
        self.assertTrue(fence_locked(world()))
        self.assertFalse(fence_locked(world(climb=False)))
        self.assertFalse(fence_locked(world(ut=True)))  # preserve old UT seeds

    def test_one_way_spawns_cannot_target_fence_side_without_climb(self):
        import json
        catalog = json.loads(CATALOG_SOURCE.read_text(encoding='utf-8'))
        # A reverse half is normally absent from one-way pools, but verify
        # the fence guard even if a future catalog marks it primary.
        augmented = [dict(e, primary=True) if e['id'] == 393 else e for e in catalog]
        fence_locked, targets = load_functions('_fence_pair_must_stay_vanilla', '_one_way_targets',
            CATALOG=augmented, Safety=SimpleNamespace(allowed_route=lambda a,b: True),
            mixed_categories=lambda w: {'child_spawn', 'overworld'},
            enabled_categories=lambda w: {'child_spawn', 'overworld'},
            _river_path_revision=lambda w: 1, RIVER_WATER_ALIASES={},
            HF_LAKE_TO_FENCE=393)
        targets.__globals__['_fence_pair_must_stay_vanilla'] = fence_locked
        child_spawn = next(row for row in catalog if row['category'] == 'child_spawn')
        ids = {row['id'] for row in targets(world(), child_spawn)}
        self.assertNotIn(393, ids)
        self.assertIn(258, ids)
        self.assertIn(393, {row['id'] for row in targets(world(climb=False), child_spawn)})

    def test_paired_entrances_cannot_shuffle_into_fence_landing(self):
        import json
        catalog = json.loads(CATALOG_SOURCE.read_text(encoding='utf-8'))
        ids = {e['id'] for e in catalog}
        fence_locked, candidate = load_functions('_fence_pair_must_stay_vanilla', '_candidate',
            _eligible=lambda w: [e for e in catalog if e['category'] == 'overworld'],
            mixed_categories=lambda w: set(),
            _paired_pool_key=lambda e,m: e['category'],
            _one_way_targets=lambda w,e: [],
            _spawn_destination_allowed=lambda w,e,t: True,
            LOCAL_CARRIER_DOORS=frozenset(), HF_FENCE_TO_LAKE=258,
            defaultdict=defaultdict,
            HF_LAKE_TO_FENCE=393)
        candidate.__globals__['_fence_pair_must_stay_vanilla'] = fence_locked
        shuffled = candidate(world())
        self.assertEqual(shuffled[258], 258)
        self.assertEqual(shuffled[393], 393)
        self.assertTrue(set(shuffled).issubset(ids))
        # The ordinary pair pool is still shuffled, not disabled globally.
        self.assertGreater(len(shuffled), 2)

    def test_arrival_to_fenced_hyrule_field_requires_real_climb(self):
        class Rule:
            def resolve(self, _world):
                return lambda state: bool(state.climb)
        w = world()
        w.registered = []
        w.register_rule_dependencies = w.registered.append
        H = SimpleNamespace(can_climb=lambda bundle: Rule())
        arrival, = load_functions('_arrival_rule',
            H=H, HF_LAKE_TO_FENCE=393, WATER_SUBMERGED_ENDPOINTS=frozenset(),
            WATER_ARRIVAL_LEVELS={}, resolve_enemy_region=lambda x: x)
        self.assertFalse(arrival(w, {'id':393, 'target':'HYRULE_FIELD'})(SimpleNamespace(climb=False)))
        self.assertTrue(arrival(w, {'id':393, 'target':'HYRULE_FIELD'})(SimpleNamespace(climb=True)))
        self.assertEqual(len(w.registered), 2)

    def test_both_stock_directions_require_climb_not_swim(self):
        base = SOURCE.parent / '_vendor_oot_soh/location_access/overworld'
        for filename in ('hyrule_field.py', 'lake_hylia.py'):
            text = (base / filename).read_text(encoding='utf-8')
            self.assertRegex(text, r'\(Regions\.(?:LAKE_HYLIA|HYRULE_FIELD), lambda bundle: can_climb\(bundle\)\)')
            self.assertNotIn('can_climb(bundle) | can_swim(bundle) | can_use(Items.EPONA, bundle)', text)


if __name__ == '__main__':
    unittest.main()
