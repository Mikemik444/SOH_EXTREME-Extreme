"""Regression for Impa's House invisible Wonder Item vs cow actor Soul gates.

Runs without an Archipelago server. Evaluates the actual fallback expression from
set_rules(), and checks the custom location's declared actor family.
"""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[3]
WORLD = ROOT / "archipelago" / "soh_extreme"


def _assigned_value(tree, var):
    matches = [node.value for node in ast.walk(tree)
               if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == var
                                                       for t in node.targets)]
    if len(matches) != 1:
        raise AssertionError(f"Expected one real assignment of {var}; got {len(matches)}")
    return matches[0]


class CowWonderGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        main = (WORLD / "__init__.py").read_text(encoding="utf-8")
        main_ast = ast.parse(main)
        fork_text = (WORLD / "ForkLocations.py").read_text(encoding="utf-8")
        lines = fork_text.splitlines()
        cow_line = [x for x in lines if "ForkLocationData('EXTREME Kak Wonder Above Cow'" in x]
        assert len(cow_line) == 1 and "'wonder'" in cow_line[0]
        cls.fork_names = set()
        for node in ast.walk(ast.parse(fork_text)):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "ForkLocationData":
                if node.args and isinstance(node.args[0], ast.Constant):
                    cls.fork_names.add(node.args[0].value)
        assert 'EXTREME Kak Wonder Above Cow' in cls.fork_names
        expr = ast.Expression(body=_assigned_value(main_ast, "direct_cow"))
        cls.compiled = compile(ast.fix_missing_locations(expr), str(WORLD / "__init__.py"), "eval")
        # Also guard against regression in the independent tagged-animal path.
        cls.has_wonder_tag_exclusion = any(
            "location.name not in fork_wonder_check_names" in ast.unparse(node.test)
            for node in ast.walk(main_ast)
            if isinstance(node, ast.If) and "tags & animal_tags" in ast.unparse(node.test)
        )

    def classify(self, name):
        return eval(self.compiled, {"FORK_LOCATION_NAME_TO_ID": {n:i for i,n in enumerate(self.fork_names)}},
                    {"upper": name.upper(), "location": SimpleNamespace(name=name)})

    def test_wonder_above_cow_never_requires_cow_actor(self):
        self.assertFalse(self.classify('EXTREME Kak Wonder Above Cow'))

    def test_real_cows_still_have_actor_gate(self):
        self.assertTrue(self.classify('Kak Impas House Cow'))
        self.assertTrue(self.classify('GV Cow'))
        self.assertTrue(self.classify('LLR Stables Left Cow'))

    def test_all_fork_locations_are_excluded_from_stock_name_fallback(self):
        for name in self.fork_names:
            with self.subTest(name=name):
                self.assertFalse(self.classify(name))

    def test_wonder_excluded_from_tagged_animal_rule(self):
        self.assertTrue(self.has_wonder_tag_exclusion)


if __name__ == '__main__':
    unittest.main()
