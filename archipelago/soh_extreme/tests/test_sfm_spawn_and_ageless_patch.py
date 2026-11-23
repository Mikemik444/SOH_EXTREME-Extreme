"""Dependency-free checks for SFM child spawn, cross-age Bow and the native client."""
import ast
import pathlib
import types
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class SafeSpawnRegression(unittest.TestCase):
    def test_minute_pad_not_child_start_when_climb_shuffled(self):
        source = (ROOT / "EntranceRandomizer.py").read_text('utf8')
        tree = ast.parse(source)
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                  and n.name == '_spawn_destination_allowed')
        ns = {'SFM_MINUET_WARP_PAD': 1536}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])),
                     '<spawn>', 'exec'), ns)
        child = {'category': 'child_spawn'}
        adult = {'category': 'adult_spawn'}
        for shuffle in (0, 1):
            world = types.SimpleNamespace(options=types.SimpleNamespace(
                shuffle_climb=types.SimpleNamespace(value=shuffle)))
            self.assertEqual(ns['_spawn_destination_allowed'](world, child, 1536), not shuffle)
            self.assertTrue(ns['_spawn_destination_allowed'](world, adult, 1536))
            self.assertTrue(ns['_spawn_destination_allowed'](world, child, 252))
        self.assertIn('_spawn_destination_allowed(world, source, target', source)
        self.assertIn('def _place_one_way(', source)
        self.assertIn('def _validate_spawn_pools(', source)
        # Kept separate so that pre-existing UT/server maps can still load.
        validate = source.split('def validate_mapping(',1)[1].split('def _one_way_targets(',1)[0]
        self.assertNotIn('_spawn_destination_allowed', validate)

    def test_meadow_gate_not_free_for_child_without_climb(self):
        source = (ROOT / '_vendor_oot_soh/location_access/overworld/sacred_forest_meadow.py').read_text('utf8')
        node = source.split('connect_regions(Regions.SACRED_FOREST_MEADOW, world, [', 1)[1].split('])',1)[0]
        self.assertNotIn('(Regions.SFM_ENTRYWAY, lambda bundle: True_())',node)
        self.assertIn('can_climb(bundle)',node)
        self.assertIn('CanReachRegion(str(Regions.SFM_ENTRYWAY))',node)

    def test_real_bow_wonder_rules_follow_unlock(self):
        source = (ROOT / '__init__.py').read_text('utf8')
        for symbol in ['RC_TH_WONDER_', 'RC_SHADOW_TEMPLE_WONDER_THREE_POTS',
                       'RC_GERUDO_TRAINING_GROUND_WONDER_BEAMOS_ROOM']:
            self.assertIn(symbol,source)
        self.assertIn('rule = can_use(Items.FAIRY_BOW, bundle)',source)


if __name__ == '__main__':
    unittest.main()
