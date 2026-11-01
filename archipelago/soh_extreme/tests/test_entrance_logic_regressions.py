import ast
from pathlib import Path
import unittest


class EntranceLogicRegressionTests(unittest.TestCase):
    def test_treasure_chest_game_entry_has_explicit_night_gate(self):
        source = Path(__file__).parents[1].joinpath("EntranceRandomizer.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        function = next(node for node in tree.body
                        if isinstance(node, ast.FunctionDef) and node.name == "_source_rule")
        source_text = ast.get_source_segment(source, function)
        self.assertIn("row['id'] == 99", source_text)
        self.assertIn("H.at_night((Regions[row['source']], world)).resolve(world)", source_text)

    def test_time_access_rule_supports_frozen_clock(self):
        helpers = Path(__file__).parents[1].joinpath("_vendor_oot_soh/LogicHelpers.py").read_text(encoding="utf-8")
        self.assertIn("def at_night(bundle", helpers)
        self.assertIn("return _time_access(bundle, False)", helpers)


if __name__ == "__main__":
    unittest.main()
