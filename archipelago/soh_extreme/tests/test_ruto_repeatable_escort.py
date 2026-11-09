"""Regressions for Jabu Jabu's Ruto escort in shuffled-room seeds."""
import hashlib
import json
from pathlib import Path
import unittest

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
COND = 'logic->Get(LOGIC_JABU_RUTO_IN_1F) && AnyAgeTime([]{return logic->CanKillEnemy(RE_BIG_OCTO);})'

def checksum(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()

class RutoRepeatableEscortTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = json.loads((BASE/'EntranceCatalog.json').read_text())
        cls.by_id = {e['id']:e for e in cls.rows}
        cls.policy = json.loads((BASE/'EntranceDestinationPolicy.json').read_text())
        cls.original_doors = {e['id']:e for e in json.loads((BASE/'DungeonDoorCatalog.json').read_text())}
        cls.hook = (ROOT/'soh/Enhancements/randomizer/hook_handlers.cpp').read_text()
        cls.routing = (BASE/'EntranceRandomizer.py').read_text()
        cls.native = (ROOT/'soh/Enhancements/randomizer/location_access/dungeons/jabujabus_belly.cpp').read_text()

    def test_big_octo_door_requires_ruto_and_fight(self):
        self.assertEqual(self.by_id[8490]['condition'], COND)
        self.assertEqual(self.original_doors[11202090]['condition'], COND)
        self.assertIn('ENTRANCE(RR_JABU_JABUS_BELLY_BIGOCTO,        '+COND, self.native)

    def test_ruto_carrier_doors_cannot_be_shuffled_away(self):
        self.assertIn('LOCAL_CARRIER_DOORS', self.routing)
        self.assertIn('e[\'source_scene\'] == 2 and e[\'door\'] in {2, 4, 11, 12, 14, 21}', self.routing)
        self.assertIn('if source in LOCAL_CARRIER_DOORS and dest != source:', self.routing)
        self.assertIn('mapping = {e[\'id\']: e[\'id\'] for e in eligible if e[\'id\'] in LOCAL_CARRIER_DOORS}', self.routing)

    def test_kidnapped_ruto_recovers_on_shuffled_jabu_reload_without_resetting_story(self):
        begin = self.hook.index('case VB_RUTO_BE_CONSIDERED_NOT_KIDNAPPED:')
        code = self.hook[begin:self.hook.index('case VB_SET_VOIDOUT_FROM_SURFACE:', begin)]
        self.assertIn('Archipelago_EntranceShuffleActive()', code)
        self.assertIn('gPlayState->sceneNum == SCENE_JABU_JABU', code)
        self.assertIn('*should = recoverableJabuEscort || !Flags_GetInfTable(INFTABLE_145)', code)
        self.assertNotIn('Flags_UnsetInfTable(', code)
        self.assertNotIn('Actor_Spawn(', code)
        actor = (ROOT/'src/overlays/actors/ovl_En_Ru1/z_en_ru1.c').read_text()
        self.assertIn('if (!func_80AEB020(this, play)) {',actor)

    def test_apworld_destination_policy_matches_new_door(self):
        policy_rows = {e['id']: e for e in self.policy['endpoints']}
        self.assertEqual(self.policy['catalog_sha256'],checksum(sorted(self.rows,key=lambda r:r['id'])))
        self.assertEqual(policy_rows[8490]['catalog_row_sha256'],checksum(self.by_id[8490]))

    def test_spirit_temple_adult_foyer_return_needs_gauntlets(self):
        native = (ROOT/'soh/Enhancements/randomizer/location_access/dungeons/spirit_temple.cpp').read_text()
        self.assertIn('ENTRANCE(RR_SPIRIT_TEMPLE_FOYER,          logic->CanUse(RG_SILVER_GAUNTLETS))',native)
        graph = json.loads((BASE/'EnemyRoomGraph.json').read_text())
        edges = graph['RR_SPIRIT_TEMPLE_ADULT_SIDE_HUB']['exits']
        self.assertTrue(any(e['target']=='RR_SPIRIT_TEMPLE_FOYER' and 'SILVER_GAUNTLETS' in e['condition'] for e in edges))

if __name__ == '__main__':
    unittest.main()
