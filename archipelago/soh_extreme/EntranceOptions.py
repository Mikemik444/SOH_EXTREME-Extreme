"""Physical entrance pools. Two-way connections always remain coupled."""
from Options import Toggle, OptionSet, OptionGroup


class ShuffleOverworldEntrances(Toggle):
    """Experimental. Shuffle connections between overworld areas, including Goron City,
    Death Mountain Trail and Death Mountain Crater. Return exits stay paired.
    """
    display_name = "Shuffle Overworld Entrances (Experimental)"


class ShuffleInteriorEntrances(Toggle):
    """Experimental. Shuffle houses, shops and other interiors, including multi-exit buildings."""
    display_name = "Shuffle Interior Entrances (Experimental)"


class ShuffleDungeonEntrances(Toggle):
    """Experimental. Shuffle dungeon entrances, including Ganon's Castle. Return exits stay paired."""
    display_name = "Shuffle Dungeon Entrances (Experimental)"


class ShuffleGrottoEntrances(Toggle):
    """Experimental. Shuffle grotto and grave entrances. Opening requirements stay at the entrance."""
    display_name = "Shuffle Grotto and Grave Entrances (Experimental)"


class ShuffleBossEntrances(Toggle):
    """Experimental. Shuffle boss chambers. Boss exits and blue warps follow their paired connection."""
    display_name = "Shuffle Boss Chambers (Experimental)"


class ShuffleOneWayEntrances(Toggle):
    """Experimental. Shuffle naturally one-way routes, such as the valley river and ranch fence exits.
    These routes never grant a reverse connection. Normal entrances remain coupled.
    """
    display_name = "Shuffle One-Way Entrances (Experimental)"


class ShuffleOwlDrops(Toggle):
    """Experimental. Shuffle owl flight destinations. Flights are one-way and may share destinations."""
    display_name = "Shuffle Owl Destinations (Experimental)"


class ShuffleWarpSongs(Toggle):
    """Experimental. Shuffle warp song destinations. Songs still require their notes, buttons and ocarina.
    Warps are one-way and may share destinations.
    """
    display_name = "Shuffle Warp Song Destinations (Experimental)"


class ShuffleChildSpawn(Toggle):
    """Experimental. Shuffle child Link's starting and save-warp destination.
    Each enabled age's location must have a usable return and reach Hyrule
    Field as that age with the configured starting inventory. Later entrance
    swaps preserve both ages' escape routes. Both age spawns avoid Water Temple
    arrivals without starting Swim when that ability is shuffled.
    """
    display_name = "Shuffle Child Spawn (Experimental)"


class ShuffleAdultSpawn(Toggle):
    """Experimental. Shuffle adult Link's starting and save-warp destination.
    Each enabled age's location must have a usable return and reach Hyrule
    Field as that age with the configured starting inventory. Later entrance
    swaps preserve both ages' escape routes. Both age spawns avoid Water Temple
    arrivals without starting Swim when that ability is shuffled.
    """
    display_name = "Shuffle Adult Spawn (Experimental)"


class ShuffleDungeonDoors(Toggle):
    """Experimental. Shuffle physical dungeon room doors. Keys, switches and combat requirements
    remain on the source door. Two-way doors always have a paired return.
    Six Jabu-Jabu doors needed to carry Ruto keep their normal room connections
    and traversal checks, so her rescue and puzzle routes remain playable.
    Logic conservatively requires a dungeon's complete small-key set (or its
    key ring / Skeleton Key) for shuffled small-key doors, since keys can be
    spent on different branches. Individual keys still work normally in-game.
    """
    display_name = "Shuffle Dungeon Room Doors (Experimental)"


class MixedEntrancePools(OptionSet):
    """Experimental. Categories that share destinations. Only enabled categories participate.
    Use all to mix every enabled category; disabled shuffles stay disabled.
    Include dungeon_doors to mix room doors with scene entrances. One-way categories
    use this pool as destinations without creating reverse routes or consuming a
    two-way destination. An empty set keeps categories separate. Destinations
    use reviewed normal scene setups; cutscene-only, debug, and unused entries
    are excluded. Age-specific physical returns are checked in the mixed graph.
    """
    display_name = "Mixed Entrance Pools (Experimental)"
    valid_keys = frozenset(("all", "overworld", "interiors", "dungeons", "grottos", "bosses", "one_ways",
                           "owls", "warp_songs", "child_spawn", "adult_spawn", "dungeon_doors"))
    default = frozenset()


ENTRANCE_OPTIONS = {
    "shuffle_overworld_entrances": ShuffleOverworldEntrances,
    "shuffle_interior_entrances": ShuffleInteriorEntrances,
    "shuffle_dungeon_entrances": ShuffleDungeonEntrances,
    "shuffle_grotto_entrances": ShuffleGrottoEntrances,
    "shuffle_boss_entrances": ShuffleBossEntrances,
    "shuffle_one_way_entrances": ShuffleOneWayEntrances,
    "shuffle_owl_drops": ShuffleOwlDrops,
    "shuffle_warp_songs": ShuffleWarpSongs,
    "shuffle_child_spawn": ShuffleChildSpawn,
    "shuffle_adult_spawn": ShuffleAdultSpawn,
    "shuffle_dungeon_doors": ShuffleDungeonDoors,
    "mixed_entrance_pools": MixedEntrancePools,
}
ENTRANCE_GROUP = OptionGroup("Entrance Randomizer (Experimental)", list(ENTRANCE_OPTIONS.values()))
