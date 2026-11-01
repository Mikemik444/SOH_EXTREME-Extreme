"""Offline regressions for final entrance graph installation and route safety."""
from __future__ import annotations
import importlib.util
import json
import sys
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
file = BASE / 'EntranceTopologyAudit.py'
spec = importlib.util.spec_from_file_location('soh_entrance_topology_audit', file)
topology = importlib.util.module_from_spec(spec)
spec.loader.exec_module(topology)


class TopologyAuditTests(unittest.TestCase):
    def test_consistent_physical_edges(self):
        expected = {258: ('Hyrule Field', 'Lake Hylia'),
                    99: ('Market', 'Treasure Chest Game'),
                    8192: ('Deku Tree Lobby', 'Deku Tree Middle')}
        topology.validate_edges(expected, dict(expected))

    def test_wrong_arrival_rejected(self):
        with self.assertRaisesRegex(ValueError, 'endpoint 99'):
            topology.validate_edges({99: ('Market', 'Treasure Chest Game')},
                                    {99: ('Market', 'Castle')})

    def test_wrong_source_rejected(self):
        with self.assertRaisesRegex(ValueError, 'endpoint 258'):
            topology.validate_edges({258: ('Hyrule Field', 'Lake Hylia')},
                                    {258: ('Lake Hylia', 'Lake Hylia')})

    def test_disconnected_edge_rejected(self):
        with self.assertRaisesRegex(ValueError, 'endpoint 99'):
            topology.validate_edges({99: ('Market', 'Treasure Chest Game')},
                                    {99: ('Market', None)})

    def test_missing_edge_rejected(self):
        with self.assertRaisesRegex(ValueError, 'missing'):
            topology.validate_edges({99: ('Market', 'Treasure Chest Game')}, {})

    def test_unexpected_edge_rejected(self):
        with self.assertRaisesRegex(ValueError, 'extra'):
            topology.validate_edges({}, {99: ('Market', 'Treasure Chest Game')})

    def test_final_generation_and_ut_both_audited(self):
        source = (BASE/'EntranceRandomizer.py').read_text(encoding='utf8')
        self.assertIn('def assert_installed_topology():', source)
        self.assertEqual(source.count('        assert_installed_topology()'), 1)
        self.assertIn('    assert_installed_topology()\n    final_state', source)
        self.assertIn('check.access_rule is not source_rule', source)
        self.assertIn('TopologyAudit.validate_edges(expected, actual)', source)

    def test_recovery_no_longer_compares_cleared_resolved_index(self):
        runtime = (ROOT/'soh/Network/Archipelago/EntranceRuntime.inc').read_text(encoding='utf8')
        beg = runtime.index('bool RecoverRejectedArrival(')
        end = runtime.index('\nint TransitionLayer(', beg)
        recovery = runtime[beg:end]
        self.assertNotIn('if (pendingArrival.resolvedIndex == policy->nativeIndex', recovery)
        self.assertIn('pendingArrival.resolvedIndex = policy->nativeIndex;', recovery)
        self.assertIn('gSaveContext.entranceIndex == policy->nativeIndex', recovery)

    def test_fence_market_and_water_portal_contracts(self):
        cat = json.loads((BASE/'EntranceCatalog.json').read_text(encoding='utf8'))
        by_id = {row['id']:row for row in cat}
        for src, source, target in [(258,'HYRULE_FIELD','LAKE_HYLIA'),
                                    (393,'LAKE_HYLIA','HYRULE_FIELD'),
                                    (99,'MARKET','MARKET_TREASURE_CHEST_GAME'),
                                    (473,'HYRULE_FIELD','ZR_FRONT'),
                                    (785,'ZR_FRONT','HYRULE_FIELD')]:
            # Water path source names are checked separately to avoid silently
            # rewriting the catalogue when the physical region enum changes.
            self.assertIn(src,by_id)
            if src in (99,258,393):
                self.assertEqual(by_id[src]['source'],source)
                self.assertEqual(by_id[src]['target'],target)
        for src in (473,785):
            self.assertEqual(by_id[src].get('gate'), 'swim')

if __name__=='__main__': unittest.main()
