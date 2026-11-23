"""Physical entrances blocked by movable/breakable boulders or covering rocks.

These IDs refer to *source* openings in EntranceCatalog.json.  Their
Rock/Boulder Soul requirement must travel with the source when shuffled.  A
reverse path into the overworld is never made Soul-dependent just because its
vanilla counterpart was covered by a boulder.

Do not place generic bombable ground holes, Song of Storms holes, tree holes,
or bombable *walls* here unless a real rock/boulder blocks that doorway.
"""

# 4: DMT rock outside Dodongo's Cavern (BgSpot16Bombstone)
# 1214: DMC Great Fairy entrance, Hammer boulders
# 1400: HC Boulder Crawlspace to Din's Fire fountain
# Grottos: uncovered by rock/boulder or Silver Gauntlets/Hammer.
# 1817/1818 are Lost Woods grottos hidden under rock obstructions.
BOULDER_BLOCKED_ENDPOINTS = frozenset({
    4, 1214, 1400,
    1792, 1795, 1797, 1798, 1801, 1807, 1808, 1812, 1817, 1818, 1823,
})

# Identity for the Scene Transition checks attached to source crossings.
BOULDER_BLOCKED_SCENE_CHECKS = frozenset(11000000 + eid for eid in BOULDER_BLOCKED_ENDPOINTS)
