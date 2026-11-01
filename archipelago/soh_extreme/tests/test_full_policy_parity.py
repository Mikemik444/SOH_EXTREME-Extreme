"""Verify every reviewed Python native arrival layer is identical in C++.

A source/destination map can be structurally valid but still load the wrong
scene/spawn when these independent generated files disagree.
"""
from __future__ import annotations
import json
import re
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
NATIVE = BASE.parents[1]/'soh/Network/Archipelago/EntranceDestinationData.inc'
RECORD = re.compile(r'^\{(-?\d+), (-?\d+), (-?\d+), (-?\d+), (-?\d+), '\
                    r'\{\{(\d+), (\d+)\}, \{(\d+), (\d+)\}, '\
                    r'\{(\d+), (\d+)\}, \{(\d+), (\d+)\}\}\},')
KINDS = {'native':0, 'grotto_load':1, 'grotto_return':2, 'door':3}


class DestinationParityTests(unittest.TestCase):
    def test_every_policy_layer_matches_cplusplus(self):
        actual = []
        for line in NATIVE.read_text(encoding='utf8').splitlines():
            match = RECORD.match(line)
            if match:
                actual.append(tuple(map(int, match.groups())))
        policies = json.loads((BASE/'EntranceDestinationPolicy.json').read_text(encoding='utf8'))['endpoints']
        self.assertEqual(len(actual), 721)
        self.assertEqual(len(policies), len(actual))
        for policy, native in zip(policies, actual):
            expected = (policy['id'], policy['native_index'], KINDS[policy['kind']],
                        policy['source_age_mask'], policy['arrival_age_mask'],
                        *(field for layer in policy['normal_layers'] for field in
                          (layer['scene'], layer['spawn'])))
            with self.subTest(source=policy['id']):
                self.assertEqual(native, expected)

    def test_every_small_key_door_scene_has_budget(self):
        catalog = json.loads((BASE/'EntranceCatalog.json').read_text(encoding='utf8'))
        key_scenes = {3,4,5,6,7,8,11,13}
        small_key_doors = [e for e in catalog if e['door'] >= 0 and
                           ((e['actor']==46 and ((e['params']>>6)&15)==11) or
                            (e['actor']==9 and ((e['params']>>7)&7)==1))]
        self.assertGreater(len(small_key_doors), 50)
        for e in small_key_doors:
            with self.subTest(source=e['id']):
                self.assertIn(e['source_scene'], key_scenes)

if __name__ == '__main__': unittest.main()
