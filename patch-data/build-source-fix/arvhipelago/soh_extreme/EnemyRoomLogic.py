"""Native room graph for finite enemy checks (SOH-EXTREME 0.11.18).

The graph is exported from the same C++ ENTRANCE/EVENT_ACCESS definitions used
by Check Finder. Unknown syntax/dependencies are errors, never free access.
Private regions do not add checks or change network IDs. Their only entrances
are the corresponding established dungeon entrances; room clear switches and
age-dependent actions are represented as real local events.
"""
from __future__ import annotations

import dataclasses
from typing import ClassVar
import hashlib
import json
import re
from enum import StrEnum
from collections import Counter
from functools import lru_cache
from importlib.resources import files

from Options import OptionError
from rule_builder.rules import Rule, And, Or, Has, True_, False_
from ._vendor_oot_soh import LogicHelpers as H
from ._vendor_oot_soh.Enums import Regions, Items, Events, Enemies, EnemyDistance, Ages
from ._vendor_oot_soh.Regions import SohRegion

GRAPH = json.loads(files(__package__).joinpath('EnemyRoomGraph.json').read_text())
ENEMY_ROOM_MAP = json.loads(files(__package__).joinpath('EnemyRoomMap.json').read_text())
_region_name_counts = Counter(row['name'] for row in GRAPH.values())
NativeEnemyRegions = StrEnum('NativeEnemyRegions', {
    key: 'EXTREME Enemy Route: ' + row['name'] + ((' ['+key+']') if _region_name_counts[row['name']]>1 else '')
    for key, row in GRAPH.items()
})
ENTRY_BINDINGS = {
    'RR_DEKU_TREE_ENTRYWAY': 'DEKU_TREE_ENTRYWAY',
    'RR_DODONGOS_CAVERN_ENTRYWAY': 'DODONGOS_CAVERN_ENTRYWAY',
    'RR_JABU_JABUS_BELLY_ENTRYWAY': 'JABU_JABUS_BELLY_ENTRYWAY',
    'RR_FOREST_TEMPLE_ENTRYWAY': 'FOREST_TEMPLE_ENTRYWAY',
    'RR_FIRE_TEMPLE_ENTRYWAY': 'FIRE_TEMPLE_ENTRYWAY',
    'RR_WATER_TEMPLE_ENTRYWAY': 'WATER_TEMPLE_ENTRYWAY',
    'RR_SPIRIT_TEMPLE_ENTRYWAY': 'SPIRIT_TEMPLE_ENTRYWAY',
    'RR_SHADOW_TEMPLE_ENTRYWAY': 'SHADOW_TEMPLE_ENTRYWAY',
    'RR_BOTW_ENTRYWAY': 'BOTTOM_OF_THE_WELL_ENTRYWAY',
    'RR_ICE_CAVERN_ENTRYWAY': 'ICE_CAVERN_ENTRYWAY',
    'RR_GERUDO_TRAINING_GROUND_ENTRYWAY': 'GERUDO_TRAINING_GROUND_ENTRYWAY',
    'RR_GANONS_CASTLE_ENTRYWAY': 'GANONS_CASTLE_ENTRYWAY',
}

def resolve_enemy_region(token):
    if token.startswith('RR_'):
        return NativeEnemyRegions[token]
    return Regions[token]


def event_item(token):
    return 'EXTREME Native Event: ' + token


def as_rule(value):
    if isinstance(value, bool):
        return True_() if value else False_()
    return value


# AST grammar deliberately accepts only the expressions emitted by the source
# exporter. There is no eval/exec of C++ or slot data.
@lru_cache(maxsize=None)
def parse(expression):
    expression = re.sub(r'/\*.*?\*/|//[^\n]*', '', expression, flags=re.S)
    expression = re.sub(r'ctx->GetDungeon\([^)]*\)->IsVanilla\(\)', 'true', expression)
    expression = re.sub(r'ctx->GetDungeon\([^)]*\)->IsMQ\(\)', 'false', expression)
    expression = re.sub(r'ctx->GetTrial\((\w+)\)->IsSkipped\(\)', r'TrialSkipped(\1)', expression)
    expression = re.sub(r'ctx->GetOption\((\w+)\)\.Is\((\w+)\)', r'OptionIs(\1,\2)', expression)
    expression = expression.replace('ctx->GetTrickOption', 'Trick').replace('ctx->GetOption', 'Option')
    expression = expression.replace('logic->', '').replace('Rando::', '').replace('(bool)', '').rstrip('; \t\r\n')
    expression = re.sub(r'\[\s*\]\s*\{\s*return\s+', 'Lambda(', expression)
    expression = re.sub(r';\s*\}', ')', expression)
    tokens = re.findall(r'\s*(\d+|[A-Za-z_]\w*|&&|\|\||>=|<=|==|!=|[!?:(),<>])', expression)
    residue = re.sub(r'\s*(\d+|[A-Za-z_]\w*|&&|\|\||>=|<=|==|!=|[!?:(),<>])', '', expression)
    if residue.strip():
        raise OptionError('Unsupported native room expression syntax: ' + expression)
    index = 0
    def atom():
        nonlocal index
        if index >= len(tokens): raise OptionError('Truncated native room expression: ' + expression)
        t = tokens[index]; index += 1
        if t == '!': return ('not', atom())
        if t == '(':
            n = conditional()
            if index >= len(tokens) or tokens[index] != ')': raise OptionError('Unclosed native expression: ' + expression)
            index += 1; return n
        if t.isdigit(): return ('constant', int(t))
        if t in ('true','false'): return ('constant', t == 'true')
        if index < len(tokens) and tokens[index] == '(':
            index += 1; args = []
            while tokens[index] != ')':
                args.append(conditional())
                if tokens[index] != ',': break
                index += 1
            if tokens[index] != ')': raise OptionError('Malformed native call: ' + expression)
            index += 1; return ('call', t, tuple(args))
        return ('name', t)
    def comparison():
        nonlocal index
        n=atom()
        if index<len(tokens) and tokens[index] in ('>=','<=','>','<','==','!='):
            op=tokens[index];index+=1;n=('compare',op,n,atom())
        return n
    def conjunction():
        nonlocal index
        nodes=[comparison()]
        while index<len(tokens) and tokens[index]=='&&':
            index+=1;nodes.append(comparison())
        return nodes[0] if len(nodes)==1 else ('and',tuple(nodes))
    def disjunction():
        nonlocal index
        nodes=[conjunction()]
        while index<len(tokens) and tokens[index]=='||':
            index+=1;nodes.append(conjunction())
        return nodes[0] if len(nodes)==1 else ('or',tuple(nodes))
    def conditional():
        nonlocal index
        n=disjunction()
        if index<len(tokens) and tokens[index]=='?':
            index+=1;a=conditional()
            if tokens[index]!=':':raise OptionError('Malformed ternary: '+expression)
            index+=1;n=('select',n,a,conditional())
        return n
    result=conditional()
    if index!=len(tokens):raise OptionError('Unparsed native expression: '+expression)
    return result


ALIASES = {
    'BIGGORON_SWORD':'BIGGORONS_SWORD','GIANTS_KNIFE':'BIGGORONS_SWORD',
    'FIRE_ARROWS':'FIRE_ARROW','ICE_ARROWS':'ICE_ARROW','LIGHT_ARROWS':'LIGHT_ARROW',
    'BOMBCHU_5':'BOMBCHUS_5','BOMBCHU_10':'BOMBCHUS_10','BOMBCHU_20':'BOMBCHUS_20',
    'SCARECROWS_SONG':'SCARECROW',
}
CAPABILITIES = {
    'RG_POWER_BRACELET':('shuffle_grab','Grab / Power Bracelet'),
    'RG_CLIMB':('shuffle_climb','Climb'), 'RG_CRAWL':('shuffle_crawl','Crawl'),
    'RG_ROLL':('shuffle_roll','Roll'), 'RG_OPEN_CHEST':('shuffle_open_chest','Open Chest'),
    'RG_SHOVEL':('shuffle_shovel','Shovel'), 'RG_NPC_SOUL':('shuffle_npc_soul','NPC Soul'),
    'RG_POT_SOUL':('shuffle_pot_soul','Pot Soul'),
}
SILVER = {
 'RG_SHADOW_SILVER_BLADES':'Shadow Silver: Blades', 'RG_SHADOW_SILVER_PIT':'Shadow Silver: Pit',
 'RG_SHADOW_SILVER_SPIKES':'Shadow Silver: Spikes', 'RG_SPIRIT_SILVER_CHILD':'Spirit Silver: Child',
 'RG_SPIRIT_SILVER_SUN':'Spirit Silver: Sun', 'RG_SPIRIT_SILVER_BOULDERS':'Spirit Silver: Boulders',
 'RG_BOTW_SILVER':'Bottom of the Well Silver', 'RG_ICE_CAVERN_SILVER_BLADES':'Ice Cavern Silver: Blades',
 'RG_ICE_CAVERN_SILVER_BLOCK':'Ice Cavern Silver: Block', 'RG_GTG_SILVER_SLOPE':'Training Ground Silver: Slope',
 'RG_GTG_SILVER_LAVA':'Training Ground Silver: Lava', 'RG_GTG_SILVER_WATER':'Training Ground Silver: Water',
 'RG_GANONS_CASTLE_SILVER_LIGHT':"Ganon's Castle Silver: Light", 'RG_GANONS_CASTLE_SILVER_FOREST':"Ganon's Castle Silver: Forest",
 'RG_GANONS_CASTLE_SILVER_FIRE':"Ganon's Castle Silver: Fire", 'RG_GANONS_CASTLE_SILVER_SPIRIT':"Ganon's Castle Silver: Spirit",
}
RESOURCES = {
 'LOGIC_STICK_ACCESS': Events.CAN_FARM_STICKS, 'LOGIC_NUT_ACCESS': Events.CAN_FARM_NUTS,
 'LOGIC_BUG_ACCESS':Events.CAN_ACCESS_BUGS, 'LOGIC_FAIRY_ACCESS':Events.CAN_ACCESS_FAIRIES,
 'LOGIC_BLUE_FIRE_ACCESS':Events.CAN_ACCESS_BLUE_FIRE, 'LOGIC_FISH_ACCESS':Events.CAN_ACCESS_FISH,
}
KEYS = {
 'SCENE_FOREST_TEMPLE':'FOREST_TEMPLE_SMALL_KEY', 'SCENE_FIRE_TEMPLE':'FIRE_TEMPLE_SMALL_KEY',
 'SCENE_WATER_TEMPLE':'WATER_TEMPLE_SMALL_KEY', 'SCENE_SPIRIT_TEMPLE':'SPIRIT_TEMPLE_SMALL_KEY',
 'SCENE_SHADOW_TEMPLE':'SHADOW_TEMPLE_SMALL_KEY', 'SCENE_BOTTOM_OF_THE_WELL':'BOTTOM_OF_THE_WELL_SMALL_KEY',
 'SCENE_GERUDO_TRAINING_GROUND':'TRAINING_GROUND_SMALL_KEY', 'SCENE_INSIDE_GANONS_CASTLE':'GANONS_CASTLE_SMALL_KEY',
}
SIMPLE_HELPERS = {
 'HasExplosives':'has_explosives','BlastOrSmash':'blast_or_smash','BlueFire':'blue_fire',
 'CanJumpslash':'can_jump_slash','CanJumpslashExceptHammer':'can_jump_slash_except_hammer',
 'CanUseSword':'can_use_sword','CanAttack':'can_attack','CanDamage':'can_damage',
 'CanShield':'can_shield','CanStandingShield':'can_standing_shield','TakeDamage':'take_damage',
 'CanGetDekuBabaSticks':'can_get_deku_baba_sticks','CanGetDekuBabaNuts':'can_get_deku_baba_nuts',
 'CanBreakPots':'can_break_pots','CanBreakSmallCrates':'can_break_small_crates',
 'CanBreakMudWalls':'can_break_mud_walls','CanHitEyeTargets':'can_hit_eye_targets',
 'CanReflectNuts':'can_reflect_nuts','HasFireSource':'has_fire_source',
 'HasFireSourceWithTorch':'has_fire_source_with_torch','CanClearStalagmite':'can_clear_stalagmite',
 'CanUseProjectile':'can_use_projectile','CallGossipFairy':'call_gossip_fairy',
 'CanDetonateUprightBombFlower':'can_detonate_upright_bomb_flower','ScarecrowsSong':'scarecrows_song',
}
FORMULAS = {
 'SpiritExplosiveKeyLogic':'SmallKeys(SCENE_SPIRIT_TEMPLE, HasExplosives() ? 1 : 2)',
 'OuterWestHandLogic':'HasExplosives() && (HasItem(RG_CLIMB) || CanUse(RG_LONGSHOT)) && HasItem(RG_POWER_BRACELET) && SmallKeys(SCENE_SPIRIT_TEMPLE, HasItem(RG_LONGSHOT) ? 3 : 5)',
 'CanClimbLadder':'HasItem(RG_CLIMB) || (Trick(RT_HOOKSHOT_LADDERS) && CanUse(RG_HOOKSHOT))',
 'CanClimbHighLadder':'HasItem(RG_CLIMB) || (Trick(RT_HOOKSHOT_LADDERS) && CanUse(RG_LONGSHOT))',
 'BunnyHovers':'CanUse(RG_HOVER_BOOTS) && BunnyHood()',
 'ReachScarecrow':'ScarecrowsSong() && CanUse(RG_HOOKSHOT)',
 'ReachDistantScarecrow':'ScarecrowsSong() && CanUse(RG_LONGSHOT)',
 'SunlightArrows':'Option(RSK_SUNLIGHT_ARROWS) && CanUse(RG_LIGHT_ARROWS)',
 'Water3FCentralToHighEmblem':'(IsAdult && CanUse(RG_HOVER_BOOTS)) || CanMiddairGroundJump() || (Get(LOGIC_WATER_SCARECROW) && CanUse(RG_HOOKSHOT)) || ((IsAdult || BunnyHood()) && Trick(RT_WATER_HIGH_EMBLEM_JUMP))',
 'WaterRisingTargetTo3FCentral':'CanUse(RG_LONGSHOT) || (Trick(RT_HOVER_BOOST_SIMPLE) && Trick(RT_DAMAGE_BOOST_SIMPLE) && HasExplosives() && CanUse(RG_HOVER_BOOTS))',
 'SpiritSunBlockSouthLedge':'HasItem(RG_POWER_BRACELET) || IsAdult || CanKillEnemy(RE_BEAMOS) || BunnyHovers() || (CanUse(RG_HOOKSHOT) && (HasFireSource() || (Get(LOGIC_SPIRIT_SUN_BLOCK_TORCH) && (CanUse(RG_STICKS) || (Trick(RT_SPIRIT_SUN_CHEST) && CanUse(RG_FAIRY_BOW))))))',
 'SpiritEastToSwitch':'(IsAdult && (Trick(RT_SPIRIT_STATUE_JUMP) || BunnyHood())) || CanUse(RG_HOVER_BOOTS) || (CanUse(RG_ZELDAS_LULLABY) && CanUse(RG_HOOKSHOT))',
}
WATER_FORMULAS = {
 'WL_LOW':'Get(LOGIC_WATER_LOW) || (Get(LOGIC_WATER_COULD_LOW_FROM_HIGH) && (Get(LOGIC_WATER_COULD_HIGH_FROM_MID) || Get(LOGIC_WATER_HIGH)) && CanUse(RG_ZELDAS_LULLABY))',
 'WL_LOW_OR_MID':'Get(LOGIC_WATER_LOW) || Get(LOGIC_WATER_MIDDLE) || ((Get(LOGIC_WATER_COULD_LOW_FROM_HIGH) || Get(LOGIC_WATER_COULD_LOW)) && CanUse(RG_ZELDAS_LULLABY))',
 'WL_MID':'Get(LOGIC_WATER_MIDDLE) || (Get(LOGIC_WATER_LOW) && Get(LOGIC_WATER_COULD_MIDDLE)) || ((Get(LOGIC_WATER_COULD_LOW_FROM_HIGH) || Get(LOGIC_WATER_COULD_LOW)) && Get(LOGIC_WATER_COULD_MIDDLE) && CanUse(RG_ZELDAS_LULLABY))',
 'WL_HIGH':'Get(LOGIC_WATER_HIGH) || (Get(LOGIC_WATER_COULD_HIGH_FROM_MID) && Get(LOGIC_WATER_COULD_MIDDLE))',
 'WL_HIGH_OR_MID':'Get(LOGIC_WATER_MIDDLE) || Get(LOGIC_WATER_HIGH) || Get(LOGIC_WATER_COULD_MIDDLE)',
}

@dataclasses.dataclass
class NativeAsAge(Rule, game="SOH-EXTREME"):
    """Evaluate inventory conditions in Spirit's alternate-age key universe.

    This does not claim the alternate age can reach the region. It matches the
    native SpiritShared inventory test; actual access is supplied by the parent.
    Every temporary age assignment is restored, including on exceptions.
    """
    inner: Rule
    adult: bool

    def _instantiate(self, world):
        return self.Resolved(inner=self.inner.resolve(world), adult=self.adult,
                             player=world.player, caching_enabled=False)

    class Resolved(Rule.Resolved):
        inner: Rule.Resolved
        adult: bool
        force_recalculate: ClassVar[bool] = True
        def _evaluate(self,state):
            old=state._soh_age[self.player]
            try:
                state._soh_age[self.player]=Ages.ADULT if self.adult else Ages.CHILD
                return self.inner(state)
            finally:
                state._soh_age[self.player]=old
        def item_dependencies(self): return self.inner.item_dependencies()
        def region_dependencies(self): return self.inner.region_dependencies()
        def explain_str(self,state=None): return "Native Spirit shared-key alternate-age requirement"

SPIRIT_ACCESS = {
 'RR_SPIRIT_TEMPLE_SUN_BLOCK_CHEST_LEDGE':(
   'SpiritExplosiveKeyLogic() && (HasItem(RG_CLIMB) || CanUse(RG_LONGSHOT)) && HasItem(RG_POWER_BRACELET)',
   'SpiritExplosiveKeyLogic() && (HasItem(RG_CLIMB) || CanUse(RG_LONGSHOT)) && HasItem(RG_POWER_BRACELET)'),
 'RR_SPIRIT_TEMPLE_OUTER_RIGHT_HAND':('OuterWestHandLogic()','OuterWestHandLogic()'),
 'RR_SPIRIT_TEMPLE_SHORTCUT_SWITCH':(
   'SpiritExplosiveKeyLogic() && CanUse(RG_HOOKSHOT) && SpiritEastToSwitch()',
   'SpiritEastToSwitch() && (HasItem(RG_CLIMB) || CanUse(RG_LONGSHOT)) && HasItem(RG_POWER_BRACELET)'),
}

class NativeRoomCompiler:
    def __init__(self, world):
        self.world=world
        self.events={}
        self.flags={e['event'] for r in GRAPH.values() for e in r['events']}
        self.unknown_tricks=set()

    def bundle(self, rr): return NativeEnemyRegions[rr],self.world

    def expr(self, expression, rr):
        try: return as_rule(self.node(parse(expression),rr))
        except (KeyError,AttributeError,TypeError,ValueError) as e:
            raise OptionError(f'Native enemy room rule failed in {rr}: {expression}\n{e}') from e

    def latch(self, rr, ast):
        key=rr+':'+repr(ast)
        label='EXTREME Native Action: '+hashlib.sha256(key.encode()).hexdigest()[:20]
        if label not in self.events:
            self.events[label]=(rr,ast)
        return Has(label)

    def node(self,n,rr):
        kind=n[0];b=self.bundle(rr)
        if kind=='constant':return n[1]
        if kind=='name':
            if n[1]=='IsAdult':return H.is_adult(b)
            if n[1]=='IsChild':return H.is_child(b)
            return n[1]
        if kind in ('and','or'):
            values=[as_rule(self.node(a,rr)) for a in n[1]]
            return And(*values) if kind=='and' else Or(*values)
        if kind=='not':
            v=self.node(n[1],rr)
            if not isinstance(v,bool):raise OptionError('Nonmonotone native negation is unsupported')
            return not v
        if kind=='select':
            test=self.node(n[1],rr)
            if isinstance(test,bool):return self.node(n[2] if test else n[3],rr)
            # All exported inventory ternaries select a SHORTER range/fewer
            # keys when the condition holds. The fallback is still usable.
            return Or(And(as_rule(test),as_rule(self.node(n[2],rr))),as_rule(self.node(n[3],rr)))
        if kind=='compare':
            op,left,right=n[1:]
            v=self.node(right,rr)
            if left[0]=='call' and left[1] in ('WaterTimer','FireTimer'):
                if op not in ('>=','>'):raise OptionError('Unexpected timer comparison')
                return getattr(H,'water_timer_at_least' if left[1]=='WaterTimer' else 'fire_timer_at_least')(b,v+(op=='>'))
            a=self.node(left,rr)
            return {'==':lambda:a==v,'!=':lambda:a!=v,'>=':lambda:a>=v,'<=':lambda:a<=v,'>':lambda:a>v,'<':lambda:a<v}[op]()
        if kind!='call':raise OptionError('Unknown native AST node '+repr(n))
        name,args=n[1:]
        if name=='Lambda':return self.node(args[0],rr)
        if name=='AnyAgeTime':return self.latch(rr,args[0])
        # Distribute conditional argument selection over the monotone call.
        for i,a in enumerate(args):
            if a[0]=='select':
                test=self.node(a[1],rr)
                aa=list(args);bb=list(args);aa[i]=a[2];bb[i]=a[3]
                if isinstance(test,bool):return self.node(('call',name,tuple(aa if test else bb)),rr)
                return Or(And(as_rule(test),as_rule(self.node(('call',name,tuple(aa)),rr))),
                          as_rule(self.node(('call',name,tuple(bb)),rr)))
        values=[self.node(a,rr) for a in args]
        return self.call(name,values,rr,args)

    def call(self,name,a,rr,raw=()):
        b=self.bundle(rr);o=self.world.options
        if name in SIMPLE_HELPERS:return getattr(H,SIMPLE_HELPERS[name])(b,*a)
        if name in FORMULAS:return self.expr(FORMULAS[name],rr)
        if name=='Get':
            if a[0]=='LOGIC_SPIRIT_SUN_BLOCK_TORCH':return False # declared but never set in the supplied native source
            if a[0] not in self.flags and a[0] not in RESOURCES:
                raise OptionError('Undefined native local event '+a[0])
            return Has(RESOURCES.get(a[0],event_item(a[0])))
        if name in ('CanUse','HasItem'):
            token=a[0]
            if token in CAPABILITIES:
                rule=H.extreme_requirement(b,*CAPABILITIES[token])
                return rule & H.is_child(b) if name=='CanUse' and token=='RG_CRAWL' else rule
            if token.startswith('RG_SPEAK_'):
                return H.can_interact_npc(b,token[9:].capitalize())
            if token in SILVER:
                mode=o.shuffle_silver.value
                if mode==1:return Has(SILVER[token],5)
                if mode==2:return Has(SILVER[token])
                if mode==3:return True_()
                return Has(event_item('LOGIC_'+token[3:]))
            key=ALIASES.get(token[3:],token[3:])
            item=Items[key]
            return (H.can_use(item,b) if name=='CanUse' else H.has_item(item,b,*a[1:]))
        if name=='Trick':
            token=a[0][3:]
            if token not in H.Tricks.__members__:
                # These native-only tricks have no AP option and therefore no
                # enabled slot-data bit. Their unmodified native default is off.
                self.unknown_tricks.add(a[0]);return False
            return bool(o.enable_all_tricks.value or str(H.Tricks[token]) in o.tricks_in_logic.value)
        if name=='Option':
            key={'RSK_MEDALLION_LOCKED_TRIALS':'medallion_locked_trials','RSK_SUNLIGHT_ARROWS':'sunlight_arrows'}[a[0]]
            return bool(getattr(o,key).value)
        if name=='OptionIs':
            if a==['RSK_SHUFFLE_DUNGEON_ENTRANCES','RO_DUNGEON_ENTRANCE_SHUFFLE_OFF']:return True
            raise OptionError('Unknown native option comparison '+repr(a))
        if name=='TrialSkipped':
            target=a[0].removeprefix('TK_').removesuffix('_TRIAL').lower()
            return not any(target in str(t).lower() for t in self.world.ganons_trials)
        if name=='BunnyHood':
            # RSK_BUNNY_HOOD is not exposed by this AP world and AP saves use
            # the authoritative slot configuration (default disabled).
            return False
        if name=='SmallKeys':return H.small_keys(Items[KEYS[a[0]]],a[1],b)
        if name=='WaterLevel':return self.expr(WATER_FORMULAS[a[0]],rr)
        if name=='CanGroundJump':return H.can_ground_jump(b,*a)
        if name=='CanMiddairGroundJump':
            return self.expr('Trick(RT_GROUND_JUMP_HARD) && CanStandingShield() && CanUse(RG_HOVER_BOOTS) && (CanUse(RG_BOMB_BAG)'+(' || HasItem(RG_GORONS_BRACELET)' if a and a[0] else '')+')',rr)
        if name=='IsFireLoopLocked':return o.small_key_shuffle.current_key in ('anywhere','any_dungeon','overworld')
        if name=='CanHitSwitch':
            dist=EnemyDistance[(a[0] if a else 'ED_CLOSE')[3:]]
            rule=H.can_hit_at_range(b,dist,True,a[1] if len(a)>1 else False)
            if dist<=EnemyDistance.BOOMERANG:rule |= H.can_use(Items.BOOMERANG,b)
            if dist<=EnemyDistance.SHORT_JUMPSLASH:rule |= H.can_use(Items.MEGATON_HAMMER,b)
            return rule
        if name in ('CanKillEnemy','CanPassEnemy','CanAvoidEnemy'):
            enemy=a[0][3:]
            if enemy=='WALLTULA':enemy='BIG_SKULLTULA'
            more=list(a[1:])
            if more:more[0]=EnemyDistance[more[0][3:]]
            if name=='CanKillEnemy':return H.can_kill_enemy(b,Enemies[enemy],*more)
            if name=='CanPassEnemy':return H.can_pass_enemy(b,Enemies[enemy],*more)
            if enemy=='BEAMOS':return True_() # native Beamos can be walked around
            raise OptionError('Unsupported avoidance '+enemy)
        if name in ('CanRecoilHover','CanRecoilHoverFromObject'):
            gate=self.expr('CanUse(RG_HOVER_BOOTS) && Trick(RT_HOVER_BOOST_SIMPLE)',rr)
            f={
              'RECOIL_SWORD':'CanJumpslash()',
              'RECOIL_SWORD_AND_SHIELD':'(CanJumpslash() && CanStandingShield()) || CanUse(RG_MEGATON_HAMMER)',
              'RECOIL_HAMMER':'CanUse(RG_MEGATON_HAMMER)',
              'RECOIL_HAMMER_AND_SHIELD':'CanUse(RG_MEGATON_HAMMER) && CanStandingShield()',
              'TRECOIL_LONG_AND_SHIELD':'(CanUse(RG_STICKS) || CanUse(RG_BIGGORON_SWORD)) && CanStandingShield()',
              'TRECOIL_SHORT':'CanUse(RG_MEGATON_HAMMER) || CanUse(RG_KOKIRI_SWORD) || CanUse(RG_MASTER_SWORD) || CanUse(RG_STICKS) || CanUse(RG_BIGGORON_SWORD)',
              'TRECOIL_MASTER':'CanUse(RG_MASTER_SWORD) || CanUse(RG_STICKS) || CanUse(RG_BIGGORON_SWORD)',
              'TRECOIL_LONG':'CanUse(RG_STICKS) || CanUse(RG_BIGGORON_SWORD)',
            }[a[0]]
            return gate & self.expr(f,rr)
        if name=='CanVoid':
            fairy=H.has_item(Items.BOTTLE_WITH_FAIRY,b)
            damage=getattr(o,'damage_multiplier',None)
            if damage is not None and damage.current_key=='ohko':return fairy
            return fairy | H.hearts_at_least(b,2) | (H.has_item(Items.DOUBLE_DEFENSE,b)&H.hearts_at_least(b,1))
        if name in ('SpiritShared','SpiritCertainAccess'):
            target=a[0]
            child_access,adult_access=(self.expr(v,rr) for v in SPIRIT_ACCESS[target])
            child=NativeAsAge(child_access,False)
            adult=NativeAsAge(adult_access,True)
            certain_child=child & H.small_keys(Items.SPIRIT_TEMPLE_SMALL_KEY,5,b)
            certain_adult=adult & H.small_keys(Items.SPIRIT_TEMPLE_SMALL_KEY,3,b)
            if name=='SpiritCertainAccess':
                return (H.is_child(b)&certain_child)|(H.is_adult(b)&certain_adult)
            condition=as_rule(a[1])
            normal=(H.is_child(b)&condition&(certain_child|(adult&NativeAsAge(condition,True)))) | (
                    H.is_adult(b)&condition&(certain_adult|(child&NativeAsAge(condition,False))))
            if len(a)>2 and a[2]:
                # This export's anyAge invocation has a literal true condition.
                if raw[1] != ('call','Lambda',(('constant',True),)):
                    raise OptionError('Unsupported multi-age Spirit callback')
                return certain_child|certain_adult|normal
            return normal
        raise OptionError('Unknown native enemy room helper '+name)

    def install(self):
        w=self.world
        for rr,row in GRAPH.items():
            for edge in row['exits']:
                target=edge['target']
                if target not in GRAPH:continue # MQ and overworld exits are not private entrances.
                rule=self.expr(edge['condition'],rr)
                H.connect_regions(NativeEnemyRegions[rr],w,[(NativeEnemyRegions[target],rule)])
            for i,e in enumerate(row['events']):
                item=RESOURCES.get(e['event'],event_item(e['event']))
                H.add_events(NativeEnemyRegions[rr],w,[(f'EXTREME Native {rr} event {i}',item,self.expr(e['condition'],rr))])
        installed=set()
        while len(installed)<len(self.events):
            for label,(rr,ast) in list(self.events.items()):
                if label in installed:continue
                rule=as_rule(self.node(ast,rr))
                H.add_events(NativeEnemyRegions[rr],w,[(label,label,rule)])
                installed.add(label)
        w._extreme_native_room_audit={'regions':len(GRAPH),'actions':len(installed),
            'unavailable_native_only_tricks':sorted(self.unknown_tricks)}


def create_enemy_room_graph(world):
    for region in NativeEnemyRegions:
        world.multiworld.regions.append(SohRegion(str(region),world.player,world.multiworld))
    for native,base in ENTRY_BINDINGS.items():
        H.connect_regions(Regions[base],world,[(NativeEnemyRegions[native],True_())])
    compiler=NativeRoomCompiler(world)
    world._extreme_room_compiler=compiler
    # create_items resolves randomized trials/keyrings and UT's authoritative
    # slot settings. Compile predicates only afterwards, during set_rules.


def prune_optional_native_actions(world):
    """Drop impossible *internal action sites*, never network locations or rules.

    Native flags often have several activation sites, including disabled tricks
    and child-only reverse-entrance routes. AP full accessibility must not demand
    every impossible alternative site. A full-inventory fixed point identifies
    those sites; their flags are NOT granted and dependent paths remain closed.
    UT receives the same site list through slot data rather than recomputing it
    from the player's currently received inventory.
    """
    if getattr(world, '_extreme_room_actions_pruned', False):
        return
    internal = {loc.name: loc for loc in world.get_locations()
                if loc.address is None and loc.name.startswith(
                    ('EXTREME Native RR_', 'EXTREME Native Action: '))}
    if world.using_ut and 'enemy_room_disabled_actions' in world.passthrough:
        disabled = list(world.passthrough['enemy_room_disabled_actions'])
        unknown = set(disabled) - internal.keys()
        if unknown:
            raise OptionError(f'Enemy-room action manifest does not match this AP world: {sorted(unknown)}')
    else:
        state = world.multiworld.get_all_state(False)
        disabled = sorted(name for name, loc in internal.items() if not loc.can_reach(state))
    for name in disabled:
        loc = internal[name]
        assert loc.address is None and loc.locked
        loc.parent_region.locations.remove(loc)
    world._extreme_room_disabled_actions = disabled
    world._extreme_room_actions_pruned = True
