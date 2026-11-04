"""Standalone source-level and executable NPC-speech logic regressions.

Run with python -m unittest discover -s logic_regression_tests -v from the repo root.
No Archipelago server or external Python dependencies are required.
"""
import ast
import json
import pathlib
import types
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[3]
WORLD = ROOT / 'archipelago' / 'soh_extreme'
NATIVE = ROOT / 'soh' / 'Enhancements' / 'randomizer' / 'location_access' / 'overworld'


class Rule:
    def __init__(self, predicate):
        self.predicate = predicate

    def __and__(self, other):
        return Rule(lambda state: self(state) and other(state))

    def __or__(self, other):
        return Rule(lambda state: self(state) or other(state))

    def __call__(self, state):
        return self.predicate(state)


def Has(name):
    return Rule(lambda state: str(name) in state['items'])


def And(*rules):
    return Rule(lambda state: all(rule(state) for rule in rules))


def Or(*rules):
    return Rule(lambda state: any(rule(state) for rule in rules))


class EnumMap:
    def __getitem__(self, name):
        return name


class Helpers:
    @staticmethod
    def is_adult(bundle):
        return Rule(lambda state: state['age'] == 'adult')

    @staticmethod
    def is_child(bundle):
        return Rule(lambda state: state['age'] == 'child')

    @staticmethod
    def has_item(item, bundle):
        return Has(item)

    @staticmethod
    def can_use(item, bundle):
        return Has(item)


class Option:
    def __init__(self, value):
        self.value = value


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        text = (WORLD / 'NpcSpeech.py').read_text(encoding='utf8')
        tree = ast.parse(text)
        fn = next(node for node in tree.body
                  if isinstance(node, ast.FunctionDef) and node.name == 'conversation_rule')
        # Compile the REAL source function with lightweight rule objects;
        # this tests its branches, not an independent reimplementation.
        code = compile(ast.Module(body=[fn], type_ignores=[]), str(WORLD/'NpcSpeech.py'), 'exec')
        env = {
            'Has': Has, 'And': And, 'Or': Or,
            'H': Helpers(), 'Regions': EnumMap(),
            'Items': types.SimpleNamespace(GERUDO_MEMBERSHIP_CARD='Gerudo Membership Card',
                                           FAIRY_BOW='Bow'),
            'Events': types.SimpleNamespace(RESCUED_ALL_CARPENTERS='Rescued All Carpenters'),
            'ConversationRegion': lambda name: Rule(lambda state: name in state['regions']),
            'FortressCarpenters': types.SimpleNamespace(option_free=2, option_fast=1),
        }
        exec(code, env)
        cls.conversation_rule = staticmethod(env['conversation_rule'])
        cls.catalog = {e['id']: e for e in json.loads((WORLD/'NpcSpeechCatalog.json').read_text())}
        cls.world = types.SimpleNamespace(
            options=types.SimpleNamespace(shuffle_speak=Option(2), shuffle_npc_soul=Option(1),
                                          fortress_carpenters=Option(0), skip_child_zelda=Option(0)))

    def fixture(self, entry_id, *, card=True, soul=True, speak=True, age='adult',
                rescued=False, bow=False, reached=True):
        entry = self.catalog[entry_id]
        state = {'items': set(), 'regions': set(), 'age': age}
        if card: state['items'].add('Gerudo Membership Card')
        if soul: state['items'].add('NPC Soul')
        if speak: state['items'].add('Speak Gerudo')
        if rescued: state['items'].add('Rescued All Carpenters')
        if bow: state['items'].add('Bow')
        if reached: state['regions'].add(entry['routes'][0]['region'])
        return entry, state

    def test_six_fortress_npc_speech_checks_accept_card_without_carpenters(self):
        for entry_id in [10000024, 10000025, 10001022, 10001023, 10000027, 10000028]:
            with self.subTest(entry_id=entry_id):
                entry, state = self.fixture(entry_id)
                self.assertTrue(self.conversation_rule(self.world, entry)(state))

    def test_gates_do_not_lose_gerudo_language_npc_soul_region_age(self):
        for kwargs in [{'soul':False}, {'speak':False}, {'reached':False}, {'age':'child'}]:
            with self.subTest(kwargs=kwargs):
                entry,state=self.fixture(10001022,**kwargs)
                self.assertFalse(self.conversation_rule(self.world, entry)(state))

    def test_rescuing_all_carpenters_does_not_replace_membership_card(self):
        # The six guarded Gerudo NPC conversations require the actual card,
        # even after all carpenters are rescued. Bow/stun is not a talk permit.
        for entry_id in [10000024, 10000025, 10001022, 10001023, 10000027, 10000028]:
            with self.subTest(entry_id=entry_id):
                entry, state = self.fixture(entry_id, card=False, rescued=True, bow=True)
                self.assertFalse(self.conversation_rule(self.world, entry)(state))
                entry, state = self.fixture(entry_id, card=True, rescued=False, bow=False)
                self.assertTrue(self.conversation_rule(self.world, entry)(state))
                entry, state = self.fixture(entry_id, card=True, rescued=True, bow=False)
                self.assertTrue(self.conversation_rule(self.world, entry)(state))

    def test_archery_host_talk_is_not_archery_reward(self):
        entry,state=self.fixture(10000027,bow=False)
        self.assertTrue(self.conversation_rule(self.world, entry)(state))
        # Its actual minigame reward is a separate native Bow-gated check.
        native=(NATIVE/'gerudo_fortress.cpp').read_text()
        self.assertIn('RC_GF_HBA_1000_POINTS',native)
        self.assertRegex(native, r'LOCATION\(RC_GF_HBA_1000_POINTS[^\n]+CanUse\(RG_FAIRY_BOW\)')

    def test_both_wonders_are_hook_or_longshot_not_bow(self):
        ap=(WORLD/'__init__.py').read_text()
        start=ap.index('elif rc in {"RC_GF_WONDER_ARCHERY_SIGN", "RC_GF_WONDER_ENTRANCE_SIGN"}:')
        end=ap.index('elif rc ==',start+1)
        block=ap[start:end]
        self.assertIn('can_use(Items.HOOKSHOT, bundle)',block)
        self.assertIn('can_use(Items.LONGSHOT, bundle)',block)
        self.assertNotIn('FAIRY_BOW',block)
        native=(NATIVE/'gerudo_fortress.cpp').read_text()
        for name in ['RC_GF_WONDER_ENTRANCE_SIGN','RC_GF_WONDER_ARCHERY_SIGN']:
            line=next(l for l in native.splitlines() if f'LOCATION({name}' in l)
            self.assertIn('CanUse(RG_HOOKSHOT)',line)
            self.assertIn('CanUse(RG_LONGSHOT)',line)
            self.assertNotIn('RG_FAIRY_BOW',line)

    def test_archery_wonder_card_gate_and_entrance_wonder_no_card_gate(self):
        native=(NATIVE/'gerudo_fortress.cpp').read_text()
        archery=next(l for l in native.splitlines() if 'LOCATION(RC_GF_WONDER_ARCHERY_SIGN' in l)
        entrance=next(l for l in native.splitlines() if 'LOCATION(RC_GF_WONDER_ENTRANCE_SIGN' in l)
        self.assertIn('GERUDO_MEMBERSHIP_CARD',archery)
        self.assertNotIn('GERUDO_MEMBERSHIP_CARD',entrance)

    def test_wonder_named_sign_is_not_sign_soul_gated_by_either_overlay(self):
        text=(WORLD/'__init__.py').read_text()
        tree=ast.parse(text)
        # Compile the exact expression assigned to is_named_sign by set_rules,
        # and the exact later generic-Sign-Soul condition. No reimplementation.
        assignment=next(node for node in ast.walk(tree)
                        if isinstance(node,ast.Assign)
                        and any(isinstance(t,ast.Name) and t.id=='is_named_sign' for t in node.targets))
        first=compile(ast.Expression(assignment.value),str(WORLD/'__init__.py'),'eval')
        candidates=[node.test for node in ast.walk(tree)
                    if isinstance(node,ast.If) and 'SIGN' in ast.unparse(node.test)
                    and 'fork_wonder_check_names' in ast.unparse(node.test)]
        self.assertEqual(len(candidates),1)
        second=compile(ast.Expression(candidates[0]),str(WORLD/'__init__.py'),'eval')
        wonders={'EXTREME Gf Wonder Entrance Sign','EXTREME Gf Wonder Archery Sign'}
        real={'EXTREME Gf Hba Rectangle Sign'}
        for name,expected in [(n,False) for n in wonders]+[(n,True) for n in real]:
            with self.subTest(name=name):
                ctx={'location':types.SimpleNamespace(name=name),
                     'upper_name':name.upper(), 'lname':name.upper(),
                     'fork_wonder_check_names':wonders,
                     'o':types.SimpleNamespace(shuffle_sign_soul=Option(1))}
                self.assertEqual(bool(eval(first,ctx)),expected)
                self.assertEqual(bool(eval(second,ctx)),expected)

    def test_adult_mido_bypass_in_python_and_cpp(self):
        ap=(WORLD/'_vendor_oot_soh/location_access/overworld/kokiri_forest.py').read_text()
        native=(NATIVE/'kokiri_forest.cpp').read_text()
        self.assertIn('(Regions.KF_OUTSIDE_DEKU_TREE, lambda bundle: is_adult(bundle)',ap)
        self.assertIn('(Regions.KOKIRI_FOREST, lambda bundle: is_adult(bundle)',ap)
        self.assertIn('(is_child(bundle) & has_item(LocalEvents.MIDO_SWORD_AND_SHIELD, bundle))',ap)
        self.assertIn('ENTRANCE(RR_KF_OUTSIDE_DEKU_TREE,  logic->IsAdult ||',native)
        self.assertIn('ENTRANCE(RR_KOKIRI_FOREST,      logic->IsAdult ||',native)
        self.assertIn('LOGIC_SHOWED_MIDO_SWORD_AND_SHIELD',native)
        self.assertIn('RC_KF_DEKU_TREE_LEFT_GOSSIP_STONE_FAIRY',native)
        self.assertIn('RC_KF_DEKU_TREE_RIGHT_GOSSIP_STONE_FAIRY',native)

if __name__ == '__main__':
    unittest.main()
