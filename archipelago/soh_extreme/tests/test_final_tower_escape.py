"""Regression checks for the fixed Ganondorf -> Zelda escape -> Ganon route.

Run from the SOH root with:
    python -m unittest discover -s archipelago/soh_extreme/tests -p test_final_tower_escape.py -v
"""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[3]
AP = ROOT / "archipelago" / "soh_extreme"

# Ganondorf arena, collapse interiors/exteriors, final Ganon arena.
ESCAPE_SCENES = {14, 15, 25, 26, 79}
ESCAPE_INTERIORS = {14, 15, 26, 79}
STALFOS_GATED_ENTRANCES = {992, 996, 1206, 1303, 1308, 1316, 1388}


class FinalTowerEscapeRegressionTests(unittest.TestCase):
    def test_no_escape_stage_can_enter_the_shuffle_pool(self):
        catalog = json.loads((AP / "EntranceCatalog.json").read_text(encoding="utf8"))
        self.assertFalse([row for row in catalog
                          if row['source_scene'] in ESCAPE_SCENES or row['scene'] in ESCAPE_SCENES])
        self.assertTrue(any(row['scene'] == 10 for row in catalog),
                        'Normal tower climb should remain eligible for shuffle')

    def test_escape_transitions_follow_the_defeat_and_stalfos_logic(self):
        rows = json.loads((AP / "SceneTransitionCatalog.json").read_text(encoding="utf8"))
        escape = [row for row in rows if row['source_scene'] in ESCAPE_SCENES]
        self.assertGreater(len(escape), 10)
        self.assertEqual({row['source_scene'] for row in escape}, {14, 15, 25, 26})
        for row in escape:
            with self.subTest(entrance=row['index']):
                self.assertTrue(row.get('requires_final_ganon_key'))
                self.assertIn(row['target_scene'], ESCAPE_INTERIORS)
                self.assertIn(row['source'], ('GANONDORFS_LAIR', 'RR_GANONS_CASTLE_ESCAPE'))
                if row['entrances'][0] in STALFOS_GATED_ENTRANCES:
                    self.assertIn('CanKillEnemy(RE_STALFOS', row.get('condition', ''))
        # The entry to the escape has no artificial Stalfos requirement: the
        # parent Ganondorf's Lair -> Escape edge requires defeating Ganondorf.
        entry = [row for row in escape if row['source_scene'] == 25]
        self.assertEqual(len(entry), 1)
        self.assertEqual(entry[0]['index'], 'ENTR_GANONS_TOWER_COLLAPSE_EXTERIOR_0')
        self.assertEqual(entry[0]['source'], 'GANONDORFS_LAIR')
        vanilla_graph = (AP / '_vendor_oot_soh/location_access/dungeons/ganons_castle.py').read_text(encoding='utf8')
        self.assertIn('can_kill_enemy(bundle, Enemies.GANONDORF)', vanilla_graph)

    def test_enemy_randomizer_preserves_scripted_escape(self):
        source = (ROOT / 'soh/Enhancements/ExtraModes/EnemyRandomizer.cpp').read_text(encoding='utf8')
        self.assertIn('static bool IsFixedFinalCastleEscapeScene(', source)
        for scene in ('SCENE_GANONS_TOWER_COLLAPSE_EXTERIOR',
                      'SCENE_GANONS_TOWER_COLLAPSE_INTERIOR',
                      'SCENE_INSIDE_GANONS_CASTLE_COLLAPSE', 'SCENE_GANON_BOSS'):
            self.assertIn('case ' + scene + ':', source)
        self.assertEqual(source.count('if (IsFixedFinalCastleEscapeScene(play->sceneNum)) return;'), 2)
        self.assertIn('if (gPlayState && IsFixedFinalCastleEscapeScene(gPlayState->sceneNum)) return;', source)
        self.assertIn('VB_ADULT_ZELDA_SPAWN_STALFOS_IN_COLLAPSE', source)

    def test_ap_never_skips_the_escape(self):
        source = (ROOT / 'soh/Enhancements/TimeSavers/timesaver_hook_handlers.cpp').read_text(encoding='utf8')
        start = source.index('if (gSaveContext.entranceIndex == ENTR_GANONS_TOWER_COLLAPSE_EXTERIOR_0)')
        block = source[start:start + 1150]
        self.assertIn('!Archipelago_IsCurrentSaveFile()', block)
        self.assertIn('IS_BOSS_RUSH', block)
        self.assertIn('TimeSavers.SkipTowerEscape', block)


    def test_collapse_voids_restart_the_current_stage_not_the_old_tower(self):
        runtime = (ROOT / 'soh/Network/Archipelago/EntranceRuntime.inc').read_text(encoding='utf8')
        engine = (ROOT / 'src/code/z_play.c').read_text(encoding='utf8')
        bridge = (ROOT / 'soh/Network/Archipelago/ArchipelagoClient.cpp').read_text(encoding='utf8')
        header = (ROOT / 'soh/Network/Archipelago/ArchipelagoC.h').read_text(encoding='utf8')
        self.assertIn('bool RestartFinalCastleEscape()', runtime)
        self.assertIn('Archipelago_EntranceRestartFinalCastleEscape(void)', bridge)
        self.assertIn('Archipelago_EntranceRestartFinalCastleEscape(void)', header)
        block = runtime.split('bool RestartFinalCastleEscape() {', 1)[1].split('void RememberGrottoLanding()', 1)[0]
        for scene in ('SCENE_GANONS_TOWER_COLLAPSE_EXTERIOR',
                      'SCENE_GANONS_TOWER_COLLAPSE_INTERIOR',
                      'SCENE_INSIDE_GANONS_CASTLE_COLLAPSE'):
            self.assertIn('case ' + scene + ':', block)
        self.assertNotIn('case SCENE_GANON_BOSS:', block)
        self.assertIn('matchesCurrentScene(current) ? current : fallback', block)
        self.assertIn('suppressTransitionChecks = true;', block)
        self.assertIn('previousScene = previousBeforeArrival = {};', block)
        void = engine.split('static void Play_TriggerVoidOutInternal(', 1)[1].split('void Play_TriggerVoidOut(', 1)[0]
        self.assertLess(void.index('Archipelago_EntranceRestartFinalCastleEscape()'),
                        void.index('Archipelago_EntranceReturnToPreviousEntrance()'))
        self.assertIn('if (Archipelago_EntranceRestartFinalCastleEscape())',
                      engine.split('void Play_LoadToLastEntrance(', 1)[1])

    def test_scripted_stalfos_not_locked_by_soul_or_enemy_drop(self):
        souls = (ROOT / 'soh/Enhancements/randomizer/MegaSouls.cpp').read_text(encoding='utf8')
        rules = (AP / 'SceneTransitions.py').read_text(encoding='utf8')
        self.assertIn('static bool IsScriptedFinalEscapeStalfos(const Actor* actor)', souls)
        self.assertIn('actor->id == ACTOR_EN_TEST && actor->params == 5', souls)
        self.assertIn('actor == nullptr || IsScriptedFinalEscapeStalfos(actor)', souls)
        self.assertIn('H._can_kill_enemy_combat(bundle, Enemies.STALFOS, quantity=2)', rules)
        self.assertIn("entry.get('source_scene') in (14, 15, 26)", rules)


if __name__ == '__main__':
    unittest.main()
