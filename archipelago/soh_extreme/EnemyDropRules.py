"""Age-specific combat and physical encounter gates for the finite spawn catalogue.

The catalogue's parent region supplies traversal. No location is made reachable
from Menu, or matched by death position. Dungeon checks use the native room/floor graph exported with this release.
Room traversal and encounter activation are distinct from the enemy kill rule.
"""
from rule_builder.rules import Has, And, Or, True_, False_
from Options import OptionError
from ._vendor_oot_soh.Enums import Regions, Items, Tricks
from ._vendor_oot_soh.LogicHelpers import (
    can_use, has_item, has_explosives, is_child, is_adult,
    has_fire_source_with_torch, can_play_song, can_do_trick, can_talk_hint_scrub,
)
from .EnemyRoomLogic import resolve_enemy_region, event_item, ENEMY_ROOM_MAP


def enemy_drop_rule(world, entry):
    o = world.options
    region = resolve_enemy_region(entry.region_token)
    if region is None:
        raise OptionError(f"No physical AP region for {entry.name}: {entry.region_token}")
    b = (region, world)
    gates = []
    room = ENEMY_ROOM_MAP.get(str(entry.address))
    if room is not None:
        if room['native_region'] != entry.region_token:
            raise OptionError(f"Mismatched native enemy room mapping: {entry.name}")
        gates.append(world._extreme_room_compiler.expr(room['condition'], entry.region_token))
    if entry.actor_id in (0x037, 0x095):
        if o.shuffle_skulltula_soul.value:
            gates.append(Has("Skulltula Soul"))
    elif o.shuffle_enemy_soul.value == 1:
        gates.append(Has("Enemy Soul"))
    elif o.shuffle_enemy_soul.value == 2:
        if not entry.soul_item:
            raise OptionError(f"Missing enemy soul mapping: {entry.name}")
        gates.append(Has(entry.soul_item))
    if entry.soul_item == "Flying Pot Soul" and o.shuffle_pot_soul.value:
        gates.append(Has("Pot Soul"))
    if entry.actor_id == 0x192:  # En_Hintnuts: defeat fires after the conversation.
        gates.append(can_talk_hint_scrub(b))
    if entry.grotto_id >= 0 and o.shuffle_shovel.value:
        gates.append(Has("Shovel"))

    # Build each branch from only that age's usable weapons. Combining a generic
    # "child reachable" with an independently adult-reachable Bow was unsound.
    def age_combat(adult):
        sword = (can_use(Items.MASTER_SWORD, b) | can_use(Items.BIGGORONS_SWORD, b)) if adult else can_use(Items.KOKIRI_SWORD, b)
        melee = sword | (can_use(Items.MEGATON_HAMMER, b) if adult else can_use(Items.STICKS, b))
        sticks = can_use(Items.STICKS, b) if not adult else False_()
        hammer = can_use(Items.MEGATON_HAMMER, b) if adult else False_()
        sling = can_use(Items.FAIRY_SLINGSHOT, b) if not adult else False_()
        nuts = can_use(Items.NUTS, b)
        bow = can_use(Items.FAIRY_BOW, b) if adult else False_()
        hook = can_use(Items.HOOKSHOT, b) if adult else False_()
        rang = can_use(Items.BOOMERANG, b) if not adult else False_()
        ranged = (bow | hook | can_use(Items.LONGSHOT, b)) if adult else (can_use(Items.FAIRY_SLINGSHOT, b) | rang)
        explosive = has_explosives(b)
        fire = can_use(Items.DINS_FIRE, b) | (can_use(Items.FIRE_ARROW, b) if adult else False_())
        reflect = can_use(Items.HYLIAN_SHIELD, b) if adult else can_use(Items.DEKU_SHIELD, b)
        # Enemy-specific damage and activation rules, reviewed against the actor
        # damage tables and native CanKillEnemy. A stunning hit is not a kill.
        standing_shield = (can_use(Items.HYLIAN_SHIELD, b) | can_use(Items.MIRROR_SHIELD, b)) if adult else reflect
        combat = {
            "sword": sword,
            "tektite": melee | sling | bow,
            "peahat": melee | sling | bow | hook,
            "shabom": melee | rang | nuts | can_use(Items.DINS_FIRE, b) | (can_use(Items.ICE_ARROW, b) if adult else False_()),
            "jellyfish": rang | bow | hook,
            "tailpasaran": rang | sticks,
            "stinger": sling | bow | hook,
            "bubble": melee | sling | bow | explosive,
            "blue_bubble": explosive | hammer | bow | ((sword | sticks | sling) & (nuts | hook | rang | standing_shield)),
            "armos": explosive | hammer | bow | sticks | (sword if adult else (sword & (nuts | hook | rang))),
            "dead_hand": sword | (sticks & can_do_trick(Tricks.BOTW_CHILD_DEADHAND, b)),
            "dead_hand_arm": sword | sticks,
            "spike": (sword if adult else False_()) | hammer | sticks | hook | bow | explosive | can_use(Items.DINS_FIRE, b),
            "freezard": (sword if adult else False_()) | hammer | sticks | hook | explosive | fire,
            "contact": True_(), "melee": melee, "ranged": ranged,
            "ranged_or_melee": ranged | melee, "reflect_nuts": reflect,
            "explosive": explosive, "explosive_or_melee": explosive | melee,
            "hookshot_and_melee": hook & melee, "hookshot_or_melee": hook | melee,
            "boomerang_and_melee": rang & melee, "boomerang": rang,
            "sword_or_boomerang": sword | rang,
            "fire": fire, "fire_or_melee": fire | melee, "bow": bow,
        }.get(entry.combat)
        if combat is None:
            raise OptionError(f"Unknown enemy combat rule {entry.combat!r} for {entry.name}")
        if entry.encounter_gate == "peahat_larva":
            combat &= melee
        return combat

    def time_available(night):
        if not o.shuffle_flow_of_time.value:
            return True_()
        # Dusk freezes at 0xB555, before the engine's >0xC000 night boundary.
        starts_night = o.frozen_starting_time.value == 4
        return True_() if starts_night == night else (Has("Flow of Time") | can_play_song(Items.SUNS_SONG, b))

    ages = []
    for adult in (False, True):
        mask = (entry.spawn_mask >> (2 if adult else 0)) & 3
        if not mask:
            continue
        tod = True_() if mask == 3 else time_available(mask == 2)
        ages.append((is_adult(b) if adult else is_child(b)) & tod & age_combat(adult))
    gates.append(Or(*ages) if ages else False_())

    # En_Peehat remains loaded at night, but both adult Peahat variants stay
    # buried and only spawn larvae when struck. Defeating those offspring does
    # not complete the parent placement's check. Spawn presence is not the
    # same as being able to expose and defeat its vulnerable root.
    if entry.actor_id == 0x01D:
        gates.append(time_available(False))

    def grab():
        return Has("Grab / Power Bracelet") if o.shuffle_grab.value else True_()

    gate = entry.encounter_gate
    if gate == "amy":
        gates.append(grab())
    elif gate == "meg":
        gates.extend(Has(event_item(event)) for event in (
            "LOGIC_FOREST_JOELLE", "LOGIC_FOREST_BETH", "LOGIC_FOREST_AMY"))
    elif gate == "forest_block_top":
        gates.extend((is_adult(b), has_item(Items.GORONS_BRACELET, b)))
        if o.shuffle_climb.value:
            gates.append(Has("Climb"))
    elif gate == "coffin":
        gates.append(has_fire_source_with_torch(b) | can_use(Items.FAIRY_BOW, b))
    elif gate == "composer":
        if o.shuffle_npc_soul.value:
            gates.append(Has("NPC Soul"))
        if o.shuffle_speak.value:
            gates.append(Has("Speak" if o.shuffle_speak.value == 1 else "Speak Hylian"))
    elif gate == "grave":
        gates.append(grab())
    elif gate == "swim":
        gates.append(has_item(Items.BRONZE_SCALE, b))
    elif gate == "gv_lower_current":
        # The dry ledge is outside these Octoroks' surfacing range. Swim only
        # reaches the current; Iron Boots provide footing inside that range.
        # Player_UseItem permits Hookshot/Longshot underwater while grounded,
        # not Bow. can_use(IRON_BOOTS) retains EXTREME's Swim requirement.
        gates.append(can_use(Items.IRON_BOOTS, b) & can_use(Items.HOOKSHOT, b))
    elif gate == "night":
        gates.append(time_available(True))
    elif gate not in ("", "anubis", "sfm_moblin", "peahat_larva"):
        raise OptionError(f"Unknown encounter gate {gate!r} for {entry.name}")

    # Room-specific switches, block approaches and earlier combat rooms are
    # inherited from the native graph. Do not require Slingshot for the first
    # Baby Dodongos or confuse the boss-maze rooms with the upper Lizalfos loop.
    if entry.scene_id == 0x0C:
        gates.append(has_item(Items.GERUDO_MEMBERSHIP_CARD, b))
    # Ruto must be able to reach/activate the Big Octo platform.
    if entry.soul_item == "Big Octo Soul":
        gates.append(grab())
        if o.shuffle_npc_soul.value:
            gates.append(Has("NPC Soul"))
        if o.shuffle_speak.value:
            gates.append(Has("Speak" if o.shuffle_speak.value == 1 else "Speak Zora"))
    return And(*gates)
