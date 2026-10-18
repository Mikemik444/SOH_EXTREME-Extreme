"""Physical entrance pools. Two-way connections always remain coupled."""
from Options import Toggle, OptionSet, OptionGroup


class ShuffleInteriorEntrances(Toggle):
    """Shuffle houses, shops and other interiors, including multi-exit buildings."""
    display_name = "Shuffle Interior Entrances"


class ShuffleDungeonEntrances(Toggle):
    """Shuffle dungeon entrances, including Ganon's Castle. Return exits stay paired."""
    display_name = "Shuffle Dungeon Entrances"


class ShuffleGrottoEntrances(Toggle):
    """Shuffle grotto and grave entrances. Opening requirements stay at the entrance."""
    display_name = "Shuffle Grotto and Grave Entrances"


class ShuffleBossEntrances(Toggle):
    """Shuffle boss chambers. Boss exits and blue warps follow their paired connection."""
    display_name = "Shuffle Boss Chambers"


class ShuffleOneWayEntrances(Toggle):
    """Shuffle naturally one-way routes, such as the valley river and ranch fence exits.
    These routes never grant a reverse connection. Normal entrances remain coupled.
    """
    display_name = "Shuffle One-Way Entrances"


class ShuffleOwlDrops(Toggle):
    """Shuffle owl flight destinations. Flights are one-way and may share destinations."""
    display_name = "Shuffle Owl Destinations"


class ShuffleWarpSongs(Toggle):
    """Shuffle warp song destinations. Songs still require their notes, buttons and ocarina.
    Warps are one-way and may share destinations.
    """
    display_name = "Shuffle Warp Song Destinations"


class ShuffleChildSpawn(Toggle):
    """Shuffle child Link's starting and save-warp destination."""
    display_name = "Shuffle Child Spawn"


class ShuffleAdultSpawn(Toggle):
    """Shuffle adult Link's starting and save-warp destination."""
    display_name = "Shuffle Adult Spawn"


class ShuffleDungeonDoors(Toggle):
    """Shuffle physical dungeon room doors. Keys, switches and combat requirements
    remain on the source door. Two-way doors always have a paired return.
    """
    display_name = "Shuffle Dungeon Room Doors"


class MixedEntrancePools(OptionSet):
    """Categories that share destinations. Only enabled categories participate.
    Include dungeon_doors to mix room doors with scene entrances. One-way categories
    use this pool as destinations without creating reverse routes or consuming a
    two-way destination. An empty set keeps categories separate.
    """
    display_name = "Mixed Entrance Pools"
    valid_keys = frozenset(("interiors", "dungeons", "grottos", "bosses", "one_ways",
                           "owls", "warp_songs", "child_spawn", "adult_spawn", "dungeon_doors"))
    default = frozenset()


ENTRANCE_OPTIONS = {
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
ENTRANCE_GROUP = OptionGroup("SOH-EXTREME Entrance Randomizer", list(ENTRANCE_OPTIONS.values()))
