from collections import Counter
from typing import TYPE_CHECKING, Callable, Iterable, NamedTuple
from collections import Counter

from BaseClasses import MultiWorld, Options, Item
from .Locations import location_data_table
from worlds.generic.Rules import set_rule
from worlds.AutoWorld import LogicMixin
from .Enums import HintKeys as hk, Items, Locations
from .Items import SohItem, item_data_table, ItemType, no_rules_bottles

if TYPE_CHECKING:
    from . import SohWorld

import logging
logger = logging.getLogger("SOH_OOT.Logic")

class locationPair(NamedTuple):
    player: int
    location: int

class StaticHint(NamedTuple):
    key: hk
    locations: list[locationPair]
    def serialize(self):
        return {self.key.value: [[loc.player, loc.location] for loc in self.locations]}

class OptionItemMapping(NamedTuple):
    option: Options.NumericOption
    hint_items: list[Items]

def GetNonlocalHintOptionMapping(world: "SohWorld") -> dict[hk, OptionItemMapping]:
    return {
        hk.GANONDORF_HINT: OptionItemMapping(world.options.ganondorf_hint, [Items.LIGHT_ARROW, Items.MASTER_SWORD]),
        hk.SHEIK_HINT: OptionItemMapping(world.options.sheik_la_hint, [Items.LIGHT_ARROW]),
        hk.DAMPES_DIARY: OptionItemMapping(world.options.dampe_diary_hint, [Items.PROGRESSIVE_HOOKSHOT]),
        hk.GREG_RUPEE: OptionItemMapping(world.options.greg_hint, [Items.GREG_THE_GREEN_RUPEE]),
        hk.ALTAR_CHILD: OptionItemMapping(world.options.tot_altar_hint, [Items.KOKIRIS_EMERALD, Items.GORONS_RUBY, Items.ZORAS_SAPPHIRE]),
        hk.ALTAR_ADULT: OptionItemMapping(world.options.tot_altar_hint, [Items.LIGHT_MEDALLION, Items.FOREST_MEDALLION, Items.FIRE_MEDALLION, Items.WATER_MEDALLION, Items.SPIRIT_MEDALLION, Items.SHADOW_MEDALLION]),
        hk.FOREST_BOSS_KEY_HINT: OptionItemMapping(world.options.boss_key_hint, [Items.FOREST_TEMPLE_BOSS_KEY]),
        hk.FIRE_BOSS_KEY_HINT: OptionItemMapping(world.options.boss_key_hint, [Items.FIRE_TEMPLE_BOSS_KEY]),
        hk.WATER_BOSS_KEY_HINT: OptionItemMapping(world.options.boss_key_hint, [Items.WATER_TEMPLE_BOSS_KEY]),
        hk.SPIRIT_BOSS_KEY_HINT: OptionItemMapping(world.options.boss_key_hint, [Items.SPIRIT_TEMPLE_BOSS_KEY]),
        hk.SHADOW_BOSS_KEY_HINT: OptionItemMapping(world.options.boss_key_hint, [Items.SHADOW_TEMPLE_BOSS_KEY]),
        hk.GANONS_BOSS_KEY_HINT: OptionItemMapping(world.options.boss_key_hint, [Items.GANONS_CASTLE_BOSS_KEY]),
        hk.SARIA_HINT: OptionItemMapping(world.options.saria_hint, [Items.PROGRESSIVE_MAGIC_METER]),
        hk.MIDO_HINT: OptionItemMapping(world.options.mido_hint, [Items.KOKIRI_SWORD]),
        hk.FISHING_POLE: OptionItemMapping(world.options.fishing_pole_hint, [Items.FISHING_POLE])
    }

def _belongs_to(world, item):
    if item.player == world.player:
        return True
    group = world.multiworld.groups.get(item.player, {})
    return world.player in group.get("players", ())


def _item_locations(world, name):
    return sorted((loc for loc in world.multiworld.get_locations()
                   if loc.address is not None and loc.item is not None
                   and loc.item.name == name and _belongs_to(world, loc.item)),
                  key=lambda loc: (loc.player, loc.address))


def _starting_item(world, name):
    return next((item for player, items in world.multiworld.precollected_items.items()
                 for item in items if item.name == name and _belongs_to(world, item)), None)


def CreateNonlocalHints(world: "SohWorld") -> list[StaticHint]:
    # Retain the original wire format for older clients. Unplaced items are
    # normal during tracker regeneration; they must not discard other hints.
    result = []
    for key, mapping in GetNonlocalHintOptionMapping(world).items():
        if not mapping.option.value:
            continue
        locations = []
        for name in mapping.hint_items:
            if _starting_item(world, name):
                locations.append(locationPair(world.player, location_data_table[Locations.LINKS_POCKET].loc_id))
            else:
                locations.extend(locationPair(loc.player, loc.address) for loc in _item_locations(world, name))
        result.append(StaticHint(key, locations))
    return result


def CreateInGameHints(world: "SohWorld") -> dict:
    # Use finalized multiworld placements, including item-link group recipients.
    # Names travel with their owner/game; numeric IDs from different games are
    # never interpreted in SOH's item or location namespace.
    mw = world.multiworld
    def record(item, loc=None):
        finder = world.player if loc is None else loc.player
        return dict(item=item.name, recipient=mw.player_name[item.player],
                    location="Starting inventory" if loc is None else loc.name,
                    finder=mw.player_name[finder], game=mw.game[finder],
                    starting=loc is None, type="item",
                    item_id=item.code, location_id=None if loc is None else loc.address,
                    finding_player=finder, receiving_player=item.player,
                    item_flags=int(item.classification) & 7)
    result = {}
    for key, mapping in GetNonlocalHintOptionMapping(world).items():
        if not mapping.option.value:
            continue
        rows = []
        for name in mapping.hint_items:
            starting = _starting_item(world, name)
            if starting is not None:
                rows.append(record(starting))
            else:
                rows.extend(record(loc.item, loc) for loc in _item_locations(world, name))
        result[key.value] = rows
    if world.options.gossip_stone_hints.value:
        candidates = sorted((loc for loc in mw.get_locations()
                             if loc.address is not None and loc.item is not None
                             and (loc.player == world.player or _belongs_to(world, loc.item))),
                            key=lambda loc: (not loc.item.advancement, loc.player, loc.address))
        progression = [loc for loc in candidates if loc.item.advancement]
        candidates = progression or candidates
        # A separate RNG makes repeated slot-data requests deterministic and
        # leaves generation's random stream untouched.
        import random
        random.Random(f"{mw.seed_name}:{world.player}:soh-hints-v1").shuffle(candidates)
        stones = [key for key in hk if key.name.endswith("GOSSIP_STONE")]
        if candidates:
            for index, key in enumerate(stones):
                loc = candidates[index % len(candidates)]
                result[key.value] = [record(loc.item, loc)]
        from ..HintAreas import apply_area_hints
        apply_area_hints(world, result, stones)
    return result
