"""
SOH-EXTREME shared logic helpers for Archipelago generation and tracker/check-finder exports.

This module intentionally keeps all setting-gated check registration, requirement parsing,
important/progression item classification, and Silver Rupee room grouping in one place so
Archipelago, SoH, and Check Finder stop using different rule copies.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple


@dataclass(frozen=True)
class RequirementAtom:
    kind: str  # item, setting
    name: str
    value: Optional[str] = None
    negated: bool = False

    def satisfied(self, items: Set[str], settings: Mapping[str, object]) -> bool:
        if self.kind == "item":
            result = self.name in items
        elif self.kind == "setting":
            raw = settings.get(self.name, False)
            if isinstance(raw, bool):
                actual = "true" if raw else "false"
            else:
                actual = str(raw).lower()
            expected = str(self.value).lower() if self.value is not None else "true"
            result = actual == expected
        else:
            result = False
        return not result if self.negated else result


@dataclass(frozen=True)
class RequirementBranch:
    atoms: Tuple[RequirementAtom, ...] = ()

    def satisfied(self, items: Set[str], settings: Mapping[str, object]) -> bool:
        return all(atom.satisfied(items, settings) for atom in self.atoms)


@dataclass(frozen=True)
class LogicLocation:
    name: str
    region: str
    requirements: Tuple[RequirementBranch, ...] = (RequirementBranch(),)
    setting_required: Optional[str] = None
    ap_id: Optional[int] = None
    check_type: str = "misc"
    room: Optional[str] = None

    def enabled(self, settings: Mapping[str, object]) -> bool:
        if not self.setting_required:
            return True
        return RequirementAtom("setting", *parse_setting_token(self.setting_required)).satisfied(set(), settings)

    def reachable(self, items: Set[str], settings: Mapping[str, object], region_reachable: Callable[[str], bool]) -> bool:
        if not self.enabled(settings):
            return False
        if not region_reachable(self.region):
            return False
        return any(branch.satisfied(items, settings) for branch in self.requirements)


def parse_setting_token(token: str) -> Tuple[str, str, bool]:
    token = token.strip()
    negated = token.startswith("!")
    if negated:
        token = token[1:].strip()
    if "=" not in token:
        return token, "true", negated
    key, value = token.split("=", 1)
    return key.strip(), value.strip(), negated


def parse_requirement_branch(branch: str) -> RequirementBranch:
    atoms: List[RequirementAtom] = []
    for raw in branch.split(";"):
        token = raw.strip()
        if not token:
            continue
        if token.startswith("[") and token.endswith("]"):
            key, value, negated = parse_setting_token(token[1:-1])
            atoms.append(RequirementAtom("setting", key, value, negated))
        else:
            atoms.append(RequirementAtom("item", token))
    return RequirementBranch(tuple(atoms))


def branches(*branches: str) -> Tuple[RequirementBranch, ...]:
    if not branches:
        return (RequirementBranch(),)
    return tuple(parse_requirement_branch(branch) for branch in branches)


# Canonical item classification. AP item classification, SoH hold/popup behavior,
# Check Finder logic, and progression fill should all query this table.
ALWAYS_IMPORTANT: Set[str] = {
    "Bow", "Slingshot", "Hookshot", "Longshot", "Boomerang", "Megaton Hammer",
    "Bomb Bag", "Bombchus", "Magic Meter", "Dins Fire", "Farores Wind", "Nayrus Love",
    "Ocarina", "Progressive Ocarina", "Progressive Sword", "Progressive Shield",
    "Progressive Strength", "Progressive Scale", "Progressive Wallet", "Progressive Hookshot",
    "Iron Boots", "Hover Boots", "Lens of Truth", "Goron Tunic", "Zora Tunic",
    "Shovel", "Flow of Time", "Open Chest", "Speak", "Roll", "Grab / Power Bracelet", "Crawl", "Climb",
}

SOUL_ITEMS: Set[str] = {
    "Enemy Soul", "NPC Soul", "Animal Soul", "Pot Soul", "Crate Soul",
    "Grass / Bush Soul", "Rock / Boulder Soul", "Tree Soul", "Beehive Soul",
    "Scrub Soul", "Sign Soul", "Icicle Soul", "Red Ice Soul",
}

SONG_NOTE_PREFIXES: Tuple[str, ...] = (
    "Zelda's Lullaby Note", "Epona's Song Note", "Saria's Song Note", "Sun's Song Note",
    "Song of Time Note", "Song of Storms Note", "Minuet of Forest Note", "Bolero of Fire Note",
    "Serenade of Water Note", "Requiem of Spirit Note", "Nocturne of Shadow Note", "Prelude of Light Note",
)

FILLER_ITEMS: Set[str] = {
    "Recovery Heart", "Heart", "Rupee Green", "Rupee Blue", "Rupee Red", "Rupee Purple",
    "Rupee Orange", "Deku Stick", "Deku Nut", "Arrows", "Bombs", "Seeds",
}

TRAP_ITEMS: Set[str] = {"Ice Trap", "Junk Trap", "Bonk Trap", "Burn Trap", "Freeze Trap"}


def is_song_note(item_name: str) -> bool:
    if item_name.startswith("Song Note "):
        suffix = item_name[len("Song Note "):].strip()
        return suffix.isdigit() and 1 <= int(suffix) <= 74
    return item_name.endswith(" Note") or any(item_name.startswith(prefix) for prefix in SONG_NOTE_PREFIXES)


def is_soul(item_name: str) -> bool:
    return item_name in SOUL_ITEMS or item_name.endswith(" Soul")


def is_important_item(item_name: str, settings: Optional[Mapping[str, object]] = None) -> bool:
    if "Triforce" in item_name and "Piece" in item_name:
        return True
    if item_name in ALWAYS_IMPORTANT:
        return True
    if is_soul(item_name):
        return True
    if is_song_note(item_name):
        return True
    if item_name.startswith("Small Key") or item_name.startswith("Boss Key") or item_name.startswith("Silver Rupee"):
        return True
    if item_name.startswith("Progressive "):
        return True
    return False


def ap_classification(item_name: str, settings: Optional[Mapping[str, object]] = None) -> str:
    if item_name in TRAP_ITEMS or item_name.endswith(" Trap"):
        return "trap"
    if is_important_item(item_name, settings):
        return "progression"
    return "filler"


# Canonical setting -> check-family names. This is used by audit tooling and by the AP world
# to ensure all enabled settings add checks to the location pool.
CHECK_SETTINGS: Dict[str, str] = {
    "Pot Sanity": "pots",
    "Crate Sanity": "crates",
    "Grass Sanity": "grass_bushes",
    "Rock Sanity": "rocks_boulders",
    "Tree Sanity": "trees",
    "Beehive Sanity": "beehives",
    "Icicle Sanity": "icicles",
    "Red Ice Sanity": "red_ice",
    "Scrub Sanity": "scrubs",
    "Sign Sanity": "signs",
    "NPC Speech Sanity": "npc_speech",
    "Enemy Sanity": "enemy_instances",
    "Freestanding Rupees": "freestanding_rupees",
    "Hidden Rupees": "hidden_rupees",
    "Wonder Items": "wonder_items",
    "Silver Rupees": "silver_rupees",
    "Butterfly Fairies": "butterfly_fairies",
    "Shop Sanity": "shops",
    "Merchant Sanity": "merchants",
}


# Silver Rupee doors need room-local completion, not one global item.
# Extend this table as rooms are audited. Unknown rooms are still grouped by their location prefix.
SILVER_RUPEE_ROOMS: Dict[str, Tuple[str, ...]] = {
    "Ganons Castle Spirit Trial": tuple(f"Ganons Castle Spirit Trial Silver Rupee {i}" for i in range(1, 6)),
    "Ganons Castle Shadow Trial": tuple(f"Ganons Castle Shadow Trial Silver Rupee {i}" for i in range(1, 6)),
    "Ganons Castle Fire Trial": tuple(f"Ganons Castle Fire Trial Silver Rupee {i}" for i in range(1, 6)),
    "Ganons Castle Water Trial": tuple(f"Ganons Castle Water Trial Silver Rupee {i}" for i in range(1, 6)),
    "Ice Cavern Spinning Scythe": tuple(f"Ice Cavern Spinning Scythe Silver Rupee {i}" for i in range(1, 6)),
    "Shadow Temple Scythe Shortcut": tuple(f"Shadow Temple Scythe Shortcut Silver Rupee {i}" for i in range(1, 6)),
    "Spirit Temple Sun Block": tuple(f"Spirit Temple Sun Block Silver Rupee {i}" for i in range(1, 6)),
}


def room_silver_rupee_requirement(room_name: str) -> RequirementBranch:
    return RequirementBranch(tuple(RequirementAtom("item", rupee) for rupee in SILVER_RUPEE_ROOMS.get(room_name, ())))


def has_room_silver_rupees(room_name: str, items: Iterable[str]) -> bool:
    item_set = set(items)
    reqs = SILVER_RUPEE_ROOMS.get(room_name, ())
    return bool(reqs) and all(req in item_set for req in reqs)


def check_setting_audit(settings: Mapping[str, object], registered_check_types: Iterable[str]) -> List[str]:
    registered = set(registered_check_types)
    missing: List[str] = []
    for setting, family in CHECK_SETTINGS.items():
        raw = settings.get(setting, False)
        enabled = raw if isinstance(raw, bool) else str(raw).lower() == "true"
        if enabled and family not in registered:
            missing.append(f"{setting} enabled but no {family} checks were registered")
    return missing
