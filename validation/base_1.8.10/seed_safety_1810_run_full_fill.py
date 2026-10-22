"""Complete official AP fill plus immutable, deterministic final hint generation."""
from pathlib import Path
import hashlib
import json
import runpy
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source"
paths = [p for p in (SOURCE / "archipelago/soh_extreme").rglob("*")
         if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"]
before = {p.relative_to(SOURCE).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
report_path = Path(sys.argv[sys.argv.index("--report") + 1])
script = SOURCE / "tools/tests/validate_user_full_fill.py"
module = runpy.run_path(str(script))
world_class = module["SohExtremeWorld"]
original = world_class.fill_slot_data
observed = []


def shared_rng_state(world):
    from BaseClasses import ThreadBarrierProxy
    rng = world.multiworld.random
    if isinstance(rng, ThreadBarrierProxy) and not rng.passthrough:
        # Official AP deliberately removes access after pre_output. Keep that
        # guard active: successful hint calls then prove they never request it.
        return ("official_output_guard", id(rng))
    return ("readable_state", rng.getstate())


def placements(world):
    return [
        (loc.player, loc.address, loc.name, None if loc.item is None else
         (loc.item.player, loc.item.code, loc.item.name, int(loc.item.classification)))
        for loc in world.multiworld.get_locations()
    ]


def inspect_slot_data(world):
    placed_before = placements(world)
    create_hints = original.__globals__["CreateInGameHints"]
    world_rng = world.random.getstate()
    multiworld_rng = shared_rng_state(world)
    expected_hints = create_hints(world)
    assert placements(world) == placed_before, "Hint generation changed item placements"
    assert world.random.getstate() == world_rng, "Hint generation changed world RNG"
    assert shared_rng_state(world) == multiworld_rng, "Hint generation changed multiworld RNG or its output guard"
    started = time.monotonic()
    first = original(world)
    first_seconds = time.monotonic() - started
    assert placements(world) == placed_before, "Slot data changed item placements"
    # fill_slot_data retains its existing random archipelago_seed field. Test
    # the independently deterministic hint producer without changing that API.
    world_rng = world.random.getstate()
    multiworld_rng = shared_rng_state(world)
    started = time.monotonic()
    repeated_hints = create_hints(world)
    repeated_seconds = time.monotonic() - started
    from worlds.soh_extreme import EntranceSafety
    assert first['entrance_randomizer']['destination_policy_revision'] == EntranceSafety.POLICY_REVISION
    policies = EntranceSafety.POLICIES
    routes = world._er_mapping
    for source_id, target_id in routes.items():
        assert source_id in policies and target_id in policies
        assert EntranceSafety.allowed_route(source_id, target_id)
    hints = first["extreme_hint_data"]
    assert hints == expected_hints == repeated_hints, "Repeated final hints are nondeterministic"
    assert placements(world) == placed_before
    assert world.random.getstate() == world_rng
    assert shared_rng_state(world) == multiworld_rng
    assert isinstance(hints, dict) and hints
    kinds = {}
    for rows in hints.values():
        assert isinstance(rows, list)
        for row in rows:
            assert isinstance(row, dict)
            kind = row.get("type", row.get("kind", "item"))
            kinds[kind] = kinds.get(kind, 0) + 1
    encoded = json.dumps(hints, sort_keys=True, separators=(",", ":")).encode()
    area_audit = getattr(world, "_extreme_area_hint_audit", {})
    for row in getattr(world, "_extreme_area_hints", ()):
        if row["type"] == "woth":
            assert any(proof["area"] == row["area"] and
                       proof["all_goals_reachable_without_area"] is False
                       for proof in area_audit["proofs"])
        elif row["type"] == "barren":
            assert any(proof["area"] == row["area"] and proof["advancement_items"] == 0
                       for proof in area_audit["barren"])
    from collections import Counter
    from worlds.soh_extreme.SongNotes import selected_song_names, song_note_mask
    selected = selected_song_names(world.options)
    assert first['extreme_soh_cvars']['SongNoteSongMask'] == song_note_mask(world.options)
    assert first['extreme_soh_cvars']['SongNoteShuffle'] == int(bool(selected))
    assert set(first['progressive_song_requirements']) == {'Progressive ' + song for song in selected}
    song_placements = Counter(loc.item.name for loc in world.multiworld.get_filled_locations()
                              if loc.item and loc.item.player == world.player and
                              (loc.item.name in world.SONG_ITEMS or loc.item.name in first['progressive_song_requirements']))
    assert not (selected & set(song_placements)), "Selected complete songs bypassed progressive completion"
    observed.append({
        "selected_individual_note_songs": sorted(selected),
        "song_note_mask": song_note_mask(world.options),
        "song_item_placements": dict(sorted(song_placements.items())),
        "dungeon_door_mixed_outside": first['extreme_soh_cvars']['DungeonDoorMixedOutside'],
        "entrance_pool_policy_revision": first['entrance_randomizer']['pool_policy_revision'],
        "destination_policy_revision": EntranceSafety.POLICY_REVISION,
        "reviewed_mapped_arrivals": len(routes),
        "age_restricted_arrivals": sum(policies[target]["arrival_age_mask"] != EntranceSafety.BOTH for target in routes.values()),
        "slot": world.player, "hint_keys": len(hints), "hint_rows_by_kind": kinds,
        "hint_payload_sha256": hashlib.sha256(encoded).hexdigest(),
        "first_slot_data_seconds": round(first_seconds, 3),
        "repeated_hint_data_seconds": round(repeated_seconds, 3),
        "repeated_hint_data_identical": True, "placements_unchanged": True,
        "hint_generation_world_rng_unchanged": True,
        "hint_generation_multiworld_rng_check": multiworld_rng[0],
        "hint_generation_multiworld_rng_or_output_guard_unchanged": True,
        "area_proof_audit": area_audit,
    })
    return first


world_class.fill_slot_data = inspect_slot_data
try:
    sys.argv[0] = str(script)
    module["main"]()
finally:
    world_class.fill_slot_data = original

after = {p.relative_to(SOURCE).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
assert before == after, "Production AP source changed during full-fill validation"
data = json.loads(report_path.read_text())
player = data["validation"]["players"]["1"]
assert data["validation"]["passed"] and player["goal_met"]
assert player["checked"] == player["network_checks"]
assert data["world_version"] == "1.8.10"
assert data["initial_network_checks"] > 0 and data["initial_physical_checks"] > 0
assert data["initial_hyrule_field_reachable"]
assert data["saved_mixed_entrance_pools"] == ["all"]
assert data["native_overworld_flag"] == 1
assert set(data["enabled_entrance_categories"]) == set(data["expanded_mixed_categories"])
assert data["changed_overworld_endpoints"] > 0
assert observed
data.update(status="passed", source_sha256=before, source_unchanged_during_run=True,
            hint_generation=observed, yaml_sha256=hashlib.sha256(Path(data["yaml"]).read_bytes()).hexdigest())
report_path.write_text(json.dumps(data, indent=2) + "\n")
print(json.dumps({"status": data["status"], "age": data["age"], "seed": data["seed"],
                  "report": str(report_path), "hint_generation": observed}), flush=True)
