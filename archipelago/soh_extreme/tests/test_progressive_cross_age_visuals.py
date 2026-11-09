"""Progressive item generation, native receipt, 3D model and icon integration."""
from __future__ import annotations
from pathlib import Path
from PIL import Image
import ast
import unittest

BASE=Path(__file__).resolve().parents[3]
AP=BASE/'archipelago/soh_extreme'
NATIVE=BASE/'soh/Network/Archipelago/ArchipelagoClient.cpp'
ASSET=BASE/'soh/assets/custom/textures/parameter_static/gExtremeCrossAgeIcon.rgba32.png'

class ProgressiveVisuals(unittest.TestCase):
    def test_item_pool_contains_two_identical_progressive_items(self):
        s=(AP/'__init__.py').read_text()
        self.assertIn('extras.extend(("Progressive Cross-Age Equipment",) * 2)',s)
        self.assertIn('"Progressive Cross-Age Equipment": 9500402',s)
        self.assertNotIn('extras.extend(("Child Can Use Adult Items", "Adult Can Use Child Items"))',s)

    def test_native_maps_progressive_to_unique_model(self):
        s=NATIVE.read_text()
        self.assertIn('AP_ITEM_PROGRESSIVE_CROSS_AGE_EQUIPMENT = 9500402',s)
        self.assertIn('case AP_ITEM_PROGRESSIVE_CROSS_AGE_EQUIPMENT: randoGet = RG_PROGRESSIVE_CROSS_AGE_EQUIPMENT; break;',s)
        self.assertIn('case AP_ITEM_PROGRESSIVE_CROSS_AGE_EQUIPMENT:\n            return static_cast<int32_t>(RG_PROGRESSIVE_CROSS_AGE_EQUIPMENT);',s)
        self.assertIn('case AP_ITEM_PROGRESSIVE_CROSS_AGE_EQUIPMENT:\n            // First copy:',s)
        # Only legacy item IDs are intercepted for silent immediate grants.
        branch=s[s.index('if (itemId == AP_ITEM_CHILD_CAN_USE_ADULT_ITEMS ||'):s.index('RandomizerGet randoGet = RG_NONE;',s.index('if (itemId == AP_ITEM_CHILD_CAN_USE_ADULT_ITEMS ||'))]
        self.assertNotIn('AP_ITEM_PROGRESSIVE_CROSS_AGE_EQUIPMENT',branch)
        self.assertIn('FinalizeMajorItemReceipt',s)

    def test_persistent_flags_keep_directional_order(self):
        s=NATIVE.read_text()
        start=s.index('case AP_ITEM_PROGRESSIVE_CROSS_AGE_EQUIPMENT:\n            // First copy:')
        end=s.index('case AP_ITEM_SPEAK:',start)
        block=s[start:end]
        self.assertLess(block.index('RAND_INF_CHILD_CAN_USE_ADULT_ITEMS'),block.index('RAND_INF_ADULT_CAN_USE_CHILD_ITEMS'))
        self.assertIn('Flags_SetRandomizerInf(RAND_INF_CHILD_CAN_USE_ADULT_ITEMS)',block)
        self.assertIn('Flags_SetRandomizerInf(RAND_INF_ADULT_CAN_USE_CHILD_ITEMS)',block)

    def test_icon_is_32x32_with_transparency_and_distinct_native_mesh(self):
        with Image.open(ASSET) as i:
            self.assertEqual(i.size,(32,32))
            self.assertEqual(i.mode,'RGBA')
            self.assertLess(i.getchannel('A').getextrema()[0],255)
            self.assertGreater(i.getchannel('A').getextrema()[1],200)
        visuals=(BASE/'soh/Enhancements/randomizer/ProgressionItemVisuals.cpp').read_text()
        item=(BASE/'soh/Enhancements/randomizer/item_list.cpp').read_text()
        self.assertIn('void SohExtreme_DrawCrossAge',visuals)
        self.assertIn('sCrossAgeEmblemVertices',visuals)
        self.assertIn('SetCustomDrawFunc(SohExtreme_DrawCrossAge)',item)
        self.assertIn('CustomIcon(gExtremeCrossAgeIconTex)',item)
        self.assertIn('case RG_PROGRESSIVE_CROSS_AGE_EQUIPMENT:',(BASE/'soh/Enhancements/randomizer/randomizer.cpp').read_text())
        self.assertIn('Level 2/2', (BASE/'soh/Enhancements/randomizer/Messages/ItemMessages.cpp').read_text())

    def test_tracker_reflects_per_save_level(self):
        t=(BASE/'soh/Enhancements/randomizer/randomizer_item_tracker.cpp').read_text()
        self.assertIn('case RG_PROGRESSIVE_CROSS_AGE_EQUIPMENT:',t)
        self.assertIn('Progressive Cross-Age Equipment (2/2)',t)
        self.assertIn('crossAgeItems.begin()',t)

if __name__ == '__main__': unittest.main()
