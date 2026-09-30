"""Local native prerequisites missing from the inherited stock AP graph.

These are conjuncts, not substitute region routes. Names are canonical enums;
the rule is evaluated using the check's actual age-specific parent region.
"""
from ._vendor_oot_soh import LogicHelpers as H
from ._vendor_oot_soh.Enums import Locations as L, Items as I, Enemies as E, EnemyDistance as D


def grab_or_kill_skull(bundle):
    return H.can_grab(bundle) | H.can_kill_enemy(bundle, E.GOLD_SKULLTULA)


def climb_or_longshot(bundle):
    return H.can_climb(bundle) | H.can_use(I.LONGSHOT, bundle)


STOCK_INTERACTIONS = {
    # Native death_mountain_crater.cpp: the fairy's stone is behind a bomb wall.
    L.DMC_GOSSIP_STONE_BIG_FAIRY: H.has_explosives,
    # Native forest_temple.cpp: both checks sit above the first-room vines.
    L.FOREST_TEMPLE_FIRST_ROOM_CHEST: climb_or_longshot,
    L.FOREST_TEMPLE_GS_FIRST_ROOM: climb_or_longshot,
    # Native market/kakariko/LLR/ZF: lifting/throwing is itself a shuffled action.
    L.MARKET_MARKET_GS_GUARD_HOUSE: lambda b: H.can_break_crates(b) & grab_or_kill_skull(b),
    L.KAK_GS_GUARDS_HOUSE: grab_or_kill_skull,
    L.KAK_GS_SKULLTULA_HOUSE: grab_or_kill_skull,
    L.KAK_GS_HOUSE_UNDER_CONSTRUCTION: grab_or_kill_skull,
    L.KAK_GS_TREE: grab_or_kill_skull,
    L.LLR_GS_RAIN_SHED: grab_or_kill_skull,
    L.LLR_GS_TREE: grab_or_kill_skull,
    L.ZF_GS_TREE: grab_or_kill_skull,
    # One cucco is in a large crate. Cucco Soul + Grab cannot break that crate.
    L.KAK_ANJU_AS_CHILD: H.can_break_crates,
    # Native deku_tree.cpp: hitting the vines Skulltula requires this range.
    L.DEKU_TREE_GS_BASEMENT_VINES: lambda b: H.can_kill_enemy(b,E.GOLD_SKULLTULA,D.BOMB_THROW),
}
