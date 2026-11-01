"""Regression checks for the SOH-EXTREME Halloween gameplay logic changes.

Runs without the Archipelago host or game assets, so it can exercise the
health/guard decisions directly. C++ full-game integration remains separate.
"""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'archipelago' / 'soh_extreme'
HELPERS = BASE / '_vendor_oot_soh' / 'LogicHelpers.py'


class FeatureLogicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree = ast.parse(HELPERS.read_text(encoding='utf-8'))
        wanted = {'effective_health_at_least', 'take_damage', 'survive_fall', 'can_bypass_gerudo_patrol'}
        nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in wanted]
        assert {n.name for n in nodes} == wanted
        for node in nodes:
            node.returns = None
            for a in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs):
                a.annotation = None
        mod = ast.Module(body=nodes, type_ignores=[])
        ast.fix_missing_locations(mod)
        class Items:
            BOTTLE_WITH_FAIRY = 'Fairy'
            NAYRUS_LOVE = 'Nayru'
            GERUDO_MEMBERSHIP_CARD = 'Gerudo Card'
            FAIRY_BOW = 'Bow'
            FAIRY_SLINGSHOT = 'Slingshot'
        cls.items = Items
        ctx = {
            'Items': Items,
            'True_': lambda: True,
            'HeartsAtLeast': lambda amount: lambda b: b['hearts'] >= amount,
            'can_use_any': lambda item_names, b: any(n in b['items'] for n in item_names),
            'can_use': lambda name, b: name in b['items'],
            'has_item': lambda name, b: name in b['items'],
            'is_adult': lambda b: b['age'] == 'adult',
            'is_child': lambda b: b['age'] == 'child',
        }
        # The production rule-builder returns lazy Rule objects. These tiny
        # boolean versions retain the comparison outcomes for this test.
        ctx['HeartsAtLeast'] = lambda amount: RuleCondition(lambda b: b['hearts'] >= amount)
        ctx['can_use_any'] = lambda names, b: RuleCondition(lambda v: any(x in v['items'] for x in names))
        ctx['can_use'] = lambda name, b: RuleCondition(lambda v: name in v['items'])
        ctx['has_item'] = lambda name, b: RuleCondition(lambda v: name in v['items'])
        ctx['is_adult'] = lambda b: RuleCondition(lambda v: v['age'] == 'adult')
        ctx['is_child'] = lambda b: RuleCondition(lambda v: v['age'] == 'child')
        ctx['True_'] = lambda: RuleCondition(lambda b: True)
        exec(compile(mod, str(HELPERS), 'exec'), ctx)
        cls.helpers = ctx

    def bundle(self, hearts, age='child', *items):
        return dict(hearts=hearts, age=age, items=set(items))

    def rule(self, function, b, **kw):
        return self.helpers[function](b, **kw)(b)

    def test_ordinary_damage_needs_two_hearts(self):
        self.assertFalse(self.rule('take_damage', self.bundle(1)))
        self.assertTrue(self.rule('take_damage', self.bundle(2)))

    def test_fire_temple_two_heart_fall_needs_three(self):
        for hp in (0, 1, 2):
            self.assertFalse(self.rule('survive_fall', self.bundle(hp), damage_hearts=2))
        self.assertTrue(self.rule('survive_fall', self.bundle(3), damage_hearts=2))

    def test_fairy_or_nayru_protects_fall(self):
        self.assertTrue(self.rule('survive_fall', self.bundle(1, 'child', 'Fairy')))
        self.assertTrue(self.rule('survive_fall', self.bundle(1, 'adult', 'Nayru')))

    def test_guarded_routes_require_card_or_age_weapon(self):
        for age in ('child', 'adult'):
            self.assertFalse(self.rule('can_bypass_gerudo_patrol', self.bundle(3, age)))
            self.assertTrue(self.rule('can_bypass_gerudo_patrol', self.bundle(3, age, 'Gerudo Card')))
        self.assertTrue(self.rule('can_bypass_gerudo_patrol', self.bundle(3, 'child', 'Slingshot')))
        self.assertTrue(self.rule('can_bypass_gerudo_patrol', self.bundle(3, 'adult', 'Bow')))
        self.assertFalse(self.rule('can_bypass_gerudo_patrol', self.bundle(3, 'child', 'Bow')))
        self.assertFalse(self.rule('can_bypass_gerudo_patrol', self.bundle(3, 'adult', 'Slingshot')))

    def test_gerudo_safe_routes_not_blanket_gated(self):
        s = (BASE / '_vendor_oot_soh/location_access/overworld/gerudo_fortress.py').read_text()
        self.assertIn('(Regions.GV_FORTRESS_SIDE, lambda bundle: True_())',s)
        self.assertIn('(Regions.THIEVES_HIDEOUT_1_TORCH_CELL, lambda bundle: True_())',s)
        self.assertIn('can_bypass_gerudo_patrol(bundle)',s)

    def test_colossus_rocks_remain_age_independent(self):
        s = HELPERS.read_text()
        rock = s.split('def can_break_rocks(', 1)[1].split('def can_climb(', 1)[0]
        self.assertIn('has_explosives(bundle)',rock)
        self.assertIn('can_use(Items.MEGATON_HAMMER, bundle)',rock)
        self.assertNotIn('is_adult(bundle) & has_explosives(bundle)',rock)
        native = (ROOT/'soh/Enhancements/randomizer/logic.cpp')
        # Native source itself is not shipped in the minimal patch, so this
        # assertion is enforced on the complete-source distribution instead.

    def test_royal_tomb_destruction_bypasses_sign_soul(self):
        s=(ROOT/'soh/Enhancements/randomizer/ShuffleSigns.cpp').read_text()
        block=s.split('void Sign_RoyalTombSpawnCollectible(',1)[1].split('static CheckIdentity',1)[0]
        self.assertNotIn('SignSoulUnavailable()',block)
        self.assertIn('EVENTCHKINF_DESTROYED_ROYAL_FAMILY_TOMB',block)
        self.assertIn('COND_HOOK(OnSceneInit, shouldRegister',s)
        self.assertIn('identity->randomizerCheck != RC_GY_ROYAL_TOMB_GRAVE',s)

    def test_dungeon_voidout_uses_current_scene_checkpoint(self):
        s=(ROOT/'soh/Network/Archipelago/EntranceRuntime.inc').read_text()
        block=s.split('bool PrepareDungeonVoidOut() {',1)[1].split('void RememberGrottoLanding()',1)[0]
        self.assertIn('lastGroundPosition.scene == gPlayState->sceneNum',block)
        self.assertIn('roomEntry.scene == gPlayState->sceneNum',block)
        self.assertIn('gEntranceTable[gSaveContext.entranceIndex].scene != gPlayState->sceneNum',block)
        self.assertIn('point.roomIndex = landing->room',block)
        play=(ROOT/'src/code/z_play.c').read_text()
        self.assertIn('Archipelago_EntrancePrepareDungeonVoidOut();',play)


class RuleCondition:
    def __init__(self, fn): self.fn = fn
    def __call__(self, b): return bool(self.fn(b))
    def __or__(self, other): return RuleCondition(lambda b: self(b) or other(b))
    def __and__(self, other): return RuleCondition(lambda b: self(b) and other(b))


if __name__=='__main__': unittest.main()
