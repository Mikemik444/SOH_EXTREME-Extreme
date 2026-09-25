from typing import ClassVar, Any, Callable
from collections import deque
import pkgutil
import json
import dataclasses
import logging
from BaseClasses import Item, ItemClassification, CollectionState, Location, Tutorial
from rule_builder.cached_world import CachedRuleBuilderWorld
from worlds.AutoWorld import WebWorld, LogicMixin
from settings import Group, Bool
from Fill import fill_restrictive
from ._vendor_oot_soh.Items import SohItem, item_data_table, item_table
from ._vendor_oot_soh.Locations import LocTag, SohLocation, location_data_table, location_table, token_amounts
from ._vendor_oot_soh.Enums import Locations, Regions, Items, Events, EnemyDistance, GanonsTrials, Tricks
from ._vendor_oot_soh.KeyShuffle import (
    pre_fill_own_dungeon_items, get_dungeon_item_prefill_items,
    get_own_dungeon_prefill_items,
)
from ._vendor_oot_soh.DungeonRewardShuffle import pre_fill_dungeon_rewards, get_pre_fill_rewards
from ._vendor_oot_soh import DungeonRewardShuffle
from ._vendor_oot_soh.SongShuffle import pre_fill_songs, get_prefill_songs
from ._vendor_oot_soh import SongShuffle
from ._vendor_oot_soh.ShopItems import (
    get_vanilla_shop_pool, get_vanilla_shop_locations,
    remove_vanilla_shop_reservations, vanilla_shop_prices,
    fill_shop_items, generate_prices,
)
from ._vendor_oot_soh import ShopItems
from ._vendor_oot_soh.Regions import create_regions_and_locations, place_locked_items
from ._vendor_oot_soh.ItemPool import (
    create_item_pool, create_filler_item_pool, create_triforce_pieces,
    get_filler_item, give_starting_items,
)
from ._vendor_oot_soh.Hints import CreateNonlocalHints
from rule_builder.rules import Rule, Has, And, Or, True_, CanReachRegion, CanReachLocation
from ._vendor_oot_soh.Enums import Ages
from ._vendor_oot_soh.LogicHelpers import (
    can_use, can_use_any, has_item, has_explosives, blast_or_smash, blue_fire,
    can_cut_shrubs, can_jump_slash, can_jump_slash_except_hammer,
    can_hit_at_range, can_reflect_nuts, is_child, is_adult,
    can_climb, can_swim, can_play_song, can_do_trick, water_timer_at_least, fire_timer_at_least, at_day, at_night,
)
from worlds.generic.Rules import add_rule
from Options import OptionError
from .Options import SohExtremeOptions, extreme_option_groups
from .ForkLocations import FORK_LOCATIONS, FORK_LOCATION_NAME_TO_ID
from .EnemyDropLocations import ENEMY_DROP_LOCATIONS, ENEMY_DROP_LOCATION_NAME_TO_ID
from .NativeRegionMap import FORK_NATIVE_REGIONS
from .SpeechLocations import SPEECH_LOCATIONS, SPEECH_LOCATION_NAME_TO_ID
from .NativeLogic import (
    NATIVE_REGION_EDGES, NATIVE_CUSTOM_ENTRANCES, NATIVE_CUSTOM_LOCATIONS,
    NATIVE_CUSTOM_EVENTS, NATIVE_LOCATION_METADATA_RULES, NATIVE_UNMAPPED_LOCATION_RULES,
)
from .NativeLogicAlternatives import (
    NATIVE_ENTRANCE_ALTERNATIVES, NATIVE_LOCATION_ALTERNATIVES, NATIVE_EVENT_ALTERNATIVES,
)
from .NativeLocationRequirements import FORK_LOCATION_AGES, FORK_LOCATION_TIMES
from .NativeAbilityAudit import (
    NATIVE_HARD_ABILITIES_BY_AP_ID, NATIVE_EXACT_SPEAK_BY_AP_ID, NATIVE_EXACT_ANIMAL_BY_AP_ID,
)

logger = logging.getLogger("SOH_EXTREME")

# Generic flavor-NPC IDs are a runtime CAPACITY RANGE, not 512 exact physical
# locations.  Do not expose capacity slots as AP locations: doing so makes Full
# accessibility require placeholder checks which have no fixed actor/region.
# Exact NPC Speech locations from SpeechLocations.py remain normal AP checks.
# Unmapped flavor NPCs must be added only after they have an exact persistent
# actor identity + region rule on both the SoH and AP sides.
NPC_SPEECH_FALLBACK_BASE = 9650000
NPC_SPEECH_FALLBACK_COUNT = 0
NPC_SPEECH_FALLBACK_NAME_TO_ID = {}


# Generated from native location_list.cpp EnBox actor params.  These are the
# exact big-chest identities used by SOH-EXTREME's runtime (types other than
# SMALL/6/ROOM_CLEAR_SMALL/SWITCH_FLAG_FALL_SMALL).  AP generation uses this
# same list so progressive Open Chest agrees with the native Check Tracker.
NATIVE_LARGE_CHEST_NAMES = {
    'KF KOKIRI SWORD CHEST',
    'GF CHEST',
    'GRAVEYARD HOOKSHOT CHEST',
    'DEKU TREE MAP CHEST',
    'DEKU TREE COMPASS CHEST',
    'DEKU TREE SLINGSHOT CHEST',
    'DEKU TREE MQ MAP CHEST',
    'DEKU TREE MQ COMPASS CHEST',
    'DEKU TREE MQ SLINGSHOT CHEST',
    'DODONGOS CAVERN MAP CHEST',
    'DODONGOS CAVERN COMPASS CHEST',
    'DODONGOS CAVERN BOMB BAG CHEST',
    'DODONGOS CAVERN MQ MAP CHEST',
    'DODONGOS CAVERN MQ BOMB BAG CHEST',
    'DODONGOS CAVERN MQ COMPASS CHEST',
    'JABU JABUS BELLY MAP CHEST',
    'JABU JABUS BELLY BOOMERANG CHEST',
    'JABU JABUS BELLY MQ BOOMERANG CHEST',
    'FOREST TEMPLE MAP CHEST',
    'FOREST TEMPLE BOSS KEY CHEST',
    'FOREST TEMPLE BLUE POE CHEST',
    'FOREST TEMPLE MQ MAP CHEST',
    'FOREST TEMPLE MQ COMPASS CHEST',
    'FOREST TEMPLE MQ BOSS KEY CHEST',
    'FIRE TEMPLE BOSS KEY CHEST',
    'FIRE TEMPLE MAP CHEST',
    'FIRE TEMPLE COMPASS CHEST',
    'FIRE TEMPLE MEGATON HAMMER CHEST',
    'FIRE TEMPLE MQ MEGATON HAMMER CHEST',
    'FIRE TEMPLE MQ COMPASS CHEST',
    'FIRE TEMPLE MQ MAP CHEST',
    'FIRE TEMPLE MQ BOSS KEY CHEST',
    'WATER TEMPLE MAP CHEST',
    'WATER TEMPLE COMPASS CHEST',
    'WATER TEMPLE BOSS KEY CHEST',
    'WATER TEMPLE LONGSHOT CHEST',
    'WATER TEMPLE MQ BOSS KEY CHEST',
    'WATER TEMPLE MQ COMPASS CHEST',
    'SPIRIT TEMPLE SILVER GAUNTLETS CHEST',
    'SPIRIT TEMPLE MIRROR SHIELD CHEST',
    'SPIRIT TEMPLE COMPASS CHEST',
    'SPIRIT TEMPLE BOSS KEY CHEST',
    'SPIRIT TEMPLE MQ MAP CHEST',
    'SPIRIT TEMPLE MQ BOSS KEY CHEST',
    'SHADOW TEMPLE MAP CHEST',
    'SHADOW TEMPLE HOVER BOOTS CHEST',
    'SHADOW TEMPLE COMPASS CHEST',
    'SHADOW TEMPLE BOSS KEY CHEST',
    'SHADOW TEMPLE MQ COMPASS CHEST',
    'SHADOW TEMPLE MQ HOVER BOOTS CHEST',
    'SHADOW TEMPLE MQ MAP CHEST',
    'SHADOW TEMPLE MQ BOSS KEY CHEST',
    'BOTTOM OF THE WELL COMPASS CHEST',
    'BOTTOM OF THE WELL LENS OF TRUTH CHEST',
    'BOTTOM OF THE WELL MAP CHEST',
    'BOTTOM OF THE WELL MQ MAP CHEST',
    'BOTTOM OF THE WELL MQ COMPASS CHEST',
    'ICE CAVERN MAP CHEST',
    'ICE CAVERN COMPASS CHEST',
    'ICE CAVERN IRON BOOTS CHEST',
    'ICE CAVERN MQ IRON BOOTS CHEST',
    'ICE CAVERN MQ COMPASS CHEST',
    'GERUDO TRAINING GROUND MAZE PATH FINAL CHEST',
    'GANONS TOWER BOSS KEY CHEST',
    'GANONS CASTLE SHADOW TRIAL GOLDEN GAUNTLETS CHEST',
}

EXTREME_ITEMS = {
    "Roll": 9500000,
    "Grab / Power Bracelet": 9500001,
    "Climb": 9500002,
    "Crawl": 9500003,
    "Speak": 9500004,
    "Open Chest": 9500005,
    "Enemy Soul": 9500006,
    "NPC Soul": 9500007,
    "Animal Soul": 9500008,
    "Pot Soul": 9500009,
    "Crate Soul": 9500010,
    "Grass / Bush Soul": 9500011,
    "Rock / Boulder Soul": 9500012,
    "Tree Soul": 9500013,
    "Beehive Soul": 9500014,
    "Sign Soul": 9500015,
    "Skulltula Soul": 9500016,
    "Scrub Soul": 9500017,
    "Shovel": 9500018,
    "Flow of Time": 9500019,
    # Logic-only virtual event. With Shuffle Swim enabled, the first physical
    # Progressive Scale unlocks swimming but must NOT count as Silver Scale.
    "Swim": 9500094,
    "Death Mountain Crater Bean Soul": 9500095,
    "Death Mountain Trail Bean Soul": 9500096,
    "Desert Colossus Bean Soul": 9500097,
    "Gerudo Valley Bean Soul": 9500098,
    "Graveyard Bean Soul": 9500099,
    "Kokiri Forest Bean Soul": 9500100,
    "Lake Hylia Bean Soul": 9500101,
    "Lost Woods Bridge Bean Soul": 9500102,
    "Lost Woods Bean Soul": 9500103,
    "Zora's River Bean Soul": 9500104,
    "Speak Deku": 9500105,
    "Speak Gerudo": 9500106,
    "Speak Goron": 9500107,
    "Speak Hylian": 9500108,
    "Speak Kokiri": 9500109,
    "Speak Zora": 9500110,
    "Cow Soul": 9500111,
    "Cucco Soul": 9500112,
    "Dog Soul": 9500113,
    "Fish Soul": 9500114,
    "Bug Soul": 9500115,
    "Butterfly Soul": 9500116,
    "Frog Soul": 9500117,
    "Horse Soul": 9500118,
    "Stalfos Soul": 9500119,
    "Octorok Soul": 9500120,
    "Wallmaster Soul": 9500121,
    "Dodongo Soul": 9500122,
    "Keese Soul": 9500123,
    "Tektite Soul": 9500124,
    "Peahat Soul": 9500125,
    "Lizalfos and Dinolfos Soul": 9500126,
    "Gohma Larva Soul": 9500127,
    "Shabom Soul": 9500128,
    "Baby Dodongo Soul": 9500129,
    "Biri and Bari Soul": 9500130,
    "Tailpasaran Soul": 9500131,
    "Torch Slug Soul": 9500132,
    "Moblin Soul": 9500133,
    "Armos Soul": 9500134,
    "Deku Baba Soul": 9500135,
    "Deku Scrub Soul": 9500136,
    "Bubble Soul": 9500137,
    "Beamos Soul": 9500138,
    "Floormaster Soul": 9500139,
    "Redead and Gibdo Soul": 9500140,
    "Flare Dancer Soul": 9500141,
    "Dead Hand Soul": 9500142,
    "Shell Blade Soul": 9500143,
    "Like Like Soul": 9500144,
    "Spike Soul": 9500145,
    "Anubis Soul": 9500146,
    "Iron Knuckle Soul": 9500147,
    "Skull Kid Soul": 9500148,
    "Flying Pot Soul": 9500149,
    "Freezard Soul": 9500150,
    "Stinger Soul": 9500151,
    "Wolfos Soul": 9500152,
    "Guay Soul": 9500153,
    "Jabu Jabu Tentacle Soul": 9500154,
    "Dark Link Soul": 9500155,
    "Door Trap Soul": 9500156,
    "Flying Floor Tile Soul": 9500157,
    "Gerudo Thief Soul": 9500158,
    "Poe Sister Soul": 9500159,
    "Poe Soul": 9500182,
    "Leever Soul": 9500183,
    "Stalchild Soul": 9500184,
    "Big Octo Soul": 9500185,

}
for i in range(74):
    EXTREME_ITEMS[f"Song Note {i + 1:02d}"] = 9500020 + i

# Native SOH-EXTREME silver-rupee group rewards.  Individual silver rupees are
# locations; these are the progression items that advance each room's switch
# counter.  In Shuffle Silver = On, the vanilla groups need five copies.  Wallet
# mode places one copy which native SOH expands to a completed group.
SILVER_GROUP_ITEMS = {
    "Shadow Silver: Blades": 9500160,
    "Shadow Silver: Pit": 9500161,
    "Shadow Silver: Spikes": 9500162,
    "Spirit Silver: Child": 9500163,
    "Spirit Silver: Sun": 9500164,
    "Spirit Silver: Boulders": 9500165,
    "Bottom of the Well Silver": 9500166,
    "Ice Cavern Silver: Blades": 9500167,
    "Ice Cavern Silver: Block": 9500168,
    "Training Ground Silver: Slope": 9500169,
    "Training Ground Silver: Lava": 9500170,
    "Training Ground Silver: Water": 9500171,
    "Ganon's Castle Silver: Light": 9500172,
    "Ganon's Castle Silver: Forest": 9500173,
    "Ganon's Castle Silver: Fire": 9500174,
    "Ganon's Castle Silver: Spirit": 9500175,

    # Native MQ groups are registered now so remote AP receipt/model logic is
    # complete when MQ support is enabled in the AP topology later.
    "Dodongo's Cavern Silver": 9500176,
    "Shadow Silver: Invisible Blades": 9500177,
    "Spirit Silver: Lobby": 9500178,
    "Spirit Silver: Big Wall": 9500179,
    "Ganon's Castle Silver: Water": 9500180,
    "Ganon's Castle Silver: Shadow": 9500181,
}
EXTREME_ITEMS.update(SILVER_GROUP_ITEMS)

# AP currently exposes the vanilla dungeon layouts.  These sixteen groups are
# exactly the native groups active in that topology.
VANILLA_SILVER_GROUP_TOTALS = {
    "Shadow Silver: Blades": 5,
    "Shadow Silver: Pit": 5,
    "Shadow Silver: Spikes": 5,
    "Spirit Silver: Child": 5,
    "Spirit Silver: Sun": 5,
    "Spirit Silver: Boulders": 5,
    "Bottom of the Well Silver": 5,
    "Ice Cavern Silver: Blades": 5,
    "Ice Cavern Silver: Block": 5,
    "Training Ground Silver: Slope": 5,
    "Training Ground Silver: Lava": 5,
    "Training Ground Silver: Water": 5,
    "Ganon's Castle Silver: Light": 5,
    "Ganon's Castle Silver: Forest": 5,
    "Ganon's Castle Silver: Fire": 5,
    "Ganon's Castle Silver: Spirit": 5,
}

ALL_SILVER_GROUP_TOTALS = dict(VANILLA_SILVER_GROUP_TOTALS) | {
    "Dodongo's Cavern Silver": 5,
    "Shadow Silver: Invisible Blades": 10,
    "Spirit Silver: Lobby": 5,
    "Spirit Silver: Big Wall": 5,
    "Ganon's Castle Silver: Water": 5,
    "Ganon's Castle Silver: Shadow": 5,
}

# Internal native room transitions whose switch is opened by completing one
# silver-rupee group.  These are injected into the same DNF/native path graph
# used by AP generation, so a location after the door inherits the room gate.
SILVER_EDGE_REQUIREMENTS = {
    ("RR_SHADOW_TEMPLE_LOWER_HUGE_PIT", "RR_SHADOW_TEMPLE_STONE_UMBRELLA"):
        "Shadow Silver: Pit",
    ("RR_SHADOW_TEMPLE_FLOOR_SPIKES_W_DOOR", "RR_SHADOW_TEMPLE_SKULL_JAR"):
        "Shadow Silver: Spikes",

    ("RR_SPIRIT_TEMPLE_RUPEE_BRIDGE_NORTH", "RR_SPIRIT_TEMPLE_RUPEE_BRIDGE_SOUTH"):
        "Spirit Silver: Child",
    ("RR_SPIRIT_TEMPLE_RUPEE_BRIDGE_SOUTH", "RR_SPIRIT_TEMPLE_RUPEE_BRIDGE_NORTH"):
        "Spirit Silver: Child",
    ("RR_SPIRIT_TEMPLE_BOULDERS", "RR_SPIRIT_TEMPLE_PAST_BOULDERS"):
        "Spirit Silver: Boulders",

    ("RR_BOTW_LADDER_DOOR", "RR_BOTW_HIDDEN_POTS"):
        "Bottom of the Well Silver",

    ("RR_ICE_CAVERN_HUB", "RR_ICE_CAVERN_MAP_ROOM"):
        "Ice Cavern Silver: Blades",
    ("RR_ICE_CAVERN_BLOCK_ROOM", "RR_ICE_CAVERN_AFTER_BLOCK_ROOM"):
        "Ice Cavern Silver: Block",

    ("RR_GERUDO_TRAINING_GROUND_BOULDER_ROOM", "RR_GERUDO_TRAINING_GROUND_HEAVY_BLOCK_ROOM"):
        "Training Ground Silver: Slope",
    ("RR_GERUDO_TRAINING_GROUND_LAVA_ROOM", "RR_GERUDO_TRAINING_GROUND_UNDERWATER"):
        "Training Ground Silver: Lava",

    ("RR_GANONS_CASTLE_FOREST_TRIAL_BEAMOS_ROOM_FINAL_DOOR", "RR_GANONS_CASTLE_FOREST_TRIAL_FINAL_ROOM"):
        "Ganon's Castle Silver: Forest",
    ("RR_GANONS_CASTLE_FIRE_TRIAL_BARRED_DOOR", "RR_GANONS_CASTLE_FIRE_TRIAL_FINAL_ROOM"):
        "Ganon's Castle Silver: Fire",
    ("RR_GANONS_CASTLE_SPIRIT_TRIAL_BEAMOS_ROOM", "RR_GANONS_CASTLE_SPIRIT_TRIAL_BEFORE_SWITCH"):
        "Ganon's Castle Silver: Spirit",
    ("RR_GANONS_CASTLE_LIGHT_TRIAL_BOULDER_ROOM", "RR_GANONS_CASTLE_LIGHT_TRIAL_FINAL_ROOM"):
        "Ganon's Castle Silver: Light",
}

# Location-local silver group requirements (not represented by a region exit).
SILVER_LOCATION_REQUIREMENTS = {
    "Shadow Temple Early Silver Rupee Chest": "Shadow Silver: Blades",
    "Spirit Temple GS Metal Fence": "Spirit Silver: Child",
    "Gerudo Training Ground Underwater Silver Rupee Chest": "Training Ground Silver: Water",
}



# Canonical stock SoH item names used by this bridge, with compatibility
# aliases for nearby Archipelago-SoH naming revisions.  The current 0.6.7
# names are first.
SOH_ITEM_ALIASES = {
    "Progressive Bomb Bag": ("Progressive Bomb Bag", "Bomb Bag"),
    "Progressive Bow": ("Progressive Bow", "Bow"),
    "Progressive Slingshot": ("Progressive Slingshot", "Slingshot"),
    "Progressive Hookshot": ("Progressive Hookshot", "Hookshot"),
    "Strength Upgrade": ("Strength Upgrade", "Progressive Strength Upgrade"),
    "Biggoron's Sword": ("Biggoron's Sword", "Biggoron Sword"),
    "Giant's Knife": ("Giant's Knife", "Giants Knife"),
    "Progressive Stick Capacity": ("Progressive Stick Capacity", "Deku Stick Bag", "Deku Stick Capacity"),
}

def _soh_item_name(world, item_name):
    for candidate in SOH_ITEM_ALIASES.get(item_name, (item_name,)):
        if candidate in world.item_name_to_id:
            return candidate
    return None


@dataclasses.dataclass()
class RequireExistingLocationItem(Rule, game="SOH-EXTREME"):
    """Compose a hard SOH-EXTREME item gate with an existing resolved SoH rule.

    Archipelago 0.6.7 has no ``And.from_resolved`` helper.  Stock SoH has
    already resolved its access rule by the time this rule is installed, so we
    explicitly create an ``And.Resolved`` node containing that existing rule
    and the resolved Extreme item requirement.  This preserves cache
    dependencies and human-readable explanations for Universal Tracker.
    """
    location_name: str
    item_name: str
    count: int = 1

    def _instantiate(self, world):
        existing = world.get_location(self.location_name).access_rule
        resolved_name = _soh_item_name(world, self.item_name) or self.item_name
        required = Has(resolved_name, self.count).resolve(world)

        if existing.always_false:
            return existing
        if existing.always_true:
            return required
        if required.always_false:
            return required
        if required.always_true:
            return existing

        # ``And.Resolved`` is the 0.6.7-supported way to combine already
        # resolved rules.  NestedRule.Resolved accepts the child tuple first.
        return And.Resolved(
            (existing, required),
            player=world.player,
            caching_enabled=getattr(world, "rule_caching_enabled", False),
        )


@dataclasses.dataclass()
class RequireAnyExistingItems(Rule, game="SOH-EXTREME"):
    """Require one usable stock SoH item from a candidate set.

    Candidate names are filtered against the inherited SoH item table at
    generation time so this remains compatible with minor upstream naming
    differences instead of crashing on a name that does not exist.
    """
    item_names: tuple

    def _instantiate(self, world):
        valid = tuple(resolved for name in self.item_names
                      if (resolved := _soh_item_name(world, name)) is not None)
        if not valid:
            raise OptionError(f"No known items in required SOH-EXTREME alternatives: {self.item_names!r}")
        resolved = tuple(Has(name, 1).resolve(world) for name in valid)
        if len(resolved) == 1:
            return resolved[0]
        return Or.Resolved(
            resolved,
            player=world.player,
            caching_enabled=getattr(world, "rule_caching_enabled", False),
        )


@dataclasses.dataclass()
class RequireAnyItemGroups(Rule, game="SOH-EXTREME"):
    """Standalone OR-of-AND item rule for fork-native physical interactions.

    Each outer entry is an alternative and each inner entry is an item/count
    pair that must all be present for that alternative. Unknown item names stop
    generation rather than silently dropping part of a physical requirement.
    """
    groups: tuple

    def _instantiate(self, world):
        alternatives = []
        for group in self.groups:
            children = []
            for item_name, count in group:
                resolved_name = _soh_item_name(world, item_name)
                if resolved_name is None:
                    raise OptionError(f"Unknown required SOH-EXTREME item: {item_name!r}")
                children.append(Has(resolved_name, count).resolve(world))
            if not children:
                continue
            if len(children) == 1:
                alternatives.append(children[0])
            else:
                alternatives.append(And.Resolved(
                    tuple(children), player=world.player,
                    caching_enabled=getattr(world, "rule_caching_enabled", False)))
        if not alternatives:
            # Deliberately impossible if every named route disappeared from the
            # inherited item table; silently allowing the check would create a
            # false-positive progression route.
            return Has("Flow of Time", 9999).resolve(world)
        if len(alternatives) == 1:
            return alternatives[0]
        return Or.Resolved(
            tuple(alternatives), player=world.player,
            caching_enabled=getattr(world, "rule_caching_enabled", False))


@dataclasses.dataclass()
class RequireExistingAlternativeGroups(Rule, game="SOH-EXTREME"):
    """Compose stock SoH logic with one of several SOH-EXTREME item groups.

    Each inner tuple is an AND group; the outer tuple is OR.  Missing stock item
    names are ignored inside a group so minor upstream APWorld naming changes do
    not crash generation.  Custom SOH-EXTREME names are always accepted.
    """
    location_name: str
    groups: tuple

    def _instantiate(self, world):
        existing = world.get_location(self.location_name).access_rule
        group_rules = []
        for group in self.groups:
            children = []
            for item_name, count in group:
                resolved_name = _soh_item_name(world, item_name)
                if resolved_name is None:
                    raise OptionError(f"Unknown required SOH-EXTREME item: {item_name!r}")
                children.append(Has(resolved_name, count).resolve(world))
            if not children:
                continue
            if len(children) == 1:
                group_rules.append(children[0])
            else:
                group_rules.append(And.Resolved(
                    tuple(children), player=world.player,
                    caching_enabled=getattr(world, "rule_caching_enabled", False)))

        if not group_rules:
            return existing
        alternatives = group_rules[0] if len(group_rules) == 1 else Or.Resolved(
            tuple(group_rules), player=world.player,
            caching_enabled=getattr(world, "rule_caching_enabled", False))
        if existing.always_false:
            return existing
        if existing.always_true:
            return alternatives
        return And.Resolved(
            (existing, alternatives), player=world.player,
            caching_enabled=getattr(world, "rule_caching_enabled", False))


@dataclasses.dataclass()
class RequireExistingRule(Rule, game="SOH-EXTREME"):
    """AND an arbitrary age-aware native-style Rule with the inherited SoH rule."""
    location_name: str
    extra_rule: Rule

    def _instantiate(self, world):
        existing = world.get_location(self.location_name).access_rule
        extra = self.extra_rule.resolve(world)
        if existing.always_false or extra.always_true:
            return existing
        if existing.always_true or extra.always_false:
            return extra
        return And.Resolved(
            (existing, extra), player=world.player,
            caching_enabled=getattr(world, "rule_caching_enabled", False))



@dataclasses.dataclass()
class RequireExistingEntranceRule(Rule, game="SOH-EXTREME"):
    """AND a SOH-EXTREME rule with an inherited SoH Entrance rule.

    This is the structural traversal bridge.  Applying movement shuffles to
    locations is not sufficient because stock events can become reachable as
    soon as Archipelago crosses a region entrance.  Entrance overlays make the
    whole downstream region graph inherit the custom physical action.
    """
    entrance_name: str
    extra_rule: Rule

    def _instantiate(self, world):
        entrance = world.multiworld.get_entrance(self.entrance_name, world.player)
        existing = entrance.access_rule
        extra = self.extra_rule.resolve(world)

        if existing.always_false or extra.always_true:
            return existing
        if existing.always_true or extra.always_false:
            return extra
        return And.Resolved(
            (existing, extra),
            player=world.player,
            caching_enabled=getattr(world, "rule_caching_enabled", False),
        )


@dataclasses.dataclass()
class ExtendExistingAlternativeGroups(Rule, game="SOH-EXTREME"):
    """Allow a SOH-EXTREME interaction route in addition to stock SoH logic.

    Location parent-region reachability is checked separately by Archipelago, so
    this safely extends only the access-rule portion.  It is used where the fork
    adds a new physical method (notably EXTREME Grab) that stock SoH cannot know.
    """
    location_name: str
    groups: tuple

    def _instantiate(self, world):
        existing = world.get_location(self.location_name).access_rule
        group_rules = []
        for group in self.groups:
            children = []
            for item_name, count in group:
                resolved_name = _soh_item_name(world, item_name)
                if resolved_name is None:
                    raise OptionError(f"Unknown required SOH-EXTREME item: {item_name!r}")
                children.append(Has(resolved_name, count).resolve(world))
            if not children:
                continue
            group_rules.append(children[0] if len(children) == 1 else And.Resolved(
                tuple(children), player=world.player,
                caching_enabled=getattr(world, "rule_caching_enabled", False)))
        if not group_rules:
            return existing
        added = group_rules[0] if len(group_rules) == 1 else Or.Resolved(
            tuple(group_rules), player=world.player,
            caching_enabled=getattr(world, "rule_caching_enabled", False))
        if existing.always_true or added.always_true:
            return existing if existing.always_true else added
        if existing.always_false:
            return added
        return Or.Resolved(
            (existing, added), player=world.player,
            caching_enabled=getattr(world, "rule_caching_enabled", False))


class SohExtremeItem(SohItem):
    game = "SOH-EXTREME"

class SohExtremeLocation(SohLocation):
    game = "SOH-EXTREME"


@dataclasses.dataclass()
class GVUpperStreamDropHealth(Rule, game="SOH-EXTREME"):
    """True once Link has enough maximum health to survive the GV cow-ledge drop.

    Native SoH requires two full hearts for this route.  This rule reads the
    stock SoH CollectionState heart tracker so gaining health later immediately
    makes the route available too.
    """

    class Resolved(Rule.Resolved):
        force_recalculate: ClassVar[bool] = True

        def _evaluate(self, state) -> bool:
            return state.soh_heart_count.get(self.player, 0) >= 2

        def explain_str(self, state=None) -> str:
            return "2+ Hearts (survive Gerudo Valley drop)"


@dataclasses.dataclass()
class RequireForkLocationItems(Rule, game="SOH-EXTREME"):
    """Compose all SOH-EXTREME requirements for a fork-native location.

    Fork locations begin with a plain Python access_rule callable, so the stock
    resolved-rule composer cannot safely inspect it.  We accumulate every
    Extreme requirement for the location and install one resolved And node.
    This prevents later gates from overwriting earlier ones.
    """
    requirements: tuple

    def _instantiate(self, world):
        resolved = tuple(Has(name, count).resolve(world) for name, count in self.requirements)
        if not resolved:
            return Has("Flow of Time", 0).resolve(world)
        if len(resolved) == 1:
            return resolved[0]
        return And.Resolved(
            resolved,
            player=world.player,
            caching_enabled=getattr(world, "rule_caching_enabled", False),
        )


class SohExtremeLogicState(LogicMixin):
    """CollectionState support required by the vendored SoH rule set.

    SOH-EXTREME deliberately does not execute/register the stock ``SohWorld``
    package initializer.  That also means we cannot rely on stock SoH mixins to
    create the age-reachability and heart-count state used by LogicHelpers.
    Keep the state here so the standalone APWorld is genuinely self-contained.
    """
    def init_mixin(self, parent):
        players = list(parent.get_game_players("SOH-EXTREME") + parent.get_game_groups("SOH-EXTREME"))

        # Be additive instead of assuming another SoH mixin has already run.
        # This fixes standalone generation where these attributes do not exist at
        # all, while also avoiding clobbering another world's entries if present.
        if not hasattr(self, "_soh_stale"):
            self._soh_stale = {}
        if not hasattr(self, "_soh_child_reachable_regions"):
            self._soh_child_reachable_regions = {}
        if not hasattr(self, "_soh_adult_reachable_regions"):
            self._soh_adult_reachable_regions = {}
        if not hasattr(self, "_soh_child_blocked_regions"):
            self._soh_child_blocked_regions = {}
        if not hasattr(self, "_soh_adult_blocked_regions"):
            self._soh_adult_blocked_regions = {}
        if not hasattr(self, "_soh_age"):
            self._soh_age = {}
        if not hasattr(self, "soh_piece_of_heart_count"):
            self.soh_piece_of_heart_count = {}
        if not hasattr(self, "soh_heart_count"):
            self.soh_heart_count = {}

        for player in players:
            self._soh_stale[player] = True
            self._soh_child_reachable_regions[player] = set()
            self._soh_adult_reachable_regions[player] = set()
            self._soh_child_blocked_regions[player] = set()
            self._soh_adult_blocked_regions[player] = set()
            self._soh_age[player] = Ages.null
            self.soh_piece_of_heart_count[player] = 0
            self.soh_heart_count[player] = parent.worlds[player].options.starting_hearts.value

        # Tracks virtual stock-song progression created by collecting every
        # individual note for a song.  The stock SoH access rules still ask for
        # the normal song item names, while the SOH-EXTREME client grants the
        # quest song after all of that song's notes have arrived.
        self._soh_extreme_virtual_songs = {player: set() for player in players}
        # First Progressive Scale is consumed as this virtual event when
        # Shuffle Swim is enabled. Stock SoH AP scale rules then remain shifted:
        # physical #1=Swim/Bronze, #2=Silver Scale, #3=Golden Scale.
        self._soh_extreme_virtual_swim = {player: False for player in players}
        # Shuffle Grab inserts a progression tier BEFORE vanilla Strength. The first
        # physical Strength Upgrade grants Grab/Power Bracelet only; the second is
        # the first real strength tier (Goron Bracelet).
        self._soh_extreme_virtual_grab = {player: False for player in players}

    def copy_mixin(self, new_state):
        # Copy the stock-compatible state that SOH-EXTREME owns in standalone
        # mode.  CollectionState.copy() is heavily used during fill simulation.
        new_state._soh_stale = self._soh_stale.copy()
        new_state._soh_child_reachable_regions = {
            player: regions.copy() for player, regions in self._soh_child_reachable_regions.items()
        }
        new_state._soh_adult_reachable_regions = {
            player: regions.copy() for player, regions in self._soh_adult_reachable_regions.items()
        }
        new_state._soh_child_blocked_regions = {
            player: regions.copy() for player, regions in self._soh_child_blocked_regions.items()
        }
        new_state._soh_adult_blocked_regions = {
            player: regions.copy() for player, regions in self._soh_adult_blocked_regions.items()
        }
        new_state._soh_age = self._soh_age.copy()
        new_state.soh_piece_of_heart_count = self.soh_piece_of_heart_count.copy()
        new_state.soh_heart_count = self.soh_heart_count.copy()

        new_state._soh_extreme_virtual_songs = {
            player: songs.copy() for player, songs in self._soh_extreme_virtual_songs.items()
        }
        new_state._soh_extreme_virtual_swim = self._soh_extreme_virtual_swim.copy()
        new_state._soh_extreme_virtual_grab = self._soh_extreme_virtual_grab.copy()
        # CollectionState.copy() chains every registered LogicMixin copy hook as
        #     ret = function(self, ret)
        # so every hook MUST return the copied state.
        return new_state

    def _soh_invalidate(self, player):
        self._soh_child_reachable_regions[player] = set()
        self._soh_adult_reachable_regions[player] = set()
        self._soh_child_blocked_regions[player] = set()
        self._soh_adult_blocked_regions[player] = set()
        self._soh_stale[player] = True

    def _soh_update_age_reachable_regions(self, player):
        """Vendored equivalent of stock SoH RegionAgeAccess.SohAgeLogic.

        Kept here so standalone SOH-EXTREME does not need to register the stock
        Ship of Harkinian AutoWorld/mixin just to evaluate IsChild/IsAdult rules.
        """
        self._soh_stale[player] = False
        for age in (Ages.CHILD, Ages.ADULT):
            self._soh_age[player] = age
            start = self.multiworld.get_region(Regions.ROOT, player)

            if age == Ages.CHILD:
                reachable = self._soh_child_reachable_regions[player]
                blocked = self._soh_child_blocked_regions[player]
            else:
                reachable = self._soh_adult_reachable_regions[player]
                blocked = self._soh_adult_blocked_regions[player]

            queue = deque(blocked)
            if start not in reachable:
                reachable.add(start)
                blocked.update(start.exits)
                queue.extend(start.exits)

            while queue:
                connection = queue.popleft()
                new_region = connection.connected_region
                if new_region is None:
                    continue
                if new_region in reachable:
                    blocked.discard(connection)
                elif connection.can_reach(self):
                    reachable.add(new_region)
                    blocked.discard(connection)
                    blocked.update(new_region.exits)
                    queue.extend(new_region.exits)
                    self.path[new_region] = (new_region.name, self.path.get(connection, None))

        self._soh_age[player] = Ages.null

    def _soh_can_reach_as_age(self, region, age, player):
        # Match the stock SoH recursion guard.  Region rules themselves may ask
        # for an age while the breadth-first search is already evaluating one.
        if self._soh_age[player] == Ages.null:
            self._soh_age[player] = age
            try:
                return self.multiworld.get_region(region.value, player).can_reach(self)
            finally:
                self._soh_age[player] = Ages.null
        return self._soh_age[player] == age

class SohExtremeWebWorld(WebWorld):
    theme = "ice"
    option_groups = extreme_option_groups
    setup_en = Tutorial(
        tutorial_name="SOH-EXTREME Start Guide",
        description="A guide to playing SOH-EXTREME with Archipelago.",
        language="English",
        file_name="guide_en.md",
        link="guide/en",
        authors=["mikemik44"],
    )
    tutorials = [setup_en]
    game_info_languages = ["en"]


class SohExtremeSettings(Group):
    class AllowTrueNoLogic(Bool):
        """Allow SOH-EXTREME true-no-logic generation."""

    class DisableFillOverflow(Bool):
        """Disable the EXTREME prefill overflow fallback (debug only)."""

    allow_true_no_logic: AllowTrueNoLogic | bool = False
    disable_fill_overflow: DisableFillOverflow | bool = False


def _create_groups(obj):
    groups = {}
    for key, data in obj.items():
        tags = getattr(data, "tags", None)
        if tags is None:
            continue
        for tag in tags:
            tag_name = tag.name.replace("_", " ")
            groups.setdefault(tag_name, set()).add(str(key))
    return groups


class SohExtremeWorld(CachedRuleBuilderWorld):
    """Standalone Archipelago world for the SOH-EXTREME Ship fork.

    This is deliberately *not* a SohWorld subclass.  Stock Ship of Harkinian
    tables/helpers are used as source data where they describe vanilla OoT, but
    lifecycle, pool mutation, rules, slot data and Universal Tracker behavior are
    owned by SOH-EXTREME.
    """
    game = "SOH-EXTREME"
    web = SohExtremeWebWorld()
    options: SohExtremeOptions
    options_dataclass = SohExtremeOptions
    settings: ClassVar[SohExtremeSettings]

    # SOH-EXTREME intentionally does not expose a synthetic UT "Glitched" state.
    ut_can_gen_without_yaml = True

    item_name_to_id = dict(item_table) | EXTREME_ITEMS
    location_name_to_id = (dict(location_table) | FORK_LOCATION_NAME_TO_ID |
                           SPEECH_LOCATION_NAME_TO_ID | NPC_SPEECH_FALLBACK_NAME_TO_ID |
                           ENEMY_DROP_LOCATION_NAME_TO_ID)
    item_name_groups = {k: set(v) for k, v in _create_groups(item_data_table).items() if k != "Everything"} | {
        "Extreme Abilities": {"Roll", "Grab / Power Bracelet", "Climb", "Crawl", "Speak", "Open Chest", "Shovel", "Flow of Time"},
        "Extreme Souls": {name for name in EXTREME_ITEMS if name.endswith("Soul")},
        "Song Notes": {name for name in EXTREME_ITEMS if name.startswith("Song Note ")},
        "Silver Rupees": set(SILVER_GROUP_ITEMS),
    }
    location_name_groups = {k: set(v) for k, v in _create_groups(location_data_table).items() if k != "Everywhere"} | {
        "SOH-EXTREME Fork Locations": set(FORK_LOCATION_NAME_TO_ID),
        "Wonder Items": {loc.name for loc in FORK_LOCATIONS if loc.family == "wonder"},
        "Silver Rupee Checks": {loc.name for loc in FORK_LOCATIONS if loc.family == "silver"},
        "NPC Speech Sanity": set(SPEECH_LOCATION_NAME_TO_ID) | set(NPC_SPEECH_FALLBACK_NAME_TO_ID),
        "Enemy Drops": set(ENEMY_DROP_LOCATION_NAME_TO_ID),
    }

    def __init__(self, multiworld, player):
        super().__init__(multiworld, player)
        self.item_pool = []
        self.preplaced_items = []
        self.included_locations = {}
        self.shop_prices = {}
        self.shop_vanilla_items = {}
        self.triforce_pieces_required = 0
        self.randomized_progressive_skulltula_count = 0
        self.ganons_trials = []
        self.pre_fill_pool = []
        self.reserved_pre_fill_locations = []
        self.using_ut = False
        self.passthrough = {}
        try:
            manifest = json.loads(pkgutil.get_data(__name__, "archipelago.json").decode("utf-8"))
            self.apworld_version = manifest.get("world_version", "0.0.0")
        except Exception:
            self.apworld_version = "0.0.0"

    def reserve_prefill_locations(self) -> None:
        DungeonRewardShuffle.reserve_dungeon_reward_locations(self)
        SongShuffle.reserve_song_locations(self)
        ShopItems.reserve_vanilla_shop_locations(self)

    def get_pre_fill_items(self):
        return [self.create_item(item) for item in self.pre_fill_pool]

    def get_filler_item_name(self) -> str:
        return get_filler_item(self)

    def set_completion_rule(self, goal: Rule = None) -> None:
        if not self.options.true_no_logic:
            super().set_completion_rule(Has(str(Events.GAME_COMPLETED)) if goal is None else goal)

    def get_empty_locations_from_list_shuffled(self, location_list):
        result = []
        for location in location_list:
            loc = self.get_location(str(location))
            if loc.item is not None or loc.locked or location in self.reserved_pre_fill_locations:
                continue
            result.append(loc)
        self.random.shuffle(result)
        return result

    def get_pre_fill_state(self):
        my_locations = list(self.multiworld.get_locations(self.player))
        state = CollectionState(self.multiworld)
        for item in self.item_pool:
            state.collect(item, True)
        for item in self.pre_fill_pool:
            state.collect(self.create_item(item), True)
        state.sweep_for_advancements(my_locations)
        return state

    def add_items_to_item_pool_list(self, items) -> None:
        if items:
            self.item_pool.extend(items)
            self.multiworld.itempool.extend(items)

    def run_prefill(self, item_pool, locations, prefill_state=None, original_goal=None):
        def create_new_goal(empty_locations):
            goal = True_()
            for reg in empty_locations:
                goal &= CanReachLocation(str(reg.name))
            return goal

        if prefill_state is None:
            for item in item_pool:
                if item in self.pre_fill_pool:
                    self.pre_fill_pool.remove(item)
            prefill_state = self.get_pre_fill_state()

        empty_all = self.get_empty_locations_from_list_shuffled(locations)
        total = len(empty_all)
        chunk = min(len(item_pool) + 100, total)
        if bool(getattr(self.settings, "disable_fill_overflow", False)) or chunk == total:
            empty_locations = empty_all
        else:
            empty_locations = empty_all[:chunk]

        items = [self.create_item(str(item)) for item in item_pool]
        self.preplaced_items.extend(items)
        self.set_completion_rule(create_new_goal(empty_locations) if original_goal is None else original_goal)
        fill_restrictive(
            self.multiworld, prefill_state, empty_locations, items,
            single_player_placement=True, lock=True,
            allow_partial=(not bool(getattr(self.settings, "disable_fill_overflow", False))),
            name="SOH_EXTREME_Prefill_Initial",
        )
        if items and chunk != total:
            empty_locations = empty_all[chunk:]
            if original_goal is None:
                self.set_completion_rule(create_new_goal(empty_locations))
            fill_restrictive(
                self.multiworld, prefill_state, empty_locations, items,
                single_player_placement=True, lock=True, allow_partial=True,
                name="SOH_EXTREME_Prefill_Secondary",
            )
        self.add_items_to_item_pool_list(items)
        for item in items:
            if item in self.preplaced_items:
                self.preplaced_items.remove(item)

    @staticmethod
    def interpret_slot_data(slot_data):
        """Return the complete slot snapshot for Universal Tracker re-generation.

        Universal Tracker places this dictionary in
        ``multiworld.re_gen_passthrough["SOH-EXTREME"]``.  ``generate_early``
        consumes it before stock SoH performs any option-dependent setup, making
        UT build the same region/location graph and the same access rules as the
        original seed.
        """
        return dict(slot_data)

    def _apply_universal_tracker_slot_data(self) -> None:
        """Restore the seed's resolved options when Universal Tracker re-gens.

        Do not use local/template option values here.  ``fill_slot_data`` publishes
        ``extreme_all_options`` specifically so every stock SoH and SOH-EXTREME
        logic option survives the AP -> UT boundary, including options that were
        originally set to Random but resolved to a concrete value for the seed.
        """
        passthrough = getattr(self.multiworld, "re_gen_passthrough", None)
        self.using_ut = bool(passthrough and self.game in passthrough)
        if not self.using_ut:
            self.passthrough = {}
            return

        slot_data = passthrough[self.game]
        self.passthrough = dict(slot_data)
        option_snapshot = slot_data.get("extreme_all_options", slot_data)

        restored = 0
        for field in dataclasses.fields(type(self.options)):
            name = field.name
            if name not in option_snapshot:
                # Older SOH-EXTREME slots may predate extreme_all_options but
                # still contain many options at the top level.
                if name not in slot_data:
                    continue
                raw_value = slot_data[name]
            else:
                raw_value = option_snapshot[name]

            current = getattr(self.options, name)
            option_type = type(current)
            try:
                parsed = option_type.from_any(raw_value)
            except Exception as exc:
                raise OptionError(
                    f"SOH-EXTREME Universal Tracker could not restore option "
                    f"{name!r} from slot data value {raw_value!r}: {exc}"
                ) from exc
            setattr(self.options, name, parsed)
            restored += 1

        # Keep the exact generated shop prices available to the re-generated
        # world.  Stock SoH may recreate the same logical shop slots, but its RNG
        # stream is not guaranteed to match Universal Tracker's fake generation.
        # The numeric-id map is applied after stock setup has created shop_prices.
        self._extreme_ut_shop_prices_by_id = {
            int(location_id): int(price)
            for location_id, price in slot_data.get("extreme_shop_prices", {}).items()
        }

        logger.info(
            "SOH-EXTREME Universal Tracker restored %d resolved option(s) from slot data",
            restored,
        )

    def _restore_universal_tracker_shop_prices(self) -> None:
        prices_by_id = getattr(self, "_extreme_ut_shop_prices_by_id", None)
        if not prices_by_id:
            return

        restored = 0
        for location_name, location_id in self.location_name_to_id.items():
            if location_id not in prices_by_id:
                continue
            # shop_prices is keyed by the stock Locations enum when possible.
            # Fall back to the location name only for fork-native checks.
            try:
                key = Locations(location_name)
            except (ValueError, KeyError):
                key = location_name
            self.shop_prices[key] = prices_by_id[location_id]
            restored += 1

        logger.info(
            "SOH-EXTREME Universal Tracker restored %d generated shop price(s)",
            restored,
        )


    def _fork_location_enabled(self, loc) -> bool:
        o = self.options
        if loc.family == "rock": return bool(o.shuffle_rocks.value)
        if loc.family == "boulder": return o.shuffle_boulders.value == 3 or (o.shuffle_boulders.value == 1 and loc.dungeon) or (o.shuffle_boulders.value == 2 and not loc.dungeon)
        if loc.family == "bush":
            # Native SOH-EXTREME treats overworld/all GrassSanity as including
            # bushes.  The separate BushSanity toggle remains an explicit way to
            # shuffle bushes when GrassSanity itself is off/dungeon-only.
            grass = o.shuffle_grass.value
            return bool(o.shuffle_bushes.value) or grass == 3 or (grass == 2 and not loc.dungeon)
        if loc.family == "icicle": return bool(o.shuffle_icicles.value)
        if loc.family == "red_ice": return bool(o.shuffle_red_ice.value)
        if loc.family == "sign": return o.shuffle_signs.value == 3 or (o.shuffle_signs.value == 1 and loc.dungeon) or (o.shuffle_signs.value == 2 and not loc.dungeon)
        if loc.family == "beggar": return bool(o.shuffle_beggar.value)
        if loc.family == "chest_minigame": return bool(o.shuffle_chest_minigame.value)
        if loc.family == "wonder": return o.shuffle_wonder_items.value == 3 or (o.shuffle_wonder_items.value == 1 and loc.dungeon) or (o.shuffle_wonder_items.value == 2 and not loc.dungeon)
        # Start With silver rupees satisfies the puzzle state instead of exposing the individual rupees as AP checks.
        if loc.family == "silver": return o.shuffle_silver.value in (1, 2)
        if loc.family == "butterfly_fairy": return bool(o.shuffle_butterfly_fairies.value)
        return False

    def create_regions(self) -> None:
        create_regions_and_locations(self)
        place_locked_items(self)
        self.reserve_prefill_locations()
        for location in self.get_locations():
            location.name = str(location.name)
        for region in self.get_regions():
            region.name = str(region.name)
        if self.using_ut:
            fill_shop_items(self)

        if self.options.shuffle_enemy_drops.value or self.options.shuffle_silver.value in (1, 2):
            from .EnemyRoomLogic import create_enemy_room_graph
            create_enemy_room_graph(self)

        actual_regions = {
            region.name: region
            for region in self.multiworld.regions
            if region.player == self.player
        }

        # Stock oot_soh already knows the correct contracted AP region graph.
        # For fork checks that exist in native micro-regions which AP contracts
        # differently, anchor them to a physically co-located stock location
        # rather than trying to recreate that micro-region from Menu.
        stock_locations_by_name = {
            location.name: location
            for location in self.multiworld.get_locations(self.player)
            if location.parent_region is not None
        }
        exact_fork_stock_anchors = {
            # Native GTG: this silver is true in CENTRAL_MAZE_RIGHT, the same
            # micro-region as the stock freestanding key.
            "RC_GTG_UNDER_LEDGE_LAVA_SILVER":
                "Gerudo Training Ground Freestanding Key",

            # Native DC: pedestal and End Of Bridge Chest are both in FAR_BRIDGE.
            "RC_DODONGOS_CAVERN_TOP_FLOOR_PEDESTAL":
                "Dodongos Cavern End Of Bridge Chest",

            # Native ZD: King Zora red ice/thaw are the same Domain interaction
            # region; the custom rule below still adds Adult + Blue Fire.
            "RC_ZD_KING_ZORA_RED_ICE":
                "ZD King Zora Thawed",
        }

        region_members = {region.name: region for region in Regions}
        native_region_aliases = {
            "THE_LOST_WOODS": "LOST_WOODS",
            # Malon's Egg can be disabled while her speech check remains enabled.
            # The native gate is the child castle grounds, never the Menu root.
            "HC_GATE": "HYRULE_CASTLE_GROUNDS",
        }

        def resolve_native_region(rr_token: str):
            token = rr_token[3:] if rr_token.startswith("RR_") else rr_token
            token = native_region_aliases.get(token, token)

            member = region_members.get(token)
            if member is not None and member.value in actual_regions:
                return actual_regions[member.value]

            # Native/AP names differ in a few historical spellings. Only accept
            # normalization when it identifies exactly one live AP region.
            norm = token.replace("THE_", "").replace("JABUJABUS", "JABU_JABUS")
            matches = []
            for member_name, candidate in region_members.items():
                candidate_norm = (
                    member_name.replace("THE_", "").replace("JABUJABUS", "JABU_JABUS")
                )
                if candidate_norm == norm and candidate.value in actual_regions:
                    matches.append(actual_regions[candidate.value])

            unique = {region.name: region for region in matches}
            if len(unique) == 1:
                return next(iter(unique.values()))
            return None

        # Exact Speech Sanity checks use the live stock oot_soh location with
        # `base_address` as their region anchor. This is intentionally different
        # from requiring every native RR_* micro-region to exist in the AP
        # Regions enum: stock oot_soh contracts several native regions (for
        # example RR_HC_GATE) into a larger AP region.
        #
        # The stock base location gives us the exact AP-side parent that exists
        # in this generated world while the custom NPC Soul / Speak / age/time
        # rules are layered in set_rules().
        self._exact_speech_region_names = set()
        if self.options.npc_speech_sanity.value:
            stock_locations_by_address = {
                location.address: location
                for location in self.multiworld.get_locations(self.player)
                if location.address is not None
            }

            # A restored vanilla shop shelf has address=None because it is an
            # event. Its original static ID and physical parent still exist.
            # Use that stable lookup in both generation and tracker regeneration.
            for stock_name, stock_data in location_data_table.items():
                live = stock_locations_by_name.get(str(stock_name))
                if live is not None and stock_data.loc_id is not None:
                    stock_locations_by_address.setdefault(stock_data.loc_id, live)

            speech_added = 0
            speech_stock_anchored = 0
            speech_native_anchored = 0
            speech_fallback_anchored = 0

            for speech in SPEECH_LOCATIONS:
                stock_location = stock_locations_by_address.get(speech.base_address)
                region = (
                    stock_location.parent_region
                    if stock_location is not None
                    and stock_location.parent_region is not None
                    else None
                )

                if region is not None:
                    speech_stock_anchored += 1
                else:
                    region = resolve_native_region(speech.region_token)
                    if region is not None:
                        speech_native_anchored += 1

                if region is None:
                    raise OptionError(
                        f"SOH-EXTREME speech check {speech.rc!r} has no physical "
                        f"region anchor ({speech.region_token!r}). Generation stopped "
                        "rather than making an unknown NPC reachable from Menu."
                    )

                name = f"NPC Speech: {speech.rc[3:].replace('_', ' ').title()}"
                region.locations.append(
                    SohExtremeLocation(self.player, name, speech.address, region)
                )
                self._exact_speech_region_names.add(region.name)
                speech_added += 1

            logger.info(
                "SOH-EXTREME added %d exact NPC Speech Sanity AP locations "
                "(%d stock-region anchored, %d native-region anchored, "
                "%d fallback anchored)",
                speech_added, speech_stock_anchored, speech_native_anchored,
                speech_fallback_anchored,
            )

            fallback_region = actual_regions.get("Menu") or next(iter(actual_regions.values()))
            fallback_added = 0
            for name, address in NPC_SPEECH_FALLBACK_NAME_TO_ID.items():
                fallback_region.locations.append(
                    SohExtremeLocation(self.player, name, address, fallback_region)
                )
                fallback_added += 1

            logger.info(
                "SOH-EXTREME added %d generic flavor-NPC placeholder checks (exact-only mode)",
                fallback_added,
            )

        # Shuffle Enemy Drops: one normal AP location for every finite vanilla
        # enemy actor placement extracted from oot.o2r.  These are NOT
        # progression-excluded: normal AP fill is allowed to place progression
        # here, and set_rules() installs Soul + combat/access requirements.
        if self.options.shuffle_enemy_drops.value:
            enemy_added = 0
            enemy_fallback = 0
            for enemy_drop in ENEMY_DROP_LOCATIONS:
                from .EnemyRoomLogic import resolve_enemy_region
                region_member = resolve_enemy_region(enemy_drop.region_token)
                region = actual_regions.get(str(region_member)) if region_member is not None else None
                if region is None:
                    raise OptionError(
                        f"SOH-EXTREME enemy check {enemy_drop.name!r} has no mapped "
                        f"region {enemy_drop.region_token!r}. Generation stopped rather "
                        "than treating an unknown location as reachable from Menu."
                    )
                region.locations.append(
                    SohExtremeLocation(self.player, enemy_drop.name, enemy_drop.address, region)
                )
                enemy_added += 1

            logger.info(
                "SOH-EXTREME added %d exact per-placement enemy defeat checks "
                "(%d region fallbacks; native room routes; progression allowed)",
                enemy_added, enemy_fallback,
            )

        # Every fork-native check stays in the active pool.
        #
        #  - one live native source region: attach directly to that exact region.
        #  - multiple live source regions: parent it to Menu and install
        #    CanReachRegion(A) | CanReachRegion(B) | ... in set_rules().
        #
        # This represents the native OR-of-regions exactly without deleting the
        # location or forcing it to filler.
        self._fork_multi_region_sources = {}
        added = 0
        exact_single = 0
        exact_multi = 0

        neutral_region = actual_regions.get("Menu") or next(iter(actual_regions.values()))

        for loc in FORK_LOCATIONS:
            if not self._fork_location_enabled(loc):
                continue

            if loc.family == "silver":
                # Every authored collection route is an incoming edge to this
                # single-ID proxy. Its condition is evaluated in the SAME age as
                # the source room. No dungeon-entrance or Menu fallback exists.
                from .SilverRoomLogic import create_silver_location_region
                region = create_silver_location_region(self, loc)
                region.locations.append(
                    SohExtremeLocation(self.player, loc.name, loc.address, region)
                )
                added += 1
                exact_single += 1
                continue

            # Prefer a live stock-location parent when we have audited a
            # physically co-located oot_soh check. This is more exact than an
            # OR over native RR_* micro-regions that the AP world may contract.
            stock_anchor_name = exact_fork_stock_anchors.get(loc.rc)
            stock_anchor = (
                stock_locations_by_name.get(stock_anchor_name)
                if stock_anchor_name is not None else None
            )
            if stock_anchor is not None:
                region = stock_anchor.parent_region
                region.locations.append(
                    SohExtremeLocation(self.player, loc.name, loc.address, region)
                )
                added += 1
                exact_single += 1
                continue

            rr_tokens = FORK_NATIVE_REGIONS.get(loc.rc, ())

            resolved = []
            unresolved_tokens = []
            for rr_token in rr_tokens:
                region = resolve_native_region(rr_token)
                if region is not None:
                    resolved.append(region)
                else:
                    unresolved_tokens.append(rr_token)

            unique_regions = {region.name: region for region in resolved}

            if len(unique_regions) == 1 and not unresolved_tokens:
                region = next(iter(unique_regions.values()))
                exact_single += 1
            elif unique_regions:
                # We can represent every AP-visible native route as an OR. Native
                # micro-regions that oot_soh contracts away are projected through
                # the broad parent as one additional route rather than causing a
                # generation failure or disabling the check.
                broad_region = self.multiworld.get_region(str(loc.region), self.player)
                projected_sources = set(unique_regions)
                if unresolved_tokens:
                    projected_sources.add(broad_region.name)

                if len(projected_sources) == 1:
                    region = broad_region
                    exact_single += 1
                else:
                    region = neutral_region
                    self._fork_multi_region_sources[loc.address] = tuple(
                        sorted(projected_sources)
                    )
                    exact_multi += 1

                if unresolved_tokens:
                    logger.debug(
                        "SOH-EXTREME projected native micro-region(s) %s for %s "
                        "through AP parent %s",
                        unresolved_tokens, loc.rc, broad_region.name,
                    )
            else:
                # No native source token maps 1:1 to an oot_soh Regions enum.
                # This is normal for contracted native micro-regions such as
                # RR_HC_GATE. Keep the location fully progression-capable and
                # project it to the manually audited broad AP parent.
                region = self.multiworld.get_region(str(loc.region), self.player)
                exact_single += 1
                logger.debug(
                    "SOH-EXTREME projected contracted native region(s) %s for %s "
                    "through AP parent %s",
                    rr_tokens, loc.rc, region.name,
                )

            region.locations.append(
                SohExtremeLocation(self.player, loc.name, loc.address, region)
            )
            added += 1

        logger.info(
            "SOH-EXTREME added %d fork-native AP locations: %d exact single-region, "
            "%d exact OR-of-regions; none excluded from progression",
            added, exact_single, exact_multi,
        )

        missing_exact_anchors = [
            f"{rc} -> {stock_name}"
            for rc, stock_name in exact_fork_stock_anchors.items()
            if stock_name not in stock_locations_by_name
        ]
        if missing_exact_anchors:
            raise RuntimeError(
                "SOH-EXTREME exact fork stock anchor(s) missing from oot_soh: "
                + ", ".join(missing_exact_anchors)
            )

    def _generate_stock_foundation(self) -> None:
        """Run the vanilla-OoT foundation owned by SOH-EXTREME.

        This is the subset of stock Ship generation that prepares options and
        prefill pools.  It is intentionally local instead of dispatching through
        SohWorld.generate_early(), so stock world overrides cannot alter EXTREME.
        """
        if self.options.true_no_logic and not bool(getattr(self.settings, "allow_true_no_logic", False)):
            raise OptionError(
                f"Player {self.player_name} enabled True No Logic, but the "
                "SOH-EXTREME host setting allow_true_no_logic is disabled."
            )

        self.options.apply_any_required_option_adjustments()
        self.randomized_progressive_skulltula_count = (
            self.options.calculate_progression_skulltula_count(token_reward_counts=token_amounts)
        )

        key_ring_options = [
            self.options.gerudo_fortress_key_ring, self.options.forest_temple_key_ring,
            self.options.fire_temple_key_ring, self.options.water_temple_key_ring,
            self.options.spirit_temple_key_ring, self.options.shadow_temple_key_ring,
            self.options.bottom_of_the_well_key_ring,
            self.options.gerudo_training_ground_key_ring, self.options.ganons_castle_key_ring,
        ]
        if self.options.key_rings != "selection":
            for option in key_ring_options:
                option.value = False
        if self.options.key_rings == "count":
            if (self.options.fortress_carpenters == "normal" and
                    self.options.gerudo_fortress_key_shuffle == "vanilla"):
                if self.options.key_rings_count.value > 8:
                    self.options.key_rings_count.value = 8
                if self.options.gerudo_fortress_key_ring in key_ring_options:
                    key_ring_options.remove(self.options.gerudo_fortress_key_ring)
            self.random.shuffle(key_ring_options)
            for option in key_ring_options[:self.options.key_rings_count.value]:
                option.value = True
        elif (self.options.key_rings == "selection" and
              self.options.fortress_carpenters == "normal" and
              self.options.gerudo_fortress_key_shuffle == "vanilla"):
            self.options.gerudo_fortress_key_ring.value = False

        self.pre_fill_pool += get_pre_fill_rewards(self)
        self.pre_fill_pool += get_prefill_songs(self)
        for key_shuffle in get_own_dungeon_prefill_items(self).values():
            self.pre_fill_pool += key_shuffle
        self.pre_fill_pool += get_dungeon_item_prefill_items(self, False)
        self.pre_fill_pool += get_dungeon_item_prefill_items(self, True)
        self.pre_fill_pool += get_vanilla_shop_pool(self)

        if self.options.ganons_trials == "set_number" and self.options.ganons_trials_count.value > 0:
            self.ganons_trials = [str(trial) for trial in GanonsTrials]
            if self.options.ganons_trials_count.value < 6:
                self.random.shuffle(self.ganons_trials)
                self.ganons_trials = self.ganons_trials[:self.options.ganons_trials_count.value]

        if self.using_ut:
            self.ganons_trials = self.passthrough.get("required_trials", self.ganons_trials)
            for name in (
                "gerudo_fortress_key_ring", "forest_temple_key_ring", "fire_temple_key_ring",
                "water_temple_key_ring", "spirit_temple_key_ring", "shadow_temple_key_ring",
                "bottom_of_the_well_key_ring", "gerudo_training_ground_key_ring",
                "ganons_castle_key_ring",
            ):
                if name in self.passthrough:
                    getattr(self.options, name).value = self.passthrough[name]

    def push_precollected(self, item: Item) -> None:
        if self.options.song_note_shuffle.value and item.name in self.SONG_NOTE_GROUPS:
            existing = {entry.name for entry in self.multiworld.precollected_items[self.player]}
            for note in self.SONG_NOTE_GROUPS[item.name]:
                if note not in existing:
                    super().push_precollected(self.create_item(note))
            return
        super().push_precollected(item)

    def _expand_starting_song_requests(self) -> None:
        """Expand common AP starting inventory before Main consumes the options.

        Main calls MultiWorld.push_precollected directly, so overriding the
        world's convenience method alone does not cover these two options.
        From-pool requests must also be expressed in the same note units that
        Main later removes from the physical pool.
        """
        if not self.options.song_note_shuffle.value:
            return
        for option in (self.options.start_inventory, self.options.start_inventory_from_pool):
            expanded = dict(option.value)
            for song, notes in self.SONG_NOTE_GROUPS.items():
                count = expanded.pop(song, 0)
                if count:
                    # A completed song is a set, not repeatable progression tiers.
                    for note in notes:
                        expanded[note] = max(expanded.get(note, 0), 1)
            option.value = expanded

    def _create_stock_item_pool(self) -> None:
        """Create the vanilla OoT portion of the pool without SohWorld."""
        if not self.options.shuffle_swim:
            self.push_precollected(self.create_item(Items.PROGRESSIVE_SCALE, create_as_event=True))
        if not self.options.shuffle_deku_stick_bag:
            self.push_precollected(self.create_item(Items.PROGRESSIVE_STICK_CAPACITY, create_as_event=True))
        if not self.options.shuffle_deku_nut_bag:
            self.push_precollected(self.create_item(Items.PROGRESSIVE_NUT_CAPACITY, create_as_event=True))
        if not self.options.shuffle_childs_wallet:
            self.push_precollected(self.create_item(Items.PROGRESSIVE_WALLET, create_as_event=True))

        if self.options.small_key_shuffle in ("vanilla", "own_dungeon"):
            self.multiworld.push_precollected(self.create_item(str(Items.FIRE_TEMPLE_SMALL_KEY), True))

        give_starting_items(self)
        create_item_pool(self)
        if self.options.triforce_hunt:
            create_triforce_pieces(self)
        create_filler_item_pool(self)
        self.set_completion_rule()

    def generate_early(self) -> None:
        # Universal Tracker must restore the exact generated option snapshot
        # *before* stock SoH's generate_early() resolves any option-dependent
        # regions, pools, prices, or prefill state.
        self._apply_universal_tracker_slot_data()

        # Resolve the native Random=0 sentinel once, before rules are built.
        # The concrete value is exported to both SoH and Universal Tracker;
        # neither may independently choose a different day/night topology.
        if self.options.frozen_starting_time.value == 0:
            # Pre-0.11.11 clients interpreted an exported zero as Dawn. Do not
            # reroll that legacy slot on tracker reconnect.
            self.options.frozen_starting_time.value = (
                1 if self.using_ut else self.random.choice((1, 2, 3, 4))
            )

        # Soul-controlled object families must exist in the generated topology.
        # Apply these implications before the foundation computes included
        # locations/prefill state.
        if self.options.shuffle_pot_soul.value and self.options.shuffle_pots.value == 0:
            self.options.shuffle_pots.value = 3
        if self.options.shuffle_crate_soul.value and self.options.shuffle_crates.value == 0:
            self.options.shuffle_crates.value = 3
        if self.options.shuffle_grass_bush_soul.value and self.options.shuffle_grass.value == 0:
            self.options.shuffle_grass.value = 3
        if self.options.shuffle_tree_soul.value and self.options.shuffle_trees.value == 0:
            self.options.shuffle_trees.value = 1
        if self.options.shuffle_beehive_soul.value and self.options.shuffle_beehives.value == 0:
            self.options.shuffle_beehives.value = 1

        self._expand_starting_song_requests()
        if self.options.song_note_shuffle.value and self.options.shuffle_songs != "anywhere":
            logger.info("SOH-EXTREME individual notes use the normal pool; whole-song "
                        "placement mode %s does not place complete songs", self.options.shuffle_songs.current_key)
        self._generate_stock_foundation()
        self._restore_universal_tracker_shop_prices()

        # The Extreme Soul options gate these object types in the game.  If a
        # corresponding sanity option is left Off, the Extreme item pool can be
        # larger than the stock SoH check pool.  Enable the matching stock check
        # family so the Soul has checks to gate and so every Extreme item has a
        # legitimate Archipelago location slot.
        #
        # Choice values in the stock SoH APWorld:
        #   shuffle_pots / shuffle_crates / shuffle_grass: 0=off, 3=all
        #   shuffle_trees / shuffle_beehives: Toggle, 0=off, 1=on
        if self.options.shuffle_pot_soul.value and self.options.shuffle_pots.value == 0:
            self.options.shuffle_pots.value = 3
        if self.options.shuffle_crate_soul.value and self.options.shuffle_crates.value == 0:
            self.options.shuffle_crates.value = 3
        if self.options.shuffle_grass_bush_soul.value and self.options.shuffle_grass.value == 0:
            self.options.shuffle_grass.value = 3
        if self.options.shuffle_tree_soul.value and self.options.shuffle_trees.value == 0:
            self.options.shuffle_trees.value = 1
        if self.options.shuffle_beehive_soul.value and self.options.shuffle_beehives.value == 0:
            self.options.shuffle_beehives.value = 1


    def _prefill_stock_locations(self, dungeon_only: bool):
        """Return only official SoH locations for stock key/dungeon prefill.

        SOH-EXTREME adds fork-native checks which are intentionally not members
        of the official ``Locations`` enum / ``location_data_table``.  The stock
        SoH 1.4.x any-dungeon/overworld prefill helpers index every unfilled
        location through that table, which raises KeyError for EXTREME checks.
        Keep those checks in the normal fill pool, but exclude them from stock
        dungeon-item prefill candidate lists.
        """
        result = []
        for loc in self.multiworld.get_unfilled_locations(self.player):
            data = location_data_table.get(loc.name)
            if data is None:
                continue
            if dungeon_only and data.dungeon_tag is None:
                continue
            if not dungeon_only and data.dungeon_tag is not None:
                continue
            result.append(Locations(loc.name))
        return result

    def pre_fill(self) -> None:
        if self.options.shuffle_enemy_drops.value or self.options.shuffle_silver.value in (1, 2):
            from .EnemyRoomLogic import prune_optional_native_actions
            prune_optional_native_actions(self)
        # Tracker regeneration restores the original shop events in create_regions.
        # It must not refill them or randomly relocate original dungeon items.
        if self.using_ut:
            self.set_completion_rule()
            return

        # The official own-dungeon helper already guards unknown location names.
        pre_fill_own_dungeon_items(self)
        pre_fill_dungeon_rewards(self)
        pre_fill_songs(self)

        # Do NOT call stock pre_fill_any_dungeon_keys/pre_fill_overworld_items
        # here.  In SoH 1.4.x they index location_data_table[loc.name] for every
        # unfilled location, which crashes on our EXTREME fork-native checks.
        any_dungeon_items = get_dungeon_item_prefill_items(self, False)
        self.run_prefill(any_dungeon_items, self._prefill_stock_locations(True))

        overworld_items = get_dungeon_item_prefill_items(self, True)
        self.run_prefill(overworld_items, self._prefill_stock_locations(False))

        # This is generation-side Archipelago logic, not client-side SoH code.
        #
        # Stock oot_soh.fill_shop_items() uses run_prefill() to place the small
        # set of vanilla shop items that remain when Shopsanity shuffles fewer
        # than all 8 shelves.  SOH-EXTREME adds many extra access rules, and that
        # restrictive prefill can legitimately leave one of those shop slots
        # unfilled.  The stock helper then immediately dereferences
        # `location.item.name`, causing the NoneType crash seen in Generate.exe.
        #
        # For these shop-stock items there is no gameplay reason to run a logic
        # search: the locations are already hard-reserved specifically for these
        # vanilla shop entries.  Fill the reserved slots directly, preserving
        # stock SoH's pool/slot selection and seed randomness.
        if self.options.shuffle_shops:
            remove_vanilla_shop_reservations(self)

            vanilla_shop_pool = list(get_vanilla_shop_pool(self))
            vanilla_shop_slots = list(get_vanilla_shop_locations(self))

            # Match stock prefill bookkeeping: these items were staged in
            # self.pre_fill_pool during generate_early(), so consume them here.
            for item in list(vanilla_shop_pool):
                if item in self.pre_fill_pool:
                    self.pre_fill_pool.remove(item)

            if len(vanilla_shop_pool) != len(vanilla_shop_slots):
                raise RuntimeError(
                    "SOH-EXTREME shop prefill mismatch: "
                    f"{len(vanilla_shop_pool)} vanilla shop items for "
                    f"{len(vanilla_shop_slots)} reserved shop slots"
                )

            self.random.shuffle(vanilla_shop_pool)
            self.random.shuffle(vanilla_shop_slots)

            for slot, item_enum in zip(vanilla_shop_slots, vanilla_shop_pool):
                location = self.get_location(slot)

                if location.item is not None:
                    raise RuntimeError(
                        f"SOH-EXTREME expected reserved shop slot {slot} to be empty "
                        f"after reservation removal, but found {location.item.name!r}"
                    )

                item = self.create_item(str(item_enum))
                location.address = None
                location.place_locked_item(item)

                self.preplaced_items.append(item)
                self.shop_prices[slot] = vanilla_shop_prices[item_enum]
                self.shop_vanilla_items[slot] = item.name

            print(
                f"SOH-EXTREME directly filled {len(vanilla_shop_slots)} reserved "
                f"vanilla shop slot(s) for Archipelago generation"
            )

        self.set_completion_rule()

    def create_item(self, name: str, create_as_event: bool = False, classification: ItemClassification = None):
        if name in EXTREME_ITEMS:
            # Every SOH-EXTREME ability, Soul, Shovel/Flow item and individual Song
            # Note is real progression.  Keep the AP advancement bit set so remote
            # clients render them as IMPORTANT and balanced fill never treats them as
            # disposable filler.  This is intentionally broader than stock oot_soh.
            classification = ItemClassification.progression
            return SohExtremeItem(name, classification,
                                  None if create_as_event else EXTREME_ITEMS[name], self.player)
        item_entry = Items(name)
        data = item_data_table[item_entry]

        # Triforce Hunt pieces are required-goal progression in SOH-EXTREME.
        # Stock oot_soh may classify them as non-progression/useful, which makes
        # Archipelago clients describe them as useless.  Force the advancement
        # bit here so local and remote clients consistently treat every piece as
        # important progression.
        resolved_classification = data.classification if classification is None else classification
        item_name = str(name)
        if "Triforce" in item_name and "Piece" in item_name:
            resolved_classification = ItemClassification.progression

        return SohExtremeItem(item_name, resolved_classification,
                              None if create_as_event else data.item_id, self.player)

    SONG_ITEMS = {
        "Zelda's Lullaby", "Epona's Song", "Saria's Song", "Sun's Song",
        "Song of Time", "Song of Storms", "Minuet of Forest", "Bolero of Fire",
        "Serenade of Water", "Requiem of Spirit", "Nocturne of Shadow", "Prelude of Light",
    }

    # Must match ArchipelagoClient::RefreshSongNotes() in the SOH fork.
    # The 74 AP note items are contiguous, and each tuple gives the normal SoH
    # song item unlocked once every note in that slice has been collected.
    SONG_NOTE_LAYOUT = (
        ("Zelda's Lullaby", 6),
        ("Epona's Song", 6),
        ("Saria's Song", 6),
        ("Sun's Song", 6),
        ("Song of Time", 6),
        ("Song of Storms", 6),
        ("Minuet of Forest", 6),
        ("Bolero of Fire", 8),
        ("Serenade of Water", 5),
        ("Requiem of Spirit", 6),
        ("Nocturne of Shadow", 7),
        ("Prelude of Light", 6),
    )

    SONG_NOTE_GROUPS = {}
    _song_note_offset = 0
    for _song_name, _song_note_count in SONG_NOTE_LAYOUT:
        SONG_NOTE_GROUPS[_song_name] = tuple(
            f"Song Note {i + 1:02d}"
            for i in range(_song_note_offset, _song_note_offset + _song_note_count)
        )
        _song_note_offset += _song_note_count
    del _song_note_offset, _song_name, _song_note_count

    @classmethod
    def _song_for_note(cls, note_name: str):
        for song_name, notes in cls.SONG_NOTE_GROUPS.items():
            if note_name in notes:
                return song_name, notes
        return None, None

    def _refresh_virtual_song_for_note(self, state, note_name: str) -> bool:
        """Mirror the client's note->song unlock in Archipelago logic.

        Stock SoH rules use the twelve normal song names.  With individual note
        shuffle those normal song items are removed from the pool, so once all
        notes for one song have been collected we add one logical copy of the
        stock song to ``prog_items``.  It is removed again if fill simulation
        removes a required note.
        """
        song_name, notes = self._song_for_note(note_name)
        if song_name is None:
            return False

        virtual = state._soh_extreme_virtual_songs.setdefault(self.player, set())
        complete = all(state.has(required_note, self.player) for required_note in notes)

        if complete and song_name not in virtual:
            # IMPORTANT: do not mutate state.prog_items directly here. The SoH
            # rules use CachedRuleBuilder, and direct Counter mutation does not
            # invalidate Has(song) dependencies that may already be cached false.
            # Route the virtual song through CollectionState.collect so the normal
            # world collect hook and rule-cache invalidation run exactly as if the
            # stock song item had been collected.
            virtual.add(song_name)
            state.collect(self.create_item(song_name, create_as_event=True), True)
            state._soh_stale[self.player] = True
            return True

        if not complete and song_name in virtual:
            # Same reason as above: use CollectionState.remove so cached rules
            # depending on the stock song are invalidated during fill simulation.
            virtual.remove(song_name)
            state.remove(self.create_item(song_name, create_as_event=True))
            state._soh_stale[self.player] = True
            return True

        return False

    def collect(self, state, item: Item) -> bool:
        # Stock SoH already expands Shuffle Swim to THREE Progressive Scale items:
        #   #1 = Bronze/basic surface swim, #2 = Silver, #3 = Golden.
        # SOH-EXTREME additionally exposes a virtual ``Swim`` event for custom
        # native rules, but MUST NOT consume scale #1. Consuming it shifts the
        # counted progression down by one and makes Golden Scale (count 3)
        # impossible, which in turn makes checks such as LH Lab Dive unreachable
        # even with every generated item collected.
        if self.options.shuffle_swim.value and item.name == "Progressive Scale":
            if not state._soh_extreme_virtual_swim.setdefault(self.player, False):
                state._soh_extreme_virtual_swim[self.player] = True
                state.collect(self.create_item("Swim", create_as_event=True), True)
                state._soh_stale[self.player] = True
            # Fall through: the physical scale must ALSO be counted normally.

        # Native SOH-EXTREME uses the first physical Strength Upgrade as the
        # shuffled Grab/Power Bracelet tier without increasing UPG_STRENGTH.
        # Keep AP logic shifted the same way so physical #2 is Goron Bracelet.
        if self.options.shuffle_grab.value and item.name in SOH_ITEM_ALIASES["Strength Upgrade"]:
            virtual = state._soh_extreme_virtual_grab.setdefault(self.player, False)
            if not virtual:
                state._soh_extreme_virtual_grab[self.player] = True
                state.collect(self.create_item("Grab / Power Bracelet", create_as_event=True), True)
                state._soh_stale[self.player] = True
                return True

        changed = super().collect(state, item)
        state._soh_stale[self.player] = True
        if item.name == str(Items.HEART_CONTAINER):
            state.soh_heart_count[self.player] += 1
        if item.name in (str(Items.PIECE_OF_HEART), str(Items.PIECE_OF_HEART_WINNER)):
            state.soh_piece_of_heart_count[self.player] += 1
            if state.soh_piece_of_heart_count[self.player] == 4:
                state.soh_piece_of_heart_count[self.player] = 0
                state.soh_heart_count[self.player] += 1
        if self.options.song_note_shuffle.value and item.name.startswith("Song Note "):
            changed = self._refresh_virtual_song_for_note(state, item.name) or changed
        return changed

    def remove(self, state, item: Item) -> bool:
        if self.options.shuffle_swim.value and item.name == "Progressive Scale":
            # Keep the virtual Swim event synchronized with the real progressive
            # count. The event exists while at least one physical scale exists.
            changed = super().remove(state, item)
            if changed and not state.has("Progressive Scale", self.player):
                if state._soh_extreme_virtual_swim.get(self.player, False):
                    state._soh_extreme_virtual_swim[self.player] = False
                    state.remove(self.create_item("Swim", create_as_event=True))
            state._soh_invalidate(self.player)
            return changed

        if self.options.shuffle_grab.value and item.name in SOH_ITEM_ALIASES["Strength Upgrade"]:
            # Reverse the native strength shift: remove real strength tiers first,
            # then the virtual Grab tier only after no stock Strength remains.
            strength_name = _soh_item_name(self, "Strength Upgrade") or "Strength Upgrade"
            if state.has(strength_name, self.player):
                changed = super().remove(state, item)
                state._soh_invalidate(self.player)
                return changed
            if state._soh_extreme_virtual_grab.get(self.player, False):
                state._soh_extreme_virtual_grab[self.player] = False
                state.remove(self.create_item("Grab / Power Bracelet", create_as_event=True))
                state._soh_invalidate(self.player)
                return True

        changed = super().remove(state, item)
        if not changed:
            return False
        # Clearing only _soh_stale left previously reachable child/adult
        # regions accessible after an ability, song, or button was removed.
        state._soh_invalidate(self.player)
        if item.name == str(Items.HEART_CONTAINER):
            state.soh_heart_count[self.player] -= 1
        if item.name in (str(Items.PIECE_OF_HEART), str(Items.PIECE_OF_HEART_WINNER)):
            state.soh_piece_of_heart_count[self.player] -= 1
            if state.soh_piece_of_heart_count[self.player] == -1:
                state.soh_piece_of_heart_count[self.player] = 3
                state.soh_heart_count[self.player] -= 1
        if self.options.song_note_shuffle.value and item.name.startswith("Song Note "):
            changed = self._refresh_virtual_song_for_note(state, item.name) or changed
        return changed

    HEALTH_REPLACEMENT_ITEMS = {
        "Piece of Heart", "Heart Container", "Piece of Heart (WINNER)",
    }

    def _remove_pool_item(self, item) -> None:
        self.item_pool.remove(item)
        if item in self.multiworld.itempool:
            self.multiworld.itempool.remove(item)

    def _remove_replaceable_items(self, count: int, replace_songs: bool = False) -> None:
        """Make room for Extreme items without removing real SoH progression.

        Stock SoH keeps progression/useful pool entries in ``self.item_pool``, but
        ``create_filler_item_pool`` appends junk and Ice Traps directly to
        ``multiworld.itempool``.  The older SOH-EXTREME build only searched
        ``self.item_pool``, so it could not see most of the available filler and
        eventually started precollecting important stock items.

        This version replaces, in order:
          1. the 12 full-song items when Individual Song Notes are enabled;
          2. filler/trap/non-progression entries from the *actual global pool*;
          3. optional heart upgrades only if an unusual configuration still needs
             a few more slots.

        Dungeon keys, equipment, rewards, overworld door keys, Skeleton Key, etc.
        are never precollected or deleted by this function.
        """
        removed = 0

        def remove_item(item) -> None:
            nonlocal removed
            if item in self.multiworld.itempool:
                self.multiworld.itempool.remove(item)
            if item in self.item_pool:
                self.item_pool.remove(item)
            removed += 1

        # Individual notes replace the normal twelve songs first.
        if replace_songs:
            for item in list(reversed(self.multiworld.itempool)):
                if removed >= count:
                    break
                if item.player == self.player and item.name in self.SONG_ITEMS:
                    remove_item(item)

        # IMPORTANT: scan multiworld.itempool, not just self.item_pool.
        # SoH's create_filler_item_pool() puts its filler and traps directly here.
        for item in list(reversed(self.multiworld.itempool)):
            if removed >= count:
                break
            if item.player != self.player:
                continue
            if item.classification & ItemClassification.progression:
                continue
            remove_item(item)

        # Last-resort optional health slots.  These are still preferable to
        # touching any required key/equipment/reward progression.
        if removed < count:
            for item in list(reversed(self.multiworld.itempool)):
                if removed >= count:
                    break
                if item.player != self.player or item.name not in self.HEALTH_REPLACEMENT_ITEMS:
                    continue
                remove_item(item)

        if removed != count:
            raise Exception(
                f"SOH-EXTREME needs {count} pool slots but only found {removed} replaceable slots. "
                "Enable the corresponding object sanity checks or use a less restrictive stock item pool."
            )

    # SOH-EXTREME logic bridge.  These are not tracker-only rules: generation,
    # spoiler spheres, hints and Universal Tracker all consume the same rules.
    # They mirror the fork's central MegaSoulAllowsLocation()/interaction gates.
    def set_rules(self) -> None:
        generate_prices(self)
        if self.options.shuffle_enemy_drops.value or self.options.shuffle_silver.value in (1, 2):
            from .SilverRoomLogic import install_silver_routes
            install_silver_routes(self)
            # Trial selection and UT slot-data restoration happen in create_items.
            # Compiling these rules in create_regions would silently skip trials.
            self._extreme_room_compiler.install()

        o = self.options

        # Core SOH-EXTREME ability helpers must be defined before any route
        # hardening below can call them.  0.11.8 defined Grab/Climb much later
        # in set_rules(), which made Python treat them as local variables that
        # were still unbound when the DMT/DMC ingress rules executed.
        def grab_rule():
            return Has("Grab / Power Bracelet") if o.shuffle_grab.value else True_()

        def swim_rule():
            # Surface swimming is innate when Shuffle Swim is disabled. When it
            # is enabled, the first physical Progressive Scale provides Swim.
            return Has("Swim") if o.shuffle_swim.value else True_()

        def climb_rule():
            return Has("Climb") if o.shuffle_climb.value else True_()

        animal_tags = LocTag.Cow | LocTag.Overworld_Fish | LocTag.Grotto_Fish | LocTag.Pond_Fish
        grass_tags = LocTag.Overworld_Grass | LocTag.Grotto_Grass | LocTag.Dungeon_Grass
        npc_tags = (LocTag.Shop | LocTag.Merchant | LocTag.Trade_Location |
                    LocTag.Shooting_Minigame | LocTag.House_of_Skulltula_Reward)

        # Large chests use the second Progressive Open Chest level.  Do not infer
        # this from item/name keywords: use the native EnBox type table exported
        # above, so AP generation and the in-game native reachability engine agree.
        large_chest_names = set(NATIVE_LARGE_CHEST_NAMES)

        fork_requirements = {}
        fork_any_requirements = {}
        fork_group_requirements = {}
        fork_native_rules = {}

        def add_resolved_rule(spot, rule: Rule, combine: str = "and", register_indirects: bool = False):
            """Combine a Rule Builder rule with either a resolved rule or legacy callable.

            Stock oot_soh on AP 0.6.7 can leave ordinary Python callables on some
            Locations/Entrances.  ``And.Resolved`` / ``Or.Resolved`` may only contain
            ``Rule.Resolved`` children, so wrapping those callables as if they were
            resolved rules crashes on attributes such as ``always_false``.  Resolve
            only the new SOH-EXTREME rule, register its dependencies, then use AP's
            callable-compatible ``add_rule`` to preserve the inherited rule.
            """
            resolved = rule.resolve(self) if isinstance(rule, Rule) else rule
            if isinstance(resolved, Rule.Resolved):
                self.register_rule_dependencies(resolved)
                if register_indirects:
                    self._register_rule_indirects(resolved, spot)
            add_rule(spot, resolved, combine)

        def alternative_groups_rule(groups):
            """Build the physical outer-OR / inner-AND rule used by EXTREME gates."""
            alternatives = []
            for group in groups:
                children = []
                for item_name, count in group:
                    resolved_name = _soh_item_name(self, item_name)
                    if resolved_name is None:
                        raise OptionError(f"Unknown required SOH-EXTREME item: {item_name!r}")
                    children.append(Has(resolved_name, count))
                if not children:
                    continue
                alternatives.append(children[0] if len(children) == 1 else And(*children))

            if not alternatives:
                return None
            return alternatives[0] if len(alternatives) == 1 else Or(*alternatives)

        def require(location, item_name: str, count: int = 1):
            # Fork-native checks do not have stock SoH resolved rules.  Accumulate
            # every Extreme requirement and install them together after all gates
            # have been discovered, rather than overwriting one gate with another.
            if location.name in FORK_LOCATION_NAME_TO_ID:
                fork_requirements.setdefault(location.name, []).append((item_name, count))
                return

            # AP 0.6.7 stock SoH may use either Rule.Resolved or a plain callable.
            # add_resolved_rule safely ANDs the new gate onto both representations.
            resolved_name = _soh_item_name(self, item_name) or item_name
            add_resolved_rule(location, Has(resolved_name, count))

        # Use one catalogue-driven rule implementation for generation and UT.
        from .EnemyDropRules import enemy_drop_rule
        if o.shuffle_enemy_drops.value:
            for enemy_drop in ENEMY_DROP_LOCATIONS:
                try:
                    enemy_location = self.get_location(enemy_drop.name)
                except KeyError as error:
                    raise OptionError(f"Missing active enemy location: {enemy_drop.name}") from error
                add_resolved_rule(enemy_location, enemy_drop_rule(self, enemy_drop), register_indirects=True)

        def speech_item_for(location_name: str) -> str:
            upper = location_name.upper()

            # Exact native exception: the Zora River bean salesman is a Hylian-
            # language interaction in the C++ logic despite living in Zora's River.
            # Name/area heuristics would incorrectly require Speak Zora.
            if "ZR MAGIC BEAN SALESMAN" in upper or "ZORA'S RIVER MAGIC BEAN SALESMAN" in upper:
                return "Speak Hylian"

            if any(k in upper for k in ("DEKU", "SCRUB")):
                return "Speak Deku"
            if any(k in upper for k in ("GERUDO", "FORTRESS", "GF ", "GV ", "THIEVES")):
                return "Speak Gerudo"
            if any(k in upper for k in ("GORON", "GC ", "DMT ", "DMC ")):
                return "Speak Goron"
            if any(k in upper for k in ("ZORA", "ZR ", "ZD ", "ZF ", "JABU")):
                return "Speak Zora"
            if any(k in upper for k in ("KOKIRI", "KF ", "LOST WOODS", "LW ", "SFM ", "SARIA", "MIDO", "SKULL KID")):
                return "Speak Kokiri"
            return "Speak Hylian"

        def require_speak(location):
            if o.shuffle_speak.value == 1:
                require(location, "Speak")
            elif o.shuffle_speak.value == 2:
                # Prefer the mechanically extracted native C++ language for every
                # mapped check. Fall back to the name heuristic only for custom/
                # event locations that have no native AP id.
                exact = NATIVE_EXACT_SPEAK_BY_AP_ID.get(location.address)
                if exact is not None:
                    require(location, f"Speak {exact}")
                else:
                    require(location, speech_item_for(location.name))

        def require_language(location, language: str):
            if o.shuffle_speak.value == 1:
                require(location, "Speak")
            elif o.shuffle_speak.value == 2:
                require(location, f"Speak {language}")

        def animal_item_for(location_name: str) -> str:
            upper = location_name.upper()
            if "COW" in upper:
                return "Cow Soul"
            if any(k in upper for k in ("CUCCO", "CHICKEN", "ANJU")):
                return "Cucco Soul"
            if "DOG" in upper:
                return "Dog Soul"
            if any(k in upper for k in ("FISH", "POND")):
                return "Fish Soul"
            if "BUG" in upper:
                return "Bug Soul"
            if "BUTTERFLY" in upper:
                return "Butterfly Soul"
            if "FROG" in upper:
                return "Frog Soul"
            if any(k in upper for k in ("HORSE", "EPONA", "HBA", "BIG POE", "TALON RACE", "TIME TRIAL")):
                return "Horse Soul"
            return "Animal Soul"

        def require_animal(location, forced_type: str | None = None):
            if not o.shuffle_animal_soul.value:
                return
            if o.shuffle_animal_soul.value == 1:
                require(location, "Animal Soul")
            else:
                exact = NATIVE_EXACT_ANIMAL_BY_AP_ID.get(location.address)
                animal_name = forced_type or (f"{exact} Soul" if exact is not None else animal_item_for(location.name))
                require(location, animal_name)

        def animal_rule(kind: str):
            if not o.shuffle_animal_soul.value:
                return True_()
            if o.shuffle_animal_soul.value == 1:
                return Has("Animal Soul")
            return Has(f"{kind} Soul")

        def enemy_item_for(location_name: str) -> str | None:
            """Best-effort exact enemy Soul from concrete actor/check names.

            This is only used for native metadata that already says the check is
            enemy-backed. Unknown names are left ungated here rather than falling
            back to the nonexistent all-enemies wildcard in Individual mode.
            """
            upper = location_name.upper()
            mapping = (
                (("DEKU BABA", "BABA "), "Deku Baba Soul"),
                (("OCTOROK",), "Octorok Soul"),
                (("STALFOS",), "Stalfos Soul"),
                (("WALLMASTER",), "Wallmaster Soul"),
                (("DODONGO",), "Dodongo Soul"),
                (("KEESE",), "Keese Soul"),
                (("TEKTITE",), "Tektite Soul"),
                (("PEAHAT",), "Peahat Soul"),
                (("LIZALFOS", "DINOLFOS"), "Lizalfos and Dinolfos Soul"),
                (("GOHMA LARVA",), "Gohma Larva Soul"),
                (("SHABOM",), "Shabom Soul"),
                (("BABY DODONGO",), "Baby Dodongo Soul"),
                (("BIRI", "BARI"), "Biri and Bari Soul"),
                (("TAILPASARAN",), "Tailpasaran Soul"),
                (("TORCH SLUG",), "Torch Slug Soul"),
                (("MOBLIN",), "Moblin Soul"),
                (("ARMOS",), "Armos Soul"),
                (("DEKU SCRUB",), "Deku Scrub Soul"),
                (("BUBBLE",), "Bubble Soul"),
                (("BEAMOS",), "Beamos Soul"),
                (("FLOORMASTER",), "Floormaster Soul"),
                (("REDEAD", "GIBDO"), "Redead and Gibdo Soul"),
                (("FLARE DANCER",), "Flare Dancer Soul"),
                (("DEAD HAND",), "Dead Hand Soul"),
                (("SHELL BLADE",), "Shell Blade Soul"),
                (("LIKE LIKE",), "Like Like Soul"),
                (("SPIKE",), "Spike Soul"),
                (("ANUBIS",), "Anubis Soul"),
                (("IRON KNUCKLE",), "Iron Knuckle Soul"),
                (("SKULL KID",), "Skull Kid Soul"),
                (("FLYING POT",), "Flying Pot Soul"),
                (("FREEZARD",), "Freezard Soul"),
                (("STINGER",), "Stinger Soul"),
                (("WOLFOS",), "Wolfos Soul"),
                (("GUAY",), "Guay Soul"),
                (("JABU", "TENTACLE"), "Jabu Jabu Tentacle Soul"),
                (("DARK LINK",), "Dark Link Soul"),
                (("POE SISTER",), "Poe Sister Soul"),
            )
            for needles, item in mapping:
                if any(needle in upper for needle in needles):
                    return item
            return None

        def require_any_fork(location, *item_names: str):
            if location.name in FORK_LOCATION_NAME_TO_ID:
                fork_any_requirements.setdefault(location.name, []).append(tuple(item_names))

        def require_groups_fork(location, groups):
            if location.name in FORK_LOCATION_NAME_TO_ID:
                fork_group_requirements.setdefault(location.name, []).append(tuple(groups))

        def require_native_fork(location, rule: Rule):
            if location.name in FORK_LOCATION_NAME_TO_ID:
                fork_native_rules.setdefault(location.name, []).append(rule)

        def require_native_existing(location, rule: Rule):
            if location.name in FORK_LOCATION_NAME_TO_ID:
                require_native_fork(location, rule)
            else:
                add_resolved_rule(location, rule)

        def region_for_location(location):
            name = location.parent_region.name
            for region in Regions:
                if region.value == name or str(region) == name:
                    return region
            return None

        def native_bundle_for_location(location):
            region = region_for_location(location)
            return (region, self) if region is not None else None


        def find_region(name: str):
            for region in self.multiworld.regions:
                if region.player == self.player and region.name == name:
                    return region
            return None

        def require_entrance(source_region: str, target_region: str, rule: Rule):
            """Compose a custom rule onto the actual directed region entrance."""
            source = find_region(source_region)
            if source is None:
                logger.warning("SOH-EXTREME entrance source region missing: %s", source_region)
                return False

            matched = False
            for entrance in source.exits:
                connected = getattr(entrance, "connected_region", None)
                if connected is None or connected.name != target_region:
                    continue
                add_resolved_rule(entrance, rule, register_indirects=True)
                matched = True

            if not matched:
                logger.warning(
                    "SOH-EXTREME entrance not found: %s -> %s",
                    source_region, target_region,
                )
            return matched

        def require_entrance_item(source_region: str, target_region: str,
                                  item_name: str, enabled: bool):
            if enabled:
                require_entrance(source_region, target_region, Has(item_name))

        # ------------------------------------------------------------------
        # 0.7.9 BOOLEAN-PRESERVING NATIVE-LOGIC OVERLAY
        # ------------------------------------------------------------------
        # 0.7.5 flattened every custom dependency found in a native expression
        # into one AND-list.  That was fail-closed, but it destroyed native OR
        # alternatives and could make hundreds of locations impossible to fill.
        #
        # 0.7.6 uses generated DNF alternatives from the actual C++ boolean
        # expressions.  Each inner tuple is an AND branch; outer tuples are OR.
        # A blank branch means there is a legitimate route that does not require
        # any shuffled SOH-EXTREME action/Soul, so no extra overlay is added and
        # the inherited SoH rule remains authoritative for that route.

        def native_item_enabled(item_name: str) -> bool:
            return {
                "Climb": bool(o.shuffle_climb.value),
                "Crawl": bool(o.shuffle_crawl.value),
                "Grab / Power Bracelet": bool(o.shuffle_grab.value),
                "Speak": bool(o.shuffle_speak.value),
                "Open Chest": bool(o.shuffle_open_chest.value),
                "Animal Soul": bool(o.shuffle_animal_soul.value),
                "Enemy Soul": bool(o.shuffle_enemy_soul.value),
                "NPC Soul": bool(o.shuffle_npc_soul.value),
                "Pot Soul": bool(o.shuffle_pot_soul.value),
                "Crate Soul": bool(o.shuffle_crate_soul.value),
                "Grass / Bush Soul": bool(o.shuffle_grass_bush_soul.value),
                "Rock / Boulder Soul": bool(o.shuffle_rock_boulder_soul.value),
                "Tree Soul": bool(o.shuffle_tree_soul.value),
                "Beehive Soul": bool(o.shuffle_beehive_soul.value),
                "Sign Soul": bool(o.shuffle_sign_soul.value),
                "Skulltula Soul": bool(o.shuffle_skulltula_soul.value),
                "Scrub Soul": bool(o.shuffle_business_scrub_soul.value),
                "Shovel": bool(o.shuffle_shovel.value),
                "Roll": bool(o.shuffle_roll.value),
                "Swim": bool(o.shuffle_swim.value),
            }.get(item_name, False)

        def native_requirement_rule(item_name: str):
            """Translate one native custom dependency into the AP topology in use.

            Combined Speak/Enemy/Animal modes have one wildcard item.  Individual
            modes intentionally do not create those wildcard items, so a raw
            Has("Speak"), Has("Enemy Soul"), or Has("Animal Soul") would be
            permanently false and make the seed unbeatable.

            Exact actor/talk checks are gated later with require_speak(),
            require_animal(), and actor-specific enemy rules.  The generic native
            graph overlay therefore omits those wildcard requirements only while
            their individual topology is selected.
            """
            if item_name == "Speak":
                if not o.shuffle_speak.value:
                    return None
                return Has("Speak") if o.shuffle_speak.value == 1 else None

            if item_name == "Animal Soul":
                if not o.shuffle_animal_soul.value:
                    return None
                return Has("Animal Soul") if o.shuffle_animal_soul.value == 1 else None

            if item_name == "Enemy Soul":
                if not o.shuffle_enemy_soul.value:
                    return None
                return Has("Enemy Soul") if o.shuffle_enemy_soul.value == 1 else None

            # Combat-room traversal can name the exact enemy Soul. In combined
            # mode that exact dependency maps to the single Enemy Soul; in
            # individual mode it remains the exact per-enemy Soul.
            if item_name == "Lizalfos and Dinolfos Soul":
                if not o.shuffle_enemy_soul.value:
                    return None
                if o.shuffle_enemy_soul.value == 1:
                    return Has("Enemy Soul")
                return Has("Lizalfos and Dinolfos Soul")

            # Exact Adult bypass token used by the lower Dodongo's Cavern
            # Lizalfos traversal. The enemy checks themselves are independent.
            if item_name == "Adult":
                return is_adult((Regions.DODONGOS_CAVERN_ENTRYWAY, self))

            if item_name in ALL_SILVER_GROUP_TOTALS:
                # Off and Start With do not require an AP item. "On" advances
                # the native counter one rupee per item; Wallet completes the
                # native group with a single received item.
                if o.shuffle_silver.value == 1:
                    return Has(item_name, ALL_SILVER_GROUP_TOTALS[item_name])
                if o.shuffle_silver.value == 2:
                    return Has(item_name)
                return None

            if not native_item_enabled(item_name):
                return None
            return Has(item_name)

        def native_alternative_rule(alternatives):
            """Build (A & B) | (C & D), preserving individual Soul/Speak topology."""
            enabled_branches = []
            for branch in alternatives:
                branch_rules = []
                for name in branch:
                    rule = native_requirement_rule(name)
                    if rule is not None:
                        branch_rules.append(rule)

                # If this branch has no active custom requirement, it is a
                # legitimate custom-free alternative.
                if not branch_rules:
                    return True_()

                branch_rule = branch_rules[0]
                for rule in branch_rules[1:]:
                    branch_rule = branch_rule & rule
                enabled_branches.append(branch_rule)

            if not enabled_branches:
                return True_()

            rule = enabled_branches[0]
            for branch_rule in enabled_branches[1:]:
                rule = rule | branch_rule
            return rule

        native_region_aliases = {
            "THE_LOST_WOODS": "LOST_WOODS",
            "KF_OUTSIDE_LOST_WOODS": None,
            "KF_LINKS_PORCH": None,
        }
        region_member_names = {region.name: region for region in Regions}
        # The native enemy graph is already explicitly compiled. The older
        # contracted-stock projection must not overwrite its source predicates.
        actual_regions = {region.name: region for region in self.multiworld.regions
                          if region.player == self.player and
                          not region.name.startswith("EXTREME Enemy Route: ")}

        def rr_direct_region_name(rr_token: str):
            token = rr_token[3:] if rr_token.startswith("RR_") else rr_token
            alias = native_region_aliases.get(token, token)
            if alias is None:
                return None
            member = region_member_names.get(alias)
            if member is not None and member.value in actual_regions:
                return member.value
            norm = alias.replace("THE_", "").replace("JABUJABUS", "JABU_JABUS")
            for member_name, member in region_member_names.items():
                mnorm = member_name.replace("THE_", "").replace("JABUJABUS", "JABU_JABUS")
                if mnorm == norm and member.value in actual_regions:
                    return member.value
            return None

        # Keep the complete native graph and the boolean-preserving requirement
        # for each native directed edge.
        edge_alternatives = {
            (source, target): alternatives
            for source, target, alternatives in NATIVE_ENTRANCE_ALTERNATIVES
        }

        # The generated native overlay predates native ITEMTYPE_SILVER and
        # therefore does not mention the group completion items. Add them to
        # every AND branch of the exact room edge. This is the Location-parent
        # requirement layer: every downstream check inherits the door gate.
        for silver_edge, silver_item in SILVER_EDGE_REQUIREMENTS.items():
            branches = edge_alternatives.get(silver_edge, ((),))
            edge_alternatives[silver_edge] = tuple(
                tuple(dict.fromkeys((*branch, silver_item)))
                for branch in branches
            )

        native_forward = {}
        for native_source, native_target in NATIVE_REGION_EDGES:
            native_forward.setdefault(native_source, set()).add(native_target)

        # Find native paths corresponding to one AP entrance.  Intermediate
        # native regions may be contracted away by the stock APWorld.  We stop a
        # path if it reaches some *other* AP-visible region, so requirements are
        # not smeared across unrelated areas.
        rr_by_ap_region = {}
        for rr in set(native_forward) | {t for ts in native_forward.values() for t in ts}:
            ap_name = rr_direct_region_name(rr)
            if ap_name is not None:
                rr_by_ap_region.setdefault(ap_name, set()).add(rr)

        def dnf_reduce(branches):
            normalized = {frozenset(branch) for branch in branches}
            if frozenset() in normalized:
                return ((),)
            ordered = sorted(normalized, key=lambda b: (len(b), sorted(b)))
            kept = []
            for branch in ordered:
                if any(existing.issubset(branch) for existing in kept):
                    continue
                kept.append(branch)
            return tuple(tuple(sorted(branch)) for branch in kept)

        def dnf_and(left, right):
            if not left or not right:
                return ()
            return dnf_reduce(tuple(set(a) | set(b) for a in left for b in right))

        def edge_dnf(source_rr, target_rr):
            # No custom record means this native edge has no shuffled custom
            # dependency and therefore contributes TRUE to the custom overlay.
            return edge_alternatives.get((source_rr, target_rr), ((),))

        def native_paths_custom_dnf(ap_source_name, ap_target_name, max_depth=10):
            starts = rr_by_ap_region.get(ap_source_name, ())
            goals = set(rr_by_ap_region.get(ap_target_name, ()))
            if not starts or not goals:
                return None
            all_branches = []
            for start_rr in starts:
                stack = [(start_rr, ((),), {start_rr}, 0)]
                while stack:
                    cur, cur_dnf, seen, depth = stack.pop()
                    if depth >= max_depth:
                        continue
                    for nxt in native_forward.get(cur, ()):
                        if nxt in seen:
                            continue
                        mapped = rr_direct_region_name(nxt)
                        # Reaching the requested AP target completes this path.
                        if nxt in goals or mapped == ap_target_name:
                            all_branches.extend(dnf_and(cur_dnf, edge_dnf(cur, nxt)))
                            continue
                        # Do not tunnel through a third AP-visible region.
                        if mapped is not None and mapped != ap_source_name:
                            continue
                        next_dnf = dnf_and(cur_dnf, edge_dnf(cur, nxt))
                        if not next_dnf:
                            continue
                        stack.append((nxt, next_dnf, seen | {nxt}, depth + 1))
            return dnf_reduce(tuple(all_branches)) if all_branches else None

        def native_location_path_custom_dnf(ap_source_name, goal_rr, max_depth=24):
            """Custom requirements from an AP parent region to one exact native RR.

            This is the CheckLocation -> Location inheritance from the EXTREME
            logic model: a check keeps its own local rule, and also inherits all
            custom requirements on the native path to its room. It fixes gates
            that stock AP contracts into one broad dungeon region.
            """
            starts = rr_by_ap_region.get(ap_source_name, ())
            if not starts:
                return None

            all_branches = []
            for start_rr in starts:
                if start_rr == goal_rr:
                    all_branches.append(())
                    continue

                stack = [(start_rr, ((),), {start_rr}, 0)]
                while stack:
                    cur, cur_dnf, seen, depth = stack.pop()
                    if depth >= max_depth:
                        continue
                    for nxt in native_forward.get(cur, ()):
                        if nxt in seen:
                            continue

                        next_dnf = dnf_and(cur_dnf, edge_dnf(cur, nxt))
                        if not next_dnf:
                            continue

                        if nxt == goal_rr:
                            all_branches.extend(next_dnf)
                            continue

                        mapped = rr_direct_region_name(nxt)
                        # Do not tunnel through an unrelated AP-visible region.
                        if mapped is not None and mapped != ap_source_name:
                            continue

                        stack.append((nxt, next_dnf, seen | {nxt}, depth + 1))

            return dnf_reduce(tuple(all_branches)) if all_branches else None

        native_entrance_hits = 0
        native_entrance_custom_gates = 0
        unresolved_ap_entrances = 0
        for source_region in actual_regions.values():
            for entrance in source_region.exits:
                target_region = getattr(entrance, "connected_region", None)
                if target_region is None:
                    continue
                alternatives = native_paths_custom_dnf(source_region.name, target_region.name)
                if alternatives is None:
                    unresolved_ap_entrances += 1
                    continue
                native_entrance_hits += 1
                rule = native_alternative_rule(alternatives)
                # native_alternative_rule() returns an unresolved Rule AST here.
                # Only resolved rule nodes expose always_true/always_false in
                # Archipelago 0.6.7, so test the raw True_ sentinel directly.
                if not isinstance(rule, True_):
                    native_entrance_custom_gates += 1
                    add_resolved_rule(entrance, rule, register_indirects=True)


        def deep_swim_route():
            # SOH-EXTREME 0.9.1 stopped consuming the first physical scale into
            # the virtual Swim event.  The counted Progressive Scale stack now
            # mirrors the game exactly: #1 = Bronze/basic Swim, #2 = Silver/deep
            # dive, #3 = Golden.  Therefore every custom deep-water route must
            # require two physical Progressive Scales.
            return Has("Progressive Scale", 2)

        # ------------------------------------------------------------------
        # 0.11.15 LAKE HYLIA TRAVERSAL CONTRACT
        # Keep exact source/destination edges rather than source-name guesses.
        # A known song is not a playable song; boots/fairies/voids are not Swim.
        # The vendor region rules use the same helpers. This final audit also
        # protects against a later/generated overlay weakening a physical edge.
        field_bundle = (Regions.HYRULE_FIELD, self)
        lake_bundle = (Regions.LAKE_HYLIA, self)
        lake_routes = (
            (Regions.HYRULE_FIELD, Regions.LAKE_HYLIA,
             can_climb(field_bundle) | can_use(Items.EPONA, field_bundle)),
            (Regions.LAKE_HYLIA, Regions.HYRULE_FIELD,
             can_climb(lake_bundle) | can_use(Items.EPONA, lake_bundle)),
            (Regions.GV_LOWER_STREAM, Regions.LAKE_HYLIA,
             can_swim((Regions.GV_LOWER_STREAM, self))),
            (Regions.LH_FROM_SHORTCUT, Regions.LAKE_HYLIA,
             can_swim((Regions.LH_FROM_SHORTCUT, self))),
            (Regions.LH_FROM_WATER_TEMPLE, Regions.LAKE_HYLIA,
             can_swim((Regions.LH_FROM_WATER_TEMPLE, self))),
            (Regions.LAKE_HYLIA, Regions.LH_FROM_SHORTCUT, can_swim(lake_bundle)),
            (Regions.LAKE_HYLIA, Regions.LH_FROM_WATER_TEMPLE, can_swim(lake_bundle)),
        )
        self._extreme_lake_route_contract = []
        for source, target, route_rule in lake_routes:
            region = actual_regions.get(str(source))
            matches = [] if region is None else [edge for edge in region.exits
                if edge.connected_region is not None and edge.connected_region.name == str(target)]
            if len(matches) != 1:
                raise OptionError(
                    f"SOH-EXTREME Lake Hylia route audit: expected one {source} -> {target} edge, "
                    f"found {len(matches)}. Refusing to leave this route unverified."
                )
            add_resolved_rule(matches[0], route_rule, register_indirects=True)
            self._extreme_lake_route_contract.append(matches[0].name)

        # Exact Kokiri Forest -> Lost Woods route.
        # In SOH-EXTREME this entrance is the climb route only.
        kf_region = actual_regions.get(str(Regions.KOKIRI_FOREST))
        lw_name = str(Regions.LOST_WOODS)
        kf_lw_edges = [] if kf_region is None else [
            entrance for entrance in kf_region.exits
            if getattr(entrance, "connected_region", None) is not None
            and entrance.connected_region.name == lw_name
        ]
        if not kf_lw_edges:
            raise OptionError(
                "SOH-EXTREME logic audit failed: could not find the actual "
                "Kokiri Forest -> Lost Woods AP entrance."
            )
        kf_route = Has("Climb") if o.shuffle_climb.value else True_()
        for entrance in kf_lw_edges:
            self.set_rule(entrance, kf_route)

        # Exact external ways into the main Lost Woods:
        #   A) Kokiri Forest climb (installed above)
        #   B) Goron City bomb/bombchu route + Rock/Boulder Soul
        #   C) Zora's River underwater shortcut + Progressive Scale
        #
        # Shuffle Swim keeps all three physical Progressive Scale counts. The
        # first scale also creates the virtual Swim event; counted scale #1 is
        # Bronze/basic swim, #2 Silver, and #3 Golden.
        gc_route = Has("Progressive Bomb Bag") | Has("Bombchu Bag")
        if o.shuffle_rock_boulder_soul.value:
            gc_route = gc_route & Has("Rock / Boulder Soul")

        scale_route = deep_swim_route()

        gc_lw_edges = []
        zr_lw_edges = []
        for source_region in actual_regions.values():
            source_upper = source_region.name.upper()
            for entrance in source_region.exits:
                target = getattr(entrance, "connected_region", None)
                if target is None or target.name != lw_name:
                    continue

                if "GORON" in source_upper or "GC WOODS WARP" in source_upper:
                    self.set_rule(entrance, gc_route)
                    gc_lw_edges.append(entrance)
                elif "ZORA" in source_upper or "ZR FROM SHORTCUT" in source_upper:
                    self.set_rule(entrance, scale_route)
                    zr_lw_edges.append(entrance)

        if not gc_lw_edges:
            logger.warning("SOH-EXTREME did not find the GC -> Lost Woods AP edge")
        if not zr_lw_edges:
            logger.warning("SOH-EXTREME did not find the ZR shortcut -> Lost Woods AP edge")

        # ------------------------------------------------------------------
        # DMC ingress / mountain-route hardening.
        #
        # The stock AP graph can make the DMC micro-regions reachable through
        # broad contracted regions even when the physical SOH-EXTREME route is
        # still blocked.  Keep the three real approaches distinct:
        #
        #   1) DMT rockfall -> summit -> DMC upper entry: requires Climb when
        #      Climb is shuffled.  Stock keeps the shield/adult safety checks.
        #   2) Lost Woods <-> Goron City shortcut: requires bombs/bombchus and
        #      Rock/Boulder Soul when that soul is shuffled.
        #   3) Darunia chamber -> DMC pots entry: adult route requires Grab and,
        #      because opening the adult Darunia route depends on the Goron NPC,
        #      NPC Soul + the appropriate Goron speech ability when shuffled.
        #
        # Bolero / Fire Temple arrivals are intentionally untouched; if the
        # player really has one of those routes, DMC may still be reachable
        # without Climb.
        dmt_trail = actual_regions.get(str(Regions.DEATH_MOUNTAIN_TRAIL))
        dmt_summit_name = str(Regions.DEATH_MOUNTAIN_SUMMIT)
        if dmt_trail is not None:
            for entrance in dmt_trail.exits:
                target = getattr(entrance, "connected_region", None)
                if target is not None and target.name == dmt_summit_name:
                    add_resolved_rule(entrance, climb_rule(), register_indirects=True)

        # Fix the reverse Lost Woods -> GC shortcut as well.  The forward edge
        # is already guarded by gc_route above, but stock LOST_WOODS ->
        # GC_WOODS_WARP is otherwise unconditional.
        lw_region = actual_regions.get(str(Regions.LOST_WOODS))
        gc_warp_name = str(Regions.GC_WOODS_WARP)
        if lw_region is not None:
            for entrance in lw_region.exits:
                target = getattr(entrance, "connected_region", None)
                if target is not None and target.name == gc_warp_name:
                    add_resolved_rule(entrance, gc_route, register_indirects=True)

        darunia_region = actual_regions.get(str(Regions.GC_DARUNIAS_CHAMBER))
        dmc_pots_entry_name = str(Regions.DMC_LOWER_LOCAL)
        if darunia_region is not None:
            dmc_pots_gate = grab_rule()
            if o.shuffle_npc_soul.value:
                dmc_pots_gate = dmc_pots_gate & Has("NPC Soul")
            if o.shuffle_speak.value == 1:
                dmc_pots_gate = dmc_pots_gate & Has("Speak")
            elif o.shuffle_speak.value == 2:
                dmc_pots_gate = dmc_pots_gate & Has("Speak Goron")
            for entrance in darunia_region.exits:
                target = getattr(entrance, "connected_region", None)
                if target is not None and target.name == dmc_pots_entry_name:
                    add_resolved_rule(entrance, dmc_pots_gate, register_indirects=True)

        # Dodongo's Cavern lower Lizalfos heart approach:
        # adult can cross directly; child needs Grab / Power Bracelet.
        for source_region in actual_regions.values():
            if "DODONGOS CAVERN SE CORRIDOR" not in source_region.name.upper():
                continue
            # LogicHelpers age rules require the canonical Regions enum value,
            # not the runtime SohRegion instance.
            source_region_enum = next(
                (region_enum for region_enum in Regions if str(region_enum) == source_region.name),
                None,
            )
            if source_region_enum is None:
                raise OptionError(
                    "SOH-EXTREME logic audit failed: could not resolve region enum for "
                    f"{source_region.name!r}"
                )
            bundle = (source_region_enum, self)
            for entrance in source_region.exits:
                target = getattr(entrance, "connected_region", None)
                if target is None:
                    continue
                if "DODONGOS CAVERN NEAR LOWER LIZALFOS" in target.name.upper():
                    self.set_rule(
                        entrance,
                        is_adult(bundle) |
                        (Has("Grab / Power Bracelet") if o.shuffle_grab.value else True_()),
                    )

        # Fork checks that physically exist in more than one native source region
        # use the exact OR of those live regions. Their parent is the neutral
        # Menu region only so no one source path is accidentally privileged.
        locations_by_address = {
            location.address: location for location in self.get_locations()
            if location.address is not None
        }

        # Mechanical direct-ability audit generated from every native C++
        # LOCATION(...) expression. The table contains only abilities that are
        # mandatory on EVERY native occurrence of that AP check, so true OR
        # alternatives are preserved rather than flattened into false AND gates.
        ability_enabled = {
            "Roll": bool(o.shuffle_roll.value),
            "Grab / Power Bracelet": bool(o.shuffle_grab.value),
            "Climb": bool(o.shuffle_climb.value),
            "Crawl": bool(o.shuffle_crawl.value),
            "Shovel": bool(o.shuffle_shovel.value),
            "Flow of Time": bool(o.shuffle_flow_of_time.value),
        }
        native_hard_ability_hits = 0
        for ap_id, abilities in NATIVE_HARD_ABILITIES_BY_AP_ID.items():
            location = locations_by_address.get(ap_id)
            if location is None:
                continue
            for ability in abilities:
                if ability_enabled.get(ability, False):
                    require_native_existing(location, Has(ability))
                    native_hard_ability_hits += 1

        for ap_id, source_region_names in getattr(
            self, "_fork_multi_region_sources", {}
        ).items():
            location = locations_by_address.get(ap_id)
            if location is None:
                continue

            source_rules = [
                CanReachRegion(region_name)
                for region_name in source_region_names
            ]
            if not source_rules:
                raise OptionError(
                    f"SOH-EXTREME multi-region check {location.name!r} has no sources"
                )

            region_rule = source_rules[0]
            for source_rule in source_rules[1:]:
                region_rule = region_rule | source_rule

            require_native_existing(location, region_rule)

        # Exact location overlay.  Preserve C++ OR alternatives rather than
        # requiring the flattened union of every helper/action mentioned.
        native_location_hits = 0
        native_location_custom_gates = 0
        native_location_path_hits = 0
        for native_region, native_rc, ap_id, alternatives in NATIVE_LOCATION_ALTERNATIVES:
            location = locations_by_address.get(ap_id)
            if location is None:
                continue
            native_location_hits += 1

            # Local check requirements AND parent/native-room path requirements.
            # If the exact room cannot be projected, preserve the pre-existing
            # local rule rather than inventing a route.
            path_alternatives = native_location_path_custom_dnf(
                location.parent_region.name, native_region
            )
            combined_alternatives = alternatives
            if path_alternatives is not None:
                combined_alternatives = dnf_and(path_alternatives, alternatives)
                native_location_path_hits += 1

            rule = native_alternative_rule(combined_alternatives)
            # Same unresolved-rule compatibility rule as the entrance pass.
            if isinstance(rule, True_):
                continue
            native_location_custom_gates += 1
            require_native_existing(location, rule)

        # Location-local silver requirements which are not a room transition.
        for silver_location_name, silver_item in SILVER_LOCATION_REQUIREMENTS.items():
            try:
                silver_location = self.get_location(silver_location_name)
            except Exception:
                continue
            silver_rule = native_requirement_rule(silver_item)
            if silver_rule is not None:
                require_native_existing(silver_location, silver_rule)

        # Fork-native checks also inherit their exact native-room path. This is
        # critical for sanity checks living behind an internal silver door.
        fork_native_path_hits = 0
        for fork_loc in FORK_LOCATIONS:
            if not self._fork_location_enabled(fork_loc):
                continue
            try:
                fork_location = self.get_location(fork_loc.name)
            except Exception:
                continue

            # Multi-source checks are parented to neutral Menu and already get
            # the exact OR of their native source regions above. Adding another
            # derived Menu->room path here double-gates them and can make every
            # valid alternate route impossible.
            if fork_location.address in getattr(self, "_fork_multi_region_sources", {}):
                continue

            all_path_branches = []
            for goal_rr in FORK_NATIVE_REGIONS.get(fork_loc.rc, ()):
                path_alternatives = native_location_path_custom_dnf(
                    fork_location.parent_region.name, goal_rr
                )
                if path_alternatives is not None:
                    all_path_branches.extend(path_alternatives)

            if not all_path_branches:
                continue

            path_rule = native_alternative_rule(dnf_reduce(tuple(all_path_branches)))
            if isinstance(path_rule, True_):
                continue

            fork_native_path_hits += 1
            require_native_existing(fork_location, path_rule)

        # SOH-EXTREME: GV cow / upper-stream ledge route.
        #
        # The native direct drop costs enough health that a one-heart start
        # cannot use it.  The physically valid alternatives are:
        #   * Swim
        #   * usable Cucco (Cucco Soul + Grab when those systems are shuffled)
        #   * 2+ maximum hearts to survive the drop
        #
        # Stock/AP region contraction does not preserve this internal GV
        # subregion boundary, so install the route explicitly on its checks.
        gv_upper_stream_route = GVUpperStreamDropHealth()

        if o.shuffle_swim.value:
            gv_upper_stream_route = gv_upper_stream_route | Has("Swim")
        else:
            # Swim is innate when Shuffle Swim is disabled.
            gv_upper_stream_route = True_()

        grab_for_cucco = Has("Grab / Power Bracelet") if o.shuffle_grab.value else True_()
        if o.shuffle_animal_soul.value == 0:
            cucco_for_route = True_()
        elif o.shuffle_animal_soul.value == 1:
            cucco_for_route = Has("Animal Soul")
        else:
            cucco_for_route = Has("Cucco Soul")

        usable_cucco_route = grab_for_cucco & cucco_for_route
        if isinstance(gv_upper_stream_route, True_):
            pass
        else:
            gv_upper_stream_route = gv_upper_stream_route | usable_cucco_route

        for gv_upper_name in ("GV Near Cow Crate", "GV Cow"):
            try:
                gv_upper_location = self.multiworld.get_location(gv_upper_name, self.player)
            except KeyError:
                continue
            require_native_existing(gv_upper_location, gv_upper_stream_route)

        # SOH-EXTREME: these four Market crates are physically positioned so
        # that breaking them with explosives is not sufficient to collect them.
        # Link must be able to Roll to reach/bonk into the crate position.
        # Crate Soul and the normal crate-breaking/existence rules remain
        # independent gates below.
        if o.shuffle_roll.value:
            for market_crate_name in (
                "Market Near Bazaar Crate 1",
                "Market Near Bazaar Crate 2",
                "Market Shooting Gallery Crate 1",
                "Market Shooting Gallery Crate 2",
            ):
                try:
                    market_crate_location = self.multiworld.get_location(
                        market_crate_name, self.player
                    )
                except KeyError:
                    continue
                require_native_existing(market_crate_location, Has("Roll"))

        # SOH-EXTREME: these lower/mid Zora's River checks physically require
        # surface Swim.  Adult age, Boomerang, Iron Boots, Bombchus, or being
        # able to break the object do not substitute for actually swimming to
        # the check's position.
        if o.shuffle_swim.value:
            for zr_swim_location_name in (
                "EXTREME Zr Underwater Rock 1",
                "EXTREME Zr Underwater Rock 2",
                "EXTREME Zr Underwater Rock 3",
                "EXTREME Zr Underwater Rock 4",
                "EXTREME Zr Wonder Before Ladder 1",
                "EXTREME Zr Wonder Before Ladder 2",
                "EXTREME Zr Wonder Before Ladder 3",
                "EXTREME Zr Wonder Before Ladder 4",
                "EXTREME Zr Wonder Before Ladder 5",
                "EXTREME Zr Wonder Before Ladder 6",
                "EXTREME Zr Wonder Frog Bridge 1",
                "EXTREME Zr Wonder Frog Bridge 2",
                "EXTREME Zr Wonder Frog Bridge 3",
                "EXTREME Zr Wonder Lower Land Bridge 1",
                "EXTREME Zr Wonder Lower Land Bridge 2",
                "EXTREME Zr Wonder Lower Land Bridge 3",
                "EXTREME Zr Wonder Lower Land Bridge 4",
            ):
                try:
                    zr_swim_location = self.multiworld.get_location(
                        zr_swim_location_name, self.player
                    )
                except KeyError:
                    continue
                require_native_existing(zr_swim_location, Has("Swim"))

        # Exact central actor/type Soul gates generated from location_list.cpp.
        # These are unconditional actor-existence requirements, so they remain
        # simple AND gates even when the action expression has alternatives.
        for native_rc, ap_id, item_names in NATIVE_LOCATION_METADATA_RULES:
            location = locations_by_address.get(ap_id)
            if location is None:
                continue
            for item_name in item_names:
                if not native_item_enabled(item_name):
                    continue
                if item_name == "Speak":
                    require_speak(location)
                elif item_name == "Animal Soul":
                    require_animal(location)
                elif item_name == "Enemy Soul":
                    if o.shuffle_enemy_soul.value == 1:
                        require(location, "Enemy Soul")
                    elif o.shuffle_enemy_soul.value == 2:
                        specific_enemy = enemy_item_for(location.name)
                        if specific_enemy is not None:
                            require(location, specific_enemy)
                else:
                    require(location, item_name)

        native_unmapped_rule_count = len(NATIVE_UNMAPPED_LOCATION_RULES)

        # Do NOT apply NATIVE_EVENT_ALTERNATIVES by region union.  0.7.5 did
        # that and accidentally made unrelated stock events depend on every
        # custom helper used anywhere in the region.  Exact stock event gates
        # (Mido, GC woods warp, fish/bugs, Baba/pot resources, etc.) are applied
        # below by their actual event names and physical source.

        logger.info(
            "SOH-EXTREME native audit 0.9.9: %d AP entrances matched (%d custom-gated); "
            "%d exact native locations matched (%d custom-gated, %d inherited native-room paths); "
            "%d fork checks inherited native-room paths; "
            "%d AP entrances had no direct native-path projection",
            native_entrance_hits, native_entrance_custom_gates,
            native_location_hits, native_location_custom_gates, native_location_path_hits,
            fork_native_path_hits,
            unresolved_ap_entrances,
        )

        def lost_woods_access_rule(include_gc_warp: bool = True):
            """The three supported physical entry routes into Lost Woods."""
            climb_route = Has("Climb") if o.shuffle_climb.value else True_()
            bomb_route = Has("Progressive Bomb Bag") | Has("Bombchu Bag")
            if o.shuffle_rock_boulder_soul.value:
                bomb_route = bomb_route & Has("Rock / Boulder Soul")
            scale_route = Has("Progressive Scale", 1)

            routes = [climb_route, scale_route]
            if include_gc_warp:
                routes.append(bomb_route)

            rule = routes[0]
            for route in routes[1:]:
                rule = rule | route
            return rule

        def sacred_forest_meadow_access_rule():
            """Physical SFM access, including the child Wolfos gate."""
            # Minuet bypasses Lost Woods completely.  On the normal child route,
            # the entry Wolfos must actually be defeatable before the gate into
            # the meadow opens.  Adult keeps the native bypass.
            bundle = (Regions.SACRED_FOREST_MEADOW, self)
            wolfos_soul = True_()
            if o.shuffle_enemy_soul.value == 1:
                wolfos_soul = Has("Enemy Soul")
            elif o.shuffle_enemy_soul.value == 2:
                wolfos_soul = Has("Wolfos Soul")

            # Bombchus are deliberately NOT accepted for the entry Wolfos gate.
            # Native CanKillEnemy(RE_WOLFOS) considers them a theoretical kill,
            # but in the actual SFM lock-in encounter they do not provide a
            # dependable/physical route to opening the gate.  Tracker logic must
            # model the room-clear condition, not merely generic Wolfos damage.
            wolfos_kill = (
                can_jump_slash(bundle)
                | can_use(Items.FAIRY_BOW, bundle)
                | can_use(Items.FAIRY_SLINGSHOT, bundle)
                | Has("Din's Fire")
                | (Has("Progressive Bomb Bag") & (
                    Has("Progressive Nut Capacity")
                    | can_use(Items.HOOKSHOT, bundle)
                    | can_use(Items.BOOMERANG, bundle)
                ))
            )
            child_gate = is_child(bundle) & wolfos_soul & wolfos_kill
            # Adult can physically bypass the entry gate in native SoH; do not
            # invent a Saria's Song requirement for that bypass.
            adult_gate = is_adult(bundle)
            through_mido = lost_woods_access_rule() & (child_gate | adult_gate)
            return can_use(Items.MINUET_OF_FOREST, bundle) | through_mido

        # 0.7.55 forest-route invariants.  These are deliberately installed on
        # the AP region graph instead of inferred from location names so the fill
        # solver, Universal Tracker and spoiler spheres all see the same routes.
        #
        # Two leaks were proven by seed 28413042166554303232:
        #   * Closed Forest=On still let AP reach Hyrule Field in sphere 1.
        #   * SFM checks were reachable even though the helper below that models
        #     Mido was never attached to an entrance.
        # That put Shovel in SFM (sphere 2), then Rock Soul in a Shovel grotto
        # (sphere 3), while Kokiri Sword / Deku Shield were outside the forest.
        sfm_name = str(Regions.SACRED_FOREST_MEADOW)
        sfm_inbound = []
        for region in actual_regions.values():
            for entrance in region.exits:
                connected = getattr(entrance, "connected_region", None)
                if connected is not None and connected.name == sfm_name:
                    sfm_inbound.append(entrance)
        if not sfm_inbound:
            raise OptionError(
                "SOH-EXTREME logic audit failed: no inbound Sacred Forest Meadow "
                "entrance was found; refusing to generate with unverified Mido logic."
            )
        sfm_rule = sacred_forest_meadow_access_rule()
        for entrance in sfm_inbound:
            add_resolved_rule(entrance, sfm_rule, register_indirects=True)

        # Closed Forest ON means the Kokiri/Lost-Woods bridge route cannot reach
        # Hyrule Field until the Deku Tree is actually completed.  Stock oot_soh
        # can contract the native LW Bridge regions, so enforce the invariant on
        # every AP-visible forest -> Hyrule Field edge that survives contraction.
        # Warp-song/other non-forest entrances are intentionally untouched.
        closed_forest_on = getattr(o.closed_forest, "current_key", None) == "on"
        if closed_forest_on:
            hf_name = str(Regions.HYRULE_FIELD)
            closed_forest_edges = []
            for region in actual_regions.values():
                parent_upper = region.name.upper()
                forest_parent = (
                    region.name in (str(Regions.KOKIRI_FOREST), str(Regions.LOST_WOODS))
                    or "LOST WOODS" in parent_upper
                    or "LW BRIDGE" in parent_upper
                    or "KOKIRI" in parent_upper
                )
                if not forest_parent:
                    continue
                for entrance in region.exits:
                    connected = getattr(entrance, "connected_region", None)
                    if connected is not None and connected.name == hf_name:
                        add_resolved_rule(
                            entrance, Has("Deku Tree Completed"), register_indirects=True
                        )
                        closed_forest_edges.append(entrance)
            if not closed_forest_edges:
                raise OptionError(
                    "SOH-EXTREME logic audit failed: Closed Forest is ON but no "
                    "forest -> Hyrule Field AP edge was found. Refusing to generate "
                    "a seed that could leak outside Kokiri Forest."
                )

        def require_physical_existing(location, groups):
            # Compose a physical OR with the stock SoH rule. The inherited rule
            # still carries age, room, trick, ammo-source and route details; this
            # layer only replaces/extends the interaction methods changed by the
            # EXTREME fork (notably Grab / Power Bracelet).
            if location.name in FORK_LOCATION_NAME_TO_ID:
                require_groups_fork(location, groups)
            else:
                physical = alternative_groups_rule(groups)
                if physical is not None:
                    add_resolved_rule(location, physical)

        def extend_physical_existing(location, groups):
            # Add a fork-only interaction method in OR with stock interaction logic.
            # Parent-region reachability remains unchanged.
            if location.name in FORK_LOCATION_NAME_TO_ID:
                require_groups_fork(location, groups)
            else:
                physical = alternative_groups_rule(groups)
                if physical is not None:
                    add_resolved_rule(location, physical, combine="or")

        def require_alternatives(location_name: str, groups):
            try:
                location = self.get_location(location_name)
            except Exception:
                return
            physical = alternative_groups_rule(groups)
            if physical is not None:
                add_resolved_rule(location, physical)

        # Fork-native locations are not present in the stock Archipelago-SoH
        # location table, so the inherited world cannot add these physical
        # SOH-EXTREME gates for us.  Mirror MegaSoulAllowsLocation() and the
        # corresponding runtime actor gates here for every custom family.
        # This is intentionally done before the individual trigger rules below
        # so multiple requirements compose rather than overwrite one another.
        for fork_loc in FORK_LOCATIONS:
            if not self._fork_location_enabled(fork_loc):
                continue
            location = self.get_location(fork_loc.name)
            family = fork_loc.family

            # Use the exact parent chosen by create_regions(), so age-aware
            # helper dependencies follow the native subregion instead of the old
            # broad ForkLocations parent.
            bundle_region = next(
                (
                    region_enum
                    for region_enum in Regions
                    if region_enum.value == location.parent_region.name
                ),
                fork_loc.region,
            )
            bundle = (bundle_region, self)

            # Source-proven age must constrain the SAME branch as its action.
            # Broad overworld parents exist in both ages; the physical child
            # bush/sign/rock or adult beggar/ice actor often does not.
            native_age = FORK_LOCATION_AGES.get(fork_loc.rc)
            if native_age == "child":
                require_native_fork(location, is_child(bundle))
            elif native_age == "adult":
                require_native_fork(location, is_adult(bundle))
            native_time = FORK_LOCATION_TIMES.get(fork_loc.rc)
            if native_time == "day":
                require_native_fork(location, at_day(bundle))
            elif native_time == "night":
                require_native_fork(location, at_night(bundle))

            # 0.10.4: Fork-native Ganon's Castle sanity actors were all parented
            # to the broad Entryway region.  That bypassed the six native trial
            # doors and made their checks appear in Universal Tracker even when
            # Medallion Locked Trials was enabled.  Mirror the native trial-door
            # requirements directly on every custom actor that physically lives
            # inside a trial.
            if o.medallion_locked_trials.value:
                rc_upper = fork_loc.rc.upper()
                if rc_upper.startswith("RC_GANONS_CASTLE_") or rc_upper.startswith("RC_GANONS_GANONS_CASTLE_"):
                    trial_medallion = None
                    if "_FOREST_" in rc_upper:
                        trial_medallion = "Forest Medallion"
                    elif "_FIRE_" in rc_upper:
                        trial_medallion = "Fire Medallion"
                    elif "_WATER_TRIAL_" in rc_upper:
                        trial_medallion = "Water Medallion"
                    elif "_SPIRIT_" in rc_upper:
                        trial_medallion = "Spirit Medallion"
                    elif "_SHADOW_" in rc_upper:
                        trial_medallion = "Shadow Medallion"
                    elif "_LIGHT_" in rc_upper:
                        trial_medallion = "Light Medallion"
                    if trial_medallion is not None:
                        require(location, trial_medallion)

            if family == "rock":
                rc_upper = fork_loc.rc.upper()
                if "UNDERWATER_ROCK" in rc_upper:
                    # Native underwater rocks: Bombchus can detonate at depth, or
                    # Adult Link can use EXTREME Grab. Reaching the object also
                    # needs Adult access or a child water/projectile route. The
                    # bomb-underwater trick is intentionally left to stock trick
                    # logic rather than assumed.
                    physical = (
                        can_use(Items.BOMBCHU_BAG, bundle)
                        | (is_adult(bundle) & grab_rule())
                    ) & (
                        is_adult(bundle)
                        | swim_rule()
                        | can_use(Items.BOOMERANG, bundle)
                    )
                else:
                    # Logic::CanBreakRocks deliberately excludes Hammer.
                    # Ordinary En_Ishi rocks require explosives or Grab.
                    physical = has_explosives(bundle) | grab_rule()
                require_native_fork(location, physical)
            elif family == "boulder":
                rc_upper = fork_loc.rc.upper()
                if "SILVER_BOULDER" in rc_upper:
                    physical = can_use(Items.SILVER_GAUNTLETS, bundle)
                elif "BRONZE_BOULDER" in rc_upper:
                    physical = can_use(Items.MEGATON_HAMMER, bundle)
                else:
                    # Generic bombable boulders are BlastOrSmash. This is
                    # deliberately conservative for event-removed boulders too:
                    # never certify an unreachable check merely because its
                    # broad parent region can be entered.
                    physical = blast_or_smash(bundle)
                require_native_fork(location, physical)
            elif family == "silver" and fork_loc.rc in {
                "RC_GTG_MIDDLE_WATER_SILVER", "RC_GTG_ABOVE_TARGET_WATER_SILVER",
                "RC_GTG_LEFT_WATER_SILVER", "RC_GTG_UNDER_TARGET_WATER_SILVER",
                "RC_GTG_RIGHT_WATER_SILVER",
            }:
                # Native gerudo_training_ground.cpp, UNDERWATER room: reaching
                # the room does not remove its Song of Time blocks or reach its
                # submerged silver rupees. Keep the one shallow scale route.
                water_route = (can_use(Items.IRON_BOOTS, bundle)
                               & water_timer_at_least(bundle, 16))
                if fork_loc.rc == "RC_GTG_ABOVE_TARGET_WATER_SILVER":
                    water_route |= has_item(Items.GOLDEN_SCALE, bundle)
                require_native_fork(location, can_play_song(Items.SONG_OF_TIME, bundle)
                                    & swim_rule() & water_route)
            elif family == "bush":
                # En_Wood02 bushes drop when Link (or his horse) moves through
                # them. They are NOT En_Kusa cuttable grass. Native region/age
                # access is retained; the Grass / Bush Soul existence gate is
                # added below. No sword, explosives, Grab or Roll is required.
                pass
            elif family == "icicle":
                rc_upper = fork_loc.rc.upper()
                if "STALAGMITE" in rc_upper or "ICICLES_SLOPE_SILVER" in rc_upper:
                    physical = (
                        can_jump_slash(bundle)
                        | has_explosives(bundle)
                        | (is_adult(bundle) & Has("Giant's Knife"))
                    )
                    require_native_fork(location, physical)
                # Falling icicles/stalactites are trigger checks once the room
                # itself is reachable, so no invented weapon gate is added.
            elif family == "red_ice":
                red_ice_rule = blue_fire(bundle)
                if fork_loc.rc.upper() == "RC_ZD_KING_ZORA_RED_ICE":
                    red_ice_rule &= is_adult(bundle)
                require_native_fork(location, red_ice_rule)
            elif family == "butterfly_fairy":
                # HC butterfly checks are physically beyond the climbable castle
                # approach.  They also require the normal butterfly interaction
                # (Deku Stick); the individual Butterfly Soul gate is layered
                # below by require_animal().
                butterfly_rule = can_use(Items.STICKS, bundle)
                if fork_loc.rc.upper().startswith("RC_HC_"):
                    butterfly_rule &= climb_rule()
                require_native_fork(location, butterfly_rule)
            elif family == "wonder":
                rc = fork_loc.rc.upper()
                rule = None
                water_access = swim_rule() | can_use(Items.IRON_BOOTS, bundle)

                if rc.startswith("RC_COLOSSUS_WONDER_GF_TREE_") or rc in {
                        "RC_COLOSSUS_WONDER_OASIS_TREE_1", "RC_COLOSSUS_WONDER_OASIS_TREE_2"}:
                    rule = ((is_adult(bundle) & can_use(Items.FAIRY_BOW, bundle))
                            | (is_child(bundle) & can_use(Items.FAIRY_SLINGSHOT, bundle)))
                elif rc == "RC_COLOSSUS_WONDER_OASIS_CHILD_TREE":
                    rule = is_child(bundle) & can_use(Items.FAIRY_SLINGSHOT, bundle)
                elif rc == "RC_DMC_WONDER_BENEATH_BRIDGE_PLATFORM":
                    rule = is_adult(bundle) & can_use_any([Items.LONGSHOT, Items.HOVER_BOOTS], bundle)
                elif rc in {"RC_GERUDO_TRAINING_GROUND_WONDER_BEAMOS_ROOM",
                            "RC_GERUDO_TRAINING_GROUND_WONDER_TORCH_SLUGS_ROOM"}:
                    rule = can_use(Items.FAIRY_BOW, bundle)
                elif rc == "RC_GERUDO_TRAINING_GROUND_WONDER_EYE_STATUE_ROOM":
                    rule = can_use(Items.HOVER_BOOTS, bundle) | Has("Bunny Hood")
                elif rc in {"RC_GF_WONDER_ARCHERY_SIGN", "RC_GF_WONDER_ENTRANCE_SIGN"}:
                    rule = can_use(Items.HOOKSHOT, bundle)
                elif rc == "RC_GV_WONDER_LOWER_WATERFALL":
                    # Native also permits the planted-bean and void-collection
                    # routes. The scale/iron routes are the always-modelled AP
                    # alternatives and are safe for progression certification.
                    rule = is_adult(bundle) & water_access
                elif rc == "RC_GV_WONDER_UPPER_WATERFALL":
                    # Physical waterfall access still requires the shuffled
                    # Climb ability even after Swim is unlocked. Do not let
                    # AP certify progression here from Bronze Scale alone.
                    rule = is_adult(bundle) & climb_rule() & water_access
                elif rc in {"RC_HC_WONDER_COURTYARD_LEFT_WINDOW", "RC_HC_WONDER_COURTYARD_RIGHT_WINDOW"}:
                    rule = can_use(Items.FAIRY_SLINGSHOT, bundle)
                elif rc in {"RC_HC_WONDER_LEFT_TORCH", "RC_HC_WONDER_RIGHT_TORCH"}:
                    rule = can_use(Items.FAIRY_SLINGSHOT, bundle) & (
                        swim_rule() | can_use(Items.BOOMERANG, bundle))
                elif rc.startswith("RC_HC_WONDER_MOAT_"):
                    # Every HC moat Wonder is beyond the shuffled Climb gate.
                    # Swim/Iron Boots only handle the water portion; they never
                    # substitute for Climb for these ten checks.
                    rule = climb_rule() & water_access
                elif rc.startswith("RC_HF_WONDER_BRIDGE_"):
                    rule = is_child(bundle)
                elif rc == "RC_KAK_WONDER_UNDER_CONSTRUCTION":
                    # The hidden construction-area Wonder/rupee is physically
                    # reachable as child without Roc's Feather. The previous AP
                    # projection copied an obsolete jump helper and hid a real
                    # check from generation/Check Finder until Ice Cavern.
                    rule = is_child(bundle)
                elif rc.startswith("RC_KF_WONDER_CRAWL_GRASS_") or rc.startswith("RC_KF_WONDER_PLATFORMS_") or rc.startswith("RC_KF_WONDER_TRAINING_"):
                    rule = is_child(bundle)
                elif rc == "RC_KF_WONDER_SIGN":
                    rule = is_child(bundle) & can_jump_slash_except_hammer(bundle)
                elif rc in {"RC_LLR_WONDER_BIG_FENCE", "RC_LLR_WONDER_SMALL_FENCE"}:
                    rule = (is_adult(bundle) & can_use(Items.EPONAS_SONG, bundle) &
                            (has_item(Items.CHILD_WALLET, bundle) | has_item(Events.FREED_EPONA, bundle)))
                elif rc.startswith("RC_GY_WONDER_DAMPE_RACE_"):
                    # Every Dampe-race Wonder is physically inside Dampe's race
                    # tunnel and therefore inherits the same actor/talk gate as
                    # the native CanTalkToDampe() helper. Broad Graveyard parent
                    # reachability alone is not enough.
                    rule = True_()
                    if o.shuffle_npc_soul.value:
                        rule &= Has("NPC Soul")
                    if o.shuffle_speak.value == 1:
                        rule &= Has("Speak")
                    elif o.shuffle_speak.value == 2:
                        rule &= Has("Speak Hylian")
                elif rc.startswith("RC_LW_WONDER_") and "SKULL_KIDS_GRASS" in rc:
                    rule = is_child(bundle)
                elif rc.startswith("RC_MKT_WONDER_DAY_"):
                    rule = is_child(bundle)
                    if o.shuffle_flow_of_time.value and o.frozen_starting_time.value in (3, 4):
                        rule &= Has("Flow of Time")
                elif rc.startswith("RC_MKT_WONDER_NIGHT_"):
                    rule = is_child(bundle)
                    if o.shuffle_flow_of_time.value and o.frozen_starting_time.value in (1, 2):
                        rule &= Has("Flow of Time")
                elif rc == "RC_SHADOW_TEMPLE_WONDER_THREE_POTS":
                    rule = can_use(Items.FAIRY_BOW, bundle)
                elif rc.startswith("RC_TH_WONDER_") and rc != "RC_TH_WONDER_KITCHEN_SOUP":
                    rule = can_use(Items.FAIRY_BOW, bundle)
                elif rc == "RC_TH_WONDER_KITCHEN_SOUP":
                    # Native normal route:
                    # (TakeDamage OR Adult OR Goron Tunic) AND CanPass Gerudo Guard.
                    # With tricks/glitches off, Adult is the stable normal branch;
                    # native CanPass Gerudo Guard accepts card, Bow, or Hookshot.
                    guard_pass = (
                        Has("Gerudo Membership Card")
                        | can_use(Items.FAIRY_BOW, bundle)
                        | can_use(Items.HOOKSHOT, bundle)
                    )
                    rule = is_adult(bundle) & guard_pass
                elif rc == "RC_ZF_WONDER_ROCK":
                    rule = is_adult(bundle) & has_item(Items.SCARECROW, bundle)
                elif rc.startswith("RC_ZR_WONDER_"):
                    # Exact child-only Zora River Wonder topology. Broad region
                    # reachability is not enough: several Wonder actors disappear
                    # as Adult and some are physically above the ladder / on the
                    # Cucco pillar route. Keep the same route split as native C++.
                    #
                    # Upper-child entry can be reached by either:
                    #   A) Silver Scale/deep-dive access. With Shuffle Swim on,
                    #      the first physical Progressive Scale also grants virtual
                    #      Swim while remaining counted as physical tier #1;
                    #   B) Rock/Boulder Soul + Bomb Bag/Bombchu; or
                    #   C) Rock/Boulder Soul + EXTREME Grab.
                    deep_dive_route = deep_swim_route()
                    rock_break_route = Has("Progressive Bomb Bag") | Has("Bombchu Bag") | grab_rule()
                    if o.shuffle_rock_boulder_soul.value:
                        rock_break_route &= Has("Rock / Boulder Soul")
                    upper_child_route = deep_dive_route | rock_break_route

                    if rc.startswith("RC_ZR_WONDER_LOWER_RIVER_"):
                        # Lower river wonders are underwater triggers in RR_ZR_FRONT.
                        rule = is_child(bundle) & water_access
                    elif (rc.startswith("RC_ZR_WONDER_AFTER_LADDER_")
                          or rc.startswith("RC_ZR_WONDER_NEAR_DOMAIN_")):
                        # Above-ladder wonders inherit the upper-child entry AND
                        # the physical ladder path. Climb is innate if its shuffle
                        # is off; when shuffled it must be owned.
                        atop_route = climb_rule() & (
                            deep_swim_route()
                            | can_use(Items.HOVER_BOOTS, bundle)
                            | (grab_rule() & animal_rule("Cucco"))
                        )
                        rule = is_child(bundle) & upper_child_route & atop_route
                    elif rc.startswith("RC_ZR_WONDER_PILLARS_"):
                        # Pillar wonders are reached as Child by the Cucco+Grab
                        # route (or Hover Boots). Adult-only trick routes do not
                        # count because the Wonder actors are not present as Adult.
                        pillar_route = can_use(Items.HOVER_BOOTS, bundle) | (grab_rule() & animal_rule("Cucco"))
                        rule = is_child(bundle) & upper_child_route & pillar_route
                    else:
                        # Before ladder, Frog Bridge, lower land bridge and near-
                        # Cucco wonders live in the upper child section itself.
                        rule = is_child(bundle) & upper_child_route
                # Dampe race wonders are inside the race tunnel. Their
                # NPC/Speak gates are installed explicitly below.

                if rule is not None:
                    require_native_fork(location, rule)

            # 0.11.17: source-linked local requirements. Reaching the broad
            # parent is not sufficient to lift a pillar, reach an upper rupee,
            # sell the requested contents, or buy the Chest Game key.
            if fork_loc.rc == "RC_GANONS_GANONS_CASTLE_UNDER_PILLAR_FIRE_SILVER":
                require_native_fork(location, can_use(Items.GOLDEN_GAUNTLETS, bundle)
                                    & fire_timer_at_least(bundle, 24))
            elif fork_loc.rc == "RC_GTG_UPPER_LAVA_SILVER":
                require_native_fork(location, can_use(Items.HOOKSHOT, bundle))
            elif fork_loc.rc == "RC_ZF_UNDERGROUND_BOULDER":
                require_native_fork(location, can_use(Items.SILVER_GAUNTLETS, bundle)
                                    & blast_or_smash(bundle))
            elif fork_loc.rc == "RC_MARKET_TREASURE_CHEST_GAME_SHOPKEEPER":
                require_native_fork(location, has_item(Items.CHILD_WALLET, bundle))
            elif family == "beggar":
                # CanUse filled bottles checks both a bottle and a usable
                # contents source. An empty bottle cannot be sold as a fish.
                contents = {
                    "BLUE_FIRE": Items.BOTTLE_WITH_BLUE_FIRE,
                    "BUGS": Items.BOTTLE_WITH_BUGS,
                    "FISH": Items.BOTTLE_WITH_FISH,
                }
                for suffix, item in contents.items():
                    if fork_loc.rc.endswith("_BEGGAR_" + suffix):
                        require_native_fork(location, can_use(item, bundle))
                        break

            if o.shuffle_rock_boulder_soul.value and family in ("rock", "boulder"):
                require(location, "Rock / Boulder Soul")
            if o.shuffle_grass_bush_soul.value and family == "bush":
                require(location, "Grass / Bush Soul")
            if o.shuffle_sign_soul.value and family == "sign":
                require(location, "Sign Soul")
            if o.shuffle_animal_soul.value and family == "butterfly_fairy":
                require_animal(location)

            # These checks are driven by NPC interaction in the native fork.
            if family in ("beggar", "chest_minigame"):
                if o.shuffle_npc_soul.value:
                    require(location, "NPC Soul")
                if o.shuffle_speak.value:
                    require_speak(location)

            # Treasure Chest Game randomized rewards are still chest opens.
            if family == "chest_minigame" and o.shuffle_open_chest.value:
                require(location, "Open Chest")

        # Fork-native checks currently have no stock SoH rule attached.  Add the
        # time gate that the fork itself enforces for night-only Wonder Items.
        # In SOH-EXTREME, time is frozen until Flow of Time is collected, so these
        # locations must not appear in logic while Flow of Time is missing.
        if o.shuffle_flow_of_time.value:
            # Stock SoH models changing time through synthetic "Day Night Cycle"
            # event locations. Gate those events behind Flow of Time so all stock
            # night/day logic also stays frozen until the item is collected.
            for location in self.get_locations():
                if "Day Night Cycle" in location.name:
                    require(location, 'Flow of Time')

            # The Hyrule Field -> Market Entrance edge owns the child drawbridge
            # requirement. Do not lock every Market check behind Flow: an adult
            # route or a child already inside a night Market remains legitimate.

            # Conversely, a frozen DAWN/DAY start must not satisfy explicitly
            # night-only checks until time is unlocked.  The stock day/night-cycle
            # events cover most of these; these name fallbacks cover fork/native
            # checks that bypass those helper events.
            if o.frozen_starting_time.value in (1, 2):
                for location in self.get_locations():
                    upper = location.name.upper()
                    if " NIGHT " in f" {upper} " or "NIGHT BALCONY" in upper:
                        require(location, 'Flow of Time')

        import re

        for location in self.get_locations():
            if location.name.startswith(("Enemy Defeat:", "EXTREME Native Event", "EXTREME Native Action", "EXTREME Native RR_")):
                continue  # Explicit actor/action rules; never classify by room names.
            data = location_data_table.get(location.name)
            tags = data.tags if data is not None and data.tags is not None else LocTag(0)
            upper_name = location.name.upper()

            # The stock AP world does not tag every concrete physical check the same
            # way the native SOH-EXTREME logic does. Keep LocTags as the primary
            # source, then use conservative object-name fallbacks for checks which
            # are unmistakably the actual object (rather than merely being near it).
            is_named_chest = "CHEST" in upper_name
            # Pot Soul is a universal physical gate: if the check is a pot in the
            # native game, it cannot be collected before Pot Soul. Do not rely solely
            # on official SoH LocTags because some sanity/location tables omit them.
            is_named_pot = (not upper_name.startswith("EXTREME ") and
                            re.search(r"\bPOTS?\b", upper_name) is not None)
            is_named_crate = re.search(r"(^|\s)(?:SMALL\s+)?CRATE(?:\s|$|\d)", upper_name) is not None
            is_named_grass = (
                re.search(r"GRASS\s+\d+$", upper_name) is not None
                or re.search(r"GRASS\s+MAZE\s+\d+$", upper_name) is not None
            )
            is_named_bush = re.search(r"BUSH\s+\d+$", upper_name) is not None
            is_named_beehive = "BEEHIVE" in upper_name
            is_named_sign = "SIGN" in upper_name
            is_named_skull = (" SKULLTULA" in upper_name or " GS " in f" {upper_name} ")

            # Stock Archipelago-SoH metadata does not reliably survive into the
            # EXTREME world's included_locations table for every inherited check.
            # The native fork makes these checks real NPC interactions (and its
            # location_access rules explicitly require one of RG_SPEAK_*), while
            # NPC Soul physically removes the owning actors.  Use conservative
            # name fallbacks for unmistakable shop/merchant/scrub/minigame checks
            # so generation cannot put foundational progression behind an NPC
            # that Link cannot yet speak to / that does not yet exist.
            is_named_npc_interaction = (
                re.search(r"\bSHOP ITEM \d+$", upper_name) is not None
                or re.search(r"\bBAZAAR ITEM \d+$", upper_name) is not None
                or "MEDIGORON" in upper_name
                or "CARPET SALESMAN" in upper_name
                or "BEAN SALESMAN" in upper_name
                or "SHOOTING GALLERY" in upper_name
                or "BOMBCHU BOWLING" in upper_name
                or "HORSEBACK ARCHERY" in upper_name
                or "TREASURE CHEST GAME" in upper_name
                or re.search(r"\b(?:10|20|30|40|50|100) GOLD SKULLTULA REWARD$", upper_name) is not None
            )
            # Avoid treating every "Deku Tree ..." dungeon location as a TreeSanity
            # object. These patterns name a literal overworld tree actor.
            is_named_tree = (
                re.search(r"(^|\s)TREE(?:\s+IN|\s+NEAR|\s+BY|\s+WITH|\s+AT|\s+\d|$)", upper_name) is not None
                and not upper_name.startswith("DEKU TREE ")
            )

            # Chest-opening ability is a hard gameplay gate in the fork. Name
            # fallback catches Mido's house and other stock checks missed by tags.
            if o.shuffle_open_chest.value and ((tags & LocTag.Chest) or is_named_chest):
                normalized_chest_name = location.name.upper().replace("'", "").replace("-", " ")
                is_large_chest = any(
                    normalized_chest_name == native_name or normalized_chest_name.endswith(" " + native_name)
                    for native_name in large_chest_names
                )
                count = 2 if o.shuffle_open_chest.value == 2 and is_large_chest else 1
                require(location, 'Open Chest', count)

            # Supplement the source-aware helper with native close-pot methods
            # for inherited locations which did not call it directly. Rebuild
            # the fork's default close-pot interaction exactly enough to preserve
            # all valid OR routes: Grab, swords/sticks, hammer, bombs/Bombchus,
            # boomerang, hookshot/longshot, slingshot and bow. can_hit_at_range
            # supplies age/progressive/ammo rules; Boomerang and Giant's Knife are
            # the two native alternatives not represented by that helper.
            is_pot_check = bool((tags & LocTag.Pot) or is_named_pot)
            if is_pot_check:
                bundle = native_bundle_for_location(location)
                if bundle is not None:
                    # Bombs/Bombchus are disabled in these residential interiors.
                    # Do not let a generic "has explosives" route make their pots
                    # appear reachable.  The remaining methods mirror native close
                    # pot interactions: Grab/lift, jumpslash/hammer/sticks, boomerang,
                    # hook/longshot, slingshot, bow, and the adult Giant's Knife.
                    indoor_no_explosive_pot = (
                        upper_name == "KF LINKS HOUSE POT"
                        or upper_name.startswith("KF TWINS HOUSE POT ")
                        or upper_name.startswith("KF BROTHERS HOUSE POT ")
                        or upper_name.startswith("MARKET GUARD HOUSE CHILD POT ")
                        or upper_name.startswith("MARKET GUARD HOUSE ADULT POT ")
                        or upper_name.startswith("MARKET BACK ALLEY HOUSE POT ")
                        or upper_name.startswith("LLR TALONS HOUSE POT ")
                    )
                    if indoor_no_explosive_pot:
                        pot_physical = (
                            can_jump_slash(bundle)
                            | can_use_any([Items.BOOMERANG, Items.HOOKSHOT, Items.LONGSHOT,
                                           Items.FAIRY_SLINGSHOT, Items.FAIRY_BOW], bundle)
                            | grab_rule()
                            | (is_adult(bundle) & Has("Giant's Knife"))
                        )
                    else:
                        pot_physical = (
                            can_hit_at_range(bundle, EnemyDistance.CLOSE, True, False)
                            | can_use(Items.BOOMERANG, bundle)
                            | grab_rule()
                            | (is_adult(bundle) & Has("Giant's Knife"))
                        )
                    require_native_existing(location, pot_physical)
                if o.shuffle_pot_soul.value:
                    require(location, 'Pot Soul')

            # Crate Soul only unlocks the crate; it never counts as a breaking
            # method by itself. Mirror the native physical interaction.
            #
            # Large/fixed crates:
            #   Roll OR explosives OR Megaton Hammer
            #
            # Small crates:
            #   Roll OR jumpslash OR explosives OR Grab/lift
            #
            # If Shuffle Roll is disabled, Roll is innate and already provides
            # a valid break route.
            is_crate_check = bool((tags & LocTag.Crate) or is_named_crate)
            if is_crate_check:
                bundle = native_bundle_for_location(location)

                if o.shuffle_roll.value:
                    crate_roll = Has("Roll")
                else:
                    crate_roll = True_()

                if bundle is not None:
                    if "SMALL CRATE" in upper_name:
                        crate_physical = (
                            crate_roll
                            | can_jump_slash(bundle)
                            | has_explosives(bundle)
                            | grab_rule()
                        )
                    else:
                        crate_physical = (
                            crate_roll
                            | has_explosives(bundle)
                            | can_use(Items.MEGATON_HAMMER, bundle)
                        )
                    require_native_existing(location, crate_physical)
                elif o.shuffle_roll.value:
                    # Fail closed for an unmapped region instead of treating
                    # Crate Soul alone as a complete interaction.
                    require_native_existing(location, Has("Roll"))

            if o.shuffle_crate_soul.value and is_crate_check:
                require(location, 'Crate Soul')
            if o.shuffle_grass_bush_soul.value and ((tags & grass_tags) or is_named_grass or is_named_bush):
                require(location, 'Grass / Bush Soul')

            # Grass checks are collectable either by lifting with EXTREME Grab
            # OR by using a normal shrub-breaking method (sword/stick, bombs,
            # Bombchus, boomerang, etc.). Do not require Grab as a hard AND gate:
            # that disagrees with the runtime and can create fake deadlocks when
            # Bombs are the intended route. Grass/Bush Soul remains an independent
            # existence gate above.
            if (tags & grass_tags) or is_named_grass:
                bundle = native_bundle_for_location(location)
                if bundle is not None:
                    require_native_existing(location, can_cut_shrubs(bundle) | grab_rule())
            is_tree_check = bool((tags & LocTag.Tree) or is_named_tree)
            if o.shuffle_tree_soul.value and is_tree_check:
                require(location, 'Tree Soul')
            if o.shuffle_roll.value and is_tree_check:
                require(location, 'Roll')
            # Every Hyrule Castle tree is physically beyond/within the castle
            # climb route in SOH-EXTREME.  Tree Soul + Roll remain independent
            # bonk requirements above; Climb is an additional access gate.
            if o.shuffle_climb.value and is_tree_check and upper_name.startswith("HC "):
                require(location, 'Climb')
            if upper_name == "HC BUTTERFLY FAIRY":
                # Stock helper event backing Hyrule Castle's butterfly fairy
                # access must obey the same physical gates as the shuffled
                # butterfly checks themselves.
                require_native_existing(location, climb_rule())
                require_animal(location, "Butterfly Soul")
                bundle = native_bundle_for_location(location)
                if bundle is not None:
                    require_native_existing(location, can_use(Items.STICKS, bundle))

            if o.shuffle_beehive_soul.value and ((tags & LocTag.Bee_Hive) or is_named_beehive):
                require(location, 'Beehive Soul')
            if o.shuffle_sign_soul.value and is_named_sign:
                require(location, 'Sign Soul')

            # Physical ledge audit from SOH-EXTREME runtime. These actors are
            # placed on ledges/raised terrain that cannot be reached by the
            # normal child route when Climb is shuffled. Keep this on the
            # concrete checks rather than the broad parent region so unrelated
            # Hyrule Field / Castle Grounds checks do not inherit it.
            explicit_climb_checks = {
                "EXTREME HC BOULDER",
                "EXTREME HC DEAD END RECTANGLE SIGN",
                "EXTREME HF CENTER EXIT ARROW SIGN",
            }
            if upper_name in explicit_climb_checks and o.shuffle_climb.value:
                require(location, 'Climb')
            if (tags & LocTag.Gold_Skulltula) or is_named_skull:
                # Soul existence and the location's actual time-of-day route
                # are separate. No universal Flow gate for indoor/daytime GS.
                if o.shuffle_skulltula_soul.value:
                    require(location, 'Skulltula Soul')

                # GC GS Boulder Maze is physically inside a crate behind the
                # boulder maze.  Do not let stock BlastOrSmash/region reachability
                # skip any part of the real interaction chain.
                if getattr(location, "address", None) == 509:
                    if o.shuffle_rock_boulder_soul.value:
                        require(location, 'Rock / Boulder Soul')
                    require_native_existing(location, Has("Progressive Bomb Bag") | Has("Bombchu Bag"))
                    if o.shuffle_crate_soul.value:
                        require(location, 'Crate Soul')
            # SOH-EXTREME: every check physically inside the Goron City boulder
            # maze inherits the maze entrance gate. Native OoT logic can otherwise
            # expose the Center/Right chests simply from Open Chest + BlastOrSmash
            # even while Rock/Boulder Soul is missing.
            if upper_name.startswith("GC MAZE ") or upper_name.startswith("EXTREME GC MAZE "):
                if o.shuffle_rock_boulder_soul.value:
                    require(location, 'Rock / Boulder Soul')
                # Entering the maze needs an actual boulder-breaking method. Keep
                # this broad enough for the native legal methods; more restrictive
                # sub-check rules (silver/bronze boulders, crate, etc.) still stack.
                require_native_existing(
                    location,
                    Has("Progressive Bomb Bag") | Has("Bombchu Bag") | grab_rule()
                )

            if o.shuffle_animal_soul.value and (tags & animal_tags):
                require_animal(location)

            # Business scrubs are their own soul class in SOH-EXTREME.
            if o.shuffle_business_scrub_soul.value and (tags & LocTag.Scrub):
                require(location, 'Scrub Soul')

            # Every native Business Scrub interaction explicitly requires
            # RG_SPEAK_DEKU. LocTag.Scrub is intentionally separate from generic
            # NPC tags, so install the exact language gate here instead of relying
            # on area/name guessing.
            if o.shuffle_speak.value and (tags & LocTag.Scrub):
                require_language(location, "Deku")
            if o.shuffle_npc_soul.value and (tags & LocTag.Scrub):
                require(location, "NPC Soul")

            # The single AP Speak item grants every native Speak_* flag.  Native
            # speak checks also require NPC Soul when that option is active.
            if o.shuffle_speak.value and ((tags & npc_tags) or is_named_npc_interaction):
                require_speak(location)
            if o.shuffle_npc_soul.value and ((tags & npc_tags) or is_named_npc_interaction):
                require(location, 'NPC Soul')

        # 0.7.6 uses the boolean-preserving native C++ overlay above instead of
        # hand-maintained entrance-name tables.

        # SOH-EXTREME: the adult rolling Goron reward is backed by the native
        # LOGIC_GORON_CITY_STOP_ROLLING_GORON_AS_ADULT event rather than carrying
        # NPC tags directly on the randomized location.  Stock SoH already owns
        # the age/stopping-method portion of the check, but the EXTREME event also
        # requires the Goron actor to exist and Link to be able to speak to Gorons.
        # Without this explicit event->location projection Universal Tracker can
        # incorrectly list GC Rolling Goron as Adult while NPC Soul / Speak Goron
        # are still missing.
        try:
            rolling_goron_adult = self.get_location("GC Rolling Goron as Adult")
        except Exception:
            rolling_goron_adult = None
        if rolling_goron_adult is not None:
            if o.shuffle_npc_soul.value:
                require(rolling_goron_adult, "NPC Soul")
            if o.shuffle_speak.value:
                require_speak(rolling_goron_adult)

        # Stock AP also models some progression interactions as event locations
        # which are not covered by NPC LocTags. In Closed Forest, Mido is a real
        # actor interaction, so Speak/NPC Soul must gate the event that opens the
        # Deku Tree / forest progression route.
        for event_name in ("Mido", "Mido From Outside Deku Tree"):
            try:
                event_location = self.get_location(event_name)
            except Exception:
                continue
            if o.shuffle_speak.value:
                require_speak(event_location)
            if o.shuffle_npc_soul.value:
                require(event_location, "NPC Soul")

        # Song from Saria is an inherited stock location whose native metadata
        # does not always carry NPC tags into the standalone EXTREME world.
        # Saria must physically exist, and the interaction uses Kokiri speech.
        try:
            saria_song = self.get_location("Song from Saria")
        except Exception:
            saria_song = None
        if saria_song is not None:
            if o.shuffle_npc_soul.value:
                require(saria_song, "NPC Soul")
            if o.shuffle_speak.value == 1:
                require(saria_song, "Speak")
            elif o.shuffle_speak.value == 2:
                require(saria_song, "Speak Kokiri")

        # Stock SoH also exposes progression *event* locations which represent
        # physical actors/interactions rather than normal randomized checks.
        # Those inherited events must obey SOH-EXTREME's existence Souls too.
        #
        # Without these gates AP can create circular playthroughs such as:
        #   Bombchus -> GC Woods Warp From Woods -> ... -> Rock Soul
        # even though the bombable shortcut rock does not exist before Rock Soul.
        stock_event_soul_requirements = {}

        if o.shuffle_rock_boulder_soul.value:
            stock_event_soul_requirements.update({
                # The Lost Woods <-> Goron City shortcut event is set by removing
                # the bombable obstruction.  If rocks/boulders are absent, the
                # interaction that sets the event cannot happen.
                "GC Woods Warp From Woods": ("Rock / Boulder Soul",),
                "GC Woods Warp": ("Rock / Boulder Soul",),
            })

        # NPC Speech Sanity locations are real talk interactions. Region reachability
        # supplies spatial/age/entrance logic; shuffled Speak and NPC Soul stack.
        # IMPORTANT: this block must live after require() is defined.
        if self.options.npc_speech_sanity.value:
            for speech in SPEECH_LOCATIONS:
                name = f"NPC Speech: {speech.rc[3:].replace('_', ' ').title()}"
                try:
                    location = self.get_location(name)
                except Exception:
                    continue
                if self.options.shuffle_speak.value:
                    require_speak(location)
                if self.options.shuffle_npc_soul.value:
                    require(location, "NPC Soul")

            # Generic flavor-NPC capacity slots are intentionally absent from the
            # AP location table in 0.8.11.  Only exact mapped first-talk checks are
            # legal generation locations.  This prevents fake capacity IDs from
            # poisoning Full accessibility and progression validation.
            flavor_region_rules = [
                CanReachRegion(region_name)
                for region_name in sorted(
                    getattr(self, "_exact_speech_region_names", set())
                )
            ]
            flavor_world_rule = True_()
            for region_rule in flavor_region_rules:
                flavor_world_rule = flavor_world_rule & region_rule

            for name in NPC_SPEECH_FALLBACK_NAME_TO_ID:
                try:
                    location = self.get_location(name)
                except Exception:
                    continue

                if self.options.shuffle_npc_soul.value:
                    require(location, "NPC Soul")

                if self.options.shuffle_speak.value == 1:
                    require(location, "Speak")
                elif self.options.shuffle_speak.value == 2:
                    for language in ("Deku", "Gerudo", "Goron", "Hylian", "Kokiri", "Zora"):
                        require(location, f"Speak {language}")

                if self.options.shuffle_flow_of_time.value:
                    require(location, "Flow of Time")

                require_native_existing(location, flavor_world_rule)

        # Apply source-aware gates to stock resource/helper events. These are
        # progression events in the inherited SoH world and therefore can appear
        # in Archipelago playthrough spheres even though they are not ordinary
        # shuffled locations.
        for event_location in self.get_locations():
            upper_event = event_location.name.upper()

            # Fish/insects are Animal Soul actors.  This includes stock helper
            # events such as "ZD Fish Group -> Can Access Fish".
            if o.shuffle_animal_soul.value:
                if (
                    "FISH GROUP" in upper_event
                    or upper_event.endswith(" PUDDLE FISH")
                    or upper_event.endswith(" GROTTO FISH")
                    or upper_event.endswith(" POND FISH")
                    or upper_event.endswith(" WANDERING BUGS")
                    or upper_event.endswith(" BUGS")
                    or "BUG ROCK" in upper_event
                    or "BUG GRASS" in upper_event
                    or "BUG SHRUB" in upper_event
                ):
                    require_animal(event_location)

            # Bug rocks/grass additionally need the object that releases them to
            # exist in the scene.
            if o.shuffle_rock_boulder_soul.value and "BUG ROCK" in upper_event:
                require(event_location, "Rock / Boulder Soul")
            if o.shuffle_grass_bush_soul.value and (
                "BUG GRASS" in upper_event or "BUG SHRUB" in upper_event
            ):
                require(event_location, "Grass / Bush Soul")

            # Stock "Can Farm Sticks/Nuts" events inherit the physical source.
            # Deku Babas are enemies; stick/nut pots are pots.
            if "BABA" in upper_event and (
                upper_event.endswith(" STICKS") or upper_event.endswith(" NUTS")
            ):
                if o.shuffle_enemy_soul.value == 1:
                    require(event_location, "Enemy Soul")
                elif o.shuffle_enemy_soul.value == 2:
                    require(event_location, "Deku Baba Soul")
            if "POT" in upper_event and (
                upper_event.endswith(" STICKS") or upper_event.endswith(" NUTS")
            ):
                if o.shuffle_pot_soul.value:
                    require(event_location, "Pot Soul")

        for event_name, requirements in stock_event_soul_requirements.items():
            try:
                stock_event = self.get_location(event_name)
            except Exception:
                continue
            for requirement in requirements:
                require(stock_event, requirement)

        # Animal Soul is an existence gate.  Stock AP's LocTags do not cover every
        # concrete actor-backed check, so explicitly gate every stock check whose
        # physical cow/cucco/frog/fish/horse actor disappears in SOH-EXTREME.
        #
        # Important: these are not "reward-only" gates.  Without Animal Soul the
        # actor itself is not in the scene, so any route that needs that actor must
        # be impossible in generation as well.
        if o.shuffle_animal_soul.value:
            animal_actor_locations = (
                # Frogs
                'ZR Frogs Ocarina Game',
                'ZR Frogs in the Rain',
                "ZR Frogs Zelda's Lullaby",
                "ZR Frogs Epona's Song",
                "ZR Frogs Saria's Song",
                "ZR Frogs Sun's Song",
                'ZR Frogs Song of Time',

                # Cucco/chicken checks
                "LLR Talons Chickens",
                'Kak Anju as Child',

                # Direct cow checks from the native fork
                'LLR Stables Left Cow',
                'LLR Stables Right Cow',
                'LLR Tower Left Cow',
                'LLR Tower Right Cow',
                "KF Link's House Cow",
                'HF Cow Grotto Cow',
                'DMT Cow Grotto Cow',
                "Kak Impas House Cow",
                'GV Cow',
                'Jabu Jabus Belly MQ Cow',

                # Horse/Epona-backed progression.  The horse actor also vanishes
                # without Animal Soul, even if stock AP has already set Freed Epona.
                'LLR Talon Race',
                'LLR Time Trial',
                'HF Big Poe',
                'GF HBA 1000 Points',
                'GF HBA 1500 Points',
            )
            for animal_location in animal_actor_locations:
                try:
                    require_animal(self.get_location(animal_location))
                except Exception:
                    pass

            # Some stock fish checks are not consistently tagged by the inherited
            # SoH world.  Name fallbacks are limited to checks that are unmistakably
            # the actual fish/fishing actor, not merely locations inside a "Cow
            # Grotto" or other animal-named region.
            for location in self.get_locations():
                upper = location.name.upper()
                direct_fish = (
                    re.search(r'\bPOND FISH(?:\s+\d+)?$', upper) is not None
                    or upper.endswith(' GROTTO FISH')
                    or upper.endswith(' PUDDLE FISH')
                    or upper in ('LH CHILD FISHING', 'LH ADULT FISHING')
                )
                direct_cow = upper.endswith(' COW')
                direct_frog = upper.startswith('ZR FROGS ')
                if direct_fish or direct_cow or direct_frog:
                    require_animal(location)

        # The Near Domain PoH has multiple physical collection routes in the fork.
        # Child's normal route is the cucco route (Grab + Animal Soul when those
        # systems are shuffled), while Boomerang/Hovers bypass the cucco.
        cucco_group = []
        if o.shuffle_grab.value:
            cucco_group.append(('Grab / Power Bracelet', 1))
        if o.shuffle_animal_soul.value:
            cucco_group.append((('Animal Soul' if o.shuffle_animal_soul.value == 1 else 'Cucco Soul'), 1))
        if cucco_group:
            require_alternatives('ZR Near Domain Freestanding PoH', (
                tuple(cucco_group),
                (('Boomerang', 1),),
                (('Hover Boots', 1),),
            ))

        # Region-access sanity for stock freestanding PoHs whose inherited
        # logic treats child Grab as sufficient. In SOH-EXTREME those child routes
        # physically use a Cucco, so Animal Soul must exist when that route is used.
        # Existing stock rules remain ANDed, so these only remove false positives.
        for location_name, route_builder in (
            # Upper Stream is a broad AP parent, not the waterfall alcove.
            # Reaching the stream (including surviving a fall) does not reach
            # this pickup. Keep the two complete physical routes separate:
            # child Cucco + Grab, OR Climb + surface Swim at either age.
            # In particular, neither adult age nor Swim alone is a bypass.
            ('GV Waterfall Freestanding PoH', lambda b: (
                (is_child(b) & grab_rule() & animal_rule('Cucco'))
                | (climb_rule() & swim_rule())
            )),
            ('ZR Near Open Grotto Freestanding PoH', lambda b: (
                (is_child(b) & grab_rule() & animal_rule('Cucco'))
                | can_use(Items.HOVER_BOOTS, b)
                | (is_adult(b) & can_do_trick(Tricks.ZR_LOWER, b))
            )),
            ('Kak Impas House Freestanding PoH', lambda b: (
                is_adult(b)
                | can_use(Items.HOOKSHOT, b)
                | (is_child(b) & grab_rule() & animal_rule('Cucco'))
            )),
        ):
            try:
                loc = self.get_location(location_name)
            except Exception:
                continue
            bundle = native_bundle_for_location(loc)
            if bundle is not None:
                require_native_existing(loc, route_builder(bundle))

        # SOH-EXTREME physical audit: the Deku Tree lobby lower heart is
        # on the 2F ledge.  The inherited/native 1F Boomerang rule is a false
        # positive in actual gameplay; Boomerang cannot reach it from below.
        # A real route to the ledge is Climb (when shuffled) or Hookshot.
        try:
            lower_heart = self.get_location('Deku Tree Lobby Lower Heart')
            bundle = native_bundle_for_location(lower_heart)
            if bundle is not None:
                require_native_existing(lower_heart, climb_rule() | can_use(Items.HOOKSHOT, bundle))
        except Exception:
            pass

        # 0.10.8 GRAVEYARD BEAN-PLATFORM CRATE ROUTE
        # The Freestanding PoH crate is on the adult bean platform. The intended
        # bean route requires the Graveyard-specific Bean Soul; Longshot remains
        # the legitimate alternate access route. Generic crate handling below
        # separately requires Crate Soul and a real break method.
        try:
            gy_crate = self.get_location("Graveyard Freestanding PoH Crate")
            gy_bundle = native_bundle_for_location(gy_crate)
            if gy_bundle is not None:
                bean_route = is_adult(gy_bundle) & Has("Graveyard Bean Soul")
                longshot_route = can_use(Items.LONGSHOT, gy_bundle)
                require_native_existing(gy_crate, bean_route | longshot_route)
            else:
                require_native_existing(gy_crate, Has("Graveyard Bean Soul"))
        except Exception:
            pass

        # These stock checks use cucco handling directly in the native fork.
        # Apply the shuffled interaction abilities as hard requirements there too.
        explicit_interactions = {
            "LLR Talons Chickens": (
                ('Grab / Power Bracelet', bool(o.shuffle_grab.value)),
                ('Animal Soul', bool(o.shuffle_animal_soul.value)),
                ('Speak', bool(o.shuffle_speak.value)),
                ('NPC Soul', bool(o.shuffle_npc_soul.value)),
            ),
            'Kak Anju as Child': (
                ('Climb', bool(o.shuffle_climb.value)),
                ('Grab / Power Bracelet', bool(o.shuffle_grab.value)),
                ('Animal Soul', bool(o.shuffle_animal_soul.value)),
                ('Speak', bool(o.shuffle_speak.value)),
                ('NPC Soul', bool(o.shuffle_npc_soul.value)),
            ),
        }
        for location_name, requirements in explicit_interactions.items():
            try:
                location = self.get_location(location_name)
            except Exception:
                continue
            for item_name, enabled in requirements:
                if not enabled:
                    continue
                if item_name == "Speak":
                    require_speak(location)
                elif item_name == "Animal Soul":
                    # These explicit interactions are cucco handling.
                    require_animal(location, "Cucco Soul")
                elif item_name == "Enemy Soul":
                    if o.shuffle_enemy_soul.value == 1:
                        require(location, "Enemy Soul")
                else:
                    require(location, item_name)

        # Shared interaction invariants.  NativeLogic carries the exact race/region
        # requirements; these conservative AP guards prevent stock oot_soh rules from
        # leaking around EXTREME's shuffled abilities/souls.
        for location in self.get_locations():
            if location.name.startswith(("Enemy Defeat:", "EXTREME Native Event", "EXTREME Native Action", "EXTREME Native RR_")):
                continue
            lname = location.name.upper()
            if o.shuffle_sign_soul.value and (" SIGN" in lname or lname.startswith("EXTREME ") and "SIGN" in lname):
                require(location, "Sign Soul")
            if o.shuffle_speak.value and (" SHOP ITEM " in lname or "BAZAAR ITEM " in lname or "POTION SHOP ITEM " in lname):
                require_speak(location)
            if o.shuffle_npc_soul.value and (" SHOP ITEM " in lname or "BAZAAR ITEM " in lname or "POTION SHOP ITEM " in lname):
                require(location, "NPC Soul")
            if o.shuffle_business_scrub_soul.value and "DEKU SCRUB" in lname:
                require(location, "Scrub Soul")

        # Bomb/rock-hidden grottos keep their physical blocker in SOH-EXTREME.
        # Shovel reveals/permits the grotto system, but these particular holes
        # additionally require Rock / Boulder Soul before the blocker can be
        # removed.  The inherited physical rule still supplies the attack/tool
        # requirement; this overlay prevents AP from routing through the blocker
        # while its Soul is missing.
        if o.shuffle_rock_boulder_soul.value:
            rock_blocked_grotto_rr = {
                "RR_COLOSSUS_GROTTO", "RR_DMC_SCRUB_GROTTO", "RR_DMC_UPPER_GROTTO",
                "RR_DMT_COW_GROTTO", "RR_GV_OCTOROK_GROTTO", "RR_HF_COW_GROTTO",
                "RR_HF_FAIRY_GROTTO", "RR_HF_INSIDE_FENCE_GROTTO", "RR_HF_NEAR_KAK_GROTTO",
                "RR_HF_NEAR_MARKET_GROTTO", "RR_HF_SOUTHEAST_GROTTO", "RR_HF_TEKTITE_GROTTO",
                "RR_KAK_REDEAD_GROTTO", "RR_LH_GROTTO", "RR_LW_NEAR_SHORTCUTS_GROTTO",
                "RR_LW_SCRUBS_GROTTO", "RR_SFM_WOLFOS_GROTTO", "RR_ZR_FAIRY_GROTTO",
            }
            rock_blocked_grotto_regions = {
                rr_direct_region_name(rr) for rr in rock_blocked_grotto_rr
                if rr_direct_region_name(rr) is not None
            }
            for region in self.multiworld.regions:
                if region.player != self.player:
                    continue
                for entrance in region.exits:
                    connected = getattr(entrance, "connected_region", None)
                    if connected is not None and connected.name in rock_blocked_grotto_regions:
                        add_resolved_rule(entrance, Has("Rock / Boulder Soul"), register_indirects=True)

        # SOH-EXTREME Shovel semantics: EVERY grotto is unavailable without
        # Shovel, including normally-open holes.  Gate both the physical AP
        # entrance and every location inside a grotto so entrance randomization
        # or contracted region graphs cannot leak checks around the requirement.
        if o.shuffle_shovel.value:
            for region in self.multiworld.regions:
                if region.player != self.player:
                    continue
                for entrance in region.exits:
                    connected = getattr(entrance, "connected_region", None)
                    if connected is None or "GROTTO" not in connected.name.upper():
                        continue
                    add_resolved_rule(entrance, Has("Shovel"), register_indirects=True)

            for location in self.get_locations():
                if "GROTTO" in location.name.upper():
                    require(location, "Shovel")

        # Freestanding pickups physically covered by a rock/boulder must not be
        # reachable merely because AP can see the pickup actor.  The obstacle
        # stays in-world and is unbreakable until Rock / Boulder Soul exists.
        if o.shuffle_rock_boulder_soul.value:
            for location_name in (
                "LW Boulder Rupee",
                "DMT Blue Rupee Under Boulder",
                "DMT Red Rupee Under Boulder",
            ):
                try:
                    require(self.get_location(location_name), "Rock / Boulder Soul")
                except Exception:
                    pass

        # Likewise, stock SoH rules assume crawling is an innate Link action.
        # Explicit crawlspace checks need the shuffled Crawl ability.
        if o.shuffle_crawl.value:
            for location in self.get_locations():
                if "CRAWLSPACE" in location.name.upper():
                    require(location, "Crawl")

            # Native SOH-EXTREME gates RR_KF_BOULDER_LOOP itself behind Crawl.
            # Therefore every check on the far side must inherit Crawl, even when
            # the check's own name does not contain the word "crawlspace".
            kokiri_boulder_loop_prefixes = (
                "KF Kokiri Sword Chest",
                "KF Boulder Rupee ",
                "KF Child Grass Maze ",
                "KF After Crawlspace ",
                "KF Boulder Maze ",
                "EXTREME Kf Wonder Crawl ",
            )
            for location in self.get_locations():
                if location.name.startswith(kokiri_boulder_loop_prefixes):
                    require(location, "Crawl")

            # Native SOH-EXTREME uses Crawl to enter Bottom of the Well.
            for location in self.get_locations():
                if location.name.startswith("Bottom of the Well "):
                    require(location, "Crawl")

        # Dampe race / grave audit.
        #
        # NPC Soul is existential: with it missing, Dampe is absent. Reaching the
        # grave room cannot make race tunnel rupees/Wonders logically available.
        dampe_region_enum = getattr(Regions, "GRAVEYARD_DAMPES_GRAVE", None)
        dampe_region_name = (
            dampe_region_enum.value
            if dampe_region_enum is not None
            else "Graveyard Dampes Grave"
        )

        for location in self.get_locations():
            name = location.name
            in_dampe_race = (
                location.parent_region is not None
                and location.parent_region.name == dampe_region_name
            ) or (
                name.startswith("Graveyard Dampe's Grave Rupee ")
                or name.startswith("Graveyard Dampes Grave Pot ")
                or name.startswith("EXTREME Gy Wonder Dampe Race ")
                or name in {
                    "Graveyard Hookshot Chest",
                    "Graveyard Dampe Race Freestanding PoH",
                    "Graveyard Dampes Windmill Access",
                }
            )
            if not in_dampe_race:
                continue

            if o.shuffle_npc_soul.value:
                require(location, "NPC Soul")
            if o.shuffle_speak.value:
                require_language(location, "Hylian")

        # The child digging tour is a different Dampe interaction.
        try:
            dampe_tour = self.get_location("Graveyard Dampe Gravedigging Tour")
            if o.shuffle_npc_soul.value:
                require(dampe_tour, "NPC Soul")
            if o.shuffle_speak.value:
                require_language(dampe_tour, "Hylian")
        except Exception:
            pass

        # Native one-off gates which are not represented by stock SoH LocTags.
        specials = {
            'LLR Freestanding PoH': [('Grab / Power Bracelet', o.shuffle_grab.value), ('Crawl', o.shuffle_crawl.value)],
            'Graveyard Dampe Gravedigging Tour': [('Shovel', o.shuffle_shovel.value)],
            'Spirit Temple MQ Crawlspace Boulder': [('Crawl', o.shuffle_crawl.value)],
            # Mechanical C++ ability audit: these native checks are in the
            # generated unmapped-rule table, so they need explicit stock-name
            # parity guards rather than relying on the AP-ID overlay.
            'Dodongos Cavern MQ Vines Silver': [('Climb', o.shuffle_climb.value)],
            'Forest Temple MQ Basement Chest': [('Grab / Power Bracelet', o.shuffle_grab.value)],
        }
        for location_name, requirements in specials.items():
            try:
                location = self.get_location(location_name)
            except Exception:
                continue
            for item_name, enabled in requirements:
                if enabled:
                    require(location, item_name)


        # ------------------------------------------------------------------
        # 0.9.6 FULL PARITY POST-PASS
        # ------------------------------------------------------------------
        # These are physical-access invariants from the SOH-EXTREME fork that
        # can be lost when many native micro-regions/events are contracted into
        # one stock Archipelago region. Keep this pass late so it can only add
        # missing requirements; it never replaces the normal stock/native rule.

        # Every check in Deku Theater is behind the theater hole. In EXTREME the
        # theater is part of the Shovel-gated grotto system even though its stock
        # AP names do not contain the word "Grotto".
        if o.shuffle_shovel.value:
            for location in self.get_locations():
                parent = location.parent_region.name.upper() if location.parent_region else ""
                lname = location.name.upper()
                if parent == "DEKU THEATER" or lname.startswith("EXTREME LW THEATER "):
                    require(location, "Shovel")

        # These actors are physically on/behind climb-only geometry in the fork.
        # Their broad stock parent regions are reachable earlier, so parent-region
        # reachability alone is insufficient.
        if o.shuffle_climb.value:
            for location_name in (
                "EXTREME Hc Boulder",
                "EXTREME Hc Dead End Rectangle Sign",
                "EXTREME Hf Center Exit Arrow Sign",
            ):
                try:
                    require(self.get_location(location_name), "Climb")
                except Exception:
                    pass

        # Darunia's Chamber must inherit the *door-opening* condition.  Stock AP
        # can contract Goron City/Darunia into one broad region, which exposed the
        # pots with only Pot Soul + a break method.  Native EXTREME allows:
        #   Child: usable Zelda's Lullaby (therefore Ocarina + required buttons,
        #          and with note shuffle all six Lullaby notes via the virtual song)
        #   Adult: stop the rolling Goron first.
        # The stock/native parent route still supplies any additional conditions;
        # this rule restores the missing door event itself.
        for location in self.get_locations():
            parent = location.parent_region.name.upper() if location.parent_region else ""
            if parent != "GC DARUNIAS CHAMBER" and not location.name.startswith("GC Darunia "):
                continue
            bundle = native_bundle_for_location(location)
            if bundle is None:
                continue

            child_route = is_child(bundle) & can_use(Items.ZELDAS_LULLABY, bundle)
            adult_stopper = (
                has_explosives(bundle)
                | can_use(Items.FAIRY_BOW, bundle)
                | Has("Strength Upgrade")
                | grab_rule()
            )
            adult_route = is_adult(bundle) & adult_stopper
            if o.shuffle_npc_soul.value:
                adult_route &= Has("NPC Soul")
            if o.shuffle_speak.value == 1:
                adult_route &= Has("Speak")
            elif o.shuffle_speak.value == 2:
                adult_route &= Has("Speak Goron")
            require_native_existing(location, child_route | adult_route)

        # Graveyard grave pits are NOT part of the Shovel grotto system.  Do not
        # add Shovel/NPC/Speak merely because a check is physically below ground.
        # Dampé *race* and gravedigging checks remain handled by their dedicated
        # rules above; this exception is intentionally limited to grave-pit rooms.
        grave_pit_markers = (
            "SHIELD GRAVE", "HEART PIECE GRAVE", "COMPOSERS GRAVE",
            "ROYAL FAMILYS TOMB", "ROYAL FAMILY'S TOMB",
        )
        # No extra rule is installed here by design; the markers are retained in
        # one place so future automatic grotto-family passes can explicitly skip
        # them instead of accidentally inheriting Shovel/NPC/Speak.
        self._soh_extreme_grave_pit_markers = grave_pit_markers

        # Global sanity-object audit.  Every enabled Grass/Bush check must carry
        # the existence soul regardless of whether it came from stock LocTags,
        # a generated EXTREME name, or a native micro-region projection.
        if o.shuffle_grass_bush_soul.value:
            for location in self.get_locations():
                lname = location.name.upper()
                data = location_data_table.get(location.name)
                tags = data.tags if data is not None and data.tags is not None else LocTag(0)
                # Only actual grass/bush sanity locations inherit Grass/Bush Soul.
                # Freestanding rupees/hearts that happen to be placed in grass remain
                # independent checks and must not be hidden behind the soul.
                if tags & grass_tags:
                    require(location, "Grass / Bush Soul")

        # Deku Tree micro-location reachability.  Stock AP contracts several
        # vertical Deku Tree regions, so these checks can otherwise appear from
        # the broad room even when Link cannot physically climb to the actor.
        if o.shuffle_climb.value:
            for location_name in (
                "Deku Tree Basement Grass 1",
                "Deku Tree Basement Grass 2",
                "Deku Tree Compass Grass 1",
                "Deku Tree Compass Grass 2",
                "Deku Tree 2F Grass 1",
                "Deku Tree 2F Grass 2",
                "Deku Tree Lobby Upper Heart",
            ):
                try:
                    require(self.get_location(location_name), "Climb")
                except Exception:
                    pass

        # Royal Family's Tomb enemy placements inherit the tomb-opening event.
        # The entrance is not merely "Graveyard reachable": Zelda's Lullaby must
        # actually be playable.  can_use() includes Ocarina/button requirements,
        # and SOH-EXTREME's note shuffle only creates the virtual Lullaby after all
        # six Zelda notes have been collected.
        royal_tomb_region = getattr(Regions, "GRAVEYARD", None)
        if royal_tomb_region is None:
            royal_tomb_region = getattr(Regions, "THE_GRAVEYARD", None)
        if royal_tomb_region is not None:
            royal_tomb_open = can_use(Items.ZELDAS_LULLABY, (royal_tomb_region, self))
            for enemy_drop in ENEMY_DROP_LOCATIONS:
                if enemy_drop.scene_id != 0x41:
                    continue
                try:
                    require_native_existing(self.get_location(enemy_drop.name), royal_tomb_open)
                except Exception:
                    pass

        # ------------------------------------------------------------------
        # 0.10.6 STRICT ZORA'S RIVER PHYSICAL ROUTES
        # ------------------------------------------------------------------
        # AP contracts several native ZR subregions into the broad Zora River
        # region.  Re-apply the actual physical route immediately before the
        # fork rules are installed so UT cannot list upper-river actors from
        # basic Swim alone.
        zr_bundle = (Regions.ZORA_RIVER, self)
        zr_basic_swim = swim_rule()
        zr_deep_swim = deep_swim_route()
        zr_front_break = Has("Progressive Bomb Bag") | Has("Bombchu Bag") | grab_rule()
        if o.shuffle_rock_boulder_soul.value:
            zr_front_break = zr_front_break & Has("Rock / Boulder Soul")
        zr_upper_child_entry = zr_deep_swim | zr_front_break

        # Before-ladder wonders are Child-only, need surface swimming to reach
        # their triggers, and need either the front rock route or the deeper
        # backside/shortcut route.
        zr_before_ladder = is_child(zr_bundle) & zr_basic_swim & zr_upper_child_entry
        for zr_name in (
            "EXTREME Zr Wonder Before Ladder 1",
            "EXTREME Zr Wonder Before Ladder 2",
            "EXTREME Zr Wonder Before Ladder 3",
            "EXTREME Zr Wonder Before Ladder 4",
            "EXTREME Zr Wonder Before Ladder 5",
            "EXTREME Zr Wonder Before Ladder 6",
        ):
            try:
                require_native_existing(self.get_location(zr_name), zr_before_ladder)
            except Exception:
                pass

        # After-ladder wonders are also Child-only.  In addition to reaching
        # upper ZR, Link must be able to traverse the ladder route.  Preserve the
        # real Cucco+Grab and Hover alternatives while basic Swim is the normal
        # child route; deep Swim can also approach from the backside.
        zr_atop_ladder = climb_rule() & (
            zr_basic_swim
            | can_use(Items.HOVER_BOOTS, zr_bundle)
            | (grab_rule() & animal_rule("Cucco"))
        )
        zr_after_ladder = is_child(zr_bundle) & zr_upper_child_entry & zr_atop_ladder
        for zr_name in (
            "EXTREME Zr Wonder After Ladder 1",
            "EXTREME Zr Wonder After Ladder 2",
            "EXTREME Zr Wonder After Ladder 3",
        ):
            try:
                require_native_existing(self.get_location(zr_name), zr_after_ladder)
            except Exception:
                pass

        # The waterfall plaque is not Child-only, but broad ZR contraction must
        # not make it readable from the front bank.  Adult can use the normal
        # upper route; Child needs the front rock route or deep Swim.  Hovers are
        # retained as the native Adult/upper-ZR alternative.
        zr_plaque_route = (
            is_adult(zr_bundle)
            | zr_deep_swim
            | zr_front_break
            | can_use(Items.HOVER_BOOTS, zr_bundle)
        )
        try:
            require_native_existing(self.get_location("EXTREME Zr Sleepless Waterfall Plaque"), zr_plaque_route)
        except Exception:
            pass

        # ZR Near Freestanding PoH Grass is a Child-only grass actor.  It needs
        # the upper-river route, basic Swim, Grass/Bush Soul when shuffled, and
        # an actual shrub-breaking method.  The previous broad ZR parent allowed
        # this check to leak into logic with only one piece of the route.
        zr_poh_grass_rule = (
            is_child(zr_bundle)
            & zr_basic_swim
            & zr_upper_child_entry
            & can_cut_shrubs(zr_bundle)
        )
        try:
            zr_poh_grass = self.get_location("ZR Near Freestanding PoH Grass")
        except Exception:
            zr_poh_grass = None
        if zr_poh_grass is not None:
            require_native_existing(zr_poh_grass, zr_poh_grass_rule)
            if o.shuffle_grass_bush_soul.value:
                require(zr_poh_grass, "Grass / Bush Soul")

        # Re-assert Saria at the very end of rule construction.  This prevents
        # any inherited stock/event rule installed later from exposing the song
        # without the actor and the correct language interaction.
        try:
            saria_song = self.get_location("Song from Saria")
        except Exception:
            saria_song = None
        if saria_song is not None:
            if o.shuffle_npc_soul.value:
                require(saria_song, "NPC Soul")
            if o.shuffle_speak.value == 1:
                require(saria_song, "Speak")
            elif o.shuffle_speak.value == 2:
                require(saria_song, "Speak Kokiri")

        # Metadata-independent native interaction IDs. These are extracted from
        # actual Speak_<language> requirements, not guessed from the area name.
        # Auto-granted Skip Zelda reward is intentionally not an NPC visit.
        native_npc_interactions = {}
        for location in self.get_locations():
            source = location_data_table.get(location.name)
            address = location.address if location.address is not None else (source.loc_id if source else None)
            language = NATIVE_EXACT_SPEAK_BY_AP_ID.get(address)
            if language is None or (location.name == "Song from Impa" and o.skip_child_zelda.value):
                continue
            require_language(location, language)
            # Scrub Soul still controls the scrub actor; merchant conversation
            # additionally needs NPC interaction availability, just like native
            # HasItem(RG_SPEAK_DEKU) and the runtime business-scrub talk hook.
            if o.shuffle_npc_soul.value:
                require(location, "NPC Soul")
            native_npc_interactions[location.name] = language
        self._extreme_native_interactions = native_npc_interactions

        # Install fork-native rules once, after every soul/ability/time gate has
        # been accumulated.  This fixes the broad-location logic leak where one
        # later requirement could silently replace an earlier requirement.
        for fork_loc in FORK_LOCATIONS:
            location_name = fork_loc.name
            if location_name not in FORK_LOCATION_NAME_TO_ID:
                continue
            and_requirements = fork_requirements.get(location_name, [])
            any_requirements = fork_any_requirements.get(location_name, [])
            group_requirements = fork_group_requirements.get(location_name, [])
            native_rules = fork_native_rules.get(location_name, [])
            if not and_requirements and not any_requirements and not group_requirements and not native_rules:
                continue

            resolved_rules = [Has(name, count) for name, count in and_requirements]
            resolved_rules.extend(RequireAnyExistingItems(group) for group in any_requirements)
            resolved_rules.extend(RequireAnyItemGroups(groups) for groups in group_requirements)
            resolved_rules.extend(native_rules)
            if len(resolved_rules) == 1:
                self.set_rule(self.get_location(location_name), resolved_rules[0])
            else:
                self.set_rule(self.get_location(location_name), And(*resolved_rules))

        # These checks use complete, source-derived incoming routes, not the
        # legacy contracted-parent projection assembled above.
        from .SilverRoomLogic import finalize_silver_locations
        finalize_silver_locations(self)
        from ._vendor_oot_soh.LogicHelpers import can_interact_npc
        for sheik_name in (
            "Sheik in Forest", "Sheik in Crater", "Sheik in Ice Cavern",
            "Sheik at Colossus", "Sheik in Kakariko", "Sheik at Temple",
        ):
            sheik = self.get_location(sheik_name)
            add_resolved_rule(sheik, can_interact_npc((sheik.parent_region, self), "Hylian"))

    def create_items(self) -> None:
        self._create_stock_item_pool()

        # Official oot_soh has already sized the *actual global player pool* to
        # the available fill capacity.  Much of oot_soh's filler is appended
        # directly to multiworld.itempool and is NOT mirrored in self.item_pool,
        # so len(self.item_pool) is not a valid capacity target.
        target_player_pool_size = sum(
            1 for item in self.multiworld.itempool if item.player == self.player
        )

        # super().create_items() already sizes filler against every location
        # currently in the MultiWorld, including all dynamically-added Speech
        # Sanity checks. Do not add a second filler item for those locations.

        extras: list[str] = []
        o = self.options
        toggles = [
            (o.shuffle_roll, "Roll"),
            (o.shuffle_climb, "Climb"),
            (o.shuffle_crawl, "Crawl"),
            (o.shuffle_npc_soul, "NPC Soul"),
            (o.shuffle_pot_soul, "Pot Soul"),
            (o.shuffle_crate_soul, "Crate Soul"),
            (o.shuffle_grass_bush_soul, "Grass / Bush Soul"),
            (o.shuffle_rock_boulder_soul, "Rock / Boulder Soul"),
            (o.shuffle_tree_soul, "Tree Soul"),
            (o.shuffle_beehive_soul, "Beehive Soul"),
            (o.shuffle_sign_soul, "Sign Soul"),
            (o.shuffle_skulltula_soul, "Skulltula Soul"),
            (o.shuffle_business_scrub_soul, "Scrub Soul"),
            (o.shuffle_shovel, "Shovel"),
            (o.shuffle_flow_of_time, "Flow of Time"),
        ]
        extras.extend(name for enabled, name in toggles if enabled.value)

        if o.shuffle_bean_souls.value:
            extras.extend([
                "Death Mountain Crater Bean Soul",
                "Death Mountain Trail Bean Soul",
                "Desert Colossus Bean Soul",
                "Gerudo Valley Bean Soul",
                "Graveyard Bean Soul",
                "Kokiri Forest Bean Soul",
                "Lake Hylia Bean Soul",
                "Lost Woods Bridge Bean Soul",
                "Lost Woods Bean Soul",
                "Zora's River Bean Soul",
            ])

        if o.shuffle_speak.value == 1:
            extras.append("Speak")
        elif o.shuffle_speak.value == 2:
            extras.extend(["Speak Deku", "Speak Gerudo", "Speak Goron",
                           "Speak Hylian", "Speak Kokiri", "Speak Zora"])

        if o.shuffle_enemy_soul.value == 1:
            extras.append("Enemy Soul")
        elif o.shuffle_enemy_soul.value == 2:
            extras.extend([
                "Stalfos Soul",
                "Octorok Soul",
                "Wallmaster Soul",
                "Dodongo Soul",
                "Keese Soul",
                "Tektite Soul",
                "Peahat Soul",
                "Lizalfos and Dinolfos Soul",
                "Gohma Larva Soul",
                "Shabom Soul",
                "Baby Dodongo Soul",
                "Biri and Bari Soul",
                "Tailpasaran Soul",
                "Torch Slug Soul",
                "Moblin Soul",
                "Armos Soul",
                "Deku Baba Soul",
                "Deku Scrub Soul",
                "Bubble Soul",
                "Beamos Soul",
                "Floormaster Soul",
                "Redead and Gibdo Soul",
                "Flare Dancer Soul",
                "Dead Hand Soul",
                "Shell Blade Soul",
                "Like Like Soul",
                "Spike Soul",
                "Anubis Soul",
                "Iron Knuckle Soul",
                "Skull Kid Soul",
                "Flying Pot Soul",
                "Freezard Soul",
                "Stinger Soul",
                "Wolfos Soul",
                "Guay Soul",
                "Jabu Jabu Tentacle Soul",
                "Dark Link Soul",
                "Door Trap Soul",
                "Flying Floor Tile Soul",
                "Gerudo Thief Soul",
                "Poe Sister Soul",
                "Poe Soul",
                "Leever Soul",
                "Stalchild Soul",
                "Big Octo Soul",

            ])

        if o.shuffle_animal_soul.value == 1:
            extras.append("Animal Soul")
        elif o.shuffle_animal_soul.value == 2:
            extras.extend(["Cow Soul", "Cucco Soul", "Dog Soul", "Fish Soul",
                           "Bug Soul", "Butterfly Soul", "Frog Soul", "Horse Soul"])

        # Silver Rupee sanity has two layers:
        #   * each physical silver rupee is an AP location
        #   * each collected group-piece is an AP progression item
        #
        # Native balanced/scarce/minimal pools contain five pieces per vanilla
        # group; plentiful contains six (door still opens at five). Wallet mode
        # places one item per group and native SOH fills that group's counter.
        if o.shuffle_silver.value == 1:
            pool_key = str(getattr(o.item_pool, "current_key", o.item_pool)).lower()
            silver_pool_copies = 6 if pool_key == "plentiful" else 5
            for silver_name in VANILLA_SILVER_GROUP_TOTALS:
                extras.extend([silver_name] * silver_pool_copies)
        elif o.shuffle_silver.value == 2:
            extras.extend(VANILLA_SILVER_GROUP_TOTALS)

        # Shuffle Grab is not a separate network item. Native SOH-EXTREME adds
        # one extra physical Strength Upgrade and consumes its first copy as the
        # Grab/Power Bracelet tier. Mirror that pool shape exactly.
        if o.shuffle_grab.value:
            extras.append("Strength Upgrade")
        if o.shuffle_open_chest.value == 1:
            extras.append("Open Chest")
        elif o.shuffle_open_chest.value == 2:
            extras.extend(["Open Chest", "Open Chest"])
        if o.song_note_shuffle.value:
            starting_notes = {item.name for item in self.multiworld.precollected_items[self.player]}
            from_pool = o.start_inventory_from_pool.value
            # Starting-song options already grant these notes. For common
            # from-pool requests, leave one in the pool for AP's later depletion.
            extras.extend(
                note for notes in self.SONG_NOTE_GROUPS.values() for note in notes
                if note not in starting_notes or from_pool.get(note, 0)
            )

        # Setting/check coverage audit.  An enabled sanity family must actually
        # contribute checks to the AP world.  This catches the class of bugs
        # where a YAML toggle is sent to SOH but generation silently omitted the
        # corresponding locations.
        setting_family_enabled = {
            "rock": bool(o.shuffle_rocks.value),
            "boulder": bool(o.shuffle_boulders.value),
            "bush": bool(o.shuffle_bushes.value) or o.shuffle_grass.value in (2, 3),
            "icicle": bool(o.shuffle_icicles.value),
            "red_ice": bool(o.shuffle_red_ice.value),
            "sign": bool(o.shuffle_signs.value),
            "beggar": bool(o.shuffle_beggar.value),
            "chest_minigame": bool(o.shuffle_chest_minigame.value),
            "wonder": bool(o.shuffle_wonder_items.value),
            "silver": o.shuffle_silver.value in (1, 2),
            "butterfly_fairy": bool(o.shuffle_butterfly_fairies.value),
        }
        active_family_counts = {
            family: sum(
                1 for loc in FORK_LOCATIONS
                if loc.family == family and self._fork_location_enabled(loc)
            )
            for family in setting_family_enabled
        }
        missing_families = [
            family for family, enabled in setting_family_enabled.items()
            if enabled and active_family_counts.get(family, 0) == 0
        ]
        if missing_families:
            raise OptionError(
                "SOH-EXTREME setting coverage audit found enabled sanity with no AP checks: "
                + ", ".join(sorted(missing_families))
            )

        if o.shuffle_silver.value in (1, 2):
            silver_location_count = active_family_counts["silver"]
            if silver_location_count != 80:
                raise OptionError(
                    "SOH-EXTREME silver audit expected 80 vanilla Silver Rupee AP checks, "
                    f"found {silver_location_count}"
                )

        logger.info(
            "SOH-EXTREME setting coverage: %s",
            ", ".join(
                f"{family}={count}"
                for family, count in sorted(active_family_counts.items())
                if setting_family_enabled[family]
            ),
        )

        if extras:
            self._remove_replaceable_items(len(extras), replace_songs=bool(o.song_note_shuffle.value))
            new_items = [self.create_item(name) for name in extras]
            self.item_pool.extend(new_items)
            self.multiworld.itempool.extend(new_items)

        # Do NOT force EXTREME progression items local or into sphere 1.
        # The normal Archipelago fill should place them wherever progression
        # logic permits, including other players' worlds. Solvability comes from
        # accurately expressing every enabled physical gate in set_rules(), not
        # from handing foundational abilities to this player early.

        # SOH-EXTREME trap percentage is a real pool option, not merely a client CVar.
        # Replace eligible filler with stock SoH Ice Trap items; the native client
        # turns those into the selected EXTREME effect and can relay them via TrapLink.
        if o.extreme_trap_pool.value and o.extreme_trap_filler_replacement.value:
            candidates = [
                item for item in self.multiworld.itempool
                if item.player == self.player
                and item.name != "Ice Trap"
                and not (item.classification & (ItemClassification.progression | ItemClassification.useful))
            ]
            replace_count = (len(candidates) * o.extreme_trap_filler_replacement.value) // 100
            for item in candidates[:replace_count]:
                if item in self.multiworld.itempool:
                    self.multiworld.itempool.remove(item)
                if item in self.item_pool:
                    self.item_pool.remove(item)
                trap = self.create_item("Ice Trap")
                self.multiworld.itempool.append(trap)
                self.item_pool.append(trap)
            if replace_count:
                logger.info("SOH-EXTREME replaced %d filler items with traps", replace_count)

        # Keep every enabled AP check/location and make this player's actual
        # global AP pool exactly match the capacity stock oot_soh calculated.
        #
        # Rules:
        #   - too many items  -> remove junk/filler only
        #   - too few items   -> add junk filler
        #   - never delete progression/advancement items
        #
        # IMPORTANT: compare multiworld.itempool, not self.item_pool. Stock SoH
        # filler lives primarily in the global pool, and _remove_replaceable_items()
        # deliberately removes from that same pool.
        current_player_pool_size = sum(
            1 for item in self.multiworld.itempool if item.player == self.player
        )
        delta = current_player_pool_size - target_player_pool_size

        junk_names = {
            "Recovery Heart",
            "Blue Rupee", "Red Rupee", "Purple Rupee", "Huge Rupee",
            "Deku Stick (1)",
            "Deku Nuts (5)", "Deku Nuts (10)",
            "Deku Seeds (30)",
            "Arrows (5)", "Arrows (10)", "Arrows (30)",
            "Bombs (5)", "Bombs (10)", "Bombs (20)",
            "Ice Trap",
            "Rupees (5)", "Rupees (20)", "Rupees (50)", "Rupees (200)",
        }

        if delta > 0:
            # Prefer explicitly-known junk even if oot_soh labels some of it
            # "useful". Then fall back to other non-advancement items.
            removable = [
                item for item in self.multiworld.itempool
                if item.player == self.player and item.name in junk_names
            ]

            if len(removable) < delta:
                already = {id(item) for item in removable}
                removable.extend(
                    item for item in self.multiworld.itempool
                    if item.player == self.player
                    and id(item) not in already
                    and not item.advancement
                )

            if len(removable) < delta:
                raise RuntimeError(
                    "SOH-EXTREME needs to remove "
                    f"{delta} item(s) to match its enabled checks, but only "
                    f"{len(removable)} non-progression junk item(s) are available."
                )

            priority = {
                "Recovery Heart": 0,
                "Blue Rupee": 1, "Red Rupee": 1, "Purple Rupee": 1, "Huge Rupee": 1,
                "Rupees (5)": 1, "Rupees (20)": 1, "Rupees (50)": 1, "Rupees (200)": 1,
                "Deku Stick (1)": 2,
                "Deku Nuts (5)": 2, "Deku Nuts (10)": 2,
                "Deku Seeds (30)": 2,
                "Arrows (5)": 2, "Arrows (10)": 2, "Arrows (30)": 2,
                "Bombs (5)": 2, "Bombs (10)": 2, "Bombs (20)": 2,
                "Ice Trap": 3,
            }
            removable.sort(key=lambda item: (priority.get(item.name, 10), item.name))

            for item in removable[:delta]:
                try:
                    self.item_pool.remove(item)
                except ValueError:
                    pass
                try:
                    self.multiworld.itempool.remove(item)
                except ValueError:
                    pass

            logger.info(
                "SOH-EXTREME removed %d junk item(s) to match %d enabled fill slots",
                delta, target_player_pool_size,
            )

        elif delta < 0:
            missing = -delta
            for _ in range(missing):
                filler = self.create_filler()
                self.item_pool.append(filler)
                self.multiworld.itempool.append(filler)

            logger.info(
                "SOH-EXTREME added %d junk filler item(s) to match %d enabled fill slots",
                missing, target_player_pool_size,
            )

        # Internal consistency check before AP's fill stage.
        final_player_pool_size = sum(
            1 for item in self.multiworld.itempool if item.player == self.player
        )
        if final_player_pool_size != target_player_pool_size:
            raise RuntimeError(
                "SOH-EXTREME pool balancing failed: "
                f"{final_player_pool_size} global player items for target "
                f"{target_player_pool_size}"
            )


    def fill_hook(self, progitempool, usefulitempool, filleritempool, fill_locations) -> None:
        """Reserve a guaranteed progression backbone before AP's normal fill."""
        super().fill_hook(progitempool, usefulitempool, filleritempool, fill_locations)
        from .FrontierFill import frontier_fill
        frontier_fill(self, progitempool, fill_locations)

    def post_fill(self) -> None:
        """Fail generation rather than output a seed whose AP logic stalls."""
        super().post_fill()
        if self.options.song_note_shuffle.value:
            bypasses = [location.name for location in self.multiworld.get_filled_locations()
                        if location.address is not None and location.item is not None
                        and location.item.player == self.player
                        and location.item.name in self.SONG_ITEMS]
            if bypasses:
                raise OptionError(
                    "SOH-EXTREME individual-note mode cannot place complete song items: "
                    + ", ".join(bypasses)
                    + ". Use Song Note items in plando, or disable individual notes."
                )
        from .FrontierFill import validate_filled_world
        validate_filled_world(self)

    def fill_slot_data(self):
        # Publish every resolved option directly.  Dynamic seed state that is not
        # an Option is added below.  This makes SOH-EXTREME slot data independent
        # from SohWorld.fill_slot_data() and gives Universal Tracker a complete
        # regeneration snapshot.
        data = {
            field.name: getattr(self.options, field.name).value
            for field in dataclasses.fields(type(self.options))
        }
        try:
            hints = CreateNonlocalHints(self)
            static_hints = {}
            for hint in hints:
                static_hints.update(hint.serialize())
        except Exception:
            static_hints = {}
        data.update({
            "required_trials": self.ganons_trials,
            "triforce_hunt_pieces_required": self.triforce_pieces_required,
            "shop_prices": self.shop_prices,
            "shop_vanilla_items": self.shop_vanilla_items,
            "apworld_version": self.apworld_version,
            "enemy_room_logic_version": "0.11.18",
            "enemy_room_disabled_actions": list(getattr(self, "_extreme_room_disabled_actions", [])),
            "enemy_spawn_policy": "placed_and_non_enemy_scripted_encounters",
            "static_hints": static_hints,
            "hintable_items": {item.code for item in self.item_pool + self.preplaced_items if item.code is not None},
            "archipelago_seed": self.random.randint(0, 4294967295),
        })
        o = self.options

        # AutoWorld.fill_slot_data() is not required to include every option.
        # SOH-EXTREME's native-settings bridge needs the fully resolved option
        # values, so seed the slot-data working dictionary directly from the
        # generated options before translating them to SoH CVars.  setdefault
        # preserves any values a superclass intentionally published.
        for field in dataclasses.fields(type(o)):
            option = getattr(o, field.name)
            value = option.value
            if isinstance(value, set):
                value = sorted(value)
            elif isinstance(value, tuple):
                value = list(value)
            data.setdefault(field.name, value)
        # Publish the exact server-side location set for this generated slot.
        # The C++ client uses this to send LocationScouts only for locations that
        # actually exist under the selected shuffle options.
        active_locations = sorted({
            int(location.address)
            for location in self.multiworld.get_locations(self.player)
            if isinstance(location.address, int)
        })
        # Standalone-world compatibility bridge for the native SOH client.  The
        # C++ side must not assume stock oot_soh names/IDs after SOH-EXTREME became
        # its own game.  Publish the exact active location namespace for this seed.
        extreme_location_name_to_id = {
            str(location.name): int(location.address)
            for location in self.multiworld.get_locations(self.player)
            if isinstance(location.address, int)
        }

        # Translate every official SoH slot option that has an equivalent in this
        # SOH-EXTREME fork into the fork's actual gRando.Settings CVar name/value.
        # This gives the native client one authoritative settings snapshot to apply
        # before Randomizer_InitSaveFile() instead of relying on whatever happened
        # to be selected in the local randomizer menu.
        cvars = {}
        def cv(name, value):
            cvars[name] = int(value)

        # World access / bridge / trials.
        # AP accessibility is Full=0 / Minimal=1.  Native SoH uses a boolean
        # AllLocationsReachable, so translate it instead of inheriting a local value.
        cv("AllLocationsReachable", 1 if data["accessibility"] == 0 else 0)
        cv("ClosedForest", data["closed_forest"])
        cv("DoorOfTime", data["door_of_time"])
        cv("ZorasFountain", data["zoras_fountain"])
        cv("SleepingWaterfall", data["sleeping_waterfall"])
        cv("JabuJabu", data["jabu_jabu"])
        cv("LockOverworldDoors", data["lock_overworld_doors"])
        cv("FortressCarpenters", data["fortress_carpenters"])
        cv("RainbowBridge", 8 if data["rainbow_bridge"] == 7 else data["rainbow_bridge"])
        cv("BridgeRewardOptions", data["rainbow_bridge_greg_modifier"])
        cv("StoneCount", data["rainbow_bridge_stones_required"])
        cv("MedallionCount", data["rainbow_bridge_medallions_required"])
        cv("RewardCount", data["rainbow_bridge_dungeon_rewards_required"])
        cv("DungeonCount", data["rainbow_bridge_dungeons_required"])
        cv("TokenCount", data["rainbow_bridge_skull_tokens_required"])
        cv("GanonTrial", data["ganons_trials"])
        cv("GanonTrialCount", data["ganons_trials_count"])
        cv("MedallionLockedTrials", data["medallion_locked_trials"])

        # Goal / songs / core item shuffles.
        cv("TriforceHuntTotalPieces", data["triforce_hunt_pieces_total"] if data["triforce_hunt"] else 0)
        # Native SoH decides both the Triforce pickup message and the tracker
        # required-count display from the normal WinCon settings.  AP Triforce
        # Hunt previously only sent the total, so native SoH saw no Triforce
        # trigger and called every piece "useless" / displayed required=total.
        if data["triforce_hunt"]:
            cv("ShuffleWincon", 7)  # RO_WINCON_TRIFORCE_PIECES
            cv("WinconTriforceCount", data["triforce_hunt_pieces_required"])
        cv("ShuffleSongs", data["shuffle_songs"])
        cv("ShuffleTokens", data["shuffle_skull_tokens"])
        cv("GsExpectSunsSong", data["skulls_sun_song"])
        cv("ShuffleKokiriSword", data["shuffle_kokiri_sword"])
        cv("ShuffleMasterSword", data["shuffle_master_sword"])
        cv("ShuffleChildWallet", data["shuffle_childs_wallet"])
        cv("IncludeTycoonWallet", data["shuffle_tycoon_wallet"])
        cv("ShuffleOcarinas", data["shuffle_ocarinas"])
        cv("ShuffleOcarinaButtons", data["shuffle_ocarina_buttons"])
        cv("ShuffleSwim", data["shuffle_swim"])
        cv("ShuffleGerudoToken", data["shuffle_gerudo_membership_card"])
        cv("ShuffleWeirdEgg", data["shuffle_weird_egg"])
        cv("ShuffleFishingPole", data["shuffle_fishing_pole"])
        cv("ShuffleDekuStickBag", data["shuffle_deku_stick_bag"])
        cv("ShuffleDekuNutBag", data["shuffle_deku_nut_bag"])

        # Location families.  Fishsanity and dungeon rewards use different enum
        # layouts in this fork, so translate them instead of copying raw values.
        cv("ShuffleRocks", o.shuffle_rocks.value)
        cv("ShuffleBoulders", o.shuffle_boulders.value)
        # The patched native fork makes GrassSanity Overworld/All include bushes.
        # Keep the explicit BushSanity setting too, but never send a false value
        # that would contradict the AP location set for those GrassSanity modes.
        cv("ShuffleBushes", int(bool(o.shuffle_bushes.value) or o.shuffle_grass.value in (2, 3)))
        cv("ShuffleIcicles", o.shuffle_icicles.value)
        cv("ShuffleRedIce", o.shuffle_red_ice.value)
        cv("ShuffleSigns", o.shuffle_signs.value)
        cv("ShuffleBeggar", o.shuffle_beggar.value)
        cv("ShuffleChestMinigame", o.shuffle_chest_minigame.value)
        cv("ShuffleWonderItems", o.shuffle_wonder_items.value)
        cv("ShuffleSilver", o.shuffle_silver.value)
        cv("ShuffleButterflyFairies", o.shuffle_butterfly_fairies.value)
        # Enemy-drop randomization is a first-class AP option. It randomizes the
        # native ordinary-enemy drop table; Enemy Soul separately controls whether
        # ordinary enemies are allowed to die.
        cv("ShuffleEnemyDrops", o.shuffle_enemy_drops.value)
        cv("ShuffleBeanSouls", o.shuffle_bean_souls.value)
        cv("ShuffleFreestanding", data["shuffle_freestanding_items"])
        cv("Shopsanity", 1 if data["shuffle_shops"] else 0)
        cv("ShopsanityCount", data["shuffle_shops_item_amount"])
        cv("ShopsanityPrices", 5 if data["shop_affordable_prices"] else 4)
        cv("ShopsanityPriceRange1", data["shuffle_shops_minimum_price"])
        cv("ShopsanityPriceRange2", data["shuffle_shops_maximum_price"])
        cv("ShopsanityPricesAffordable", data["shop_affordable_prices"])
        cv("Fishsanity", {0: 0, 1: 2, 2: 3, 3: 4}.get(data["shuffle_fish"], 0))
        cv("ShuffleScrubs", data["shuffle_scrubs"])
        cv("ScrubsPrices", 5 if data["scrub_affordable_prices"] else 4)
        cv("ScrubsPriceRange1", data["shuffle_scrubs_minimum_price"])
        cv("ScrubsPriceRange2", data["shuffle_scrubs_maximum_price"])
        cv("ScrubsPricesAffordable", data["scrub_affordable_prices"])
        cv("ShuffleBeehives", data["shuffle_beehives"])
        cv("ShuffleCows", data["shuffle_cows"])
        cv("ShufflePots", data["shuffle_pots"])
        cv("ShuffleCrates", data["shuffle_crates"])
        cv("ShuffleTrees", data["shuffle_trees"])
        cv("ShuffleMerchants", data["shuffle_merchants"])
        cv("MerchantPrices", 5 if data["merchant_affordable_prices"] else 4)
        cv("MerchantPriceRange1", data["shuffle_merchants_minimum_price"])
        cv("MerchantPriceRange2", data["shuffle_merchants_maximum_price"])
        cv("MerchantPricesAffordable", data["merchant_affordable_prices"])
        cv("ShuffleFrogSongRupees", data["shuffle_frog_song_rupees"])
        cv("ShuffleAdultTrade", data["shuffle_adult_trade_items"])
        cv("ShuffleFountainFairies", data["shuffle_fountain_fairies"])
        cv("ShuffleStoneFairies", data["shuffle_stone_fairies"])
        cv("ShuffleBeanFairies", data["shuffle_bean_fairies"])
        cv("ShuffleFairySpots", data["shuffle_song_fairies"])
        cv("ShuffleGrass", data["shuffle_grass"])
        cv("ShuffleDungeonReward", {0: 0, 1: 1, 2: 3, 3: 4, 4: 5}.get(data["shuffle_dungeon_rewards"], 1))

        # Dungeon items / Ganon BK / key rings.
        cv("StartingMapsCompasses", data["maps_and_compasses"])
        gbk = data["ganons_castle_boss_key"]
        cv("ShuffleGanonBossKey", {0: 0, 1: 5, 2: 5, 3: 6, 4: 7, 5: 8, 6: 9, 7: 10}.get(gbk, 0))
        cv("GbkRewardOptions", data["ganons_castle_boss_key_greg_modifier"])
        cv("GbkStoneCount", data["ganons_castle_boss_key_stones_required"])
        cv("GbkMedallionCount", data["ganons_castle_boss_key_medallions_required"])
        cv("GbkRewardCount", data["ganons_castle_boss_key_dungeon_rewards_required"])
        cv("GbkDungeonCount", data["ganons_castle_boss_key_dungeons_required"])
        cv("GbkTokenCount", data["ganons_castle_boss_key_skull_tokens_required"])
        cv("Keysanity", data["small_key_shuffle"])
        cv("GerudoKeys", data["gerudo_fortress_key_shuffle"])
        cv("BossKeysanity", data["boss_key_shuffle"])
        cv("ShuffleKeyRings", data["key_rings"])
        cv("ShuffleKeyRingsRandomCount", data["key_rings_count"])
        for ap_key, cvar_key in (
            ("gerudo_fortress_key_ring", "ShuffleKeyRingsGerudoFortress"),
            ("forest_temple_key_ring", "ShuffleKeyRingsForestTemple"),
            ("fire_temple_key_ring", "ShuffleKeyRingsFireTemple"),
            ("water_temple_key_ring", "ShuffleKeyRingsWaterTemple"),
            ("spirit_temple_key_ring", "ShuffleKeyRingsSpiritTemple"),
            ("shadow_temple_key_ring", "ShuffleKeyRingsShadowTemple"),
            ("bottom_of_the_well_key_ring", "ShuffleKeyRingsBottomOfTheWell"),
            ("gerudo_training_ground_key_ring", "ShuffleKeyRingsGTG"),
            ("ganons_castle_key_ring", "ShuffleKeyRingsGanonsCastle"),
        ):
            # Local selection is ternary No/Random/Yes. AP has already resolved
            # random/count into a final boolean per dungeon.
            cv(cvar_key, 2 if data[ap_key] else 0)

        # Quest skips and starting inventory.
        cv("BigPoeTargetCount", data["big_poe_target_count"])
        cv("SkipEponaRace", data["skip_epona_race"])
        cv("SkipScarecrowsSong", data["skip_scarecrows_song"])
        cv("LinksPocket", data["start_with_links_pocket"])
        cv("StartingKokiriSword", data["start_with_kokiri_sword"])
        cv("StartingDekuShield", data["start_with_deku_shield"])
        cv("StartingMasterSword", data["start_with_master_sword"])
        cv("StartingOcarina", data["start_with_ocarina"])
        cv("StartingSticks", data["start_with_stick_ammo"])
        cv("StartingNuts", data["start_with_nut_ammo"])
        cv("StartingBeans", data["start_with_magic_beans"])
        for ap_key, cvar_key in (
            ("start_with_zeldas_lullaby", "StartingZeldasLullaby"),
            ("start_with_eponas_song", "StartingEponasSong"),
            ("start_with_sarias_song", "StartingSariasSong"),
            ("start_with_suns_song", "StartingSunsSong"),
            ("start_with_song_of_time", "StartingSongOfTime"),
            ("start_with_song_of_storms", "StartingSongOfStorms"),
            ("start_with_minuet", "StartingMinuetOfForest"),
            ("start_with_bolero", "StartingBoleroOfFire"),
            ("start_with_serenade", "StartingSerenadeOfWater"),
            ("start_with_requiem", "StartingRequiemOfSpirit"),
            ("start_with_nocturne", "StartingNocturneOfShadow"),
            ("start_with_prelude", "StartingPreludeOfLight"),
        ):
            cv(cvar_key, data[ap_key])
        cv("FullWallets", data["full_wallets"])
        cv("BombchuBag", data["bombchu_bag"])
        cv("EnableBombchuDrops", data["bombchu_drops"])
        cv("BlueFireArrows", data["blue_fire_arrows"])
        cv("SunlightArrows", data["sunlight_arrows"])
        cv("RocsFeather", data["rocs_feather"])
        cv("InfiniteUpgrades", data["infinite_upgrades"])
        cv("SkeletonKey", data["skeleton_key"])
        cv("SlingBowBeehives", data["slingbow_break_beehives"])
        cv("StartingAge", data["starting_age"])
        cv("SelectedStartingAge", data["starting_age"])
        cv("Shuffle100GSReward", data["shuffle_100_gs_reward"])
        cv("StartingHearts", max(0, data["starting_hearts"] - 1))

        # Boss souls in current SoH split Ganon's soul out into its own setting.
        cv("ShuffleBossSouls", 1 if data["shuffle_boss_souls"] else 0)
        cv("ShuffleGanonsSoul", 3 if data["shuffle_boss_souls"] == 2 else 0)

        # Traps / logic / hints.
        # AP item_pool: balanced=0, plentiful=1, scarce=2, minimal=3.
        # Native SoH: plentiful=0, balanced=1, scarce=2, minimal=3.
        cv("ItemPool", {0: 1, 1: 0, 2: 2, 3: 3}.get(data["item_pool"], 1))
        cv("BaseIceTraps", 1)
        cv("AdditionalIceTraps", data["ice_trap_count"])
        cv("IceTrapPercent", data["ice_trap_filler_replacement"])
        cv("LogicRules", 1 if data.get("true_no_logic", 0) else 0)
        for ap_key, cvar_key in (
            ("hint_clarity", "HintClarity"), ("gossip_stone_hints", "GossipStoneHints"),
            ("tot_altar_hint", "AltarHint"), ("ganondorf_hint", "GanondorfHint"),
            ("sheik_la_hint", "SheikLAHint"), ("boss_key_hint", "BossKeyHint"),
            ("dampe_diary_hint", "DampeHint"), ("greg_hint", "GregHint"),
            ("saria_hint", "SariaHint"), ("mido_hint", "MidoHint"),
            ("frog_game_hint", "FrogsHint"), ("ocarina_of_time_hint", "OoTHint"),
            ("big_goron_hint", "BiggoronHint"), ("big_poe_hint", "BigPoesHint"),
            ("chicken_hint", "ChickensHint"), ("malon_hint", "MalonHint"),
            ("horseback_archery_hint", "HBAHint"), ("fishing_pole_hint", "FishingPoleHint"),
            ("scrub_hints", "ScrubText"), ("merchant_hints", "MerchantText"),
            ("gs_10_hint", "10GSHint"), ("gs_20_hint", "20GSHint"),
            ("gs_30_hint", "30GSHint"), ("gs_40_hint", "40GSHint"),
            ("gs_50_hint", "50GSHint"), ("gs_100_hint", "100GSHint"),
            ("mask_shop_hint", "MaskShopHint"),
        ):
            cv(cvar_key, data[ap_key])

        # Options which were split/removed in newer SoH builds. Preserve equivalent
        # local behavior using their replacement settings.
        if data["skip_child_zelda"]:
            cv("StartingZeldasLetter", 1)
            cv("ShuffleWeirdEgg", 2)  # Skip Talon path in current fork.
        if data["complete_mask_quest"]:
            cv("ShuffleMasks", 1)
            if data["complete_mask_quest"] == 1:
                for cvar_key in ("StartingKeatonMask", "StartingSkullMask", "StartingSpookyMask",
                                 "StartingBunnyHood", "StartingGoronMask", "StartingZoraMask",
                                 "StartingGerudoMask", "StartingMaskOfTruth"):
                    cv(cvar_key, 1)

        # Official Archipelago-SoH 1.4.x does not expose MQ regions. Never let an AP save
        # inherit local MQ selections, because that creates actors/checks the server cannot own.
        cv("MQDungeons", 0)
        for cvar_key in ("MQDekuTree", "MQDodongosCavern", "MQJabuJabu", "MQForestTemple",
                         "MQFireTemple", "MQWaterTemple", "MQSpiritTemple", "MQShadowTemple",
                         "MQBottomOfTheWell", "MQIceCavern", "MQGerudoTrainingGround", "MQGanonsCastle"):
            cv(cvar_key, 0)

        # SOH-EXTREME additions are part of the same authoritative snapshot.
        for key, value in {
            "ShuffleRoll": o.shuffle_roll.value, "ShuffleGrab": o.shuffle_grab.value,
            "ShuffleClimb": o.shuffle_climb.value, "ShuffleCrawl": o.shuffle_crawl.value,
            "ShuffleSpeak": o.shuffle_speak.value, "ShuffleOpenChest": o.shuffle_open_chest.value,
            "ShuffleEnemyDrops": o.shuffle_enemy_drops.value,
            "ShuffleEnemySoul": o.shuffle_enemy_soul.value, "EnemySoulBehavior": o.enemy_soul_behavior.value, "ShuffleNpcSoul": o.shuffle_npc_soul.value,
            "ShuffleAnimalSoul": o.shuffle_animal_soul.value, "ShufflePotSoul": o.shuffle_pot_soul.value,
            "ShuffleCrateSoul": o.shuffle_crate_soul.value, "ShuffleGrassSoul": o.shuffle_grass_bush_soul.value,
            "ShuffleRockSoul": o.shuffle_rock_boulder_soul.value, "ShuffleTreeSoul": o.shuffle_tree_soul.value,
            "ShuffleBeehiveSoul": o.shuffle_beehive_soul.value, "ShuffleSignSoul": o.shuffle_sign_soul.value,
            "ShuffleSkulltulaSoul": o.shuffle_skulltula_soul.value,
            "ShuffleBusinessScrubSoul": o.shuffle_business_scrub_soul.value,
            "ShuffleShovel": o.shuffle_shovel.value, "NpcSpeechSanity": o.npc_speech_sanity.value,
            "SongNoteShuffle": o.song_note_shuffle.value, "ShuffleFlowOfTime": o.shuffle_flow_of_time.value,
            "FrozenStartingTime": o.frozen_starting_time.value, "TimeSpeedAfterUnlock": o.time_speed_after_unlock.value,
            "ExtremeTrapPool": o.extreme_trap_pool.value, "ExtremeIceTraps": o.extreme_ice_traps.value,
            "ExtremeFireTraps": o.extreme_fire_traps.value, "ExtremeSlowTraps": o.extreme_slow_traps.value,
            "ExtremeMagicSuckTraps": o.extreme_magic_suck_traps.value,
            "ExtremeHealthDrainTraps": o.extreme_health_drain_traps.value,
            "ExtremeTrapPercent": o.extreme_trap_filler_replacement.value,
        }.items():
            cv(key, value)

        # Exact AP shop prices keyed by numeric location id. The native client applies
        # these after scouting so shop actors display/charge the server-generated price.
        shop_prices_by_id = {}
        for loc, price in self.shop_prices.items():
            loc_id = self.location_name_to_id.get(str(loc))
            if isinstance(loc_id, int):
                shop_prices_by_id[str(loc_id)] = int(price)

        # Publish every resolved YAML option as diagnostic/future-proof slot data.
        # The C++ client currently consumes extreme_soh_cvars for native settings,
        # but keeping the complete resolved option set in the slot guarantees no
        # SOH-EXTREME YAML setting is silently lost at the AP boundary.
        def _jsonable_option_value(value):
            if isinstance(value, set):
                return sorted(_jsonable_option_value(v) for v in value)
            if isinstance(value, tuple):
                return [_jsonable_option_value(v) for v in value]
            if isinstance(value, list):
                return [_jsonable_option_value(v) for v in value]
            if isinstance(value, dict):
                return {str(k): _jsonable_option_value(v) for k, v in value.items()}
            return value

        all_resolved_options = {}
        for field in dataclasses.fields(type(o)):
            option = getattr(o, field.name)
            all_resolved_options[field.name] = _jsonable_option_value(option.value)

        data.update({
            "extreme_all_options": all_resolved_options,
            "extreme_soh_cvars": cvars,
            "extreme_shop_prices": shop_prices_by_id,
            "extreme_kakariko_gate_open": int(bool(data["kakariko_gate"])),
            "extreme_active_locations": active_locations,
            "extreme_location_name_to_id": extreme_location_name_to_id,
            "shuffle_rocks": o.shuffle_rocks.value,
            "shuffle_boulders": o.shuffle_boulders.value,
            "shuffle_bushes": int(bool(o.shuffle_bushes.value) or o.shuffle_grass.value in (2, 3)),
            "shuffle_bushes_explicit": o.shuffle_bushes.value,
            "shuffle_icicles": o.shuffle_icicles.value,
            "shuffle_red_ice": o.shuffle_red_ice.value,
            "shuffle_signs": o.shuffle_signs.value,
            "shuffle_beggar": o.shuffle_beggar.value,
            "shuffle_chest_minigame": o.shuffle_chest_minigame.value,
            "shuffle_wonder_items": o.shuffle_wonder_items.value,
            "shuffle_silver": o.shuffle_silver.value,
            "shuffle_butterfly_fairies": o.shuffle_butterfly_fairies.value,
            "shuffle_roll": o.shuffle_roll.value,
            "shuffle_grab": o.shuffle_grab.value,
            "shuffle_climb": o.shuffle_climb.value,
            "shuffle_crawl": o.shuffle_crawl.value,
            "shuffle_speak": o.shuffle_speak.value,
            "shuffle_open_chest": o.shuffle_open_chest.value,
            "shuffle_enemy_drops": o.shuffle_enemy_drops.value,
            "shuffle_bean_souls": o.shuffle_bean_souls.value,
            "shuffle_enemy_soul": o.shuffle_enemy_soul.value,
            "enemy_soul_behavior": o.enemy_soul_behavior.value,
            "shuffle_npc_soul": o.shuffle_npc_soul.value,
            "shuffle_animal_soul": o.shuffle_animal_soul.value,
            "shuffle_pot_soul": o.shuffle_pot_soul.value,
            "shuffle_crate_soul": o.shuffle_crate_soul.value,
            "shuffle_grass_bush_soul": o.shuffle_grass_bush_soul.value,
            "shuffle_rock_boulder_soul": o.shuffle_rock_boulder_soul.value,
            "shuffle_tree_soul": o.shuffle_tree_soul.value,
            "shuffle_beehive_soul": o.shuffle_beehive_soul.value,
            "shuffle_sign_soul": o.shuffle_sign_soul.value,
            "shuffle_skulltula_soul": o.shuffle_skulltula_soul.value,
            "shuffle_business_scrub_soul": o.shuffle_business_scrub_soul.value,
            "shuffle_shovel": o.shuffle_shovel.value,
            "npc_speech_sanity": o.npc_speech_sanity.value,
            "song_note_shuffle": o.song_note_shuffle.value,
            "shuffle_flow_of_time": o.shuffle_flow_of_time.value,
            "frozen_starting_time": o.frozen_starting_time.value,
            "time_speed_after_unlock": o.time_speed_after_unlock.value,
            "death_link": o.death_link.value,
            "trap_link": o.trap_link.value,
            "extreme_trap_pool": o.extreme_trap_pool.value,
            "extreme_ice_traps": o.extreme_ice_traps.value,
            "extreme_fire_traps": o.extreme_fire_traps.value,
            "extreme_slow_traps": o.extreme_slow_traps.value,
            "extreme_magic_suck_traps": o.extreme_magic_suck_traps.value,
            "extreme_health_drain_traps": o.extreme_health_drain_traps.value,
            "extreme_trap_filler_replacement": o.extreme_trap_filler_replacement.value,
        })
        return data

# Register lazily: UT and Kivy are imported only when this component launches.
from .TrackerClient import register_launcher as _register_tracker_launcher
_register_tracker_launcher()
