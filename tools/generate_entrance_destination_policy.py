#!/usr/bin/env python3
"""Verify the reviewed entrance destination manifest and emit native policy rows.

This tool does not approve new destinations. The checked-in JSON is the reviewed
manifest: its endpoint set, exact catalog fingerprints, and resolved native
scene/spawn facts must already match the source being verified. Review changes to
that manifest explicitly when adding an endpoint or changing an entrance table.

No network access or ROM is required. --native-include-root accepts either a
native include directory (with tables/), a full checkout, or the flat local header
fixture used by the source-only validation harnesses. --check writes nothing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys


REVISION = 1
KINDS = {"native": 0, "grotto_load": 1, "grotto_return": 2, "door": 3}
LAYER_NAMES = ("child_day", "child_night", "adult_day", "adult_night")
HARD_REJECTED_SCENES = {
    0x44: "cutscene-only Chamber of the Sages",
    0x47: "cutscene-only cinematic map",
    0x65: "debug test01",
    0x66: "debug besitu",
    0x67: "debug depth test",
    0x68: "debug syotes",
    0x69: "debug syotes2",
    0x6A: "debug sutaru",
    0x6B: "debug courtyard",
    0x6C: "debug sasatest",
    0x6D: "debug testroom",
    0x6E: "undefined SCENE_ID_MAX / SCENE_UNUSED_6E",
}
# z_select.c places this duplicate entry under its explicit Debug submenu even
# though its first four rows reuse the otherwise playable shooting-gallery scene.
HARD_REJECTED_ENTRANCE_BASE_NAMES = {"ENTR_TEST_SHOOTING_GALLERY_0"}
ALIASES = {
    "ENTR_HYRULE_FIELD_10": "ENTR_TEMPLE_OF_TIME_WARP_PAD",
    "ENTR_POTION_SHOP_KAKARIKO_1": "ENTR_CASTLE_GROUNDS_GREAT_FAIRY_EXIT",
}
CHILD_BLUE_WARP_REPAIRS = {
    "ENTR_SACRED_FOREST_MEADOW_FOREST_TEMPLE_BLUE_WARP": "ENTR_SACRED_FOREST_MEADOW_WARP_PAD",
    "ENTR_DEATH_MOUNTAIN_CRATER_FIRE_TEMPLE_BLUE_WARP": "ENTR_DEATH_MOUNTAIN_CRATER_WARP_PAD",
    "ENTR_LAKE_HYLIA_WATER_TEMPLE_BLUE_WARP": "ENTR_LAKE_HYLIA_WARP_PAD",
    "ENTR_GRAVEYARD_SHADOW_TEMPLE_BLUE_WARP": "ENTR_GRAVEYARD_WARP_PAD",
    "ENTR_DESERT_COLOSSUS_SPIRIT_TEMPLE_BLUE_WARP": "ENTR_DESERT_COLOSSUS_WARP_PAD",
}


class PolicyError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise PolicyError(message)


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=True).encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def macro_arguments(value: str) -> list[str]:
    parts, start, depth = [], 0, 0
    for offset, char in enumerate(value):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char == "," and depth == 0:
            parts.append(value[start:offset].strip())
            start = offset + 1
        require(depth >= 0, "Unbalanced native table macro")
    require(depth == 0, "Unbalanced native table macro")
    return parts + [value[start:].strip()]


def native_header(root: Path, name: str) -> Path:
    for directory in (root, root / "tables", root / "include", root / "include/tables",
                      root / "soh/include", root / "soh/include/tables"):
        candidate = directory / name
        if candidate.is_file():
            return candidate
    raise PolicyError(f"Missing native {name} under {root}")


def parse_scene_table(path: Path) -> dict[int, dict]:
    scenes = {}
    pattern = re.compile(r"/\*\s*(0x[0-9A-Fa-f]+)\s*\*/\s*DEFINE_SCENE\(([^)]*)\)")
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        match = pattern.search(line)
        if match:
            index = int(match[1], 0)
            parts = [part.strip() for part in match[2].split(",")]
            require(len(parts) == 6, f"Malformed scene row {index:#x}")
            require(index not in scenes, f"Duplicate native scene {index:#x}")
            scenes[index] = {"id": index, "name": parts[2], "resource": parts[0]}
    require(bool(scenes), "No DEFINE_SCENE rows found")
    require(sorted(scenes) == list(range(len(scenes))), "Native scene table is not contiguous")
    return scenes


def parse_entrance_table(path: Path, scenes: dict[int, dict]) -> dict[int, dict]:
    scene_ids = {row["name"]: index for index, row in scenes.items()}
    # z64scene.h explicitly aliases this unused entry to SCENE_ID_MAX (0x6E).
    scene_ids["SCENE_UNUSED_6E"] = len(scenes)
    entrances = {}
    group = None
    pattern = re.compile(r"/\*\s*(0x[0-9A-Fa-f]+)\s*\*/\s*DEFINE_ENTRANCE\((.*)\)")
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            group = None
        match = pattern.search(line)
        if not match:
            continue
        index = int(match[1], 0)
        parts = macro_arguments(match[2])
        require(len(parts) == 7, f"Malformed entrance row {index:#x}")
        require(parts[1] in scene_ids, f"Unknown scene symbol {parts[1]}")
        require(index not in entrances, f"Duplicate native entrance {index:#x}")
        if group is None:
            group = index
        spawn = int(parts[2], 0)
        require(0 <= spawn <= 0xFF, f"Invalid native spawn {index:#x}: {spawn}")
        entrances[index] = {
            "index": index, "name": parts[0], "scene": scene_ids[parts[1]],
            "scene_name": parts[1], "spawn": spawn, "group_base": group,
            "continue_bgm": parts[3] == "true", "title_card": parts[4] == "true",
            "end_transition": parts[5], "start_transition": parts[6],
        }
    require(bool(entrances), "No DEFINE_ENTRANCE rows found")
    require(sorted(entrances) == list(range(len(entrances))), "Native entrance table is not contiguous")
    return entrances


def parse_grotto_tables(path: Path, by_name: dict[str, int], scenes: dict[int, dict]) -> tuple[list, list]:
    source = path.read_text(encoding="utf-8-sig")
    scene_ids = {row["name"]: index for index, row in scenes.items()}
    load_block = source.split("grottoLoadTable[NUM_GROTTOS] = {", 1)[1].split("\n};", 1)[0]
    return_block = source.split("grottoReturnTable[NUM_GROTTOS] = {", 1)[1].split("\n};", 1)[0]
    loads, returns = [], []
    for match in re.finditer(r"\{\.entranceIndex\s*=\s*(\w+),\s*\.content\s*=\s*(0x[0-9A-Fa-f]+),\s*\.scene\s*=\s*(\w+)\}", load_block):
        loads.append({"native_index": by_name[match[1]], "content": int(match[2], 0),
                      "source_scene": scene_ids[match[3]]})
    pattern = (r"\{\.entranceIndex\s*=\s*(\w+),\s*\.room\s*=\s*(0x[0-9A-Fa-f]+),"
               r"\s*\.angle\s*=\s*(0x[0-9A-Fa-f]+),\s*\.pos\s*=\s*\{"
               r"\s*\.x\s*=\s*([+-]?[0-9.]+)f,\s*\.y\s*=\s*([+-]?[0-9.]+)f,"
               r"\s*\.z\s*=\s*([+-]?[0-9.]+)f\}\}")
    for match in re.finditer(pattern, return_block):
        returns.append({"native_index": by_name[match[1]], "room": int(match[2], 0),
                        "angle": int(match[3], 0), "position": [float(match[i]) for i in (4, 5, 6)]})
    require(len(loads) == len(returns) == 33, "Expected exactly 33 reviewed grotto load/return rows")
    return loads, returns


def assert_source_repairs(source: str, by_name: dict[str, int]) -> None:
    """Ensure derived rows still correspond to actual native table writes."""
    compact = re.sub(r"\s+", "", source)
    require("staticvoidEntrance_ReplaceChildTempleWarps(){if(Archipelago_EntranceShuffleActive()||" in compact,
            "AP-active child blue-warp repair guard is missing or changed")
    for target, origin in ALIASES.items():
        require(target in by_name and origin in by_name, f"Missing entrance alias {target}")
        assignment = f"gEntranceTable[{target}+i]=gEntranceTable[{origin}+i];"
        require(assignment in compact, f"Native alias implementation changed: {target}")
    for target, origin in CHILD_BLUE_WARP_REPAIRS.items():
        assignment = f"gEntranceTable[{target}]=gEntranceTable[{origin}];"
        require(assignment in compact, f"Native child blue-warp repair changed: {target}")
        target_night = next(name for name, index in by_name.items() if index == by_name[target] + 1)
        origin_night = next(name for name, index in by_name.items() if index == by_name[origin] + 1)
        assignment = f"gEntranceTable[{target_night}]=gEntranceTable[{origin_night}];"
        require(assignment in compact, f"Native night blue-warp repair changed: {target}")


def verify_native_endpoint_catalog(source_root: Path, catalog: list[dict]) -> None:
    """Verify the actual C++ endpoint metadata, including door coordinates."""
    path = source_root / "soh/Network/Archipelago/EntranceRandomizerData.inc"
    actual = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        require(line.startswith("{") and line.endswith("},"), "Malformed compiled entrance endpoint row")
        # This generated file contains decimal integers and JSON-compatible C++
        # quoted strings, so parse strings safely without evaluating source code.
        values = json.loads("[" + line[1:-2] + "]")
        require(len(values) == 15 and type(values[0]) is int, "Malformed compiled entrance endpoint fields")
        require(values[0] not in actual, "Duplicate compiled entrance endpoint ID")
        actual[values[0]] = values
    require(set(actual) == {row["id"] for row in catalog}, "Compiled entrance endpoint allowlist differs from catalog")
    for row in catalog:
        position = row.get("position", [0, 0, 0])
        expected = [row["id"], row["reverse"], row["scene"], row["source_scene"], row["check_id"],
                    row.get("door", -1), row.get("side", -1), row.get("from_room", -1), row.get("room", -1),
                    row.get("anchor", row["id"]), *position, row.get("rotation", 0), row["name"]]
        require(actual[row["id"]] == expected, f"Compiled entrance endpoint {row['id']} metadata differs from catalog")


def derive_endpoints(source_root: Path, include_root: Path) -> tuple[list[dict], dict]:
    catalog_path = source_root / "archipelago/soh_extreme/EntranceCatalog.json"
    door_path = source_root / "archipelago/soh_extreme/DungeonDoorCatalog.json"
    entrance_path = native_header(include_root, "entrance_table.h")
    scene_path = native_header(include_root, "scene_table.h")
    grotto_path = source_root / "soh/Enhancements/randomizer/randomizer_grotto.c"
    native_path = source_root / "soh/Enhancements/randomizer/randomizer_entrance.c"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8-sig"))
    require(isinstance(catalog, list), "EntranceCatalog must be an array")
    require(len({row["id"] for row in catalog}) == len(catalog), "Duplicate catalog endpoint IDs")
    scenes = parse_scene_table(scene_path)
    entrances = parse_entrance_table(entrance_path, scenes)
    by_name = {row["name"]: index for index, row in entrances.items()}
    assert_source_repairs(native_path.read_text(encoding="utf-8-sig"), by_name)
    loads, returns = parse_grotto_tables(grotto_path, by_name, scenes)
    door_rows = json.loads(door_path.read_text(encoding="utf-8-sig"))
    doors = {row["index"]: row for row in door_rows}
    require(len(doors) == len(door_rows), "Duplicate dungeon-door indices")
    aliases = {by_name[target]: by_name[origin] for target, origin in ALIASES.items()}
    child_repairs = {by_name[target]: by_name[origin] for target, origin in CHILD_BLUE_WARP_REPAIRS.items()}
    facts = []
    used_doors = set()
    used_grottos = {"grotto_load": set(), "grotto_return": set()}
    for endpoint in sorted(catalog, key=lambda row: row["id"]):
        endpoint_id = endpoint["id"]
        fact = {"id": endpoint_id, "catalog_row_sha256": canonical_sha256(endpoint)}
        if endpoint.get("door", -1) >= 0:
            kind = "door"
            native_index = endpoint["anchor"]
            require(endpoint["index"] in doors, f"Unknown door endpoint {endpoint_id}")
            door = doors[endpoint["index"]]
            used_doors.add(endpoint["index"])
            matches = {
                "check_id": "id", "source": "source", "target": "target",
                "source_scene": "source_scene", "scene": "target_scene",
                "door": "door", "side": "side", "from_room": "room_from", "room": "room_to",
                "actor": "actor", "params": "params", "position": "position", "rotation": "rotation",
            }
            for key, door_key in matches.items():
                require(endpoint.get(key) == door[door_key], f"Door {endpoint_id} differs from room catalog: {key}")
            require(endpoint["scene"] == endpoint["source_scene"], f"Door {endpoint_id} changes scene without a native entry")
            require(0 <= endpoint["room"] <= 0x3F and 0 <= endpoint["from_room"] <= 0x3F,
                    f"Door {endpoint_id} has an invalid room number")
            require(len(endpoint["position"]) == 3 and all(isinstance(n, int) and -32768 <= n <= 32767
                    for n in endpoint["position"]), f"Door {endpoint_id} has invalid position data")
            fact["door_metadata"] = {key: endpoint[key] for key in
                                     ("scene", "door", "side", "from_room", "room", "actor", "params", "position", "rotation")}
        elif 0x700 <= endpoint_id < 0x700 + len(loads):
            kind = "grotto_load"
            offset = endpoint_id - 0x700
            used_grottos[kind].add(offset)
            fact["grotto_offset"] = offset
            fact["grotto_metadata"] = loads[offset]
            native_index = loads[offset]["native_index"]
            require(endpoint["source_scene"] == loads[offset]["source_scene"], f"Grotto load {endpoint_id} source scene differs")
        elif 0x800 <= endpoint_id < 0x800 + len(returns):
            kind = "grotto_return"
            offset = endpoint_id - 0x800
            used_grottos[kind].add(offset)
            fact["grotto_offset"] = offset
            fact["grotto_metadata"] = returns[offset]
            native_index = returns[offset]["native_index"]
        else:
            kind = "native"
            native_index = endpoint_id
            require(endpoint.get("index") in by_name and by_name[endpoint["index"]] == native_index,
                    f"Unknown/mismatched native endpoint {endpoint_id}")
        require(native_index in entrances, f"Unresolved native index for endpoint {endpoint_id}")
        require(entrances[native_index]["name"] not in HARD_REJECTED_ENTRANCE_BASE_NAMES,
                f"Endpoint {endpoint_id} resolves to a debug-only native entrance")
        require(entrances[native_index]["group_base"] == native_index,
                f"Endpoint {endpoint_id} uses a layer offset rather than a base entrance")
        template = aliases.get(native_index, native_index)
        source_indices = [template + layer for layer in range(4)]
        if native_index in aliases:
            fact["alias_template_index"] = template
        if native_index in child_repairs:
            fact["child_blue_warp_template_index"] = child_repairs[native_index]
            fact["original_normal_layers"] = [{"scene": entrances[i]["scene"], "spawn": entrances[i]["spawn"]}
                                               for i in source_indices]
            source_indices[:2] = [child_repairs[native_index], child_repairs[native_index] + 1]
        layers = []
        for layer, index in enumerate(source_indices):
            require(index in entrances, f"Missing native layer {layer} for endpoint {endpoint_id}")
            row = entrances[index]
            require(row["group_base"] == index - layer,
                    f"Endpoint {endpoint_id} spills into a different native entrance group")
            scene = row["scene"]
            require(scene in scenes and scene not in HARD_REJECTED_SCENES,
                    f"Endpoint {endpoint_id} layer {layer} resolves to prohibited scene {scene:#x}")
            layers.append({"scene": scene, "spawn": row["spawn"]})
        require(endpoint["scene"] in {layer["scene"] for layer in layers},
                f"Endpoint {endpoint_id} declared scene has no normal native layer")
        if kind == "door":
            require(all(layer["scene"] == endpoint["scene"] for layer in layers),
                    f"Door {endpoint_id} anchor changes scene by age/time")
        fact.update({"kind": kind, "native_index": native_index, "normal_layers": layers,
                     "normal_layer_source_indices": source_indices})
        facts.append(fact)
    require(used_doors == set(doors), "Room-door catalog and entrance endpoint coverage differ")
    for kind, offsets in used_grottos.items():
        require(offsets == set(range(33)), f"Incomplete {kind} table coverage")
    verify_native_endpoint_catalog(source_root, catalog)
    evidence = {
        "catalog_sha256": canonical_sha256(sorted(catalog, key=lambda row: row["id"])),
        "source_hashes": {
            "EntranceCatalog.json": file_sha256(catalog_path),
            "DungeonDoorCatalog.json": file_sha256(door_path),
            "entrance_table.h": file_sha256(entrance_path),
            "scene_table.h": file_sha256(scene_path),
        },
        "native_entry_count": len(entrances), "native_scene_count": len(scenes),
        "scenes": scenes, "entrances": entrances,
    }
    return facts, evidence


def verify_reviewed_policy(policy: dict, facts: list[dict], evidence: dict) -> None:
    require(policy.get("revision") == REVISION, "Unknown destination policy revision")
    require(policy.get("age_mask_bits") == {"child": 1, "adult": 2}, "Unexpected native-independent age mask contract")
    require(policy.get("normal_layer_order") == list(LAYER_NAMES), "Unexpected ordinary scene-layer order")
    require(policy.get("catalog_sha256") == evidence["catalog_sha256"],
            "EntranceCatalog changed: review the destination policy before regeneration")
    approved_scenes = policy.get("approved_scene_ids", [])
    require(isinstance(approved_scenes, list) and all(type(scene) is int for scene in approved_scenes),
            "Approved scene IDs must be an explicit integer list")
    require(len(set(approved_scenes)) == len(approved_scenes), "Duplicate approved scene IDs")
    require(not set(approved_scenes) & set(HARD_REJECTED_SCENES), "Policy approves a cutscene/debug/undefined scene")
    require(set(approved_scenes) <= set(evidence["scenes"]), "Policy approves an unknown scene")
    rows = policy.get("endpoints", [])
    require(isinstance(rows, list), "Policy endpoints must be an array")
    indexed = {row["id"]: row for row in rows}
    require(len(indexed) == len(rows), "Duplicate reviewed endpoint IDs")
    require(set(indexed) == {row["id"] for row in facts}, "Reviewed endpoint allowlist differs from catalog")
    for fact in facts:
        row = indexed[fact["id"]]
        for key, value in fact.items():
            require(row.get(key) == value, f"Unreviewed endpoint {fact['id']} resolution/metadata change: {key}")
        for key in ("source_age_mask", "arrival_age_mask"):
            require(type(row.get(key)) is int and 1 <= row[key] <= 3,
                    f"Invalid reviewed age mask for endpoint {fact['id']}: {key}")
        require(all(layer["scene"] in approved_scenes for layer in fact["normal_layers"]),
                f"Endpoint {fact['id']} resolves outside the reviewed positive scene list")
    source_hashes = policy.get("provenance", {}).get("source_hashes", {})
    for name, digest in evidence["source_hashes"].items():
        require(source_hashes.get(name) == digest, f"Reviewed source provenance changed: {name}")


def render_native(policy: dict) -> str:
    lines = [
        "// Generated by tools/generate_entrance_destination_policy.py; do not edit.",
        f"// Policy revision: {policy['revision']}; canonical catalog SHA256: {policy['catalog_sha256']}",
        "// {id, nativeIndex, kind, sourceAgeMask, arrivalAgeMask, {{scene, spawn} x4}}",
        "// Kinds: native=0, grotto load=1, grotto return=2, room door=3. Ages: child=1, adult=2.",
    ]
    for row in sorted(policy["endpoints"], key=lambda entry: entry["id"]):
        layers = ", ".join("{" + f"{layer['scene']}, {layer['spawn']}" + "}" for layer in row["normal_layers"])
        lines.append("{" + f"{row['id']}, {row['native_index']}, {KINDS[row['kind']]}, "
                     f"{row['source_age_mask']}, {row['arrival_age_mask']}, " + "{" + layers + "}},")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--native-include-root", type=Path, required=True)
    parser.add_argument("--policy", type=Path, help="Reviewed JSON manifest (default: source AP world)")
    parser.add_argument("--native-output", type=Path, help="Generated native .inc output")
    parser.add_argument("--check", action="store_true", help="Validate policy and native output without writing")
    args = parser.parse_args(argv)
    source_root = args.source_root.resolve()
    policy_path = args.policy or source_root / "archipelago/soh_extreme/EntranceDestinationPolicy.json"
    native_path = args.native_output or source_root / "soh/Network/Archipelago/EntranceDestinationData.inc"
    try:
        require(policy_path.is_file(), "A reviewed destination policy is required; this tool cannot auto-approve destinations")
        policy = json.loads(policy_path.read_text(encoding="utf-8-sig"))
        facts, evidence = derive_endpoints(source_root, args.native_include_root)
        verify_reviewed_policy(policy, facts, evidence)
        rendered = render_native(policy)
        if args.check:
            require(native_path.is_file() and native_path.read_text(encoding="utf-8-sig") == rendered,
                    "Generated native destination policy is stale")
        else:
            policy_path.write_text(json.dumps(policy, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
            native_path.write_text(rendered, encoding="utf-8")
        counts = {kind: sum(row["kind"] == kind for row in facts) for kind in KINDS}
        print(json.dumps({"status": "passed", "revision": REVISION, "endpoints": len(facts),
                          "normal_layer_resolutions": len(facts) * 4, "kinds": counts,
                          "catalog_sha256": evidence["catalog_sha256"]}, sort_keys=True))
        return 0
    except (PolicyError, KeyError, ValueError, OSError, IndexError) as error:
        print(f"Destination policy verification failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
