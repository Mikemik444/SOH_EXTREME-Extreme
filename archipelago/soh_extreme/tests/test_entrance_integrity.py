"""Run with: python -m unittest discover -s archipelago/soh_extreme/tests -v"""
from __future__ import annotations
import hashlib
import json
import sys
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
import EntranceMapIntegrity as integrity


def canonical_hash(row):
    data = json.dumps(row, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(data.encode('utf8')).hexdigest()


class EntranceIntegrityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads((BASE / 'EntranceCatalog.json').read_text(encoding='utf8'))
        cls.policy = json.loads((BASE / 'EntranceDestinationPolicy.json').read_text(encoding='utf8'))
        cls.by_id = {x['id']: x for x in cls.catalog}

    def test_unique_complete_catalog(self):
        self.assertEqual(len(self.catalog), 721)
        self.assertEqual(len(self.by_id), len(self.catalog))
        self.assertEqual({e['id'] for e in self.policy['endpoints']}, set(self.by_id))
        self.assertEqual(self.policy['catalog_sha256'], canonical_hash(sorted(self.catalog, key=lambda x:x['id'])))

    def test_every_reviewed_endpoint_metadata_matches_catalog(self):
        # A valid global catalog hash is not sufficient if one per-endpoint
        # destination fingerprint has gone stale during a logic-rule change.
        policy_rows = {row['id']: row for row in self.policy['endpoints']}
        for endpoint_id, catalog_row in self.by_id.items():
            with self.subTest(endpoint=endpoint_id):
                self.assertEqual(policy_rows[endpoint_id]['catalog_row_sha256'],
                                 canonical_hash(catalog_row))

    def test_every_paired_reverse_is_symmetric(self):
        for row in self.catalog:
            reverse = row['reverse']
            if reverse >= 0:
                with self.subTest(source=row['id']):
                    self.assertIn(reverse, self.by_id)
                    self.assertEqual(self.by_id[reverse]['reverse'],row['id'])

    def test_physical_source_gate_ids(self):
        physical = {99: ('MARKET', 'MARKET_TREASURE_CHEST_GAME'),
                    258: ('HYRULE_FIELD', 'LAKE_HYLIA'),
                    393: ('LAKE_HYLIA', 'HYRULE_FIELD')}
        for endpoint, (source, target) in physical.items():
            self.assertEqual((self.by_id[endpoint]['source'], self.by_id[endpoint]['target']), (source, target))
        generator = (BASE/'EntranceRandomizer.py').read_text(encoding='utf8')
        self.assertIn("row['id'] == 99", generator)
        self.assertIn("row['id'] in (258, 393)", generator)
        self.assertIn('H.can_open_overworld_door(Items.TREASURE_CHEST_GAME_BUILDING_KEY', generator)
        self.assertIn('H.can_climb(bundle) | H.can_swim(bundle)', generator)

    def test_native_endpoint_parity_all_721(self):
        # Compare actual source/destination endpoint metadata emitted for C++.
        # A mismatched scene or door here can make AP validate an inaccessible
        # room even though both sides separately have valid-looking catalogs.
        import re
        cpp_file = BASE.parents[1] / 'soh' / 'Network' / 'Archipelago' / 'EntranceRandomizerData.inc'
        self.assertTrue(cpp_file.exists(), f'missing native entrance catalog: {cpp_file}')
        rows = {}
        for line in cpp_file.read_text(encoding='utf8').splitlines():
            match = re.match(r'\{(-?\d+), (-?\d+), (-?\d+), (-?\d+), (-?\d+), (-?\d+),',line)
            if match:
                endpoint, reverse, scene, source_scene, check, door = map(int, match.groups())
                self.assertNotIn(endpoint, rows)
                rows[endpoint] = (reverse,scene,source_scene,check,door)
        self.assertEqual(len(rows), len(self.catalog))
        for endpoint,row in self.by_id.items():
            with self.subTest(endpoint=endpoint):
                self.assertEqual(rows[endpoint], (row['reverse'],row['scene'],row['source_scene'],
                                                   row['check_id'],row['door']))

    def test_slot_map_fingerprint_order_independent(self):
        first = {258:393, 393:258, 99:469, 469:99}
        reverse_order = dict(reversed(list(first.items())))
        self.assertEqual(integrity.fingerprint(first), integrity.fingerprint(reverse_order))
        self.assertNotEqual(integrity.fingerprint(first), integrity.fingerprint({**first, 469:393}))
        self.assertGreaterEqual(integrity.fingerprint(first),0)
        self.assertLess(integrity.fingerprint(first),2**31)

    def test_missing_source_fails_closed(self):
        with self.assertRaisesRegex(ValueError, 'Incomplete entrance map'):
            integrity.validate_complete({99:469},{99,469})
        integrity.validate_complete({99:469,469:99},{99,469})


if __name__ == '__main__':
    unittest.main()
