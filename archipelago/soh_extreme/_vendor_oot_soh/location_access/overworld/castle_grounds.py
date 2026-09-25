from ...LogicHelpers import *

if TYPE_CHECKING:
    from ... import SohWorld


class EventLocations(StrEnum):
    HC_GOSSIP_STONE_SONG_FAIRY = "HC Gossip Stone Song Fairy"
    HC_BUTTERFLY_FAIRY = "HC Butterfly Fairy"
    HC_BUG_ROCK = "HC Bug Rock"
    HC_STORMS_GROTTO_BEHIND_WALLS_NUT_POT = "HC Storms Grotto Behind Walls Nut Pot"
    HC_STORMS_GROTTO_BEHIND_WALLS_GOSSIP_STONE_SONG_FAIRY = "HC Storms Grotto Behind Walls Gossip Stone Song Fairy"
    HC_STORMS_GROTTO_BEHIND_WALLS_WANDERING_BUGS = "HC Storms Grotto Behind Walls Wandering Bugs"
    HC_OGC_RAINBOW_BRIDGE = "HC OGC Rainbow Bridge"
    HC_DAY_NIGHT_CYCLE_CHILD = "HC Day Night Cycle Child"


class LocalEvents(StrEnum):
    HC_OGC_RAINBOW_BRIDGE_BUILT = "HC OGC Rainbow Bridge Built"


def set_region_rules(world: "SohWorld") -> None:
    # Castle Grounds
    # Connections
    connect_regions(Regions.CASTLE_GROUNDS, world, [
        (Regions.MARKET, lambda bundle: True_()),
        (Regions.HYRULE_CASTLE_GROUNDS, lambda bundle: is_child(bundle)),
        (Regions.GANONS_CASTLE_GROUNDS, lambda bundle: is_adult(bundle))
    ])

    # EXTREME uses separate physical approach regions. Skip Child Zelda grants
    # the quest flags and Impa's starting reward, NOT access past the castle gate.
    # Keep the same regions for generation and Universal Tracker regeneration.
    options = world.options
    climb = Has("Climb") if options.shuffle_climb.value else True_()
    grab = Has("Grab / Power Bracelet") if options.shuffle_grab.value else True_()
    crawl = Has("Crawl") if options.shuffle_crawl.value else True_()
    npc = Has("NPC Soul") if options.shuffle_npc_soul.value else True_()
    speak = (Has("Speak Hylian") if options.shuffle_speak.value == 2 else
             Has("Speak") if options.shuffle_speak.value == 1 else True_())
    butterfly = (Has("Butterfly Soul") if options.shuffle_animal_soul.value == 2 else
                 Has("Animal Soul") if options.shuffle_animal_soul.value == 1 else True_())

    # Front of the castle gate: Malon, small rocks, and the climbable tree.
    add_events(Regions.HYRULE_CASTLE_GROUNDS, world, [
        (EventLocations.HC_BUG_ROCK, Events.CAN_ACCESS_BUGS, lambda b: grab),
        (EventLocations.HC_DAY_NIGHT_CYCLE_CHILD,
         Events.CHILD_CAN_PASS_TIME, lambda b: is_child(b)),
    ])
    add_locations(Regions.HYRULE_CASTLE_GROUNDS, world, [
        (Locations.HC_MALON_EGG, lambda b: npc & speak),
        (Locations.HC_GS_TREE, lambda b: climb & can_bonk_trees(b) &
         can_kill_enemy(b, Enemies.GOLD_SKULLTULA, EnemyDistance.CLOSE)),
        (Locations.HC_SKULLTULA_TREE, lambda b: climb & can_bonk_trees(b)),
    ])
    connect_regions(Regions.HYRULE_CASTLE_GROUNDS, world, [
        (Regions.CASTLE_GROUNDS, lambda b: True_()),
        (Regions.HC_ABOVE_VINE, lambda b: climb | can_use(Items.HOOKSHOT, b)),
        # Bribing the actual guard is not possible when the actor is absent.
        (Regions.HC_PAST_GATE, lambda b: npc & speak & has_item(Items.CHILD_WALLET, b)),
    ])

    add_locations(Regions.HC_ABOVE_VINE, world, [
        (Locations.HC_MALON_GOSSIP_STONE_FAIRY, lambda b: call_gossip_fairy(b)),
        (Locations.HC_MALON_GOSSIP_STONE_BIG_FAIRY, lambda b: can_use(Items.SONG_OF_STORMS, b)),
    ])
    connect_regions(Regions.HC_ABOVE_VINE, world, [
        (Regions.HYRULE_CASTLE_GROUNDS, lambda b: True_()),
        (Regions.HC_PAST_GATE, lambda b: True_()),
    ])

    add_events(Regions.HC_PAST_GATE, world, [
        (EventLocations.HC_BUTTERFLY_FAIRY, Events.CAN_ACCESS_FAIRIES,
         lambda b: climb & butterfly & can_use(Items.STICKS, b)),
    ])
    add_locations(Regions.HC_PAST_GATE, world, [
        (Locations.HC_NEAR_GUARDS_TREE_1, lambda b: climb & can_bonk_trees(b)),
        (Locations.HC_NEAR_GUARDS_TREE_2, lambda b: climb & can_bonk_trees(b)),
        (Locations.HC_NEAR_GUARDS_TREE_3, lambda b: climb & can_bonk_trees(b)),
        (Locations.HC_NEAR_GUARDS_TREE_4, lambda b: climb & can_bonk_trees(b)),
        (Locations.HC_NEAR_GUARDS_TREE_5, lambda b: climb & can_bonk_trees(b)),
        (Locations.HC_NEAR_GUARDS_TREE_6, lambda b: climb & can_bonk_trees(b)),
    ])
    connect_regions(Regions.HC_PAST_GATE, world, [
        (Regions.HYRULE_CASTLE_GROUNDS, lambda b: True_()),
        (Regions.HC_ABOVE_VINE, lambda b: climb | can_use(Items.HOOKSHOT, b)),
        (Regions.HC_ABOVE_CLIMBABLE_ROCKS, lambda b: climb | can_use(Items.HOOKSHOT, b)),
        (Regions.HC_GREAT_FAIRY_FOUNTAIN, lambda b: blast_or_smash(b) & crawl),
    ])

    add_events(Regions.HC_ABOVE_CLIMBABLE_ROCKS, world, [
        (EventLocations.HC_GOSSIP_STONE_SONG_FAIRY, Events.CAN_ACCESS_FAIRIES,
         lambda b: call_gossip_fairy(b)),
    ])
    add_locations(Regions.HC_ABOVE_CLIMBABLE_ROCKS, world, [
        (Locations.HC_ROCK_WALL_GOSSIP_STONE_FAIRY, lambda b: call_gossip_fairy(b)),
        (Locations.HC_ROCK_WALL_GOSSIP_STONE_BIG_FAIRY, lambda b: can_use(Items.SONG_OF_STORMS, b)),
    ])
    connect_regions(Regions.HC_ABOVE_CLIMBABLE_ROCKS, world, [
        (Regions.HC_PAST_GATE, lambda b: True_()),
        (Regions.HC_MOAT, lambda b: True_()),
    ])

    # Skip Zelda starts with Talon gone. Otherwise the egg and the actual
    # NPC/language interaction are required before pushing his milk crates.
    def drain_route(b):
        talon_gone = True_() if options.skip_child_zelda.value else (npc & speak & can_use(Items.WEIRD_EGG, b))
        return ((talon_gone & grab) | can_use(Items.HOVER_BOOTS, b) |
                (can_do_trick(Tricks.DAMAGE_BOOST_SIMPLE, b) & has_explosives(b) & can_jump_slash(b)))

    add_locations(Regions.HC_MOAT, world, [
        (Locations.HC_NEAR_STORMS_GROTTO_GRASS1, lambda b: can_collect_grass(b)),
        (Locations.HC_NEAR_STORMS_GROTTO_GRASS2, lambda b: can_collect_grass(b)),
        (Locations.HC_GROTTO_TREE, lambda b: climb & can_bonk_trees(b)),
    ])
    connect_regions(Regions.HC_MOAT, world, [
        (Regions.HYRULE_CASTLE_GROUNDS, lambda b: True_()),
        (Regions.HC_STORMS_GROTTO, lambda b: can_open_storms_grotto(b)),
        (Regions.HC_DRAIN_LEDGE, drain_route),
    ])
    connect_regions(Regions.HC_DRAIN_LEDGE, world, [
        (Regions.HC_MOAT, lambda b: True_()),
        (Regions.HC_GARDEN, lambda b: crawl),
    ])
    add_locations(Regions.HC_GARDEN, world, [
        (Locations.HC_ZELDAS_LETTER, lambda b: npc & speak),
        (Locations.SONG_FROM_IMPA, lambda b: npc & speak),
    ])
    connect_regions(Regions.HC_GARDEN, world, [
        (Regions.HC_DRAIN_LEDGE, lambda b: True_()),
    ])

    # Hyrule Castle Great Fairy Fountain
    # Locations
    add_locations(Regions.HC_GREAT_FAIRY_FOUNTAIN, world, [
        (Locations.HC_GREAT_FAIRY_REWARD,
         lambda bundle: can_use(Items.ZELDAS_LULLABY, bundle))
    ])
    # Connections
    connect_regions(Regions.HC_GREAT_FAIRY_FOUNTAIN, world, [
        (Regions.HC_PAST_GATE, lambda bundle: True_())
    ])

    # Hyrule Castle Storms Grotto
    # Connections
    connect_regions(Regions.HC_STORMS_GROTTO, world, [
        (Regions.HC_MOAT, lambda bundle: True_()),
        (Regions.HC_STORMS_GROTTO_BEHIND_WALLS,
         lambda bundle: can_break_mud_walls(bundle)),
        (Regions.HC_STORMS_SKULLTULA, lambda bundle: can_use(
            Items.BOOMERANG, bundle) & can_do_trick(Tricks.HC_STORMS_GS, bundle))
    ])

    # Hyrule Castle Storms Grotto Behind Walls
    # Events
    add_events(Regions.HC_STORMS_GROTTO_BEHIND_WALLS, world, [
        (EventLocations.HC_STORMS_GROTTO_BEHIND_WALLS_NUT_POT,
         Events.CAN_FARM_NUTS, lambda bundle: can_break_pots(bundle)),
        (EventLocations.HC_STORMS_GROTTO_BEHIND_WALLS_GOSSIP_STONE_SONG_FAIRY, Events.CAN_ACCESS_FAIRIES,
         lambda bundle: call_gossip_fairy(bundle)),
        (EventLocations.HC_STORMS_GROTTO_BEHIND_WALLS_WANDERING_BUGS,
         Events.CAN_ACCESS_BUGS, lambda bundle: True_())

    ])
    # Locations
    add_locations(Regions.HC_STORMS_GROTTO_BEHIND_WALLS, world, [
        (Locations.HC_STORMS_GROTTO_GOSSIP_STONE_FAIRY,
         lambda bundle: call_gossip_fairy(bundle)),
        (Locations.HC_STORMS_GROTTO_GOSSIP_STONE_BIG_FAIRY,
         lambda bundle: can_use(Items.SONG_OF_STORMS, bundle)),
        (Locations.HC_STORMS_GROTTO_POT1, lambda bundle: can_break_pots(bundle)),
        (Locations.HC_STORMS_GROTTO_POT2, lambda bundle: can_break_pots(bundle)),
        (Locations.HC_STORMS_GROTTO_POT3, lambda bundle: can_break_pots(bundle)),
        (Locations.HC_STORMS_GROTTO_POT4, lambda bundle: can_break_pots(bundle))
    ])
    # Connections
    connect_regions(Regions.HC_STORMS_GROTTO_BEHIND_WALLS, world, [
        (Regions.HC_STORMS_GROTTO, lambda bundle: True_()),
        (Regions.HC_STORMS_SKULLTULA, lambda bundle: hookshot_or_boomerang(bundle)),
    ])

    # Hyrule Castle Storms Skulltule
    # This is a deviation from the original SOH logic because of the union of locations
    # Locations
    add_locations(Regions.HC_STORMS_SKULLTULA, world, [
        (Locations.HC_GS_STORMS_GROTTO, lambda bundle: True_())
    ])

    # Ganon's Castle Grounds
    # Events
    add_events(Regions.GANONS_CASTLE_GROUNDS, world, [
        (EventLocations.HC_OGC_RAINBOW_BRIDGE, LocalEvents.HC_OGC_RAINBOW_BRIDGE_BUILT,
         lambda bundle: can_build_rainbow_bridge(bundle))
    ])
    # Locations
    add_locations(Regions.GANONS_CASTLE_GROUNDS, world, [
        (Locations.HC_OGC_GS, lambda bundle: can_jump_slash_except_hammer(bundle) |
         can_use_projectile(bundle) |
         (can_shield(bundle) & can_use(Items.MEGATON_HAMMER, bundle)) |
         can_use(Items.DINS_FIRE, bundle))
    ])
    # Connections
    connect_regions(Regions.GANONS_CASTLE_GROUNDS, world, [
        (Regions.CASTLE_GROUNDS, lambda bundle: at_night(bundle)),
        (Regions.OGC_GREAT_FAIRY_FOUNTAIN, lambda bundle: can_use(
            Items.GOLDEN_GAUNTLETS, bundle) & at_night(bundle)),
        (Regions.GANONS_CASTLE_LEDGE, lambda bundle: has_item(
            LocalEvents.HC_OGC_RAINBOW_BRIDGE_BUILT, bundle))
    ])

    # OGC Great Fairy Fountain
    # Locations
    add_locations(Regions.OGC_GREAT_FAIRY_FOUNTAIN, world, [
        (Locations.OGC_GREAT_FAIRY_REWARD,
         lambda bundle: can_use(Items.ZELDAS_LULLABY, bundle))
    ])
    # Connections
    connect_regions(Regions.OGC_GREAT_FAIRY_FOUNTAIN, world, [
        (Regions.CASTLE_GROUNDS, lambda bundle: True_())
    ])

    # Castle Grounds from Ganon's Castle
    # Connections
    connect_regions(Regions.CASTLE_GROUNDS_FROM_GANONS_CASTLE, world, [
        (Regions.HC_DRAIN_LEDGE, lambda bundle: is_child(bundle)),
        (Regions.GANONS_CASTLE_LEDGE, lambda bundle: is_adult(bundle))
    ])

    # Ganon's Castle Ledge
    # Connections
    connect_regions(Regions.GANONS_CASTLE_LEDGE, world, [
        (Regions.GANONS_CASTLE_GROUNDS, lambda bundle: has_item(
            LocalEvents.HC_OGC_RAINBOW_BRIDGE_BUILT, bundle)),
        (Regions.GANONS_CASTLE_ENTRYWAY, lambda bundle: is_adult(bundle))
    ])
