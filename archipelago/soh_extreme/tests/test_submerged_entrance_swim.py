"""Regression: Swim gates physical underwater entrances, not entire Water Temple.

The endpoint IDs are reviewed physical underwater mouths in EntranceCatalog.json.
The source gate controls the transition check; the arrival gate controls
shuffled entrances that land at underwater mouths.
"""
import ast
import json
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]


class SubmergedEntranceSwimTest(unittest.TestCase):
    def setUp(self):
        self.catalog = {x['id']: x for x in json.loads((BASE/'EntranceCatalog.json').read_text())}
        self.er = (BASE/'EntranceRandomizer.py').read_text()

    def test_underwater_endpoints_are_explicit_and_paired(self):
        module = ast.parse(self.er)
        endpoints = None
        for stmt in module.body:
            if isinstance(stmt, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == 'WATER_SUBMERGED_ENDPOINTS' for t in stmt.targets
            ):
                endpoints = set(ast.literal_eval(stmt.value.args[0]))
                break
        self.assertIsNotNone(endpoints)
        self.assertEqual(endpoints, {16,541,477,1242,808,1376,473,785})
        for endpoint in endpoints:
            self.assertIn(endpoint, self.catalog)
            self.assertIn(self.catalog[endpoint]['reverse'], endpoints)
            self.assertNotEqual(self.catalog[endpoint]['category'], 'dungeon_doors')
        self.assertNotIn(1047, endpoints)  # Water Temple boss door is not underwater.
        self.assertNotIn(8868, endpoints)  # Water Temple Dark Link dry-room door.

    def test_shuffled_source_and_arrival_require_swim(self):
        self.assertIn("row.get('gate') == 'swim' or row['id'] in WATER_SUBMERGED_ENDPOINTS", self.er)
        self.assertIn("row.get('arrival_gate') == 'swim' or row['id'] in WATER_SUBMERGED_ENDPOINTS", self.er)
        self.assertIn("or row['id'] in WATER_SUBMERGED_ENDPOINTS", self.er)
        self.assertIn('H.can_swim(bundle).resolve(world)', self.er)
        self.assertIn("H.can_swim((Regions[row['target']], world)).resolve(world)", self.er)

    def test_non_shuffled_water_temple_exit_requires_swim(self):
        py = (BASE/'_vendor_oot_soh/location_access/dungeons/water_temple.py').read_text()
        cpp = (ROOT/'soh/Enhancements/randomizer/location_access/dungeons/water_temple.cpp').read_text()
        self.assertIn('(Regions.LH_FROM_WATER_TEMPLE, lambda bundle: can_swim(bundle))', py)
        self.assertIn('ENTRANCE(RR_LH_FROM_WATER_TEMPLE,           logic->HasItem(RG_BRONZE_SCALE))',cpp)

    def test_dry_routes_remain_not_globally_swim_gated(self):
        # Water Temple entryway -> lobby is the underwater route; do NOT
        # impose Swim on the entire scene/check list or on dry room doors.
        py = (BASE/'_vendor_oot_soh/location_access/dungeons/water_temple.py').read_text()
        self.assertIn('(Regions.WATER_TEMPLE_LOBBY, lambda bundle: (\n            can_use(Items.IRON_BOOTS, bundle)))', py)
        self.assertIn("WATER_ARRIVAL_LEVELS = {", self.er)


if __name__ == '__main__':
    unittest.main()
