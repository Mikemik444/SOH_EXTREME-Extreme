"""Run with python -m unittest discover -s archipelago/soh_extreme/tests -p test_entrance_spoiler.py -v"""
from __future__ import annotations
import ast
import importlib.util
import io
import json
from pathlib import Path
import unittest

BASE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("soh_entrance_spoiler_test", BASE / "EntranceSpoiler.py")
spoiler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(spoiler)
CATALOG = json.loads((BASE / "EntranceCatalog.json").read_text(encoding="utf-8"))
BY_ID = {entry["id"]: entry for entry in CATALOG}


class EntranceSpoilerTests(unittest.TestCase):
    def test_all_721_catalogued_sources_and_categories_appear(self):
        handle = io.StringIO()
        spoiler.write_entrance_spoiler(handle, CATALOG, {}, "Test Player")
        output = handle.getvalue()
        self.assertIn("Catalog endpoints: 721", output)
        self.assertEqual(sum(line.startswith("    [") and "] " in line
                             for line in output.splitlines()), len(CATALOG))
        for category, title in spoiler.CATEGORY_TITLES.items():
            self.assertIn("[" + title + "]", output, category)

    def test_actual_destination_is_not_stock_vanilla_label(self):
        # Child Spawn forced into the landing endpoint of another area.
        child = next(row for row in CATALOG if row["category"] == "child_spawn")
        target = next(row for row in CATALOG if row["category"] == "dungeon_doors")
        output = io.StringIO()
        spoiler.write_entrance_spoiler(output, CATALOG, {child["id"]: target["id"]}, "Tester")
        self.assertIn(f"[{child['id']}] {child['name']}", output.getvalue())
        self.assertIn(f"-> [{target['id']}]", output.getvalue())
        self.assertIn("Landing: " + target["target"] + " (scene " + str(target["scene"]) + ", room ", output.getvalue())

    def test_legacy_water_aliases_are_resolved(self):
        alias = {473: 234}
        target = next(row for row in CATALOG if row["id"] not in (234,473))
        matches = [r for r in spoiler.resolved_routes(CATALOG, {234: target["id"]}, legacy_water_aliases=alias)
                   if r[0]["id"] == 473]
        self.assertEqual(matches[0][1]["id"], target["id"])
        self.assertEqual(matches[0][2], "legacy water alias")

    def test_missing_source_is_rendered_as_unchanged(self):
        row = next(r for r in CATALOG if r["category"] == "overworld")
        output = {r[0]["id"]: (r[1]["id"], r[2]) for r in spoiler.resolved_routes(CATALOG, {})}
        self.assertEqual(output[row["id"]], (row["id"], "unchanged / not in shuffled pool"))

    def test_malformed_destination_fails_closed(self):
        with self.assertRaises(ValueError):
            list(spoiler.resolved_routes(CATALOG, {CATALOG[0]["id"]: -99999}))
        with self.assertRaises(ValueError):
            list(spoiler.resolved_routes(CATALOG, {-99999: CATALOG[0]["id"]}))

    def test_hook_is_inside_world_class(self):
        tree = ast.parse((BASE / "__init__.py").read_text(encoding="utf-8"))
        world = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                     and node.name == "SohExtremeWorld")
        methods = [m.name for m in world.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))]
        self.assertEqual(methods.count("write_spoiler"), 1)
        self.assertIn("fill_slot_data", methods)


if __name__ == "__main__":
    unittest.main()
