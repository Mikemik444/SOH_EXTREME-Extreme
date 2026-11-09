"""The game-owned tracker reconstructs older seeds from slot data, without YAML.

No installed Archipelago/Universal Tracker is needed for these regression tests.
"""
from __future__ import annotations
import importlib.util
import pathlib
import sys
import types
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
NATIVE = ROOT.parents[1] / 'soh' / 'Network' / 'Archipelago'

class NumericOption:
    @classmethod
    def from_any(cls, value):
        return types.SimpleNamespace(value=value)

class PlainOption:
    @classmethod
    def from_any(cls, value):
        return types.SimpleNamespace(value=value)

class DummyWorld:
    options_dataclass = types.SimpleNamespace(type_hints={
        'shuffle_roll': NumericOption,
        'song_note_songs': PlainOption,
        'shuffle_cross_age_equipment': NumericOption,
    })


def load_bootstrap():
    spec = importlib.util.spec_from_file_location('soh_test_bootstrap', ROOT / 'TrackerBootstrap.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TrackerCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.bootstrap = load_bootstrap()
        self.options = patch.dict(sys.modules, {'Options': types.SimpleNamespace(NumericOption=NumericOption)})
        self.options.start()
        self.addCleanup(self.options.stop)

    @staticmethod
    def snapshot(options):
        return {
            'extreme_all_options': dict(options),
            'required_trials': [],
            'shop_prices': {},
            'shop_vanilla_items': {},
            'extreme_active_locations': [100, 101],
            'archipelago_seed': 42,
        }

    def test_old_seed_without_new_cross_age_option_is_restored_disabled(self):
        args, seed, snapshot = self.bootstrap._resolved_arguments(
            DummyWorld, self.snapshot({'shuffle_roll': 1}), 'Player', 'Seed')
        self.assertEqual(seed, 42)
        self.assertEqual(args.shuffle_cross_age_equipment[1].value, 0)
        self.assertEqual(snapshot['extreme_all_options']['shuffle_cross_age_equipment'], 0)
        self.assertEqual(snapshot['extreme_all_options']['song_note_songs'], ['all'])

    def test_new_seed_still_uses_saved_cross_age_option(self):
        options = {'shuffle_roll': 0, 'shuffle_cross_age_equipment': 1, 'song_note_songs': ['all']}
        args, _, snapshot = self.bootstrap._resolved_arguments(DummyWorld, self.snapshot(options), 'P', 'S')
        self.assertEqual(args.shuffle_cross_age_equipment[1].value, 1)
        self.assertEqual(snapshot['extreme_all_options']['shuffle_cross_age_equipment'], 1)

    def test_missing_unmigrated_option_is_not_fabricated(self):
        with self.assertRaisesRegex(ValueError, 'missing resolved options'):
            self.bootstrap._resolved_arguments(DummyWorld, self.snapshot({}), 'P', 'S')

    def test_unrecognized_newer_logic_setting_is_not_silently_ignored(self):
        options = {'shuffle_roll': 0, 'shuffle_cross_age_equipment': 0,
                   'song_note_songs': ['all'], 'future_age_logic': 1}
        with self.assertRaisesRegex(ValueError, 'does not support'):
            self.bootstrap._resolved_arguments(DummyWorld, self.snapshot(options), 'P', 'S')

    def test_server_manifest_must_be_present(self):
        seed = self.snapshot({'shuffle_roll': 1})
        del seed['extreme_active_locations']
        with self.assertRaisesRegex(ValueError, 'missing its saved'):
            self.bootstrap._resolved_arguments(DummyWorld, seed, 'P', 'S')

    def test_local_yaml_is_not_referenced(self):
        source = (ROOT / 'TrackerBootstrap.py').read_text('utf-8')
        self.assertIn('LEGACY_OPTION_VALUES', source)
        self.assertIn('player_folder_override = None', source)
        self.assertNotIn('open(override_yaml_path', source)
        self.assertNotIn('with open(super_override_yaml_path', source)

    def test_release_strings_do_not_gate_native_snapshot(self):
        source = (NATIVE / 'TrackerMirror.h').read_text('utf-8')
        self.assertIn('Never gate display on candidate.version', source)
        self.assertNotIn('candidate.version != kTrackerVersion', source)
        self.assertIn('candidate.nonce != nonce_', source)

    def test_retries_do_not_stop_after_three_crashes(self):
        source = (NATIVE / 'ArchipelagoClient.cpp').read_text('utf-8')
        self.assertNotIn('finderWorkerAttempts < 3', source)
        self.assertIn('std::min<uint32_t>(finderWorkerAttempts + 1U, 4U)', source)

    def test_mirror_ignores_only_non_seed_checks(self):
        source = (ROOT / 'TrackerMirror.py').read_text('utf-8')
        self.assertIn('if i not in active or i in checked:', source)
        self.assertIn('continue', source[source.index('if i not in active or i in checked:'):])
        self.assertIn('if i in seen:raise ValueError', source)

if __name__ == '__main__':
    unittest.main()
