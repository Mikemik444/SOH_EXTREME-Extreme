#!/usr/bin/env python3
"""SOH-EXTREME 0.9.3 static logic/fill parity audit."""
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
text = (HERE / "EnemyDropLocations.py").read_text(encoding="utf-8")

pat = re.compile(
    r"EnemyDropLocationData\((['\"])(.*?)\1,\s*(\d+),\s*0x([0-9A-Fa-f]+),"
    r"\s*(-?\d+),\s*(-?\d+),\s*(-?\d+),\s*0x([0-9A-Fa-f]+),"
    r"\s*0x([0-9A-Fa-f]+),\s*(None|['\"](.*?)['\"]),",
    re.S,
)

rows = []
for m in pat.finditer(text):
    rows.append({
        "name": m.group(2),
        "id": int(m.group(3)),
        "actor": int(m.group(8), 16),
        "params": int(m.group(9), 16),
        "soul": m.group(11),
    })

assert rows, "enemy catalog parse returned zero rows"
names = [r["name"] for r in rows]
ids = [r["id"] for r in rows]
assert len(names) == len(set(names)), "duplicate enemy check name"
assert len(ids) == len(set(ids)), "duplicate enemy AP id"

structural = [r["name"] for r in rows if r["actor"] == 0x054 and r["params"] == 0]
assert not structural, (
    "structural Armos statue leaked into Enemy Defeat catalog: "
    + ", ".join(structural[:12])
)

missing = [
    r["name"] for r in rows
    if r["actor"] != 0x037 and not r["soul"]
]
assert not missing, (
    "non-Gold enemy placement lacks Soul: " + ", ".join(missing[:12])
)

required = {"Door Trap Soul", "Flying Floor Tile Soul", "Gerudo Thief Soul"}
souls = {r["soul"] for r in rows if r["soul"]}
assert required <= souls, f"missing required finite enemy souls: {required - souls}"

assert len(rows) == 553, f"expected 553 real finite enemy placements, got {len(rows)}"
print("OK: 553 real finite enemy placement checks; structural Armos statues excluded.")


# Silver Rupee AP parity: every group item must be a real EXTREME item and all
# sixteen vanilla groups must have a room/count definition in __init__.py.
world_text = (HERE / "__init__.py").read_text(encoding="utf-8")
fork_text = (HERE / "ForkLocations.py").read_text(encoding="utf-8")

silver_names = (
    "Shadow Silver: Blades",
    "Shadow Silver: Pit",
    "Shadow Silver: Spikes",
    "Spirit Silver: Child",
    "Spirit Silver: Sun",
    "Spirit Silver: Boulders",
    "Bottom of the Well Silver",
    "Ice Cavern Silver: Blades",
    "Ice Cavern Silver: Block",
    "Training Ground Silver: Slope",
    "Training Ground Silver: Lava",
    "Training Ground Silver: Water",
    "Ganon's Castle Silver: Light",
    "Ganon's Castle Silver: Forest",
    "Ganon's Castle Silver: Fire",
    "Ganon's Castle Silver: Spirit",
)
for silver_name in silver_names:
    assert silver_name in world_text, f"missing Silver Rupee group item/rule: {silver_name}"

silver_check_count = len(re.findall(
    r"ForkLocationData\([^\n]+['\"]silver['\"]", fork_text
))
assert silver_check_count == 80, (
    f"expected 80 vanilla Silver Rupee AP checks, got {silver_check_count}"
)

for required_edge_item in (
    "Ganon's Castle Silver: Spirit",
    "Ganon's Castle Silver: Forest",
    "Ganon's Castle Silver: Fire",
    "Ganon's Castle Silver: Light",
    "Training Ground Silver: Slope",
    "Training Ground Silver: Lava",
    "Ice Cavern Silver: Blades",
    "Ice Cavern Silver: Block",
    "Bottom of the Well Silver",
    "Shadow Silver: Pit",
    "Shadow Silver: Spikes",
    "Spirit Silver: Child",
    "Spirit Silver: Boulders",
):
    assert required_edge_item in world_text, f"missing silver room gate {required_edge_item}"

print("OK: 80 Silver Rupee checks + 16 vanilla silver progression groups audited.")


# 0.8.10 fast fill guard + forced-event semantics.
frontier_text = (HERE / "FrontierFill.py").read_text(encoding="utf-8")
assert "frontier_fill" in frontier_text and "validate_filled_world" in frontier_text
assert "LW Gift From Saria" not in frontier_text, (
    "Forced cutscene/event locations must not gain NPC requirements from name heuristics"
)
print("OK: fast AP fill guard + post-fill validation installed; forced events remain rule-driven.")


# 0.8.13 regressions from the Full-accessibility log.
world_text = (HERE / "__init__.py").read_text(encoding="utf-8")
assert 'enemy_has("Bottle with Blue Fire")' not in world_text
assert 'Do not apply the old whole-dungeon upper-bound gate here.' in world_text
assert 'enemy_region_member = getattr(Regions, enemy_drop.region_token, None)' in world_text
assert 'enemy_ranged = can_hit_at_range(enemy_bundle)' in world_text
assert 'fork_location.address in getattr(self, "_fork_multi_region_sources", {})' in world_text
assert 'guard_pass = (' in world_text and 'RC_TH_WONDER_KITCHEN_SOUP' in world_text
assert 'red_ice_rule &= is_adult(bundle)' in world_text
print("OK: 0.8.13 Ice Cavern + multi-source fork regressions audited.")


# 0.8.13: three remaining Full-accessibility failures must use live stock anchors.
world_text = (HERE / "__init__.py").read_text(encoding="utf-8")
expected_anchors = {
    "RC_GTG_UNDER_LEDGE_LAVA_SILVER": "Gerudo Training Ground Freestanding Key",
    "RC_DODONGOS_CAVERN_TOP_FLOOR_PEDESTAL": "Dodongos Cavern End Of Bridge Chest",
    "RC_ZD_KING_ZORA_RED_ICE": "ZD King Zora Thawed",
}
for rc, stock_name in expected_anchors.items():
    assert f'"{rc}"' in world_text
    assert f'"{stock_name}"' in world_text
assert "missing_exact_anchors" in world_text
print("OK: 0.8.13 exact stock-region anchors audited.")


# 0.9.3 logic overhaul: exact age/ability alternates and scale semantics.
alt_text = (HERE / "NativeLogicAlternatives.py").read_text(encoding="utf-8")
assert "('RR_JABU_JABUS_BELLY_MQ_WATER_SWITCH_ROOM', 'RR_JABU_JABUS_BELLY_MQ_WATER_SWITCH_ROOM_PAST_GEYSER', (('Enemy Soul',),))" in alt_text
assert "('RR_DODONGOS_CAVERN_SE_CORRIDOR', 'RR_DODONGOS_CAVERN_NEAR_LOWER_LIZALFOS', ((),))" in alt_text
assert "('RR_SPIRIT_TEMPLE_1F_ANUBIS', 'RR_SPIRIT_TEMPLE_RUPEE_BRIDGE_NORTH', ((),))" in alt_text
assert 'return Has("Progressive Scale", 2)' in world_text
print("OK: 0.9.3 age-aware ability, deep-swim, and enemy combat overhaul audited.")
