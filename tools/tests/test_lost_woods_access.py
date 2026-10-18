"""Audit every enabled Lost Woods check and the actual source entrance rules.

Run with official Archipelago 0.6.7 and this world installed on PYTHONPATH.
The supplied YAML is read only. Its entrance shuffle is disabled in isolated
worlds to distinguish vanilla approaches from legitimate randomized arrivals.
This exercises the real AP rules and age cache, not native gameplay geometry.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import random
import time

import ModuleUpdate
ModuleUpdate.update_ran = True
import settings
settings.no_gui = True
settings.skip_autosave = True
import yaml
from BaseClasses import CollectionState
from Generate import roll_settings
from test.general import setup_multiworld
from worlds.AutoWorld import call_all
from worlds.soh_extreme import SohExtremeWorld, EntranceRandomizer as ER, NpcSpeech, SceneTransitions
from worlds.soh_extreme._vendor_oot_soh import LogicHelpers as H
from worlds.soh_extreme._vendor_oot_soh.Enums import Ages, Items, Regions


FOREST_KEYS = {
    "LOST_WOODS", "LW_FOREST_EXIT", "LW_BEYOND_MIDO", "LW_BRIDGE_FROM_FOREST",
    "LW_BRIDGE", "LW_NEAR_SHORTCUTS_GROTTO", "LW_SCRUBS_GROTTO", "DEKU_THEATER",
}
FOREST_NAMES = {str(Regions[key]) for key in FOREST_KEYS}
BRIDGE_IDS = {30, 11000389, 11000525}
REPORTED = ["Progressive Scale", "Progressive Bomb Bag", "Bombchu Bag"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("yaml", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    started = time.monotonic()
    source = Path(__file__).resolve().parents[2]
    tracked = [p for p in (source / "archipelago/soh_extreme").rglob("*")
               if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"]
    hashes = {str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked}
    random.seed(186)
    rolled = roll_settings(yaml.safe_load(args.yaml.read_text()))
    options = {name: copy.deepcopy(getattr(rolled, name).value)
               for name in SohExtremeWorld.options_dataclass.type_hints}
    # AP option validation requires a literal dict, including for Counter values.
    options = {name: dict(value) if isinstance(value, dict) else value
               for name, value in options.items()}
    for key in ER.ENTRANCE_OPTIONS:
        options[key] = set() if key == "mixed_entrance_pools" else 0
    options.update(shuffle_swim=1, shuffle_climb=1, shuffle_rock_boulder_soul=1)
    worlds, assertions = [], []

    def expect(label, actual, expected):
        assertions.append({"case": label, "actual": actual, "expected": expected})
        assert actual == expected, assertions[-1]

    for age, swim in (("child", 1), ("adult", 1), ("child", 0)):
        mw = setup_multiworld(SohExtremeWorld, steps=(), seed=186,
                              options=dict(options, starting_age=age, shuffle_swim=swim))
        world = mw.worlds[1]
        for stage in ("generate_early", "create_regions", "create_items", "set_rules"):
            call_all(mw, stage)
        age_value = Ages[age.upper()]
        prefix = f"{age}/shuffle_swim={swim}"
        events = [loc for loc in world.get_locations() if loc.address is None]

        def make_state(items):
            state = CollectionState(mw)
            for name in items:
                state.collect(world.create_item(str(name)), True)
            state.sweep_for_advancements(locations=events)
            state._soh_extreme_age[1] = age_value
            return state

        def evaluate(rule, state):
            state._soh_extreme_age[1] = age_value
            return bool(rule(state))

        def edge(source_key, target_key):
            source_region = world.get_region(str(Regions[source_key]))
            matches = [e for e in source_region.exits if e.connected_region and
                       e.connected_region.name == str(Regions[target_key])]
            assert len(matches) == 1, (source_key, target_key, len(matches))
            return matches[0]

        physical_ids = {entry["id"] for entry in SceneTransitions.active_entries(world)
                        if entry["source_scene"] == 91 or entry["source"] in FOREST_KEYS}
        speech_ids = {entry["id"] for entry in NpcSpeech.active_entries(world)
                      if any(route["region"] in FOREST_KEYS for route in entry["routes"])}
        checks = sorted([loc for loc in world.get_locations() if loc.address is not None and (
            NpcSpeech.display_region(loc) in FOREST_NAMES or loc.address in physical_ids | speech_ids)],
            key=lambda loc: loc.address)
        assert len(checks) >= 82, len(checks)
        check_rows = [{"id": loc.address, "name": loc.name, "region": NpcSpeech.display_region(loc),
                       "available": {}} for loc in checks]
        results = []

        def observe(label, items):
            state = make_state(items)
            available = []
            for loc, row in zip(checks, check_rows):
                value = ER._reachable_at_starting_age(world, state, loc)
                row["available"][label] = bool(value)
                if value:
                    available.append(loc.address)
            reached = sorted(region for region in FOREST_NAMES | {"Sacred Forest Meadow", "SFM Entryway"}
                             if ER._reachable_at_starting_age(world, state, world.get_region(region)))
            results.append({"case": label, "items": list(map(str, items)), "reachable_regions": reached,
                            "available_ids": available, "physical_scale_count": state.count("Progressive Scale", 1),
                            "has_swim_event": state.has("Swim", 1)})
            return state, set(available), reached

        kf = edge("KOKIRI_FOREST", "LOST_WOODS")
        gc = edge("GC_WOODS_WARP", "LOST_WOODS")
        zr = edge("ZR_FROM_SHORTCUT", "LOST_WOODS")
        reverse_gc = edge("LOST_WOODS", "GC_WOODS_WARP")
        sfm = edge("SFM_ENTRYWAY", "SACRED_FOREST_MEADOW")

        if swim:
            state, available, reached = observe("reported", REPORTED)
            expect(prefix + ": main woods blocked", "Lost Woods" in reached, False)
            expect(prefix + ": no non-bridge check available", sorted(available - BRIDGE_IDS), [])
            if age == "child":
                expect(prefix + ": all three independent bridge checks remain", sorted(available), sorted(BRIDGE_IDS))
            for name, route in (("KF climb", kf), ("GC rock tunnel", gc), ("ZR deep shortcut", zr),
                                ("GC reverse tunnel", reverse_gc), ("SFM entry", sfm)):
                expect(prefix + ": reported " + name, evaluate(route.access_rule, state), False)
            for identity, route in ((286, kf), (1238, gc), (1242, zr)):
                row = ER.ENDPOINTS[identity]
                expect(prefix + f": endpoint {identity} has no replacement condition", "condition" in row, False)
                expect(prefix + f": endpoint {identity} retains missing-item gate",
                       evaluate(ER._source_rule(world, row), state), False)

            for label, extra, route in (("plus climb", ["Climb"], kf),
                                       ("plus rock soul", ["Rock / Boulder Soul"], gc),
                                       ("plus silver scale", ["Progressive Scale"], zr)):
                positive, _, positive_regions = observe(label, REPORTED + extra)
                expect(prefix + ": " + label + " source opens", evaluate(route.access_rule, positive), True)
                expect(prefix + ": " + label + " reaches main woods", "Lost Woods" in positive_regions, True)
            if age == "adult":
                expect(prefix + ": SFM helper requires Silver, not Bronze",
                       evaluate(sfm.access_rule, make_state(REPORTED + ["Progressive Scale"])), True)

            # A learned warp still needs its physical instrument and buttons.
            song = str(Items.MINUET_OF_FOREST)
            notes = list(world.SONG_NOTE_GROUPS[song]) if world.options.song_note_shuffle.value else [song]
            instrument = [Items.PROGRESSIVE_OCARINA, *H.ocarina_buttons_required[Items.MINUET_OF_FOREST]]
            _, _, no_instrument = observe("minuet without instrument", REPORTED + notes)
            expect(prefix + ": notes alone do not open SFM", "Sacred Forest Meadow" in no_instrument, False)
            _, _, warped = observe("playable minuet", REPORTED + notes + instrument)
            expect(prefix + ": playable Minuet reaches SFM", "Sacred Forest Meadow" in warped, True)

            # Local checks remain soul gated even after a valid climb arrival.
            climbed = make_state(REPORTED + ["Climb"])
            rock_ids = {9700544, 9700545, 9700547, 1609}
            for loc in checks:
                if loc.address in rock_ids:
                    expect(prefix + f": rock check {loc.address} needs soul",
                           bool(ER._reachable_at_starting_age(world, climbed, loc)), False)
            for start, target in (("LOST_WOODS", "LW_NEAR_SHORTCUTS_GROTTO"),
                                  ("LW_BEYOND_MIDO", "LW_SCRUBS_GROTTO")):
                expect(prefix + ": soul-gated grotto " + target,
                       evaluate(edge(start, target).access_rule, climbed), False)
            # Each submerged rupee uses the deep-water threshold independently.
            for loc in checks:
                if 1610 <= loc.address <= 1617:
                    expect(prefix + f": underwater check {loc.address} with Bronze",
                           evaluate(loc.access_rule, climbed), False)
                    expect(prefix + f": underwater check {loc.address} with Silver",
                           evaluate(loc.access_rule, make_state(REPORTED + ["Climb", "Progressive Scale"])),
                           age == "child")
        else:
            state, _, reached = observe("innate surface swim", ["Progressive Bomb Bag", "Bombchu Bag"])
            expect(prefix + ": innate Bronze is counted", state.count("Progressive Scale", 1), 1)
            expect(prefix + ": innate swim cannot deep dive", evaluate(zr.access_rule, state), False)
            expect(prefix + ": no unearned main woods", "Lost Woods" in reached, False)
            silver, _, silver_regions = observe("first received scale is Silver", REPORTED)
            expect(prefix + ": one received scale plus innate Bronze is Silver", silver.count("Progressive Scale", 1), 2)
            expect(prefix + ": Silver opens river shortcut", evaluate(zr.access_rule, silver), True)
            expect(prefix + ": Silver reaches main woods", "Lost Woods" in silver_regions, True)

        worlds.append({"starting_age": age, "shuffle_swim": swim, "enabled_checks": len(checks),
                       "precollected_items": [i.name for i in mw.precollected_items[1]],
                       "scenarios": results, "checks": check_rows})

    expect("production source unchanged during audit",
           {str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked}, hashes)
    # Keep the detailed assertion payload compact: hashes are already recorded separately.
    assertions[-1]["actual"] = assertions[-1]["expected"] = "unchanged"
    report = {"status": "passed", "world_version": "1.8.6", "archipelago_version": "0.6.7",
              "scope": "Every enabled Lost Woods/bridge/grotto/theater check and any NPC with a Lost Woods route, "
                       "plus actual KF/GC/ZR source predicates and ER predicate reuse. Three real AP worlds; "
                       "vanilla entrance topology isolated from YAML. No native gameplay or ROM geometry audit.",
              "yaml_sha256": hashlib.sha256(args.yaml.read_bytes()).hexdigest(),
              "elapsed_seconds": round(time.monotonic() - started, 3), "assertion_count": len(assertions),
              "assertions": assertions, "worlds": worlds, "source_sha256": hashes}
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": "passed", "assertions": len(assertions),
                      "enabled_checks_per_world": [w["enabled_checks"] for w in worlds],
                      "elapsed_seconds": report["elapsed_seconds"]}), flush=True)


if __name__ == "__main__":
    main()
