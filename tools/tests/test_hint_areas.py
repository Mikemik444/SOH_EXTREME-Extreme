"""Check actual final-area proofs and typed item hints using official AP state sweeps.

Run with the official Archipelago runtime and dependencies on PYTHONPATH.
These small placed worlds exercise CollectionState/can_beat_game, without ROM IO.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

import ModuleUpdate
ModuleUpdate.update_ran = True
import settings
settings.no_gui = True
settings.skip_autosave = True

from BaseClasses import Item, ItemClassification, Location, MultiWorld, Region
from worlds.AutoWorld import World
from worlds.soh_extreme import HintAreas
from worlds.soh_extreme._vendor_oot_soh import Hints
from worlds.soh_extreme._vendor_oot_soh.Enums import HintKeys, Items, Regions


class HintOptions:
    def __init__(self, **enabled):
        self.enabled = {"gossip_stone_hints": 1, **enabled}

    def __getattr__(self, name):
        return SimpleNamespace(value=self.enabled.get(name, 0))


def fixture(players=1):
    mw = MultiWorld(players)
    mw.set_seed(186)
    mw.seed_name = "area-proof-fixture"
    mw.player_name = {player: f"Player {player}" for player in mw.player_ids}
    for player in mw.player_ids:
        world = World(mw, player)
        world.game = "SOH-EXTREME" if player == 1 else "Foreign Game"
        world.options = HintOptions()
        world.using_ut = False
        mw.worlds[player] = world
        mw.game[player] = world.game
        mw.regions.append(Region("Menu", player, mw))
    mw._soh_final_validation = {"passed": True}
    return mw, mw.worlds[1]


def add_area(mw, name, entries, player=1, access_rule=None):
    region = Region(name, player, mw)
    mw.regions.append(region)
    mw.get_region("Menu", player).connect(region, rule=access_rule)
    for item_name, flags, recipient in entries:
        address = 1000 + len(mw.get_locations())
        location = Location(player, f"{name} check {address}", address, region)
        region.locations.append(location)
        location.item = Item(str(item_name), flags, address + 10000, recipient)
        location.item.location = location
    return region


def placed(mw):
    return [(loc.player, loc.address, loc.name, loc.item.player, loc.item.code,
             loc.item.name, int(loc.item.classification)) for loc in mw.get_locations() if loc.item]


P = ItemClassification.progression
F = ItemClassification.filler


class AreaProofTests(unittest.TestCase):
    def test_required_area_is_proved_optional_progression_is_not(self):
        mw, world = fixture()
        add_area(mw, "Necessary Room", [("Goal Key", P, 1), ("Rupees", F, 1)])
        add_area(mw, "Optional Room", [("Optional Bow", P, 1), ("Rupees", F, 1)])
        add_area(mw, "Empty Room", [("Rupees", F, 1), ("Useful Map", ItemClassification.useful, 1)])
        mw.completion_condition[1] = lambda state: state.has("Goal Key", 1)
        self.assertTrue(mw.can_beat_game())
        before, rng = placed(mw), (world.random.getstate(), mw.random.getstate())
        HintAreas.prepare_hint_areas(world)
        self.assertEqual({("woth", "Necessary Room"), ("barren", "Empty Room")},
                         {(row["type"], row["area"]) for row in world._extreme_area_hints})
        proofs = {row["area"]: row for row in world._extreme_area_hint_audit["proofs"]}
        self.assertFalse(proofs["Necessary Room"]["all_goals_reachable_without_area"])
        self.assertTrue(proofs["Optional Room"]["all_goals_reachable_without_area"])
        self.assertEqual(before, placed(mw))
        self.assertEqual(rng, (world.random.getstate(), mw.random.getstate()))
        first = deepcopy((world._extreme_area_hints, world._extreme_area_hint_audit))
        HintAreas.prepare_hint_areas(world)
        self.assertEqual(first, (world._extreme_area_hints, world._extreme_area_hint_audit))

    def test_remote_progression_contributes_to_actual_all_player_goal(self):
        mw, world = fixture(2)
        add_area(mw, "Remote Goal Room", [("Foreign Victory", P, 2), ("Local Rupees", F, 1)])
        add_area(mw, "Local Empty Room", [("Rupees", F, 1), ("Rupees", F, 2)])
        mw.completion_condition[2] = lambda state: state.has("Foreign Victory", 2)
        self.assertTrue(mw.can_beat_game())
        HintAreas.prepare_hint_areas(world)
        self.assertIn({"type": "woth", "area": "Remote Goal Room", "finder": "Player 1",
                       "game": "SOH-EXTREME", "finding_player": 1, "scope": "checks_in_region"},
                      world._extreme_area_hints)
        self.assertNotIn("Remote Goal Room", {row["area"] for row in world._extreme_area_hints
                                              if row["type"] == "barren"})

    def test_redundant_progression_does_not_create_false_hero_region(self):
        mw, world = fixture()
        for name in ("First Copy Room", "Second Copy Room"):
            add_area(mw, name, [("Victory", P, 1), ("Rupees", F, 1)])
        mw.completion_condition[1] = lambda state: state.has("Victory", 1)
        HintAreas.prepare_hint_areas(world)
        self.assertEqual([], world._extreme_area_hints)
        self.assertTrue(all(row["all_goals_reachable_without_area"]
                            for row in world._extreme_area_hint_audit["proofs"]))

    def test_withheld_check_cannot_reappear_through_automatic_event_sweep(self):
        mw, world = fixture()
        add_area(mw, "Key Room", [("Door Key", P, 1), ("Rupees", F, 1)])
        last = add_area(mw, "Locked Room", [("Victory", P, 1), ("Rupees", F, 1)],
                        access_rule=lambda state: state.has("Door Key", 1))
        event = Location(1, "Goal Event", None, last)
        last.locations.append(event)
        event.item = Item("Victory Event", P, None, 1)
        event.item.location = event
        event.access_rule = lambda state: state.has("Victory", 1)
        mw.completion_condition[1] = lambda state: state.has("Victory Event", 1)
        self.assertTrue(mw.can_beat_game())
        HintAreas.prepare_hint_areas(world)
        self.assertEqual({"Key Room", "Locked Room"},
                         {row["area"] for row in world._extreme_area_hints if row["type"] == "woth"})
        self.assertTrue(all(None not in row["locations"] for row in world._extreme_area_hint_audit["proofs"]))

    def test_unvalidated_tracker_or_disabled_hints_never_claim_area_proofs(self):
        for mode in ("unvalidated", "tracker", "disabled"):
            with self.subTest(mode=mode):
                mw, world = fixture()
                add_area(mw, "Room", [("Goal", P, 1), ("Rupees", F, 1)])
                mw.completion_condition[1] = lambda state: state.has("Goal", 1)
                if mode == "unvalidated": mw._soh_final_validation = {"passed": False}
                if mode == "tracker": world.using_ut = True
                if mode == "disabled": world.options.enabled["gossip_stone_hints"] = 0
                HintAreas.prepare_hint_areas(world)
                self.assertEqual([], world._extreme_area_hints)
                self.assertEqual([], world._extreme_area_hint_audit["proofs"])

    def test_proof_budget_is_bounded_and_never_forces_a_false_hero_hint(self):
        mw, world = fixture()
        for index in range(HintAreas.MAX_WOTH_PROOFS + 6):
            add_area(mw, f"Optional Room {index}", [(f"Optional {index}", P, 1), ("Rupees", F, 1)])
        HintAreas.prepare_hint_areas(world)
        self.assertEqual(HintAreas.MAX_WOTH_PROOFS, len(world._extreme_area_hint_audit["proofs"]))
        self.assertEqual([], world._extreme_area_hints)

    def test_physical_names_root_exclusion_and_moving_npc_route_coverage(self):
        mw, world = fixture()
        region = add_area(mw, "Logical Arrival", [("Goal", P, 1), ("Rupees", F, 1)])
        physical = region.locations[0]
        physical._er_display_region = "Physical Door Room"
        root = mw.get_region("Menu", 1)
        start = Location(1, "Pocket", 9900, root)
        start.item = Item("Pocket Item", P, 9901, 1)
        root.locations.append(start)
        name, speech = next((name, row) for name, row in HintAreas.SPEECH_BY_NAME.items()
                            if len({r["region"] for r in row.get("routes", ())}) > 1)
        npc = Location(1, name, 9902, root)
        npc.item = Item("Moving NPC Progression", P, 9903, 1)
        root.locations.append(npc)
        groups = HintAreas.physical_check_groups(world)
        self.assertIn(physical, groups["Physical Door Room"])
        self.assertNotIn(physical, groups["Logical Arrival"])
        self.assertNotIn("Menu", groups)
        self.assertNotIn(start, set().union(*groups.values()))
        for route in speech["routes"]:
            self.assertIn(npc, groups[str(Regions[route["region"]])])

    def test_stones_keep_item_majority_and_both_proven_area_kinds(self):
        mw, world = fixture()
        world._extreme_area_hints = [
            {"type": kind, "area": f"{kind} room {index}", "finder": "Player 1"}
            for kind in ("woth", "barren") for index in range(4)
        ]
        stones = [key for key in HintKeys if key.name.endswith("GOSSIP_STONE")]
        result = {stone.value: [{"type": "item", "item": "Progression"}] for stone in stones}
        result["special NPC"] = [{"type": "item", "item": "Static Hint"}]
        before, rng = deepcopy(result), (world.random.getstate(), mw.random.getstate())
        HintAreas.apply_area_hints(world, result, stones)
        kinds = [result[stone.value][0]["type"] for stone in stones]
        self.assertIn("woth", kinds)
        self.assertIn("barren", kinds)
        self.assertGreater(kinds.count("item"), len(kinds) // 2)
        self.assertEqual(before["special NPC"], result["special NPC"])
        again = deepcopy(before)
        HintAreas.apply_area_hints(world, again, stones)
        self.assertEqual(result, again)
        self.assertEqual(rng, (world.random.getstate(), mw.random.getstate()))


class ItemMetadataTests(unittest.TestCase):
    def test_full_typed_foreign_group_and_starting_metadata(self):
        mw, world = fixture(2)
        mw.groups[3] = {"players": {1}, "name": "Linked Players"}
        mw.player_name[3] = "Linked Players"
        mw.game[3] = world.game
        world.options = HintOptions(sheik_la_hint=1, tot_altar_hint=1)
        remote = add_area(mw, "Foreign Exact Check", [(Items.LIGHT_ARROW, P, 3), ("Foreign Item", P, 1)], player=2)
        long_name = "Full recipient Ω " * 200
        mw.player_name[3] = long_name
        starting = Item(str(Items.KOKIRIS_EMERALD), P, 70001, 1)
        mw.precollected_items[1].append(starting)
        before, rng = placed(mw), (world.random.getstate(), mw.random.getstate())
        result = Hints.CreateInGameHints(world)
        typed = result[HintKeys.SHEIK_HINT.value][0]
        target = remote.locations[0]
        self.assertEqual({"type": "item", "starting": False, "item": str(Items.LIGHT_ARROW),
                          "item_id": target.item.code, "location": target.name, "location_id": target.address,
                          "recipient": long_name, "receiving_player": 3, "finder": "Player 2",
                          "finding_player": 2, "game": "Foreign Game", "item_flags": 1}, typed)
        start = result[HintKeys.ALTAR_CHILD.value][0]
        self.assertTrue(start["starting"])
        self.assertIsNone(start["location_id"])
        self.assertEqual("Starting inventory", start["location"])
        self.assertEqual(result, Hints.CreateInGameHints(world))
        self.assertEqual(before, placed(mw))
        self.assertEqual(rng, (world.random.getstate(), mw.random.getstate()))

    def test_native_flags_are_exact_ap_flags_including_progression_variants(self):
        mw, world = fixture()
        for index, flags in enumerate((P, P | ItemClassification.useful,
                                       ItemClassification.progression_skip_balancing,
                                       P | ItemClassification.trap)):
            add_area(mw, f"Room {index}", [(f"Item {index}", flags, 1), ("Rupees", F, 1)])
        result = Hints.CreateInGameHints(world)
        by_id = {location.address: location.item for location in mw.get_locations()}
        for rows in result.values():
            for row in rows:
                self.assertEqual(by_id[row["location_id"]].flags, row["item_flags"])
                self.assertEqual(row["item_id"], by_id[row["location_id"]].code)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    sources = [root / "archipelago/soh_extreme/HintAreas.py",
               root / "archipelago/soh_extreme/_vendor_oot_soh/Hints.py",
               root / "archipelago/soh_extreme/__init__.py", Path(__file__).resolve()]
    hashes = {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sources}
    tests = unittest.defaultTestLoader.loadTestsFromModule(__import__(__name__))
    result = unittest.TextTestRunner(verbosity=2).run(tests)
    after = {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sources}
    assert hashes == after, "Production or test source changed during validation"
    report = {"status": "passed" if result.wasSuccessful() else "failed", "tests": result.testsRun,
              "source_sha256": hashes, "source_unchanged_during_test": True,
              "goal_engine": "Official Archipelago 0.6.7 CollectionState and MultiWorld.can_beat_game",
              "proof_scope": "All physical player goals, including remote item recipients",
              "production_region_catalog_exercised": True}
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
