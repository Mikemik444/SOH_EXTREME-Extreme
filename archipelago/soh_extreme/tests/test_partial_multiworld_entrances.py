"""Regression for other Archipelago worlds with deferred entrance connections.

LAS creates disconnected dungeon exits in create_regions() and connects them
in connect_entrances(), after SOH-EXTREME can be asked to do entrance shuffle.
All SOH-EXTREME probes used *inside* that stage must permit partial graph
traversal; normal post-connect fill validation remains strict.
"""
import ast
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "EntranceRandomizer.py"


class PartialMultiworldEntranceTests(unittest.TestCase):
    def test_preconnect_state_probes_allow_partial_entrances(self):
        module = ast.parse(SOURCE.read_text(encoding="utf-8"))
        functions = {node.name: node for node in module.body if isinstance(node, ast.FunctionDef)}
        for name in ("connect", "_initial_state_for_age"):
            calls = [n for n in ast.walk(functions[name]) if isinstance(n, ast.Call)
                     and (isinstance(n.func, ast.Name) and n.func.id == "CollectionState"
                          or isinstance(n.func, ast.Attribute) and n.func.attr == "get_all_state")]
            self.assertTrue(calls, f"No state construction found in {name}")
            for call in calls:
                keywords = {kw.arg: kw.value for kw in call.keywords}
                with self.subTest(function=name, line=call.lineno):
                    self.assertIn("allow_partial_entrances", keywords)
                    self.assertIsInstance(keywords["allow_partial_entrances"], ast.Constant)
                    self.assertIs(keywords["allow_partial_entrances"].value, True)

    def test_post_connect_validation_remains_strict(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn("_starting_state_is_viable(world, candidate, edges, fill_locations)", source)
        self.assertIn("assert_installed_topology()", source)
        self.assertIn("final_state.sweep_for_advancements()", source)
        self.assertIn("if not _age_routes_are_safe", source)


if __name__ == "__main__":
    unittest.main()
