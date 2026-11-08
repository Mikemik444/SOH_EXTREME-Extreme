"""Executable regression for the Thieves' Hideout Kitchen Soup Wonder Item.

Runs without Archipelago installed. Compiles the exact live access-rule AST
from the APWorld and compares its guard alternatives against native SoH rules.
"""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[3]
WORLD = ROOT / 'archipelago' / 'soh_extreme'
NATIVE = ROOT / 'soh' / 'Enhancements' / 'randomizer' / 'location_access' / 'overworld' / 'thieves_hideout.cpp'
RC = 'RC_TH_WONDER_KITCHEN_SOUP'


class Predicate:
    def __init__(self, evaluate):
        self.evaluate = evaluate

    def __and__(self, other):
        return Predicate(lambda state: self(state) and other(state))

    def __or__(self, other):
        return Predicate(lambda state: self(state) or other(state))

    def __call__(self, state):
        return bool(self.evaluate(state))


def has(item):
    return Predicate(lambda state: item in state['items'])


def can_use(item, bundle):
    # The tested adult case already satisfies normal age restrictions; test
    # the actual evaluated ORs and forbid Hookshot-only progression.
    return has(item)


def is_adult(bundle):
    return Predicate(lambda state: state['age'] == 'adult')


class TestThievesHideoutKitchenSoup(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        world_text = (WORLD / '__init__.py').read_text('utf-8')
        tree = ast.parse(world_text)
        matches = [
            n for n in ast.walk(tree)
            if isinstance(n, ast.If)
            and isinstance(n.test, ast.Compare)
            and isinstance(n.test.left, ast.Name)
            and n.test.left.id == 'rc'
            and len(n.test.ops) == 1
            and isinstance(n.test.ops[0], ast.Eq)
            and len(n.test.comparators) == 1
            and isinstance(n.test.comparators[0], ast.Constant)
            and n.test.comparators[0].value == RC
        ]
        if len(matches) != 1:
            raise AssertionError(f'Expected one Kitchen Soup rule, found {len(matches)}')
        branch = matches[0]
        assignments = [
            n for n in branch.body if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id in {'guard_pass', 'rule'} for t in n.targets)
        ]
        if len(assignments) != 2:
            raise AssertionError('Kitchen Soup must explicitly define both guard_pass and rule')
        compiled = compile(ast.fix_missing_locations(ast.Module(body=assignments, type_ignores=[])),
                           str(WORLD / '__init__.py'), 'exec')
        env = {
            'Has': has,
            'can_use': can_use,
            'is_adult': is_adult,
            'Items': SimpleNamespace(FAIRY_BOW='Bow', HOOKSHOT='Hookshot'),
            'bundle': object(),
        }
        exec(compiled, env)
        cls.rule = staticmethod(env['rule'])
        cls.guard_pass = staticmethod(env['guard_pass'])
        cls.branch_source = ast.get_source_segment(world_text, branch) or ''

    def allows(self, age='adult', *items):
        return self.rule({'age': age, 'items': set(items)})

    def test_membership_card_alone(self):
        self.assertTrue(self.allows('adult', 'Gerudo Membership Card'))

    def test_bow_alone(self):
        self.assertTrue(self.allows('adult', 'Bow'))

    def test_nothing_does_not_allow_guarded_soup(self):
        self.assertFalse(self.allows('adult'))

    def test_hookshot_or_longshot_alone_must_not_allow_guarded_soup(self):
        self.assertFalse(self.allows('adult', 'Hookshot'))
        self.assertFalse(self.allows('adult', 'Longshot'))
        self.assertFalse(self.allows('adult', 'Hookshot', 'Longshot'))

    def test_rescuing_carpenters_does_not_replace_card_or_bow(self):
        self.assertFalse(self.allows('adult', 'Rescued All Carpenters'))

    def test_slingshot_alone_not_allowed_as_adult(self):
        self.assertFalse(self.allows('adult', 'Slingshot'))

    def test_age_label_is_preserved(self):
        self.assertFalse(self.allows('child', 'Gerudo Membership Card'))

    def test_native_kitchen_soup_rule_matches_normal_adult_alternatives(self):
        text = NATIVE.read_text('utf-8')
        check_line = next(line for line in text.splitlines() if 'LOCATION(' + RC in line)
        self.assertIn('HasItem(RG_GERUDO_MEMBERSHIP_CARD)', check_line)
        self.assertIn('logic->IsAdult && logic->CanUse(RG_FAIRY_BOW)', check_line)
        self.assertNotIn('RG_HOOKSHOT', check_line)
        corridor_line = next(line for line in text.splitlines() if 'ENTRANCE(RR_TH_KITCHEN_MAIN' in line)
        self.assertIn('RG_GERUDO_MEMBERSHIP_CARD', corridor_line)
        self.assertIn('RG_FAIRY_BOW', corridor_line)
        self.assertNotIn('RG_HOOKSHOT', corridor_line)

    def test_other_wonder_hookshot_rules_are_not_changed(self):
        text = (WORLD / '__init__.py').read_text('utf-8')
        block = text[text.index('elif rc in {"RC_GF_WONDER_ARCHERY_SIGN", "RC_GF_WONDER_ENTRANCE_SIGN"}:'):]
        block = block[:block.index('elif rc ==', 1)]
        self.assertIn('can_use(Items.HOOKSHOT, bundle)', block)
        self.assertIn('can_use(Items.LONGSHOT, bundle)', block)


if __name__ == '__main__':
    unittest.main()
