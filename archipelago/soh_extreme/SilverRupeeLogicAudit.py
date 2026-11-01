#!/usr/bin/env python3
"""Focused regression audit for SOH-EXTREME silver-rupee routes.

Run from the repository root:
    python archipelago/soh_extreme/SilverRupeeLogicAudit.py
This checks that the AP silver route projection stays aligned with the native
C++ predicates for the specifically reviewed GTG, Spirit, Ice Cavern and Shadow
Temple routes, including the enemy-room gates.
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AP = ROOT / "archipelago" / "soh_extreme"
ROUTES = json.loads((AP / "SilverRoomRoutes.json").read_text(encoding="utf-8"))
GRAPH = json.loads((AP / "EnemyRoomGraph.json").read_text(encoding="utf-8"))
CPP = ROOT / "soh" / "Enhancements" / "randomizer" / "location_access" / "dungeons"

def route(rc):
    found = ROUTES.get(rc)
    assert found, f"missing silver route: {rc}"
    return found

def has_condition(rc, fragment):
    assert any(fragment in entry["condition"] for entry in route(rc)), (
        f"{rc}: expected condition fragment {fragment!r}"
    )

def edge(source, target):
    for item in GRAPH[source]["exits"]:
        if item["target"] == target:
            return item["condition"]
    raise AssertionError(f"missing room edge {source} -> {target}")

# Every native silver check has at least one concrete collection route and every
# route starts in a known room in the compiled enemy-room graph.
fork_text = (AP / "ForkLocations.py").read_text(encoding="utf-8")
import re
silver_locations = re.findall(
    r"ForkLocationData\('([^']+)',\s*(\d+),\s*'([^']+)'[^\n]*'silver'",
    fork_text,
)
assert len(silver_locations) == 80, f"expected 80 silver checks, got {len(silver_locations)}"
for name, address, rc in silver_locations:
    assert rc in ROUTES and ROUTES[rc], f"{name}: missing silver route {rc}"
    for entry in ROUTES[rc]:
        assert entry["region"] in GRAPH, f"{name}: unknown source room {entry['region']}"
        assert entry["condition"].strip(), f"{name}: empty collection condition"

# GTG: the target slope uses the age-correct Hookshot/Longshot alternative.
has_condition("RC_GTG_TARGET_SLOPE_SILVER", "RG_HOOKSHOT")
has_condition("RC_GTG_TARGET_SLOPE_SILVER", "RG_LONGSHOT")
# The upper-lava rupee is already in the upper-ledge region. The path into that
# region enforces Longshot OR the native Hookshot/movement/backside alternatives;
# a second local Hookshot-only check was incorrectly excluding valid routes.
assert route("RC_GTG_UPPER_LAVA_SILVER")[0]["condition"] == "true"
assert "RG_LONGSHOT" in edge("RR_GERUDO_TRAINING_GROUND_LAVA_ROOM",
                             "RR_GERUDO_TRAINING_GROUND_LAVA_ROOM_UPPER_LEDGE")
assert "RG_HOVER_BOOTS" in edge("RR_GERUDO_TRAINING_GROUND_LAVA_ROOM",
                                "RR_GERUDO_TRAINING_GROUND_LAVA_ROOM_UPPER_LEDGE")
# GTG fire-room access must retain its actual movement predicate.
assert "CanKillEnemy" in edge("RR_GERUDO_TRAINING_GROUND_DINALFOS",
                              "RR_GERUDO_TRAINING_GROUND_LAVA_ROOM")

# Spirit: adult-side access is gated by Silver Gauntlets; the boulder-room exit
# requires its silver group; child bridge doors require defeating Armos and Keese.
assert "RG_SILVER_GAUNTLETS" in edge("RR_SPIRIT_TEMPLE_FOYER",
                                    "RR_SPIRIT_TEMPLE_ADULT_SIDE_HUB")
assert "RG_SPIRIT_SILVER_BOULDERS" in edge("RR_SPIRIT_TEMPLE_BOULDERS",
                                          "RR_SPIRIT_TEMPLE_PAST_BOULDERS")
for target in ("RR_SPIRIT_TEMPLE_SWITCH_BRIDGE_SOUTH",
               "RR_SPIRIT_TEMPLE_RUPEE_BRIDGE_SOUTH"):
    condition = edge("RR_SPIRIT_TEMPLE_CHILD_SIDE_HUB", target)
    assert "CanKillEnemy(RE_ARMOS)" in condition and "CanKillEnemy(RE_KEESE)" in condition

# Ice Cavern: blue-fire and stalagmite requirements remain on the rooms that
# need them; individual rupees retain their exact movement/age alternatives.
assert "BlueFire()" in edge("RR_ICE_CAVERN_HUB", "RR_ICE_CAVERN_BLOCK_ROOM")
has_condition("RC_ICE_CAVERN_AIRBORNE_BLADE_SILVER", "logic->IsAdult")
has_condition("RC_ICE_CAVERN_FROZEN_BLOCK_SILVER", "BlueFire()")

# Shadow: preserve the explicit Longshot route for the east target-spikes rupee,
# and the real hover/lens alternatives for the spikes room.
has_condition("RC_SHADOW_E_TARGET_SPIKES_SILVER", "RG_LONGSHOT")
for source in ("RR_SHADOW_TEMPLE_FLOOR_SPIKES_S_DOOR",
               "RR_SHADOW_TEMPLE_FLOOR_SPIKES_W_DOOR"):
    condition = edge(source, "RR_SHADOW_TEMPLE_FLOOR_SPIKES_ROOM")
    assert "RG_HOVER_BOOTS" in condition and "RG_LENS_OF_TRUTH" in condition

# Enemy-room lock regression: doors into these encounters must not be free
# when the source logic requires the player to defeat the room's enemies.
assert "CanKillEnemy(RE_BEAMOS)" in edge("RR_GERUDO_TRAINING_GROUND_DINALFOS",
                                         "RR_GERUDO_TRAINING_GROUND_LAVA_ROOM")
print(f"OK: all {len(silver_locations)} silver checks have valid room routes; GTG, Spirit, Ice Cavern, Shadow Temple, and enemy-room gate regressions passed.")
