"""Royal Family's Tomb: the randomized grave check belongs to Lullaby, not talk.

These static regression checks run without the Archipelago or native game runtime.
The full C++ client and live gameplay still require separate verification.
"""
import ast
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[3]
PY_ROOT = ROOT / 'archipelago' / 'soh_extreme'
RC = 'RC_GY_ROYAL_TOMB_GRAVE'


class RoyalTombLullabyLogicTests(unittest.TestCase):
    def test_python_rule_requires_playable_lullaby(self):
        source = (PY_ROOT / '__init__.py').read_text(encoding='utf-8')
        block = source.split('if fork_loc.rc == "RC_GY_ROYAL_TOMB_GRAVE":', 1)[1]
        self.assertIn('require_native_fork(location, can_use(Items.ZELDAS_LULLABY, bundle))', block[:140])
        ast.parse(source)

    def test_royal_tomb_not_categorized_as_readable_sign_soul(self):
        source = (PY_ROOT / '__init__.py').read_text(encoding='utf-8')
        self.assertIn('and fork_loc.rc != "RC_GY_ROYAL_TOMB_GRAVE"', source)
        # Ordinary gravestone signs must retain their Soul gate.
        self.assertIn('if o.shuffle_sign_soul.value and is_named_sign:', source)
        metadata = (PY_ROOT / 'NativeLogic.py').read_text(encoding='utf-8')
        self.assertIn("('RR_THE_GRAVEYARD', 'RC_GY_ROYAL_TOMB_GRAVE', 9700254, ()),", metadata)
        self.assertNotIn("('RR_THE_GRAVEYARD', 'RC_GY_ROYAL_TOMB_GRAVE', 9700254, ('Sign Soul',)),", metadata)

    def test_native_access_rule_requires_lullaby_not_talking(self):
        native = (ROOT / 'soh/Enhancements/randomizer/location_access/overworld/graveyard.cpp').read_text(encoding='utf-8')
        matching = [line.strip() for line in native.splitlines() if 'LOCATION(RC_GY_ROYAL_TOMB_GRAVE,' in line]
        self.assertEqual(len(matching), 1)
        self.assertIn('logic->CanUse(RG_ZELDAS_LULLABY)', matching[0])
        self.assertNotIn('CanRead()', matching[0])
        # Other readable signs stay readable, not Lullaby-gated.
        self.assertIn('LOCATION(RC_GY_LEFT_OF_ROYAL_TOMB_GRAVE,       logic->CanRead())',native)

    def test_native_event_grants_item_without_sign_soul(self):
        source = (ROOT / 'soh/Enhancements/randomizer/ShuffleSigns.cpp').read_text(encoding='utf-8')
        function = source.split('void Sign_RoyalTombSpawnCollectible(', 1)[1].split('static CheckIdentity', 1)[0]
        self.assertIn('EVENTCHKINF_DESTROYED_ROYAL_FAMILY_TOMB', function)
        self.assertIn('RAND_INF_GY_ROYAL_TOMB_GRAVE', function)
        self.assertNotIn('SignSoulUnavailable()', function)
        self.assertIn('COND_HOOK(OnFlagSet, shouldRegister, Sign_RoyalTombSpawnCollectible)', source)
        self.assertIn('COND_HOOK(OnSceneInit, shouldRegister', source)


if __name__ == '__main__':
    unittest.main()
