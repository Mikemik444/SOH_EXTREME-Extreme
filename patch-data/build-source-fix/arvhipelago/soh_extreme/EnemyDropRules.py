"""Age-specific combat and physical encounter gates for the finite spawn catalogue.

The catalogue's parent region supplies traversal. No location is made reachable
from Menu, or matched by death position. Dungeon checks use the native room/floor graph exported with this release.
Room traversal and encounter activation are distinct from the enemy kill rule.
"""
from rule_builder.rules import Has, And, Or, True_, False_
from Options import OptionError
from ._vendor_oot_soh.Enums import Regions, Items
from ._vendor_oot_soh.LogicHelpers import (
    can_use, has_item, has_explosives, is_child, is_adult,
    has_fire_source_with_torch,
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
    if entry.grotto_id >= 0 and o.shuffle_shovel.value:
        gates.append(Has("Shovel"))

    # Build each branch from only that age's usable weapons. Combining a generic
    # "child reachable" with an independently adult-reachable Bow was unsound.
    def age_combat(adult):
        sword = (can_use(Items.MASTER_SWORD, b) | can_use(Items.BIGGORONS_SWORD, b)) if adult else can_use(Items.KOKIRI_SWORD, b)
        melee = sword | (can_use(Items.MEGATON_HAMMER, b) if adult else can_use(Items.STICKS, b))
        bow = can_use(Items.FAIRY_BOW, b) if adult else False_()
        hook = can_use(Items.HOOKSHOT, b) if adult else False_()
        rang = can_use(Items.BOOMERANG, b) if not adult else False_()
        ranged = (bow | hook | can_use(Items.LONGSHOT, b)) if adult else (can_use(Items.FAIRY_SLINGSHOT, b) | rang)
        explosive = has_explosives(b)
        fire = can_use(Items.DINS_FIRE, b) | (can_use(Items.FIRE_ARROW, b) if adult else False_())
        reflect = can_use(Items.HYLIAN_SHIELD, b) if adult else can_use(Items.DEKU_SHIELD, b)
        combat = {
            "contact": True_(), "melee": melee, "ranged": ranged,
            "ranged_or_melee": ranged | melee, "reflect_nuts": reflect,
            "explosive": explosive, "explosive_or_melee": explosive | melee,
            "hookshot_and_melee": hook & melee, "hookshot_or_melee": hook | melee,
            "boomerang_and_melee": rang & melee, "boomerang": rang,
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
        starts_night = o.frozen_starting_time.value in (3, 4)
        return True_() if starts_night == night else Has("Flow of Time")

    ages = []
    for adult in (False, True):
        mask = (entry.spawn_mask >> (2 if adult else 0)) & 3
        if not mask:
            continue
        tod = True_() if mask == 3 else time_available(mask == 2)
        ages.append((is_adult(b) if adult else is_child(b)) & tod & age_combat(adult))
    gates.append(Or(*ages) if ages else False_())

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
