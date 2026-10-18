"""Generate shared AP/native descriptive check names without changing IDs.

The append-only physical catalogs remain authoritative for identity and logic.
This tool only derives labels and carries their original names as aliases.
Run with --check to verify that the committed JSON and native include are current.
"""

from pathlib import Path
import argparse
import ast
from collections import Counter, defaultdict
import json
import re


ROOT = Path(__file__).resolve().parents[1]
WORLD = ROOT / "archipelago/soh_extreme"

# Grounded in the nine maze door positions/yaws in DungeonDoorCatalog.json.
# Left/right look into the maze from the lobby (-60, -80, -1100), facing -Z.
# Source side 0 crosses along the yaw normal; source side 1 crosses against it.
MAZE_PASSAGES = {
    11211290: "Outer Left Entrance Passage, Rightward",
    11211291: "Outer Left Entrance Passage, Leftward",
    11211292: "Inner Left Entrance Passage, Rightward",
    11211293: "Inner Left Entrance Passage, Leftward",
    11211294: "Inner Right Entrance Passage, Leftward",
    11211295: "Inner Right Entrance Passage, Rightward",
    11211296: "Outer Right Entrance Passage, Toward Entrance",
    11211297: "Outer Right Entrance Passage, Away from Entrance",
    11211298: "Middle Left Passage, Toward Entrance",
    11211299: "Middle Left Passage, Away from Entrance",
    11211300: "Far Left Passage, Toward Entrance",
    11211301: "Far Left Passage, Away from Entrance",
    11211302: "Far Center Passage, Leftward",
    11211303: "Far Center Passage, Rightward",
    11211304: "Far Right Passage, Away from Entrance",
    11211305: "Far Right Passage, Toward Entrance",
    11211306: "Middle Right Passage, Rightward",
    11211307: "Middle Right Passage, Leftward",
}


def constructor_rows(path, constructor):
    """Read immutable catalog rows without importing the AP runtime."""
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    return [ast.literal_eval(ast.Tuple(elts=node.args, ctx=ast.Load()))
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == constructor]


def stock_region_names():
    tree = ast.parse((WORLD / "_vendor_oot_soh/Enums.py").read_text(encoding="utf-8-sig"))
    region_class = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Regions")
    return {node.targets[0].id: ast.literal_eval(node.value)
            for node in region_class.body if isinstance(node, ast.Assign)
            and isinstance(node.targets[0], ast.Name) and isinstance(node.value, ast.Constant)}


def scene_display_names(enemy_rows):
    """Reuse the physical enemy catalog's human scene names and spelling."""
    names = defaultdict(Counter)
    for row in enemy_rows:
        match = re.fullmatch(r"Enemy Defeat: (.+) Room \d+ (.+)", row[0])
        if match:
            names[row[2]][match[1]] += 1
    return {scene: counts.most_common(1)[0][0] for scene, counts in names.items()}


def concise_room(name, scene_name):
    aliases = {scene_name, scene_name.removeprefix("Inside ")}
    if scene_name == "Gerudo Training Ground":
        aliases.add("Gerudo Training")  # Existing native Dinalfos region name.
    for prefix in sorted(aliases, key=len, reverse=True):
        pattern = re.escape(prefix).replace("'", "['’]?") + r"\s+"
        short, count = re.subn("^" + pattern, "", name, count=1)
        if count:
            return short
    return name


def build_descriptions():
    descriptions = {}
    graph = json.loads((WORLD / "EnemyRoomGraph.json").read_text(encoding="utf-8"))
    regions = stock_region_names()
    enemy_rows = constructor_rows(WORLD / "EnemyDropLocations.py", "EnemyDropLocationData")
    scenes = scene_display_names(enemy_rows)
    for filename in ("SceneTransitionCatalog.json", "DungeonDoorCatalog.json"):
        for row in json.loads((WORLD / filename).read_text(encoding="utf-8")):
            name = row["name"]
            arrival = None
            if row["mode"] == "door":
                passage = re.sub(r"\s+\(door \d+, room [^)]+\)$", "",
                                 name.removeprefix("Dungeon Door: "))
                source, target = passage.split(" -> ", 1)
                source_scene, target_scene = scenes[row["source_scene"]], scenes[row["target_scene"]]
                source = concise_room(source, source_scene)
                target = concise_room(target, target_scene)
                # Keep one scene heading for the physical passage, and a fully
                # qualified arrival for a shuffle into a different dungeon.
                arrival = f"{target_scene}: {target}"
                destination = target if row["source_scene"] == row["target_scene"] else arrival
                name = f"Door: {source_scene}: {source} -> {destination}"
                if row["id"] in MAZE_PASSAGES:
                    name = "Door: Gerudo Training Ground: Central Maze - " + MAZE_PASSAGES[row["id"]]
            descriptions[row["id"]] = {
                "name": name, "legacy_name": row["name"], "kind": row["mode"],
                "source_scene": row.get("source_scene", -1), "door": row.get("door", -1),
                "room_from": row.get("room_from", -1), "room_to": row.get("room_to", -1),
                "side": row.get("side", -1),
            }
            if arrival is not None:
                descriptions[row["id"]]["arrival_name"] = arrival

    enemy_names = {}
    for row in enemy_rows:
        legacy, identity, scene, room, *unused = row
        token = row[10]
        match = re.fullmatch(r"Enemy Defeat: (.+) Room \d+ (.+)", legacy)
        name = legacy
        if match:
            region = graph[token]["name"] if token in graph else match[1]
            # Keep scene distinctions such as Market Ruins and individual
            # graves; use a mapped physical subsection when one is available.
            if token in {
                "KF_OUTSIDE_DEKU_TREE", "GV_UPPER_STREAM", "GV_LOWER_STREAM",
                "DMC_CENTRAL_LOCAL", "ZF_HIDDEN_LEDGE", "ZF_HIDDEN_CAVE",
                "SFM_ENTRYWAY", "WASTELAND_NEAR_COLOSSUS",
            }:
                region = regions[token]
            name = f"Enemy Defeat: {region} - {match[2]}"
        enemy_names[identity] = name
        descriptions[identity] = {
            "name": name, "legacy_name": legacy, "kind": "enemy",
            "source_scene": scene, "door": -1, "room_from": room,
            "room_to": -1, "side": -1, "region_token": token,
        }

    # Some exact native regions span multiple physical room files. Their old
    # enemy ordinals restarted per file. Number that species across the actual
    # descriptive region in stable ID order, without inventing finer geometry.
    counts = Counter(enemy_names.values())
    duplicate_bases = {re.sub(r" \d+$", "", name) for name, count in counts.items() if count > 1}
    grouped = defaultdict(list)
    for identity, name in enemy_names.items():
        base = re.sub(r" \d+$", "", name)
        if base in duplicate_bases:
            grouped[base].append(identity)
    for base, identities in grouped.items():
        for number, identity in enumerate(sorted(identities), 1):
            descriptions[identity]["name"] = f"{base} {number}"

    canonical = [row["name"] for row in descriptions.values()]
    legacy = [row["legacy_name"] for row in descriptions.values()]
    if len(canonical) != len(set(canonical)) or len(legacy) != len(set(legacy)):
        raise ValueError("A descriptive check name or legacy alias is ambiguous.")
    if any(re.search(r"\(door \d+|\bRoom \d+\b", name) for name in canonical):
        raise ValueError("An internal room/door number remains in a canonical check name.")
    return dict(sorted(descriptions.items()))


def outputs():
    descriptions = build_descriptions()
    include = ["// Generated by tools/generate_check_descriptions.py; do not edit manually.\n",
               "// Stable AP identity, canonical name, legacy alias, and physical source metadata.\n"]
    for identity, row in descriptions.items():
        names = f"{json.dumps(row['name'], ensure_ascii=False)}, {json.dumps(row['legacy_name'], ensure_ascii=False)}"
        numbers = ", ".join(str(row.get(key, -1)) for key in
                            ("source_scene", "door", "room_from", "room_to", "side"))
        include.append(f"{{ {identity}, {names}, {numbers} }},\n")
    return {
        WORLD / "CheckDescriptions.json": json.dumps(descriptions, ensure_ascii=False, indent=2) + "\n",
        ROOT / "soh/Network/Archipelago/CheckDescriptions.inc": "".join(include),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    for path, expected in outputs().items():
        if args.check:
            if not path.is_file() or path.read_text(encoding="utf-8") != expected:
                raise SystemExit(f"Generated check descriptions are stale: {path}")
        else:
            path.write_text(expected, encoding="utf-8", newline="\n")
        print(path.relative_to(ROOT).as_posix())


if __name__ == "__main__":
    main()
