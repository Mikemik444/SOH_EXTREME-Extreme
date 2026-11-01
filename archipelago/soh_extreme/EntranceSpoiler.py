"""Human-readable SOH-EXTREME randomized entrance spoiler manifest.

Every line comes from the SAME final, authoritative _er_mapping that is exported
in the seed slot data and consumed by the native entrance resolver. The AP
location names themselves refer to the original physical source check, NOT a
randomized destination. This file intentionally has no AP imports so it can be
regression-tested outside an Archipelago installation.
"""
from __future__ import annotations

from collections import Counter
from typing import Mapping, Sequence, TextIO


CATEGORY_ORDER = (
    "child_spawn", "adult_spawn", "overworld", "interiors", "dungeons",
    "dungeon_doors", "bosses", "blue_warps", "grottos", "one_ways",
    "owls", "warp_songs",
)
CATEGORY_TITLES = {
    "child_spawn": "Child Spawn",
    "adult_spawn": "Adult Spawn",
    "overworld": "Overworld Exits",
    "interiors": "Interior Entrances and Exits",
    "dungeons": "Dungeon Entrances and Exits",
    "dungeon_doors": "Dungeon Room Doors",
    "bosses": "Boss Chamber Entrances and Returns",
    "blue_warps": "Boss Blue Warps",
    "grottos": "Grottos and Graves",
    "one_ways": "Other One-Way Transitions",
    "owls": "Owl Flights",
    "warp_songs": "Warp Songs",
}


def _short_landing_name(row: Mapping) -> str:
    # Catalog labels include the original vanilla source-to-destination pair.
    # Their right-hand side describes the landing this endpoint creates, and is
    # clearer than substituting the target region's internal RR_ identifier.
    name = str(row["name"])
    return name.split(" -> ", 1)[1] if " -> " in name else str(row["target"])


def resolved_routes(catalog: Sequence[Mapping], mapping: Mapping[int, int],
                    *, legacy_water_aliases: Mapping[int, int] | None = None):
    """Return source, target, mapping origin for ALL catalogued endpoints.

    Missing explicit routes are shown as their stock identity destinations,
    rather than silently omitted. Legacy paired Zora's River water paths use the
    same alias fallback as the C++ EntranceRouting::FindSource resolver.
    """
    by_id = {int(row["id"]): row for row in catalog}
    if len(by_id) != len(catalog):
        raise ValueError("Duplicate entrance endpoint IDs in catalog")
    unknown_sources = set(mapping) - set(by_id)
    unknown_destinations = set(mapping.values()) - set(by_id)
    if unknown_sources or unknown_destinations:
        raise ValueError(
            f"Unknown entrance IDs in finalized map (sources={sorted(unknown_sources)}, "
            f"destinations={sorted(unknown_destinations)})"
        )
    aliases = legacy_water_aliases or {}
    for row in catalog:
        source_id = int(row["id"])
        if source_id in mapping:
            target_id = int(mapping[source_id])
            origin = "generated"
        elif source_id in aliases and int(aliases[source_id]) in mapping:
            target_id = int(mapping[int(aliases[source_id])])
            origin = "legacy water alias"
        else:
            target_id = source_id
            origin = "unchanged / not in shuffled pool"
        yield row, by_id[target_id], origin


def write_entrance_spoiler(handle: TextIO, catalog: Sequence[Mapping],
                           mapping: Mapping[int, int], player_name: str,
                           *, legacy_water_aliases: Mapping[int, int] | None = None) -> None:
    """Write deterministic source -> actual destination entries to AP spoiler.

    Labels always expose the endpoint's real landing region/room, because two
    different entrances can lead to the same broad AP parent region while still
    spawning in physically distinct rooms or ledges.
    """
    ordered = list(resolved_routes(catalog, mapping,
                                   legacy_water_aliases=legacy_water_aliases))
    counts = Counter(row["category"] for row, _, _ in ordered)
    handle.write(f"\nSOH-EXTREME Complete Entrance Map ({player_name}):\n")
    handle.write(f"  Catalog endpoints: {len(ordered)} | Explicit generated routes: {len(mapping)}\n")
    handle.write("  IMPORTANT: Scene Transition and Door location names in Locations /\n")
    handle.write("  Playthrough are names of ORIGINAL checks, NOT shuffled destinations.\n")
    handle.write("  This section is the ACTUAL seed entrance map (including identity routes).\n")
    handle.write("  Source = physical exit used; Destination = randomized endpoint selected;\n")
    handle.write("  Landing = region and room where the game is expected to put Link.\n")
    for category in CATEGORY_ORDER:
        if not counts[category]:
            continue
        handle.write(f"\n  [{CATEGORY_TITLES[category]}] ({counts[category]})\n")
        entries = sorted(
            ((row, dest, origin) for row, dest, origin in ordered
             if row["category"] == category),
            key=lambda entry: (str(entry[0]["name"]), int(entry[0]["id"])),
        )
        for row, dest, origin in entries:
            source_id = int(row["id"])
            target_id = int(dest["id"])
            status = ("shuffled" if source_id != target_id
                      else "identity") if origin == "generated" else origin
            handle.write(f"    [{source_id}] {row['name']}\n")
            handle.write(f"      -> [{target_id}] {_short_landing_name(dest)} "
                         f"({status}; {dest['category']})\n")
            location = f"{dest['target']} (scene {dest['scene']}"
            if int(dest.get("room", -1)) >= 0:
                location += f", room {dest['room']}"
            location += ")"
            handle.write(f"         Landing: {location}\n")
    handle.write("\n  End of SOH-EXTREME Complete Entrance Map.\n\n")
