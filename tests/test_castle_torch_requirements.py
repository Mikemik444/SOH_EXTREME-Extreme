#!/usr/bin/env python3
"""Regression checks for the two Castle Grounds torch rules (stdlib only)."""
import ast
from pathlib import Path
import re
import unittest
import zipfile

ROOT = Path(__file__).resolve().parent.parent
CPP = ROOT / 'soh/Enhancements/randomizer/location_access/overworld/castle_grounds.cpp'
APWORLD = ROOT / 'soh_extreme.apworld'

class CastleTorchesTest(unittest.TestCase):
    def test_both_native_rules(self):
        source = CPP.read_text(encoding='utf-8')
        for name in ('LEFT', 'RIGHT'):
            line = next(l for l in source.splitlines() if l.strip().startswith(f'LOCATION(RC_HC_WONDER_{name}_TORCH,'))
            for required in ('logic->HasItem(RG_BRONZE_SCALE)', 'logic->CanUse(RG_FAIRY_SLINGSHOT)', 'logic->HasItem(RG_CLIMB)', 'logic->CanUse(RG_HOOKSHOT)', 'logic->CanUse(RG_LONGSHOT)'):
                self.assertIn(required, line, name)
            self.assertNotIn('RG_BOOMERANG', line)
            self.assertNotIn('RT_VOIDOUT_COLLECTION', line)
            self.assertRegex(line, r'RG_FAIRY_SLINGSHOT\) && \(logic->HasItem\(RG_CLIMB\) \|\| logic->CanUse\(RG_HOOKSHOT\) \|\| logic->CanUse\(RG_LONGSHOT\)\)')

    def test_archipelago_rules_and_integrity(self):
        with zipfile.ZipFile(APWORLD) as z:
            self.assertIsNone(z.testzip())
            source = z.read('soh_extreme/__init__.py').decode('utf-8')
            ast.parse(source)
        pattern = r'elif rc in \{"RC_HC_WONDER_LEFT_TORCH", "RC_HC_WONDER_RIGHT_TORCH"\}:(.*?)(?=\n                elif rc|\n                if rule is not None)'
        match = re.search(pattern, source, re.S)
        self.assertIsNotNone(match)
        block = match.group(1)
        for required in ('swim_rule()', 'can_use(Items.FAIRY_SLINGSHOT, bundle)', 'climb_rule()', 'can_use(Items.HOOKSHOT, bundle)', 'can_use(Items.LONGSHOT, bundle)'):
            self.assertIn(required, block)
        rule = '\n'.join(l for l in block.splitlines() if not l.lstrip().startswith('#'))
        self.assertNotIn('Items.BOOMERANG', rule)
        self.assertNotIn('RT_VOIDOUT_COLLECTION', rule)

    def test_required_inventory_truth_table(self):
        can_get = lambda swim, slingshot, climb, hookshot, longshot: swim and slingshot and (climb or hookshot or longshot)
        self.assertFalse(can_get(False,True,True,False,False))
        self.assertFalse(can_get(True,False,True,True,True))
        self.assertFalse(can_get(True,True,False,False,False))
        self.assertTrue(can_get(True,True,True,False,False))
        self.assertTrue(can_get(True,True,False,True,False))
        self.assertTrue(can_get(True,True,False,False,True))

if __name__ == '__main__':
    unittest.main()
