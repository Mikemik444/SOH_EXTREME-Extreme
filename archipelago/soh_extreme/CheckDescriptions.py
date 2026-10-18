"""Stable check identities with descriptive AP names and legacy aliases.

Only generated physical door/enemy labels change. Fork location names remain
untouched because their existing native rule overlays also use those names.
"""

import dataclasses
from importlib.resources import files
import json
import re


CHECK_DESCRIPTIONS = {
    int(identity): row
    for identity, row in json.loads(
        files(__package__).joinpath("CheckDescriptions.json").read_text(encoding="utf-8")
    ).items()
}
CHECK_NAME_ALIASES = {
    row["legacy_name"]: row["name"] for row in CHECK_DESCRIPTIONS.values()
    if row["legacy_name"] != row["name"]
}


def check_name(identity: int, fallback: str) -> str:
    """Return the seed-independent name of this physical AP check."""
    row = CHECK_DESCRIPTIONS.get(identity)
    return row["name"] if row is not None else fallback


def canonical_location_name(name: str) -> str:
    name = str(name)
    return CHECK_NAME_ALIASES.get(name, name)


def normalize_location_options(options) -> None:
    """Restore legacy location-set values from old UT slot snapshots.

    Normal YAML verification expands the singleton alias groups before this
    stage. UT restores saved option values directly, so normalize those too.
    """
    for field in dataclasses.fields(options):
        option = getattr(options, field.name)
        if getattr(option, "verify_location_name", False) and isinstance(option.value, set):
            option.value = {canonical_location_name(name) for name in option.value}


def shuffled_check_label(source: dict, destination: dict) -> str:
    """Keep the physical check identity separate from its seed's arrival."""
    physical = check_name(source["check_id"], "Scene Transition: " + source["name"])
    if source["id"] == destination["id"]:
        return physical
    target = CHECK_DESCRIPTIONS.get(destination.get("check_id"))
    if target is not None and target["kind"] == "door":
        arrival = target["arrival_name"]
    else:
        arrival = destination["name"].split(" -> ", 1)[-1]
        arrival = re.sub(r"\s+\(door \d+, room [^)]+\)$", "", arrival)
    return physical + " | Shuffled to: " + arrival
