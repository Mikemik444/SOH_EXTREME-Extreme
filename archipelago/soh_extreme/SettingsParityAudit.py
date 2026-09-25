"""Static SOH-EXTREME setting/check coverage metadata.

Runtime generation also performs the active setting-family audit in
SohExtremeWorld.create_items().  This module is deliberately data-only so it can
be inspected without an Archipelago install.
"""

FORK_SETTING_FAMILIES = {
    "shuffle_rocks": "rock",
    "shuffle_boulders": "boulder",
    "shuffle_bushes/shuffle_grass": "bush",
    "shuffle_icicles": "icicle",
    "shuffle_red_ice": "red_ice",
    "shuffle_signs": "sign",
    "shuffle_beggar": "beggar",
    "shuffle_chest_minigame": "chest_minigame",
    "shuffle_wonder_items": "wonder",
    "shuffle_silver": "silver",
    "shuffle_butterfly_fairies": "butterfly_fairy",
}

IMPORTANT_EXTREME_SYSTEMS = {
    "abilities": ("Roll", "Grab / Power Bracelet", "Climb", "Crawl", "Open Chest", "Shovel", "Flow of Time"),
    "souls": "all enabled EXTREME Soul items",
    "speech": ("Speak", "Speak Deku", "Speak Gerudo", "Speak Goron", "Speak Hylian", "Speak Kokiri", "Speak Zora"),
    "song_notes": "Song Note 01..74",
    "silver_rupees": "all active native silver group items",
}
