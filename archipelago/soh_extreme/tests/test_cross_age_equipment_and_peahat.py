"""Source contract checks and executable tests of the actual vendored can_use().

Runs without an Archipelago installation or C++ runtime. Gameplay/equipment
animation requires a native SOH build and cannot be verified here.
"""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT=Path(__file__).resolve().parents[3]
WORLD=ROOT/'archipelago'/'soh_extreme'
NATIVE=ROOT/'soh'/'Network'/'Archipelago'/'ArchipelagoClient.cpp'
FLAGS=ROOT/'soh'/'Enhancements'/'randomizer'/'randomizerEnums'/'RandomizerInf.h'
LOGIC=ROOT/'soh'/'Enhancements'/'randomizer'/'logic.cpp'
TIMELY=ROOT/'soh'/'Enhancements'/'Cheats'/'TimelessEquipment.cpp'

class BoolRule:
    def __init__(self,value): self.value=bool(value)
    def __and__(self,other):return BoolRule(self.value and other.value)
    def __or__(self,other):return BoolRule(self.value or other.value)
    def __bool__(self):return self.value

class ItemNames:
    def __getattr__(self,n):return n

class TestedAgeLogic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree=ast.parse((WORLD/'_vendor_oot_soh'/'LogicHelpers.py').read_text('utf-8'))
        fn=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='can_use']
        assert len(fn)==1
        node=fn[0]
        node.returns=None
        node.args.args[0].annotation=None
        node.args.args[1].annotation=None
        cls.call=compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),'LogicHelpers.py','exec')

    def use(self,item,age,inventory,cross_age_enabled=True):
        names=ItemNames()
        itemdata={
           'FAIRY_BOW':SimpleNamespace(adult_only=True,child_only=False,item_type='regular'),
           'MEGATON_HAMMER':SimpleNamespace(adult_only=True,child_only=False,item_type='regular'),
           'HOOKSHOT':SimpleNamespace(adult_only=True,child_only=False,item_type='regular'),
           'FAIRY_SLINGSHOT':SimpleNamespace(adult_only=False,child_only=True,item_type='regular'),
           'BOOMERANG':SimpleNamespace(adult_only=False,child_only=True,item_type='regular'),
           'KOKIRI_SWORD':SimpleNamespace(adult_only=False,child_only=True,item_type='regular'),
        }
        d={
           'Items':names, 'Rule':BoolRule,'item_data_table':itemdata,
           'ItemType':SimpleNamespace(magic='magic',song='song'),
           'has_item':lambda item,b:BoolRule(item in inventory),
           'Has':lambda n:BoolRule(n in inventory),
           'is_adult':lambda b:BoolRule(age=='adult'),
           'is_child':lambda b:BoolRule(age=='child'),
           'can_use':None,
           'True_':lambda:BoolRule(True),
           'HasLiveAmmo':lambda ammo,refill:BoolRule(True),
           'can_swim':lambda b:BoolRule(True),
           'has_bean_soul':lambda b:BoolRule(True),
           'can_play_song':lambda item,b:BoolRule(True),
        }
        exec(self.call,d)
        options=SimpleNamespace(shuffle_cross_age_equipment=SimpleNamespace(value=int(cross_age_enabled)))
        return bool(d['can_use'](item,(None,SimpleNamespace(options=options))))

    def test_child_adult_weapon_unlock_is_directional(self):
        owned={'FAIRY_BOW','MEGATON_HAMMER','HOOKSHOT'}
        for weapon in owned:
            self.assertFalse(self.use(weapon,'child',owned))
            self.assertTrue(self.use(weapon,'adult',owned))
            self.assertTrue(self.use(weapon,'child',owned|{'Child Can Use Adult Items'}))
            self.assertFalse(self.use(weapon,'child',owned|{'Adult Can Use Child Items'}))

    def test_adult_child_weapon_unlock_is_directional(self):
        owned={'FAIRY_SLINGSHOT','BOOMERANG','KOKIRI_SWORD'}
        for weapon in owned:
            self.assertFalse(self.use(weapon,'adult',owned))
            self.assertTrue(self.use(weapon,'child',owned))
            self.assertTrue(self.use(weapon,'adult',owned|{'Adult Can Use Child Items'}))
            self.assertFalse(self.use(weapon,'adult',owned|{'Child Can Use Adult Items'}))

    def test_off_setting_never_allows_cross_age_even_if_item_is_present(self):
        self.assertFalse(self.use('FAIRY_BOW','child',{'FAIRY_BOW','Child Can Use Adult Items'},False))
        self.assertFalse(self.use('FAIRY_SLINGSHOT','adult',{'FAIRY_SLINGSHOT','Adult Can Use Child Items'},False))
        self.assertTrue(self.use('FAIRY_BOW','adult',{'FAIRY_BOW'},False))
        self.assertTrue(self.use('FAIRY_SLINGSHOT','child',{'FAIRY_SLINGSHOT'},False))

    def test_item_itself_is_still_required(self):
        self.assertFalse(self.use('FAIRY_BOW','child',{'Child Can Use Adult Items'}))
        self.assertFalse(self.use('FAIRY_SLINGSHOT','adult',{'Adult Can Use Child Items'}))

    def test_pool_unlocks_respect_opt_in_setting(self):
        astmain=ast.parse((WORLD/'__init__.py').read_text('utf-8'))
        methods=[n for n in ast.walk(astmain) if isinstance(n,ast.FunctionDef) and n.name=='create_items']
        self.assertEqual(len(methods),1)
        method=methods[0]
        initializers=[i for i,n in enumerate(method.body) if isinstance(n,ast.AnnAssign)
                      and isinstance(n.target,ast.Name) and n.target.id=='extras']
        self.assertEqual(len(initializers),1)
        i=initializers[0]
        self.assertEqual(ast.literal_eval(method.body[i].value),[])
        toggle=method.body[i+1]
        self.assertIsInstance(toggle,ast.If)
        self.assertEqual(ast.unparse(toggle.test),'o.shuffle_cross_age_equipment.value')
        for enabled,expected in ((False,[]),(True,['Child Can Use Adult Items','Adult Can Use Child Items'])):
            context={'o':SimpleNamespace(shuffle_cross_age_equipment=SimpleNamespace(value=int(enabled)))}
            mini=ast.fix_missing_locations(ast.Module(body=method.body[i:i+2],type_ignores=[]))
            exec(compile(mini,'create_items.py','exec'),context)
            self.assertEqual(context['extras'],expected)
        items={}
        for n in astmain.body:
            if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='EXTREME_ITEMS' for t in n.targets):
                items=ast.literal_eval(n.value)
        self.assertEqual(items['Child Can Use Adult Items'],9500400)
        self.assertEqual(items['Adult Can Use Child Items'],9500401)
        self.assertEqual(len(set(items.values())),len(items))

    def test_client_persists_each_item_independently(self):
        text=NATIVE.read_text('utf-8')
        self.assertIn('case AP_ITEM_CHILD_CAN_USE_ADULT_ITEMS:\n            Flags_SetRandomizerInf(RAND_INF_CHILD_CAN_USE_ADULT_ITEMS);',text)
        self.assertIn('case AP_ITEM_ADULT_CAN_USE_CHILD_ITEMS:\n            Flags_SetRandomizerInf(RAND_INF_ADULT_CAN_USE_CHILD_ITEMS);',text)
        self.assertIn('if (itemId == AP_ITEM_CHILD_CAN_USE_ADULT_ITEMS ||',text)
        self.assertIn('if (!ApplyExtremePersistentApItem(itemId)) return false;',text)
        lines=FLAGS.read_text('utf-8')
        self.assertLess(lines.index('RAND_INF_KAK_ADULT_TREE'),lines.index('RAND_INF_CHILD_CAN_USE_ADULT_ITEMS'))
        self.assertLess(lines.index('RAND_INF_ADULT_CAN_USE_CHILD_ITEMS'),lines.index('RAND_INF_MAX)'))

    def test_native_age_checks_dynamic_not_cheat_toggle(self):
        text=TIMELY.read_text('utf-8')
        self.assertIn('COND_VB_SHOULD(VB_PLAYER_MEETS_AGE_REQ, true, {',text)
        self.assertIn('COND_VB_SHOULD(VB_ITEM_MEETS_AGE_REQ, true, {',text)
        self.assertIn('COND_VB_SHOULD(VB_SLOT_MEETS_AGE_REQ, true, {',text)
        self.assertIn('RAND_INF_CHILD_CAN_USE_ADULT_ITEMS',text)
        self.assertIn('RAND_INF_ADULT_CAN_USE_CHILD_ITEMS',text)
        logic=LOGIC.read_text('utf-8')
        self.assertIn('return mayUseAdultEquipment;',logic)
        self.assertIn('return mayUseChildEquipment;',logic)

    def test_adult_masks_follow_only_adult_unlock(self):
        text=(ROOT/'soh/Enhancements/AdultMasks.cpp').read_text('utf-8')
        self.assertIn('Flags_GetRandomizerInf(RAND_INF_ADULT_CAN_USE_CHILD_ITEMS)',text)
        fn=text[text.index('bool Ship_MasksEquippableAsAdult()'):text.index('static bool IsMask')]
        self.assertNotIn('RAND_INF_CHILD_CAN_USE_ADULT_ITEMS',fn)

    def test_child_bow_arrow_cycle_follows_only_child_unlock(self):
        text=(ROOT/'soh/Enhancements/Items/ArrowCycle.cpp').read_text('utf-8')
        fn=text[text.index('static bool CanCycleArrows()'):text.index('static s8 GetNextArrowType')]
        self.assertIn('Flags_GetRandomizerInf(RAND_INF_CHILD_CAN_USE_ADULT_ITEMS)',fn)
        self.assertNotIn('RAND_INF_ADULT_CAN_USE_CHILD_ITEMS',fn)

    def test_peahat_6_7_ranged_only_both_implementations(self):
        loc=(WORLD/'EnemyDropLocations.py').read_text('utf-8')
        for n in (6,7):
            self.assertIn(f"Peahat {n}',",loc)
            self.assertIn(f"Peahat {n}', 980052{n-1}",loc)
        rules=(WORLD/'EnemyDropRules.py').read_text('utf-8')
        self.assertIn('"peahat_flying": sling | bow | hook,',rules)
        self.assertIn('"peahat": melee | sling | bow | hook,',rules)
        native=(ROOT/'soh/Enhancements/randomizer/randomizer_check_tracker.cpp').read_text('utf-8')
        self.assertIn('case EFC_PEAHAT_FLYING: return sling || bow || hook;',native)
        self.assertIn('case EFC_PEAHAT: return melee || sling || bow || hook;',native)

if __name__=='__main__': unittest.main()
