"""Regression for physical previous-entrance emergency returns and Spirit Temple."""
import json
from pathlib import Path
import unittest

BASE = Path(__file__).resolve().parents[2]
NATIVE = BASE / 'soh' / 'Network' / 'Archipelago'
# On a normal source checkout the tests live in archipelago/soh_extreme/tests.
REPO = Path(__file__).resolve().parents[3]


class PreviousEntranceReturns(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = (REPO / 'soh/Network/Archipelago/EntranceRuntime.inc').read_text()
        cls.play = (REPO / 'src/code/z_play.c').read_text()
        cls.wallmaster = (REPO / 'src/overlays/actors/ovl_En_Wallmas/z_en_wallmas.c').read_text()
        cls.header = (REPO / 'soh/Network/Archipelago/ArchipelagoC.h').read_text()
        cls.client = (REPO / 'soh/Network/Archipelago/ArchipelagoClient.cpp').read_text()
        cls.spirit = (REPO / 'soh/Enhancements/randomizer/location_access/dungeons/spirit_temple.cpp').read_text()
        cls.graph = json.loads((REPO / 'archipelago/soh_extreme/EnemyRoomGraph.json').read_text())

    def test_real_void_uses_previous_entrance_before_checkpoint(self):
        src = self.play.split('static void Play_TriggerVoidOutInternal', 1)[1].split('void Play_TriggerVoidOut(', 1)[0]
        self.assertLess(src.index('Archipelago_EntranceReturnToPreviousEntrance()'),
                        src.index('Archipelago_EntrancePrepareDungeonVoidOut()'))
        self.assertIn('if (realDungeonVoid)', src)
        self.assertIn('void Play_TriggerSceneExitVoidOut(PlayState* play)', self.play)
        self.assertIn('Play_TriggerVoidOutInternal(play, false);', self.play)

    def test_previous_return_does_not_require_mixed_pool(self):
        src = self.runtime.split('bool ReturnToPreviousEntrance()', 1)[1].split('bool RequestDungeonReturn()', 1)[0]
        self.assertIn('validPoint(previousScene)', src)
        self.assertIn('forcedPreviousEntrance = true;', src)
        self.assertIn('suppressTransitionChecks = true;', self.runtime.split('bool ApplyDungeonReturn(',1)[1].split('bool ReturnToPreviousEntrance()',1)[0])
        self.assertIn('!request.forcedPreviousEntrance', self.runtime)
        self.assertNotIn('UsesPreviousSceneReturn()', src)
        self.assertIn('previousScene = validPoint(earlierHistory)', src)

    def test_wallmaster_does_not_override_return_with_current_pos(self):
        src = self.wallmaster.split('if (this->timer == 0x1E)',1)[1]
        self.assertIn('if (Archipelago_EntranceWallmasterReturn())',src)
        self.assertIn('Play_LoadToLastEntrance(play);',src)
        self.assertIn('} else {\n            Play_TriggerRespawn(play);',src)
        func = self.runtime.split('bool WallmasterReturn()',1)[1].split('void CancelDungeonReturn()',1)[0]
        self.assertIn('return ReturnToPreviousEntrance();',func)

    def test_c_api_matches(self):
        self.assertIn('Archipelago_EntranceReturnToPreviousEntrance(void)',self.header)
        self.assertIn('SohExtreme::EntranceRuntime::ReturnToPreviousEntrance()',self.client)

    def test_spirit_adult_foyer_is_not_free_return(self):
        adult = self.graph['RR_SPIRIT_TEMPLE_ADULT_SIDE_HUB']['exits']
        edge = next(e for e in adult if e['target'] == 'RR_SPIRIT_TEMPLE_FOYER')
        self.assertEqual(edge['condition'],'logic->CanUse(RG_SILVER_GAUNTLETS)')
        self.assertIn('ENTRANCE(RR_SPIRIT_TEMPLE_FOYER,          logic->CanUse(RG_SILVER_GAUNTLETS))',self.spirit)
        # Emergency teleportation must NOT be installed as an Archipelago graph edge.
        self.assertNotIn('PreviousEntrance', json.dumps(self.graph))


if __name__ == '__main__':
    unittest.main()
