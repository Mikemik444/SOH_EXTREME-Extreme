"""Focused AP hint transport checks; no game build or world generation needed."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib
import json
from pathlib import Path
import sys
import types
import unittest
from collections import namedtuple
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[2]
WORLD = SOURCE / "archipelago" / "soh_extreme"
PACKAGE = "_soh_hint_bridge_tests"
package = types.ModuleType(PACKAGE)
package.__path__ = [str(WORLD)]
sys.modules[PACKAGE] = package
bridge_module = importlib.import_module(f"{PACKAGE}.HintBridge")
HintBridge = bridge_module.HintBridge
NONCE = "a" * 32
PRODUCER = "b" * 32
Slot = namedtuple("Slot", "name game group_members", defaults=[()])
NetworkItem = namedtuple("NetworkItem", "item location player flags")


class Names(dict):
    def __init__(self, ctx, values):
        super().__init__(values)
        self.ctx = ctx

    def __missing__(self, key):
        return {}

    def lookup_in_slot(self, code, slot):
        return self[self.ctx.slot_info[slot].game][code]


class Context:
    def __init__(self, *args, **kwargs):
        self.game = "SOH-EXTREME"
        self.slot, self.team = 1, 0
        self._managed_nonce, self._mirror_producer = NONCE, PRODUCER
        self.slot_info = {1: Slot("Link", self.game), 2: Slot("Other", "Other Game"),
                          3: Slot("Third", "Third Game"), 4: Slot("Linked", self.game, (1,))}
        self.player_names = {1: "Link Alias", 2: "Other Alias", 3: "Third Alias", 4: "Linked Alias"}
        self.item_names = Names(self, {self.game: {501: "SOH Hookshot"},
                                      "Other Game": {501: "Other Game Progression"}})
        self.location_names = Names(self, {self.game: {101: "SOH Door", 102: "SOH Scrub"},
                                          "Other Game": {201: "Other Game Location"}})
        self.server_locations = {101, 102}
        self.locations_info = {}
        self.stored_data = {}
        self.sent = []

    def slot_concerns_self(self, slot):
        return slot == self.slot or (slot in self.slot_info and self.slot in self.slot_info[slot].group_members)

    async def send_msgs(self, messages):
        self.sent.extend(json.loads(json.dumps(messages)))


def server_hint(*, finder=1, location=101, recipient=2, item=501, flags=1, found=False, status=0):
    # NetUtils.encode preserves Hint as a dictionary with a class marker;
    # Hint is not in the client decoder's NamedTuple reconstruction allowlist.
    return {"class": "Hint", "finding_player": finder, "location": location, "receiving_player": recipient,
            "item": item, "item_flags": flags, "found": found, "status": status, "entrance": "Door entrance"}


def target(**kwargs):
    raw = server_hint(**kwargs)
    return {"finding_player": raw["finding_player"], "location_id": raw["location"],
            "receiving_player": raw["receiving_player"], "item_id": raw["item"], "item_flags": raw["item_flags"]}


def request(kind="hint_request", count=1, **kwargs):
    return {"soh_extreme_tracker": bridge_module.PROTOCOL, "kind": kind, "slot": 1,
            "nonce": NONCE, "request": count, **kwargs}


class MetadataTests(unittest.TestCase):
    def test_advancement_bit_and_trap_exclusion(self):
        ctx = Context()
        for flags in (0, 2, 4, 5, 6, 7, None, True, -1):
            self.assertEqual([], bridge_module.progression_hint_rows(ctx, [server_hint(flags=flags)]), flags)
        for flags in (1, 3, 9):
            self.assertEqual(flags, bridge_module.progression_hint_rows(ctx, [server_hint(flags=flags)])[0]["item_flags"])
        raw = server_hint()
        del raw["item_flags"]
        self.assertEqual([], bridge_module.progression_hint_rows(ctx, [raw]))

    def test_foreign_item_uses_recipient_game(self):
        row = bridge_module.progression_hint_rows(Context(), [server_hint(found=True, status=40)])[0]
        self.assertEqual("Other Game Progression", row["item"])
        self.assertEqual("SOH Door", row["location"])
        self.assertEqual("Other Game", row["item_game"])
        self.assertEqual("SOH-EXTREME", row["location_game"])
        self.assertEqual((True, 40, "Door entrance"), (row["found"], row["status"], row["entrance"]))

    def test_group_item_and_foreign_location(self):
        row = bridge_module.progression_hint_rows(Context(), [server_hint(finder=2, location=201, recipient=4)])[0]
        self.assertEqual("SOH Hookshot", row["item"])
        self.assertEqual("Other Game Location", row["location"])
        self.assertEqual("Linked Alias", row["recipient"])

    def test_missing_names_slots_and_unrelated_hints_are_omitted(self):
        ctx = Context()
        for raw in (server_hint(item=999), server_hint(location=999), server_hint(recipient=99),
                    server_hint(finder=2, location=201, recipient=3)):
            self.assertEqual([], bridge_module.progression_hint_rows(ctx, [raw]))
        ctx.player_names.pop(2)
        self.assertEqual([], bridge_module.progression_hint_rows(ctx, [server_hint()]))

    def test_full_unicode_names_are_preserved(self):
        ctx = Context()
        name = "A long progression item Ω🗝 " * 500
        ctx.item_names["Other Game"][501] = name
        self.assertEqual(name, bridge_module.progression_hint_rows(ctx, [server_hint()])[0]["item"])

    def test_invalid_and_duplicate_snapshots_are_atomic(self):
        ctx = Context()
        for raw in (None, {}, [None] * (bridge_module.MAX_HINTS + 1), [server_hint(), server_hint()]):
            with self.assertRaises(ValueError):
                bridge_module.progression_hint_rows(ctx, raw)

    def test_invalid_target_ids_flags_and_starting_inventory(self):
        for raw in ({}, target(flags=0), target(flags=5), target(location=-1), target(item=-1), target(recipient=0),
                    {**target(), "starting": True}, {**target(), "item_id": 1 << 63}):
            self.assertIsNone(bridge_module.hint_target(raw))


class TransportTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.ctx = Context()
        self.bridge = HintBridge(self.ctx)
        self.bridge.on_package("Connected", {"slot_data": {}})

    async def asyncTearDown(self):
        await self.bridge.close()

    async def flush(self):
        while self.bridge.sender is not None:
            await self.bridge.sender

    def received(self, hints, cmd="Retrieved"):
        if cmd == "Retrieved":
            self.bridge.on_package(cmd, {"keys": {self.bridge.hint_key: hints}})
        else:
            self.bridge.on_package(cmd, {"key": self.bridge.hint_key, "value": hints})

    def snapshots(self):
        return [packet["data"] for packet in self.ctx.sent if packet["cmd"] == "Bounce"]

    def creates(self):
        return [packet for packet in self.ctx.sent if packet["cmd"] == "CreateHints"]

    async def test_waits_for_fresh_current_connection_snapshot(self):
        self.ctx.stored_data[self.bridge.hint_key] = [server_hint()]
        self.bridge.on_bounce(request())
        await self.flush()
        self.assertEqual([], self.snapshots())
        self.bridge.on_package("Retrieved", {"keys": {"_read_hints_1_1": [server_hint()]}})
        await self.flush()
        self.assertEqual([], self.snapshots())
        self.received([])
        await self.flush()
        self.assertEqual([], self.snapshots()[-1]["rows"])

    async def test_snapshot_updates_found_names_and_monotonic_revision(self):
        self.bridge.on_bounce(request())
        self.received([server_hint()])
        await self.flush()
        first = self.snapshots()[-1]
        self.received([server_hint(found=True, status=40)], "SetReply")
        await self.flush()
        second = self.snapshots()[-1]
        self.ctx.player_names[2] = "New Other Alias"
        self.bridge.on_package("RoomUpdate", {"players": []})
        await self.flush()
        third = self.snapshots()[-1]
        self.assertTrue(first["revision"] < second["revision"] < third["revision"])
        self.assertTrue(second["rows"][0]["found"])
        self.assertEqual("New Other Alias", third["rows"][0]["recipient"])
        self.assertEqual((NONCE, PRODUCER, 1), (third["nonce"], third["producer"], third["slot"]))

    async def test_names_republish_after_datapackage_arrives(self):
        self.ctx.item_names["Other Game"].clear()
        self.bridge.on_bounce(request())
        self.received([server_hint()])
        await self.flush()
        self.assertEqual([], self.snapshots()[-1]["rows"])
        self.ctx.item_names["Other Game"][501] = "New item data"
        self.bridge.on_package("DataPackage", {})
        await self.flush()
        self.assertEqual("New item data", self.snapshots()[-1]["rows"][0]["item"])

    async def test_nonce_slot_request_and_standalone_validation(self):
        self.received([server_hint()])
        for packet in (request(nonce="c" * 32), request(slot=2), request(count=0),
                       request(count=True), request(count=1 << 63), request(count=1 << 64)):
            self.bridge.on_bounce(packet)
        await self.flush()
        self.assertEqual([], self.ctx.sent)
        self.ctx._managed_nonce = None
        self.bridge.on_bounce(request())
        await self.flush()
        self.assertEqual([], self.ctx.sent)

    async def test_old_requests_drop_without_cross_kind_counter_assumption(self):
        self.received([server_hint()])
        self.bridge.on_bounce(request(count=20))
        await self.flush()
        count = len(self.snapshots())
        self.bridge.on_bounce(request(count=19))
        await self.flush()
        self.assertEqual(count, len(self.snapshots()))
        self.bridge.on_bounce(request("request", count=1))
        await self.flush()
        self.assertEqual(1, self.snapshots()[-1]["request"])
        self.assertGreater(self.snapshots()[-1]["revision"], self.snapshots()[-2]["revision"])

    async def test_reconnect_discards_cached_hints_and_pending_reveals(self):
        self.bridge.on_bounce(request())
        self.received([server_hint()])
        await self.flush()
        previous = self.snapshots()[-1]["revision"]
        self.bridge.on_package("Connected", {"slot_data": {}})
        self.ctx.sent.clear()
        self.bridge.on_bounce(request())
        await self.flush()
        self.assertEqual([], self.snapshots())
        self.received([])
        await self.flush()
        self.assertGreater(self.snapshots()[-1]["revision"], previous)
        self.assertFalse(self.bridge.pending)

    async def test_own_reveal_requires_exact_read_only_scout(self):
        self.bridge.on_bounce(request("hint_reveal", targets=[target(flags=3)]))
        await self.flush()
        self.assertEqual([], self.creates())
        self.assertIn({"cmd": "LocationScouts", "locations": [101], "create_as_hint": 0}, self.ctx.sent)
        self.ctx.locations_info[101] = NetworkItem(501, 101, 2, 3)
        self.bridge.on_package("LocationInfo", {})
        await self.flush()
        self.assertEqual([{"cmd": "CreateHints", "player": 1, "locations": [101]}], self.creates())
        self.assertTrue(all(packet["cmd"] in {"LocationScouts", "CreateHints", "Get", "Bounce"}
                            for packet in self.ctx.sent))

    async def test_scout_mismatch_never_creates_hint(self):
        for scout in (NetworkItem(999, 101, 2, 1), NetworkItem(501, 101, 3, 1), NetworkItem(501, 101, 2, 0),
                      NetworkItem(501, 101, 2, 5)):
            self.ctx.locations_info[101] = scout
            self.bridge.on_bounce(request("hint_reveal", targets=[target()]))
            await self.flush()
        self.assertEqual([], self.creates())

    async def test_foreign_reveal_needs_disclosed_exact_own_item_or_group(self):
        foreign = target(finder=2, location=201, recipient=4)
        self.bridge.on_bounce(request("hint_reveal", targets=[foreign]))
        await self.flush()
        self.assertEqual([], self.creates())
        self.assertFalse(any(packet["cmd"] == "LocationScouts" for packet in self.ctx.sent))
        self.bridge.on_package("Connected", {"slot_data": {"extreme_hint_data": {"Gossip Stone": [foreign]}}})
        self.bridge.on_bounce(request("hint_reveal", targets=[foreign]))
        await self.flush()
        self.assertEqual([{"cmd": "CreateHints", "player": 2, "locations": [201]}], self.creates())
        self.assertFalse(any(packet["cmd"] == "LocationScouts" for packet in self.ctx.sent))

    async def test_reveal_limits_unknown_flags_and_non_progression(self):
        bad = [target(flags=0), target(flags=2), target(flags=5), target(location=999),
               {key: value for key, value in target().items() if key != "item_flags"}]
        self.bridge.on_bounce(request("hint_reveal", targets=bad))
        self.bridge.on_bounce(request("hint_reveal", count=2, targets=[target()] * 257))
        await self.flush()
        self.assertEqual([], self.creates())
        self.assertFalse(any(packet["cmd"] == "LocationScouts" for packet in self.ctx.sent))

    async def test_reveal_deduplicates_and_server_snapshot_acknowledges(self):
        self.ctx.locations_info[101] = NetworkItem(501, 101, 2, 1)
        self.bridge.on_bounce(request("hint_reveal", targets=[target(), target()]))
        await self.flush()
        self.bridge.on_bounce(request("hint_reveal", count=2, targets=[target()]))
        await self.flush()
        self.assertEqual(1, len(self.creates()))
        self.received([server_hint()])
        await self.flush()
        self.assertFalse(self.bridge.pending)
        self.bridge.on_bounce(request("hint_reveal", count=3, targets=[target()]))
        await self.flush()
        self.assertEqual(1, len(self.creates()))

    async def test_oversized_snapshot_is_not_partially_published(self):
        self.ctx.item_names["Other Game"][501] = "X" * bridge_module.MAX_BYTES
        self.bridge.on_bounce(request())
        with self.assertLogs("Client", level="ERROR"):
            self.received([server_hint()])
        await self.flush()
        self.assertEqual([], self.snapshots())

    async def test_coalesced_snapshot_keeps_latest_server_state(self):
        self.bridge.on_bounce(request())
        self.received([server_hint()])
        self.received([server_hint(found=True, status=40)], "SetReply")
        await self.flush()
        self.assertEqual(1, len(self.snapshots()))
        self.assertTrue(self.snapshots()[0]["rows"][0]["found"])


class ContextIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_normal_finder_request_publishes_hints_without_evaluated_world(self):
        mirror = types.ModuleType(f"{PACKAGE}.TrackerMirror")
        mirror.PROTOCOL, mirror.VERSION, mirror.TAG = bridge_module.PROTOCOL, "test", "SOHExtremeUT"
        mirror.encode_snapshot = mirror.snapshot_rows = lambda *args, **kwargs: None
        sys.modules[mirror.__name__] = mirror
        # No ammo payload is sent in this hint-only test. Keep AP's game-rule
        # registration outside this isolated import; the real refill and tracker
        # integration suites exercise those modules under their canonical name.
        ammo = types.ModuleType(f"{PACKAGE}.AmmoRefillRules")
        def unexpected_ammo(*args, **kwargs):
            self.fail("Hint-only traffic must not ask for an ammo proof")
        ammo.refill_mask = ammo.validate_observed_sources = unexpected_ammo
        sys.modules[ammo.__name__] = ammo
        client = importlib.import_module(f"{PACKAGE}.TrackerClient")

        class Base(Context):
            tags = {"Tracker"}

            def __init__(self, *args, **kwargs):
                super().__init__()
                self.tracker_core = types.SimpleNamespace(
                    get_current_world=lambda: None, disconnect=lambda: None)
                self.updates = 0

            def on_package(self, cmd, args):
                pass

            def updateTracker(self):
                self.updates += 1
                return None

            async def disconnect(self, allow_autoreconnect=False):
                pass

            async def shutdown(self):
                pass

            def reset_server_state(self):
                self.slot = self.team = None

        # This test isolates hint transport from UT evaluation. Real upstream
        # bootstrap/reconnection is exercised by test_tracker_yamlless.py.
        with patch.object(client, "install_slot_data_core", return_value=None):
            ctx = client.make_context_class(Base)()
        ctx._managed_nonce = NONCE
        ctx.on_package("Connected", {"slot_data": {}})
        ctx.on_package("Retrieved", {"keys": {ctx._hint_bridge.hint_key: [server_hint()]}})
        ctx.on_package("Bounced", {"data": request("request", live_shields=0)})
        while ctx._hint_bridge.sender is not None:
            await ctx._hint_bridge.sender
        self.assertEqual(1, ctx.updates)
        self.assertTrue(any(packet["cmd"] == "Bounce" and packet["data"]["kind"] == "hint_snapshot"
                            for packet in ctx.sent))
        ctx.reset_server_state()
        self.assertIsNone(ctx._hint_bridge.raw_hints)
        await ctx.shutdown()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    source_paths = (WORLD / "HintBridge.py", WORLD / "TrackerClient.py", WORLD / "TrackerBootstrap.py",
                    WORLD / "TrackerWorker.py")
    test_paths = (Path(__file__).resolve(),)
    def hashes(paths):
        return {str(path.relative_to(SOURCE)): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in paths}
    source_before, tests_before = hashes(source_paths), hashes(test_paths)
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    unchanged = source_before == hashes(source_paths) and tests_before == hashes(test_paths)
    passed = result.wasSuccessful() and unchanged
    if args.report:
        report = {"status": "passed" if passed else "failed", "passed": passed, "tests_run": result.testsRun,
                  "failures": len(result.failures), "errors": len(result.errors),
                  "scope": "Focused server hint metadata, reveal command authorization, transport and lifecycle checks",
                  "limitations": "No live AP server or complete native game/UI execution in this test. "
                                 "UT bootstrap is an explicit I/O boundary here; real UT reconstruction "
                                 "is covered by test_tracker_yamlless.py.",
                  "source_sha256": source_before, "test_sha256": tests_before,
                  "source_unchanged_during_tests": unchanged}
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
