"""Regression: the prepacked APWorld must carry every Python/JSON source module."""
from __future__ import annotations
import io
from pathlib import Path
import unittest
import zipfile

BASE = Path(__file__).resolve().parents[1]
ARCHIPELAGO = BASE.parent

class WorldPackageTests(unittest.TestCase):
    def test_packed_world_contains_all_active_sources(self):
        apworld = ARCHIPELAGO/'soh_extreme.apworld'
        self.assertTrue(apworld.exists(), f'missing prepackaged world: {apworld}')
        with zipfile.ZipFile(apworld) as packed:
            self.assertIsNone(packed.testzip())
            for local in BASE.rglob('*'):
                if not local.is_file() or '/tests/' in str(local).replace('\\','/'):
                    continue
                if local.suffix not in ('.py','.json'):
                    continue
                internal='soh_extreme/'+local.relative_to(BASE).as_posix()
                with self.subTest(module=internal):
                    self.assertIn(internal,packed.namelist())
                    self.assertEqual(packed.read(internal),local.read_bytes())

if __name__ == '__main__': unittest.main()
