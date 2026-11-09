"""Static contracts for the C++ boss-room and void-out routing paths.

These checks cannot replace a full Windows SOH game build or live playthrough.
"""
from pathlib import Path
import json
import unittest

ROOT = Path(__file__).resolve().parents[3]
PLAYER = ROOT / 'src/overlays/actors/ovl_player_actor/z_player.c'
PLAY = ROOT / 'src/code/z_play.c'
RUNTIME = ROOT / 'soh/Network/Archipelago/EntranceRuntime.inc'
POLICY = ROOT / 'archipelago/soh_extreme/EntranceDestinationPolicy.json'


class GohmaBossVoidSafety(unittest.TestCase):
    def test_all_eight_boss_room_destinations_have_distinct_native_scenes(self):
        rows = {row['id']: row for row in json.loads(POLICY.read_text('utf8'))['endpoints']}
        scenes = {12: 20, 141: 23, 769: 19, 773: 21,
                  1035: 18, 1039: 17, 1043: 24, 1047: 22}
        self.assertEqual(len(set(scenes.values())), 8)
        for native_index, scene in scenes.items():
            self.assertEqual(rows[native_index]['native_index'], native_index)
            self.assertTrue(all(layer['scene'] == scene for layer in rows[native_index]['normal_layers']))

    def test_intentional_scene_exit_does_not_use_real_void_recovery(self):
        play = PLAY.read_text('utf8')
        player = PLAYER.read_text('utf8')
        self.assertIn('Play_TriggerVoidOutInternal(play, true);', play)
        self.assertIn('Play_TriggerVoidOutInternal(play, false);', play)
        self.assertIn('Play_TriggerSceneExitVoidOut(play);', player)
        self.assertIn('gSaveContext.respawn[RESPAWN_MODE_DOWN].entranceIndex = play->nextEntranceIndex;', player)

    def test_failed_checkpoint_avoids_stale_respawn_in_shuffled_dungeon(self):
        body = PLAY.read_text('utf8').split('static void Play_TriggerVoidOutInternal(', 1)[1].split(
            '\nvoid Play_TriggerVoidOut(', 1)[0]
        self.assertIn('const bool hasSafeCheckpoint = Archipelago_EntrancePrepareDungeonVoidOut();', body)
        self.assertIn('if (!hasSafeCheckpoint && Archipelago_IsCurrentSaveFile()', body)
        self.assertIn('Archipelago_EntranceGameOverDungeonReturn()', body)
        self.assertIn('Entrance_GetDungeonSpawn(play->sceneNum)', body)
        self.assertIn('Archipelago_CancelEntranceTransition()', body)
        self.assertLess(body.index('play->nextEntranceIndex = gSaveContext.entranceIndex;'),
                        body.index('play->nextEntranceIndex = gSaveContext.respawn[RESPAWN_MODE_DOWN].entranceIndex;'))

    def test_boss_route_logging_identifies_source_and_actual_arrival(self):
        source = RUNTIME.read_text('utf8')
        self.assertIn('Boss route source {} -> destination {} (scene {}, native {})', source)
        self.assertIn('Boss arrival confirmed: source {} destination {} scene {}', source)
        self.assertIn('Boss arrival mismatch: source {} destination {} expected scene {}, got {}', source)


if __name__ == '__main__':
    unittest.main()
