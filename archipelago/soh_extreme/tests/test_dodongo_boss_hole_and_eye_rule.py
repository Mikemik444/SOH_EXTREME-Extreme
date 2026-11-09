"""Regression contracts for intentional boss-hole exits vs dungeon void-outs.

Code-level checks only. A full SOH build and in-game boss-hole replay are still
required, and these tests do not claim either has happened.
"""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / 'src' / 'code' / 'z_play.c'
PLAYER = ROOT / 'src' / 'overlays' / 'actors' / 'ovl_player_actor' / 'z_player.c'
CATALOG = ROOT / 'archipelago' / 'soh_extreme' / 'EntranceCatalog.json'
NATIVE = ROOT / 'soh' / 'Enhancements' / 'randomizer' / 'location_access' / 'dungeons' / 'dodongos_cavern.cpp'


class DodongoBossHoleRegression(unittest.TestCase):
    def test_exit_avoids_same_room_void_fallback(self):
        text = SOURCE.read_text('utf8')
        self.assertIn('void Play_TriggerSceneExitVoidOut(PlayState* play)', text)
        helper = text.split('static void Play_TriggerVoidOutInternal(', 1)[1].split('\nvoid Play_TriggerVoidOut(', 1)[0]
        self.assertIn('if (realDungeonVoid) {\n        const bool hasSafeCheckpoint = Archipelago_EntrancePrepareDungeonVoidOut();',helper)
        real = text.split('void Play_TriggerVoidOut(PlayState* play) {', 1)[1].split('}',1)[0]
        intended = text.split('void Play_TriggerSceneExitVoidOut(PlayState* play) {', 1)[1].split('}',1)[0]
        self.assertIn('Play_TriggerVoidOutInternal(play, true);', real)
        self.assertIn('Play_TriggerVoidOutInternal(play, false);', intended)

    def test_player_boss_hole_uses_scene_exit_special_path(self):
        player = PLAYER.read_text('utf8')
        section = player.split('if (GameInteractor_Should(VB_SET_VOIDOUT_FROM_SURFACE,',1)[1].split('gSaveContext.respawnFlag = -2;',1)[0]
        self.assertIn('gSaveContext.respawn[RESPAWN_MODE_DOWN].entranceIndex = play->nextEntranceIndex;',section)
        self.assertIn('Play_TriggerSceneExitVoidOut(play);',section)
        self.assertNotIn('Play_TriggerVoidOut(play);',section)
        self.assertIn('Entrance_OverrideNextIndex(play->nextEntranceIndex)', player)

    def test_python_eye_door_requires_usable_bow_or_slingshot(self):
        rows = {r['id']:r for r in json.loads(CATALOG.read_text('utf8'))}
        self.assertEqual(rows[8340]['condition'], 'CanHitEyeTargets()')
        self.assertEqual(rows[8340]['reverse'],8341)
        self.assertEqual(rows[8341]['reverse'],8340)
        native = NATIVE.read_text('utf8')
        self.assertIn('ENTRANCE(RR_DODONGOS_CAVERN_UPPER_LIZALFOS, logic->CanHitEyeTargets()),',native)

    def test_eye_helper_parity_and_cross_age_support(self):
        native = (ROOT / 'soh/Enhancements/randomizer/logic.cpp').read_text('utf8')
        snippet = native.split('bool Logic::CanHitEyeTargets() {',1)[1].split('}',1)[0]
        self.assertIn('CanUse(RG_FAIRY_BOW)', snippet)
        self.assertIn('CanUse(RG_FAIRY_SLINGSHOT)', snippet)
        python = (ROOT / 'archipelago/soh_extreme/_vendor_oot_soh/LogicHelpers.py').read_text('utf8')
        self.assertIn('return can_use_any([Items.FAIRY_BOW, Items.FAIRY_SLINGSHOT], bundle)',python)
        # can_use performs the equipped-age permission checks, including the
        # independently shuffled cross-age unlock items.
        self.assertIn('shuffle_cross_age_equipment',python)


if __name__ == '__main__':
    unittest.main()
