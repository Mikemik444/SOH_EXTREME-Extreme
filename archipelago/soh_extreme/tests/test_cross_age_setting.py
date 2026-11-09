"""Opt-in cross-age equipment setting contracts, without requiring installed AP."""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[3]
WORLD = ROOT / "archipelago" / "soh_extreme"

class TestCrossAgeSetting(unittest.TestCase):
    def setUp(self):
        self.options_text = (WORLD / "Options.py").read_text("utf-8")
        self.world_text = (WORLD / "__init__.py").read_text("utf-8")

    def test_option_defaults_off(self):
        tree = ast.parse(self.options_text)
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "ShuffleCrossAgeEquipment")
        self.assertEqual([n.id for n in cls.bases], ["Toggle"])
        assigns = {t.id: ast.literal_eval(n.value) for n in cls.body if isinstance(n, ast.Assign)
                   for t in n.targets if isinstance(t, ast.Name)}
        self.assertEqual(assigns["default"], 0)
        self.assertEqual(assigns["display_name"], "Shuffle Cross-Age Equipment")

    def test_field_and_option_group(self):
        tree = ast.parse(self.options_text)
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "SohExtremeOptions")
        fields = {n.target.id: ast.unparse(n.annotation) for n in cls.body
                  if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)}
        self.assertEqual(fields["shuffle_cross_age_equipment"], "ShuffleCrossAgeEquipment")
        self.assertIn("OptionGroup(\"SOH-EXTREME Abilities & Souls\", [\n        ShuffleCrossAgeEquipment",self.options_text)

    def test_setting_exports_in_slot_and_native_options(self):
        self.assertIn('"shuffle_cross_age_equipment": o.shuffle_cross_age_equipment.value',self.world_text)
        self.assertIn('"ShuffleCrossAgeEquipment": o.shuffle_cross_age_equipment.value',self.world_text)

    def test_item_ids_and_directional_unlocks_remain(self):
        tree = ast.parse(self.world_text)
        items = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign)
                     and any(isinstance(t,ast.Name) and t.id=="EXTREME_ITEMS" for t in n.targets))
        self.assertEqual(items["Child Can Use Adult Items"],9500400)
        self.assertEqual(items["Adult Can Use Child Items"],9500401)
        self.assertNotEqual(items["Child Can Use Adult Items"],items["Adult Can Use Child Items"])
        self.assertEqual(items["Progressive Cross-Age Equipment"],9500402)

if __name__ == "__main__":
    unittest.main()
