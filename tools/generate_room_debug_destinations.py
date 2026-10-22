"""Refresh exact scene-exit identities on the physical room-debug door table.

The first eleven fields are authored physical scene/room/door metadata. Only
the optional trailing entrance identity is derived here, from the immutable
SceneTransitionCatalog source and target region pair. Matching only a target
scene would confuse entrances such as Kakariko Potion Shop's front and back.
Run with --check to verify the shipped table without modifying it.
"""

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TABLE = ROOT / "soh/Enhancements/randomizer/RoomDebugDoorData.inc"
CATALOG = ROOT / "archipelago/soh_extreme/SceneTransitionCatalog.json"
NOTE = "// Scene-exit identities refreshed by tools/generate_room_debug_destinations.py."


def output():
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    result = []
    identities = 0
    for line in TABLE.read_text(encoding="utf-8").splitlines():
        if line == NOTE:
            continue
        if not line.strip().startswith("{"):
            result.append(line)
            continue
        row = json.loads("[" + line.strip()[1:-2] + "]")
        if len(row) not in (11, 12):
            raise ValueError("Unexpected room-debug door schema")
        row = row[:11]
        if row[2] < 0:
            candidates = [entry for entry in catalog
                          if entry["mode"] == "entrance"
                          and entry["source"].replace("_", " ").title() == row[9]
                          and entry["target"].replace("_", " ").title() == row[10]]
            if len(candidates) != 1 or candidates[0]["target_scene"] != row[5]:
                raise ValueError(f"Ambiguous scene-exit door: {row}")
            row.append(candidates[0]["entrances"][0])
            identities += 1
        result.append("    { " + ", ".join(json.dumps(value) for value in row) + " },")
    result.insert(1, NOTE)
    return "\n".join(result) + "\n", identities


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected, count = output()
    if args.check:
        if TABLE.read_text(encoding="utf-8") != expected:
            raise SystemExit(f"Scene-exit identities are stale: {TABLE}")
    else:
        TABLE.write_text(expected, encoding="utf-8", newline="\n")
    print(f"{count} exact scene-exit door identities verified")


if __name__ == "__main__":
    main()
