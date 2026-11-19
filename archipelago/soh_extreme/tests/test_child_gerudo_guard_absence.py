"""Guard-free Child Gerudo Fortress regression using the actual source AST.

    Run from inside/extracted APWorld: python -m unittest soh_extreme.tests.test_child_gerudo_guard_absence
"""
import ast
import pathlib
import unittest


class Rule:
    def __init__(self, f):
        self.f = f

    def __or__(self, other):
        return Rule(lambda s: self(s) or other(s))

    def __and__(self, other):
        return Rule(lambda s: self(s) and other(s))

    def __call__(self, state):
        return self.f(state)


class TestChildGerudoGuards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = pathlib.Path(__file__).resolve().parents[1]
        source = (root / '_vendor_oot_soh' / 'LogicHelpers.py').read_text(encoding='utf-8')
        tree = ast.parse(source)
        funcs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)
                 and n.name in ('can_bypass_gerudo_patrol', 'can_pass_enemy')}
        assert set(funcs) == {'can_bypass_gerudo_patrol', 'can_pass_enemy'}
        for n in funcs.values():
            n.returns = None
            for arg in n.args.args:
                arg.annotation = None
        # For can_pass_enemy, preserve the real guard-specific branch; replace
        # unrelated giant enemy cases with only those guard conditionals.
        enemy_fn = funcs['can_pass_enemy']
        guards = [n for n in enemy_fn.body if isinstance(n, ast.If)
                  and ('Enemies.GERUDO_GUARD' in ast.unparse(n.test)
                       or 'Enemies.BREAK_ROOM_GUARD' in ast.unparse(n.test))
                  and isinstance(n.test, ast.Compare)]
        assert len(guards) == 2, f'Expected two guard branches, got {len(guards)}'
        enemy_fn.body = guards
        ast.fix_missing_locations(tree)

        class Items:
            GERUDO_MEMBERSHIP_CARD = 'card'
            FAIRY_BOW = 'bow'
            FAIRY_SLINGSHOT = 'slingshot'
            HOOKSHOT = 'hookshot'

        class Enemies:
            GERUDO_GUARD = 'gerudo'
            BREAK_ROOM_GUARD = 'break'

        class Tricks:
            PASS_GUARDS_WITH_NOTHING = 'trick'

        env = {
            'Items': Items, 'Enemies': Enemies, 'Tricks': Tricks, 'EnemyDistance': type('EnemyDistance', (), {'CLOSE': 'close'}),
            'is_child': lambda bundle: Rule(lambda s: s['age'] == 'child'),
            'is_adult': lambda bundle: Rule(lambda s: s['age'] == 'adult'),
            'has_item': lambda item, bundle: Rule(lambda s: item in s['items']),
            'can_use': lambda item, bundle: Rule(lambda s: item in s['items']),
            'can_use_any': lambda items, bundle: Rule(lambda s: any(i in s['items'] for i in items)),
            'can_do_trick': lambda trick, bundle: Rule(lambda s: trick in s['items']),
        }
        module = ast.fix_missing_locations(ast.Module(body=list(funcs.values()), type_ignores=[]))
        exec(compile(module, '<actual LogicHelpers.py>', 'exec'), env)
        cls.patrol = staticmethod(env['can_bypass_gerudo_patrol'])
        cls.enemy = staticmethod(env['can_pass_enemy'])
        cls.Enemies = Enemies

    def state(self, age, *items):
        return {'age': age, 'items': set(items)}

    def test_child_walks_unguarded_with_no_items(self):
        self.assertTrue(self.patrol(None)(self.state('child')))
        self.assertTrue(self.enemy(None, self.Enemies.GERUDO_GUARD)(self.state('child')))
        self.assertTrue(self.enemy(None, self.Enemies.BREAK_ROOM_GUARD)(self.state('child')))

    def test_adult_still_needs_guard_bypass(self):
        self.assertFalse(self.patrol(None)(self.state('adult')))
        self.assertFalse(self.enemy(None, self.Enemies.GERUDO_GUARD)(self.state('adult')))
        self.assertFalse(self.enemy(None, self.Enemies.BREAK_ROOM_GUARD)(self.state('adult')))
        self.assertTrue(self.patrol(None)(self.state('adult', 'bow')))
        self.assertTrue(self.patrol(None)(self.state('adult', 'card')))
        self.assertTrue(self.enemy(None, self.Enemies.BREAK_ROOM_GUARD)(self.state('adult', 'hookshot')))

    def test_child_does_not_need_adult_stun_equipment(self):
        self.assertTrue(self.patrol(None)(self.state('child')))
        self.assertFalse(self.patrol(None)(self.state('adult', 'slingshot')))


if __name__ == '__main__':
    unittest.main()
