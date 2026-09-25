"""Focused APWorld source tests; no Archipelago runtime dependency.

These evaluate the actual shipped route lambda and actual can_grab helper using
small Has/True rule adapters. They do NOT simulate a complete AP seed or client.
Run: python validation/test_apworld_update.py
"""
from __future__ import annotations
import ast
import base64
from collections import Counter
import json
from pathlib import Path
import struct
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORLD = ROOT / 'arvhipelago' / 'soh_extreme'
GRAB = 'Grab / Power Bracelet'

class Rule:
    def __init__(self, predicate):
        self.predicate = predicate
    def __call__(self, inventory):
        return self.predicate(inventory)
    def __and__(self, other):
        return Rule(lambda inventory: self(inventory) and other(inventory))
    def __or__(self, other):
        return Rule(lambda inventory: self(inventory) or other(inventory))

def has(item, count=1):
    return Rule(lambda inventory: inventory[item] >= count)

def read_ast(path):
    return ast.parse(path.read_text(encoding='utf-8-sig'), filename=str(path))

def helper_namespace():
    tree = read_ast(WORLD / '_vendor_oot_soh' / 'LogicHelpers.py')
    selected = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                and node.name in {'extreme_requirement', 'can_grab'}]
    assert len(selected) == 2
    namespace = {'Rule': Rule, 'Has': has, 'True_': lambda: Rule(lambda inv: True)}
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(WORLD / '_vendor_oot_soh' / 'LogicHelpers.py'), 'exec'), namespace)
    return namespace

def route_lambda(path):
    tree = read_ast(path)
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == 'connect_regions' and node.args):
            continue
        parent = node.args[0]
        if not (isinstance(parent, ast.Attribute) and parent.attr == 'DODONGOS_CAVERN_BOSS_REGION'):
            continue
        for pair in node.args[2].elts:
            target, route = pair.elts
            if isinstance(target, ast.Attribute) and target.attr == 'DODONGOS_CAVERN_BOSS_ENTRYWAY':
                return eval(compile(ast.Expression(route), str(path), 'eval'), helper_namespace())
    raise AssertionError('Missing Boss Region -> Boss Entryway rule')

class APWorldSourceTests(unittest.TestCase):
    def test_all_python_and_json_files_parse(self):
        files = list((ROOT / 'arvhipelago').rglob('*.py'))
        self.assertEqual(len(files), 75)
        for path in files:
            with self.subTest(file=str(path.relative_to(ROOT))):
                compile(path.read_text(encoding='utf-8-sig'), str(path), 'exec')
        for path in (ROOT / 'arvhipelago').rglob('*.json'):
            json.loads(path.read_text(encoding='utf-8-sig'))

    def test_grab_setting_and_ownership_for_both_ages(self):
        route = route_lambda(WORLD / '_vendor_oot_soh/location_access/dungeons/dodongos_cavern.py')
        for age in ('child', 'adult'):
            for shuffled in (0, 1):
                for owned in (False, True):
                    with self.subTest(age=age, shuffled=shuffled, owned=owned):
                        world = SimpleNamespace(options=SimpleNamespace(shuffle_grab=SimpleNamespace(value=shuffled)), age=age)
                        inventory = Counter({GRAB: int(owned)})
                        self.assertEqual(route(('Dodongos Cavern Boss Region', world))(inventory), not shuffled or owned)

    def test_explosives_do_not_open_the_block_switch_route(self):
        route = route_lambda(WORLD / '_vendor_oot_soh/location_access/dungeons/dodongos_cavern.py')
        world = SimpleNamespace(options=SimpleNamespace(shuffle_grab=SimpleNamespace(value=1)))
        inventory = Counter({'Progressive Bomb Bag': 1, 'Bombchu Bag': 1})
        rule = route(('Dodongos Cavern Boss Region', world))
        self.assertFalse(rule(inventory))
        inventory[GRAB] += 1
        self.assertTrue(rule(inventory))
        inventory[GRAB] -= 1
        self.assertFalse(rule(inventory))

    def test_both_region_alias_dictionaries(self):
        tree = read_ast(WORLD / '__init__.py')
        found = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'native_region_aliases' for t in node.targets):
                aliases = ast.literal_eval(node.value)
                self.assertEqual(aliases['DODONGOS_CAVERN_BOSS_AREA'], 'DODONGOS_CAVERN_BOSS_REGION')
                found.append(node)
        self.assertEqual(len(found), 2)
        enum = read_ast(WORLD / '_vendor_oot_soh/Enums.py')
        regions = next(n for n in enum.body if isinstance(n, ast.ClassDef) and n.name == 'Regions')
        self.assertTrue(any(isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'DODONGOS_CAVERN_BOSS_REGION' for t in n.targets) for n in regions.body))

    def test_native_projection_has_grab_on_the_same_edge(self):
        tree = read_ast(WORLD / 'NativeLogicAlternatives.py')
        assignment = next(n for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'NATIVE_ENTRANCE_ALTERNATIVES' for t in n.targets))
        edges = ast.literal_eval(assignment.value)
        matching = [edge for edge in edges if edge[:2] == ('RR_DODONGOS_CAVERN_BOSS_AREA', 'RR_DODONGOS_CAVERN_BOSS_ENTRYWAY')]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0][2], ((GRAB,),))

    def test_manifests_and_tracker_wire_version(self):
        outer = json.loads((ROOT / 'arvhipelago/archipelago.json').read_text())
        inner = json.loads((WORLD / 'archipelago.json').read_text())
        self.assertEqual(outer, inner)
        self.assertEqual(inner['world_version'], '0.11.22')
        self.assertEqual(inner['minimum_ap_version'], '0.6.7')
        namespace = {}
        exec(compile((WORLD / 'TrackerMirror.py').read_text(), str(WORLD / 'TrackerMirror.py'), 'exec'), namespace)
        self.assertEqual(namespace['VERSION'], '0.11.22')
        encoded = namespace['encode_snapshot'](nonce='a'*32, request=1, revision=1, slot=1,
            producer='focused-test', received=0, active={123}, checked=set(),
            rows=[{'id': 123, 'state': 1, 'name': 'Test check', 'region': 'Test region'}])
        data = base64.b64decode(encoded)
        position = len(namespace['MAGIC'])
        strings = []
        for _ in range(3):
            size = struct.unpack_from('<H', data, position)[0]
            position += 2
            strings.append(data[position:position + size].decode())
            position += size
        self.assertEqual(strings[2], '0.11.22')

    def test_no_external_stock_world_import(self):
        for path in WORLD.rglob('*.py'):
            for node in ast.walk(read_ast(path)):
                if isinstance(node, ast.ImportFrom):
                    self.assertFalse((node.module or '').startswith('worlds.oot_soh'), str(path))
                if isinstance(node, ast.Import):
                    self.assertFalse(any(alias.name.startswith('worlds.oot_soh') for alias in node.names), str(path))

if __name__ == '__main__':
    unittest.main(verbosity=2)
