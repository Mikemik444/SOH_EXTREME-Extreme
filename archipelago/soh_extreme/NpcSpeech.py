"""First conversation identities, independent of shop shelves and NPC rewards.

IDs are permanent. Do not sort/renumber the catalogue when adding a character.
Old seeds retain SpeechLocations.py via their absent identity-version field.
"""
import json
from dataclasses import dataclass
from importlib.resources import files
from rule_builder.rules import And, Or, Has, CanReachRegion
from ._vendor_oot_soh import LogicHelpers as H
from ._vendor_oot_soh.Enums import Regions, Items, Events

IDENTITY_VERSION = 2
CATALOG = tuple(json.loads(files(__package__).joinpath("NpcSpeechCatalog.json").read_text(encoding="utf-8")))
NAME_TO_ID = {e["name"]: e["id"] for e in CATALOG}
BY_NAME = {e["name"]: e for e in CATALOG}
LANGUAGES = ("Deku", "Gerudo", "Goron", "Hylian", "Kokiri", "Zora")


@dataclass
class ConversationRegion(CanReachRegion, game="SOH-EXTREME"):
    """Region access under SohLocation's current child/adult evaluation.

    The generic region-rule cache has no age in its key. Do not reuse a child
    result for an adult route, or an adult result for a child-only NPC.
    """
    class Resolved(CanReachRegion.Resolved):
        force_recalculate = True


def identity_version(world):
    return int(world.passthrough.get("npc_speech_identity_version", 1)) if world.using_ut else IDENTITY_VERSION


def active_entries(world):
    for e in CATALOG:
        # Native one-time scrubs are not spawned when Scrub Shuffle is off.
        if e.get("native_rc") in ("RC_LW_DEKU_SCRUB_NEAR_BRIDGE", "RC_HF_DEKU_SCRUB_GROTTO",
                                   "RC_LW_DEKU_SCRUB_GROTTO_FRONT") and not world.options.shuffle_scrubs.value:
            continue
        yield e


def conversation_rule(world, entry, scrub_region=None):
    o = world.options
    rules = []
    if any(match[0] == "ACTOR_EN_SKJ" for match in entry["matches"]):
        rules.append(H.can_interact_skull_kid((Regions.LOST_WOODS, world)))
    if o.shuffle_npc_soul.value:
        rules.append(Has("NPC Soul"))
    if o.shuffle_speak.value == 1:
        rules.append(Has("Speak"))
    elif o.shuffle_speak.value == 2:
        rules.append(Or(*(Has("Speak " + lang) for lang in LANGUAGES)) if entry["language"] == "Any"
                     else Has("Speak " + entry["language"]))
    routes = entry["routes"]
    if entry.get("native_rc"):
        # Native identity carries the exact grotto/dungeon parent. No money,
        # wallet, shop stock, or reward-specific requirements for a conversation.
        region = Regions(scrub_region)
        b = (region, world)
        rules.append(H.can_stun_deku(b))
        if o.shuffle_business_scrub_soul.value:
            rules.append(Has("Scrub Soul"))
        # Surface scrub placements are child-only except the SFM scrub.
        rc = entry["native_rc"]
        if rc.startswith(("RC_LW_", "RC_DEKU_TREE_", "RC_JABU_JABUS_BELLY_")):
            rules.append(H.is_child(b))
        return And(*rules)
    alternatives = []
    for route in routes:
        region = Regions[route["region"]]
        b = (region, world)
        # SohLocation evaluates its rules with an age already selected. In that
        # context IsChild/IsAdult only check the age; they do not test the named
        # region. These NPCs have Menu as their parent to support moving actors,
        # so every alternative must explicitly require its physical region too.
        gates = [ConversationRegion(str(region)),
                 H.is_child(b) if route["age"] == "child" else H.is_adult(b)
                 if route["age"] == "adult" else (H.is_child(b) | H.is_adult(b))]
        if route["time"] != "either":
            gates.append(H.at_day(b) if route["time"] == "day" else H.at_night(b))
        for gate in route["gates"]:
            if gate == "climb":
                if o.shuffle_climb.value: gates.append(Has("Climb"))
            elif gate == "swim": gates.append(H.can_swim(b))
            elif gate == "reflect": gates.append(H.can_reflect_nuts(b))
            elif gate == "Deku Scrub Soul":
                if o.shuffle_enemy_soul.value:
                    gates.append(Has("Enemy Soul" if o.shuffle_enemy_soul.value == 1 else gate))
            elif gate == "carpenters": gates.append(H.has_item(Events.RESCUED_ALL_CARPENTERS, b))
            elif gate == "stop_goron":
                gates.append(H.has_explosives(b) | (H.is_adult(b) &
                    (H.has_item(Items.GORONS_BRACELET, b) | H.can_use(Items.FAIRY_BOW, b))))
            elif gate == "bow": gates.append(H.can_use(Items.FAIRY_BOW, b))
            elif gate == "sarias_song": gates.append(H.can_use(Items.SARIAS_SONG, b))
            elif gate == "ocarina": gates.append(H.can_use(Items.FAIRY_OCARINA, b))
            elif gate == "midos_house":
                gates.append(ConversationRegion(str(Regions.KF_MIDOS_HOUSE)) &
                             H.is_child((Regions.KF_MIDOS_HOUSE, world)))
            elif gate == "theater_mask": gates.append(H.has_item(Events.CAN_BORROW_SKULL_MASK, b))
            else: gates.append(Has(gate))
        alternatives.append(And(*gates))
    rules.append(Or(*alternatives))
    return And(*rules)


def display_region(location):
    entry = BY_NAME.get(location.name)
    if entry and entry["routes"]:
        return str(Regions[entry["routes"][0]["region"]])
    return str(location.parent_region.name) if location.parent_region else ""
