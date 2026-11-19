"""Physical Gerudo / Bow-only sanity regressions, executable without Archipelago.

Run: python -m unittest discover -s soh_extreme/tests -p test_gerudo_physical_age_regressions.py -v
These tests evaluate source AST expressions, not reimplemented logic.
"""
import ast
import json
import pathlib
import types
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class Rule:
    def __init__(self, predicate):
        self.predicate = predicate

    def __call__(self, state):
        return self.predicate(state)

    def __and__(self, other):
        return Rule(lambda state: self(state) and other(state))

    def __or__(self, other):
        return Rule(lambda state: self(state) or other(state))


def as_rule(fn):
    return Rule(fn)


class Names:
    def __getattr__(self, name):
        return 'Gerudo Membership Card' if name == 'GERUDO_MEMBERSHIP_CARD' else name

    def __getitem__(self, name):
        return name


def evaluate_expression(expr, env):
    compiled = compile(ast.fix_missing_locations(ast.Expression(expr)), '<soh-extreme source>', 'eval')
    return eval(compiled, env)


class GerudoPhysicalAgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.main = ast.parse((ROOT / '__init__.py').read_text('utf-8'))
        cls.native = ast.parse((ROOT / '_vendor_oot_soh/location_access/overworld/gerudo_fortress.py').read_text('utf-8'))
        cls.speech = ast.parse((ROOT / 'NpcSpeech.py').read_text('utf-8'))
        cls.catalog = {entry['id']: entry for entry in json.loads((ROOT / 'NpcSpeechCatalog.json').read_text('utf-8'))}

    def env(self):
        return {
            'Items': Names(),
            'EventLocations': Names(),
            'LocalEvents': Names(),
            'Regions': Names(),
            'is_adult': lambda b: as_rule(lambda s: s['age'] == 'adult'),
            'is_child': lambda b: as_rule(lambda s: s['age'] == 'child'),
            'can_use': lambda item, b: as_rule(lambda s: item in s['items']),
            'has_item': lambda item, b: as_rule(lambda s: item in s['items']),
            'can_climb': lambda b: as_rule(lambda s: 'Climb' in s['items']),
            'can_interact_path_blocker': lambda b, lang: as_rule(lambda s: 'NPC Soul' in s['items'] and 'Speak Gerudo' in s['items']),
            'can_break_crates': lambda b: as_rule(lambda s: 'Break Crates' in s['items']),
            'bundle': None,
        }

    def find_wonder_rule(self, rc):
        matches = []
        for node in ast.walk(self.main):
            if isinstance(node, ast.If) and 'rc' in ast.unparse(node.test):
                if not node.body or not isinstance(node.body[0], ast.Assign):
                    continue
                expr = node.body[0].value
                if isinstance(expr, ast.Constant) and expr.value is None:
                    continue
                # Execute real branch predicate to find the selected rule.
                try:
                    if eval(compile(ast.Expression(node.test), '<wonder predicate>', 'eval'), {'rc': rc}):
                        if 'rule' in [t.id for t in node.body[0].targets if isinstance(t, ast.Name)]:
                            matches.append(expr)
                except (NameError, TypeError, AttributeError):
                    continue
        bow_matches = [r for r in matches if 'FAIRY_BOW' in ast.unparse(r)]
        self.assertEqual(len(bow_matches), 1, f'{rc}: expected one explicit Bow rule, found {len(bow_matches)}')
        return evaluate_expression(bow_matches[0], self.env())

    def test_all_bow_only_hideout_wonders_reject_child_even_with_bow(self):
        rc_ids = [
            'RC_TH_WONDER_1_TORCH_1', 'RC_TH_WONDER_1_TORCH_2',
            'RC_TH_WONDER_BREAK_ROOM_BOTTOM_SKULL', 'RC_TH_WONDER_BREAK_ROOM_TOP_SKULL',
            'RC_TH_WONDER_DEAD_END_SKULL_ENTRANCE', 'RC_TH_WONDER_DEAD_END_SKULL_NEAR_JAIL',
            'RC_TH_WONDER_DOUBLE_JAIL_LOWER_EXIT', 'RC_TH_WONDER_DOUBLE_JAIL_UPPER_EXIT',
            'RC_TH_WONDER_KITCHEN_SKULL',
            'RC_TH_WONDER_STEEP_SLOPE_LOWER_EXIT', 'RC_TH_WONDER_STEEP_SLOPE_UPPER_EXIT',
        ]
        for rc in rc_ids:
            with self.subTest(rc=rc):
                rule = self.find_wonder_rule(rc)
                self.assertFalse(rule({'age': 'child', 'items': {'FAIRY_BOW', 'FAIRY_SLINGSHOT'}}))
                self.assertFalse(rule({'age': 'adult', 'items': {'FAIRY_SLINGSHOT'}}))
                self.assertTrue(rule({'age': 'adult', 'items': {'FAIRY_BOW'}}))

    def test_other_bow_only_wonders_are_not_child_usable(self):
        for rc in ('RC_GERUDO_TRAINING_GROUND_WONDER_BEAMOS_ROOM',
                   'RC_GERUDO_TRAINING_GROUND_WONDER_TORCH_SLUGS_ROOM',
                   'RC_SHADOW_TEMPLE_WONDER_THREE_POTS'):
            with self.subTest(rc=rc):
                rule = self.find_wonder_rule(rc)
                self.assertFalse(rule({'age': 'child', 'items': {'FAIRY_BOW'}}))
                self.assertTrue(rule({'age': 'adult', 'items': {'FAIRY_BOW'}}))

    def find_native_location(self, location_name):
        for node in ast.walk(self.native):
            if isinstance(node, ast.Tuple) and len(node.elts) >= 2 and \
                    isinstance(node.elts[0], ast.Attribute) and node.elts[0].attr == location_name and \
                    isinstance(node.elts[-1], ast.Lambda):
                return evaluate_expression(node.elts[-1], self.env())
        self.fail('native location rule not found: ' + location_name)

    def test_above_jail_crate_exists_only_for_adult(self):
        crate = self.find_native_location('GF_ABOVE_JAIL_CRATE')(None)
        self.assertFalse(crate({'age': 'child', 'items': {'Break Crates'}}))
        self.assertFalse(crate({'age': 'adult', 'items': set()}))
        self.assertTrue(crate({'age': 'adult', 'items': {'Break Crates'}}))
        main_text = (ROOT / '__init__.py').read_text('utf-8')
        self.assertIn('require_native_existing(gf_jail_crate, is_adult(gf_crate_bundle))', main_text)

    def test_fortress_side_gate_requires_adult_card_climb_and_npc_access(self):
        gate_rule = self.find_native_location('GF_GATE')(None)
        full = {'Gerudo Membership Card', 'Climb', 'NPC Soul', 'Speak Gerudo'}
        self.assertTrue(gate_rule({'age': 'adult', 'items': full}))
        self.assertFalse(gate_rule({'age': 'child', 'items': full}))
        for missing in full:
            with self.subTest(missing=missing):
                self.assertFalse(gate_rule({'age': 'adult', 'items': full - {missing} | {'LONGSHOT'}}))

    def test_unsafe_longshot_to_upper_vines_needs_card_for_adult(self):
        found = []
        for node in ast.walk(self.native):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == 'connect_regions' and len(node.args) >= 3
                    and ast.unparse(node.args[0]) == 'Regions.GF_NEAR_GROTTO'
                    and isinstance(node.args[2], ast.List)):
                for row in node.args[2].elts:
                    if (isinstance(row, ast.Tuple) and len(row.elts) == 2
                            and ast.unparse(row.elts[0]) == 'Regions.GF_TOP_OF_UPPER_VINES'):
                        found.append(evaluate_expression(row.elts[1], self.env()))
        self.assertEqual(len(found), 1)
        rule = found[0](None)
        self.assertFalse(rule({'age': 'adult', 'items': {'LONGSHOT'}}))
        self.assertTrue(rule({'age': 'adult', 'items': {'LONGSHOT', 'Gerudo Membership Card'}}))
        self.assertTrue(rule({'age': 'child', 'items': {'LONGSHOT'}}))

    def test_gate_operator_npc_route_requires_climb_and_card_but_not_bow(self):
        entry = self.catalog[10000028]
        self.assertEqual(entry['name'], 'NPC Speech: Gerudo Fortress Gate Operator')
        self.assertEqual(entry['routes'][0]['age'], 'adult')
        self.assertIn('carpenters', entry['routes'][0]['gates'])
        self.assertIn('climb', entry['routes'][0]['gates'])
        self.assertNotIn('bow', entry['routes'][0]['gates'])
        # Test the actual source conversation_rule against a lightweight rule API.
        fn = next(n for n in self.speech.body if isinstance(n, ast.FunctionDef) and n.name == 'conversation_rule')
        fn.returns = None
        for arg in fn.args.args:
            arg.annotation = None
        class FakeH:
            @staticmethod
            def is_adult(bundle): return as_rule(lambda s: s['age'] == 'adult')
            @staticmethod
            def is_child(bundle): return as_rule(lambda s: s['age'] == 'child')
            @staticmethod
            def has_item(item, bundle): return as_rule(lambda s: item in s['items'])
        env = {
            'H': FakeH, 'Regions': Names(), 'Items': types.SimpleNamespace(GERUDO_MEMBERSHIP_CARD='Gerudo Membership Card'),
            'Has': lambda name: as_rule(lambda s: name in s['items']),
            'And': lambda *rs: as_rule(lambda s: all(r(s) for r in rs)),
            'Or': lambda *rs: as_rule(lambda s: any(r(s) for r in rs)),
            'ConversationRegion': lambda name: as_rule(lambda s: name in s['regions']),
            'FortressCarpenters': types.SimpleNamespace(option_free=2, option_fast=1),
        }
        exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])), '<NpcSpeech>', 'exec'), env)
        world = types.SimpleNamespace(options=types.SimpleNamespace(
            shuffle_speak=types.SimpleNamespace(value=2),
            shuffle_npc_soul=types.SimpleNamespace(value=1),
            shuffle_climb=types.SimpleNamespace(value=1),
            fortress_carpenters=types.SimpleNamespace(value=0),
            skip_child_zelda=types.SimpleNamespace(value=0),
        ))
        actual = env['conversation_rule'](world, entry)
        items = {'Gerudo Membership Card', 'Climb', 'NPC Soul', 'Speak Gerudo'}
        self.assertTrue(actual({'age': 'adult', 'items': items, 'regions': {'GF_OUTSIDE_GATE'}}))
        self.assertFalse(actual({'age': 'child', 'items': items, 'regions': {'GF_OUTSIDE_GATE'}}))
        for missing in items:
            with self.subTest(missing=missing):
                self.assertFalse(actual({'age': 'adult', 'items': items - {missing} | {'LONGSHOT'}, 'regions': {'GF_OUTSIDE_GATE'}}))


if __name__ == '__main__':
    unittest.main()
