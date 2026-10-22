"""Exercise SOH's YAML-free bootstrap against the pinned, unmodified real UT.

The fixture uses Archipelago's real CommonContext packet handler, Generate,
TrackerGameContext, TrackerCore.TMain and the production SOH world. GUI, socket
and persistent-storage I/O are isolated; no tracker evaluation is substituted.
The seed snapshots come from current production generation stages through
generate_basic and fill_slot_data, not a handcrafted stand-in for slot data.
No item fill, game playthrough, live server or Windows launcher is claimed.

Example (from the workspace containing source and the AP 0.6.8 runtime):
  PYTHONPATH=ap-deps:ap-runtime-068 python source/tools/tests/test_tracker_yamlless.py

The three upstream UT files and missing AP server-cache dependency are immutable
test inputs downloaded from their recorded official repositories. Source hashes
are checked before and after execution and included with the regression report.
"""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from contextlib import contextmanager, ExitStack
from copy import deepcopy
from hashlib import sha256
import importlib.util
import io
import json
import logging
import os
from pathlib import Path
import sys
import tempfile
import time
import traceback
from types import ModuleType
from unittest.mock import AsyncMock, patch
import zipfile


SOURCE = Path(__file__).resolve().parents[2]
WORK = SOURCE.parent
GAME = "SOH-EXTREME"
NONCE = "a" * 32
SEED_OPTIONS = {
    "starting_age": "adult", "frozen_starting_time": "night",
    "scene_transition_checks": 1,
    "shuffle_shops": 1, "shuffle_shops_item_amount": 3,
    "shuffle_shops_minimum_price": 47, "shuffle_shops_maximum_price": 113,
    "shuffle_npc_soul": 1, "shuffle_enemy_soul": 1,
    "shuffle_pot_soul": 1, "shuffle_crate_soul": 1,
    "shuffle_rock_boulder_soul": 1,
    "shuffle_swim": 1, "shuffle_climb": 1, "shuffle_grab": 1,
    "shuffle_crawl": 1, "shuffle_speak": 1, "shuffle_roll": 1,
    "shuffle_open_chest": 1, "shuffle_flow_of_time": 1,
    "song_note_shuffle": 1,
    "song_note_songs": ["eponas_song", "prelude_of_light"],
    "ganons_trials": 1, "ganons_trials_count": 3,
    "medallion_locked_trials": 1,
    "key_rings": 2, "forest_temple_key_ring": 1, "shadow_temple_key_ring": 1,
    "start_inventory": {"Progressive Bomb Bag": 1, "Progressive Scale": 1, "Epona's Song": 1},
    "start_inventory_from_pool": {"Progressive Wallet": 1},
}


def file_hash(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def canonical(value):
    if isinstance(value, dict):
        return {str(k): canonical(v) for k, v in value.items()}
    if isinstance(value, (set, frozenset)):
        return sorted(canonical(v) for v in value)
    if isinstance(value, (list, tuple)):
        return [canonical(v) for v in value]
    return value


def digest(value):
    return sha256(json.dumps(canonical(value), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def production_hashes():
    paths = sorted((SOURCE / "archipelago/soh_extreme").rglob("*.py"))
    paths += sorted((SOURCE / "archipelago/soh_extreme").rglob("*.json"))
    return {str(p.relative_to(SOURCE)): file_hash(p) for p in paths}


def load_runtime(args):
    """Only import GUI-free modules after configuring isolated host settings."""
    sys.path.insert(0, str(args.ap_dependencies))
    import ModuleUpdate
    ModuleUpdate.update_ran = True
    import settings
    settings.no_gui = True
    settings.skip_autosave = True
    settings.get_settings._cache = settings.Settings(None)
    import Utils
    Utils.gui_enabled = False
    import worlds
    from worlds.soh_extreme import SohExtremeWorld, EntranceRandomizer
    from worlds.soh_extreme import TrackerClient, TrackerWorker, TrackerMirror

    spec = importlib.util.spec_from_file_location(
        "worlds.tracker", args.upstream / "__init__.py",
        submodule_search_locations=[str(args.upstream)])
    upstream = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = upstream
    worlds.tracker = upstream
    spec.loader.exec_module(upstream)
    from worlds.tracker import TrackerCore, TrackerClient as UpstreamClient
    import CommonClient
    import Generate
    import NetUtils
    from test.general import setup_multiworld
    from worlds.AutoWorld import call_all
    host = settings.get_settings()
    host.universal_tracker = upstream.TrackerSettings()

    # Persistent UI preferences are in-memory. Game rules, package handling,
    # option parsing and path validation below remain the actual implementations.
    storage = {}
    def persistent_store(category, key, value):
        storage.setdefault(category, {})[key] = deepcopy(value)
    Utils.persistent_load = lambda: storage
    Utils.persistent_store = persistent_store
    UpstreamClient.persistent_load = lambda: storage
    UpstreamClient.persistent_store = persistent_store

    legacy_name = "worlds.soh_extreme._tracker_yamlless_legacy"
    legacy = ModuleType(legacy_name)
    legacy.__package__ = "worlds.soh_extreme"
    with zipfile.ZipFile(args.baseline) as archive:
        legacy_bytes = archive.read("archipelago/soh_extreme/TrackerClient.py")
    exec(compile(legacy_bytes, str(args.baseline) + "!/TrackerClient.py", "exec"), legacy.__dict__)
    return locals()


class Suite:
    def __init__(self, args, runtime):
        self.args, self.r = args, runtime
        self.report = {"cases": [], "assertions": 0, "failures": []}
        self.contexts = []
        self.snapshots = {}
        self.evidence = {}
        self.expected_keys = {}

    def check(self, condition, message):
        self.report["assertions"] += 1
        if not condition:
            raise AssertionError(message)

    def equal(self, first, second, message):
        self.check(first == second, f"{message}: {first!r} != {second!r}")

    def configure(self, root, contents, *, poison=False):
        players = Path(root) / "Players"
        if contents != "missing":
            players.mkdir()
        if contents == "invalid":
            (players / "broken.yaml").write_text("[bad: yaml: [\n")
        elif contents == "unrelated":
            (players / "someone_else.yaml").write_text(json.dumps(
                {"name": "SomeoneElse", "game": "Archipelago", "Archipelago": {}}))
        elif contents == "wrong":
            (players / "same_name_wrong_seed.yaml").write_text(json.dumps(
                {"name": "YamlLessAdult", "game": GAME,
                 GAME: {"starting_age": "child", "frozen_starting_time": "dawn",
                        "scene_transition_checks": 0, "shuffle_shops": 0,
                        "shuffle_npc_soul": 0, "song_note_shuffle": 0}}))
        host, upstream = self.r["host"], self.r["upstream"]
        host.universal_tracker.player_files_path = upstream.TrackerSettings.TrackerPlayersPath(str(players))
        host.generator.player_files_path = self.r["settings"].GeneratorOptions.PlayerFilesPath(str(players))
        weights, meta = Path(root) / "weights.yaml", Path(root) / "meta.yaml"
        if poison:
            weights.write_text("[poison weights: [\n")
            meta.write_text("[poison meta: [\n")
        host.generator.weights_file_path = str(weights)
        host.generator.meta_file_path = str(meta)
        host.general_options.output_path = str(Path(root) / "output")
        return players, (players, weights, meta)

    @contextmanager
    def trace_generation(self, forbidden):
        """Observe the real settings getter, parser, file system and UT engine."""
        counts = {"player_path_reads": 0, "weights_meta_setting_reads": 0,
                  "gmain": 0, "mystery_argparse": 0, "tmain": 0,
                  "local_file_reads": [], "local_scans": [], "tmain_games": [],
                  "tmain_seconds": [], "evaluation_seconds": []}
        Group = self.r["settings"].Group
        Core = self.r["TrackerCore"]
        original_get = Group.__getattribute__
        original_gmain, original_parser = Core.GMain, Core.mystery_argparse
        original_tmain = Core.TrackerCore.TMain
        original_update = Core.TrackerCore.updateTracker
        original_scan, original_open = os.scandir, open
        original_io_open = io.open
        import builtins
        def protected(path):
            if not isinstance(path, (str, bytes, os.PathLike)):
                return False
            path = Path(os.fsdecode(path)).absolute()
            return any(path == item or item in path.parents for item in forbidden)
        def get(group, name):
            if name == "player_files_path": counts["player_path_reads"] += 1
            if name in ("weights_file_path", "meta_file_path"):
                counts["weights_meta_setting_reads"] += 1
            return original_get(group, name)
        def scan(path):
            if protected(path): counts["local_scans"].append(os.fsdecode(path))
            return original_scan(path)
        def opened(path, *a, **kw):
            if protected(path): counts["local_file_reads"].append(os.fsdecode(path))
            return original_open(path, *a, **kw)
        def io_opened(path, *a, **kw):
            if protected(path): counts["local_file_reads"].append(os.fsdecode(path))
            return original_io_open(path, *a, **kw)
        def gmain(*a, **kw):
            counts["gmain"] += 1
            return original_gmain(*a, **kw)
        def parser(*a, **kw):
            counts["mystery_argparse"] += 1
            return original_parser(*a, **kw)
        def tmain(core, namespace, *a, **kw):
            counts["tmain"] += 1
            counts["tmain_games"].append(dict(namespace.game))
            start = time.monotonic()
            try:
                return original_tmain(core, namespace, *a, **kw)
            finally:
                counts["tmain_seconds"].append(round(time.monotonic() - start, 3))
        def update(core, *a, **kw):
            start = time.monotonic()
            try:
                return original_update(core, *a, **kw)
            finally:
                counts["evaluation_seconds"].append(round(time.monotonic() - start, 3))
        with ExitStack() as stack:
            stack.enter_context(patch.object(Group, "__getattribute__", get))
            stack.enter_context(patch.object(os, "scandir", scan))
            stack.enter_context(patch.object(builtins, "open", opened))
            stack.enter_context(patch.object(io, "open", io_opened))
            stack.enter_context(patch.object(Core, "GMain", gmain))
            stack.enter_context(patch.object(Core, "mystery_argparse", parser))
            stack.enter_context(patch.object(Core.TrackerCore, "TMain", tmain))
            stack.enter_context(patch.object(Core.TrackerCore, "updateTracker", update))
            yield counts

    async def context(self, mode, name="YamlLessAdult", slot=7):
        base = self.r["UpstreamClient"].TrackerGameContext
        if mode == "baseline":
            cls = self.r["legacy"].make_context_class(base)
        elif mode == "generic":
            cls = base
        else:
            cls = self.r["TrackerClient"].make_context_class(base)
            if mode == "managed":
                cls = self.r["TrackerWorker"].make_managed_context(cls, {
                    "server": "ws://fixture.invalid:38281", "slot_name": name,
                    "password": "", "slot": slot, "nonce": NONCE})
        ctx = cls("ws://fixture.invalid:38281", None, print_count=False, print_list=False)
        ctx.auth = name
        ctx.send_msgs = AsyncMock()  # sole outbound network boundary
        self.contexts.append(ctx)
        return ctx

    async def close_context(self, ctx):
        ctx.exit_event.set()
        await ctx.shutdown()
        for key in ("watcher_task", "keep_alive_task", "_mirror_sender"):
            task = getattr(ctx, key, None)
            if task is not None:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
        if ctx in self.contexts:
            self.contexts.remove(ctx)

    async def connect(self, ctx, snapshot, name="YamlLessAdult", slot=7, seed="YamlLess-1814001"):
        ctx.disconnected_intentionally = False
        ctx.server_seed_name = seed
        # RoomInfo's normal callback resets the tracker before Connected. The
        # server auth/datapackage exchange is outside this local packet fixture.
        ctx.on_package("RoomInfo", {"seed_name": seed})
        data = {
            "cmd": "Connected", "team": 0, "slot": slot,
            "slot_info": {str(slot): self.r["NetUtils"].NetworkSlot(
                name, GAME, self.r["NetUtils"].SlotType.player)},
            "players": [self.r["NetUtils"].NetworkPlayer(0, slot, name, name)],
            "missing_locations": list(snapshot.get("extreme_active_locations", [])),
            "checked_locations": [], "slot_data": deepcopy(snapshot),
        }
        ctx.checksums[GAME] = self.r["SohExtremeWorld"].get_data_package_data()["checksum"]
        # Encode/decode through AP's real JSON wire format, then execute the real
        # CommonClient handler. Context metadata is not manually faked here.
        packet = self.r["NetUtils"].decode(self.r["NetUtils"].encode(data))
        await self.r["CommonClient"].process_server_cmd(ctx, packet)
        return packet

    def no_local_yaml(self, trace, *, generations=1):
        for key in ("player_path_reads", "weights_meta_setting_reads", "gmain", "mystery_argparse"):
            self.equal(trace[key], 0, f"slot-only bootstrap unexpectedly used {key}")
        self.equal(trace["local_file_reads"], [], "slot-only bootstrap read local YAML")
        self.equal(trace["local_scans"], [], "slot-only bootstrap scanned Players")
        self.equal(trace["tmain"], generations, "real UT.TMain call count")

    def verify_world(self, ctx, snapshot):
        core = ctx.tracker_core
        self.check(core.multiworld is not None, core.gen_error or "No regenerated world")
        self.check(not core.tracker_disabled, "Tracker disabled a valid slot")
        world = core.get_current_world()
        self.check(world.using_ut, "Regeneration passthrough was not applied")
        self.equal(core.player_id, 1, "Server slot must be normalized to UT's single graph player")
        actual = {name: canonical(getattr(world.options, name).value)
                  for name in world.options_dataclass.type_hints}
        expected = canonical(snapshot["extreme_all_options"])
        self.equal(actual, expected, "All 230 resolved options must survive regeneration")
        active = sorted(loc.address for loc in world.get_locations() if type(loc.address) is int)
        self.equal(active, sorted(snapshot["extreme_active_locations"]), "Exact active location manifest")
        self.equal(sorted(world.ganons_trials), sorted(snapshot["required_trials"]), "Resolved trials")
        self.equal(canonical(world.shop_vanilla_items), snapshot["shop_vanilla_items"], "Shop vanilla inventory")
        actual_prices = {str(world.location_name_to_id.get(str(name))): price
                         for name, price in world.shop_prices.items()
                         if type(world.location_name_to_id.get(str(name))) is int}
        self.equal(actual_prices, snapshot["extreme_shop_prices"], "Exact numeric shop prices")
        self.equal(canonical(world.shop_prices), snapshot["shop_prices"], "Named shop prices")
        self.equal(world.options.starting_age.value, snapshot["starting_age"], "Starting age")
        self.equal(world.options.frozen_starting_time.value, snapshot["frozen_starting_time"], "Starting time")
        expected_map = snapshot.get("entrance_randomizer", {}).get("connections", {})
        self.equal(canonical(world._er_mapping), expected_map, "Saved entrance destinations")
        expected_keys = self.expected_keys.get(digest(snapshot))
        if expected_keys is not None:
            actual_keys = Counter(item.name for item in world.pre_fill_pool if "Key" in item.name)
            self.equal(dict(actual_keys), expected_keys, "Resolved keyrings must match their pre-fill key pool")
        self.check(all(item.code is None for item in core.multiworld.precollected_items[1]),
                   "AP starting items were counted locally in addition to ReceivedItems")
        result = ctx.updateTracker()
        self.check(result.state is not None, "Real UT evaluation returned no state")
        self.check(set(result.in_logic_locations) <= {loc.name for loc in world.get_locations()
                                                    if type(loc.address) is int},
                   "Tracker reported a check outside the reconstructed graph")
        return {"options": len(actual), "active_checks": len(active),
                "shop_prices": len(actual_prices), "trials": sorted(world.ganons_trials),
                "option_digest": digest(actual), "active_digest": digest(active),
                "entrance_digest": digest(expected_map),
                "in_logic_checks": len(result.in_logic_locations)}, world, result

    def make_snapshot(self, seed, name, overrides=None):
        options = deepcopy(SEED_OPTIONS)
        options.update(overrides or {})
        for option in ("start_inventory", "start_inventory_from_pool"):
            for item in options.get(option, {}):
                self.check(type(self.r["SohExtremeWorld"].item_name_to_id.get(item)) is int,
                           f"Fixture {option} item is not a network item: {item}")
        # Use the real generation option verifier before the low-level graph
        # fixture, so an event-only item or malformed raw option cannot masquerade
        # as a seed that the normal YAML generator could create.
        self.r["Generate"].roll_settings({"name": name, "game": GAME, GAME: deepcopy(options)})
        mw = self.r["setup_multiworld"](self.r["SohExtremeWorld"], steps=(), seed=seed, options=options)
        mw.player_name[1] = name
        for stage in ("generate_early", "create_regions", "create_items", "set_rules",
                      "connect_entrances", "generate_basic"):
            self.r["call_all"](mw, stage)
        world = mw.worlds[1]
        snapshot = json.loads(self.r["NetUtils"].encode(world.fill_slot_data()))
        self.expected_keys[digest(snapshot)] = dict(Counter(item.name for item in world.pre_fill_pool
                                                          if "Key" in item.name))
        self.equal(len(snapshot["extreme_all_options"]), len(world.options_dataclass.type_hints),
                   "fill_slot_data must contain the complete current option set")
        fixture_path = self.args.report.parent / f"tracker_yamlless_1814_{name}_slot.json"
        fixture_path.write_text(json.dumps(snapshot, sort_keys=True, indent=2) + "\n")
        self.evidence[fixture_path.name] = {"path": str(fixture_path), "sha256": file_hash(fixture_path)}
        return snapshot

    async def baseline_cases(self):
        for contents in ("missing", "empty"):
            with tempfile.TemporaryDirectory(prefix="soh-ut-baseline-") as root:
                players, forbidden = self.configure(root, contents)
                ctx = await self.context("baseline")
                raised = None
                with self.trace_generation(forbidden) as trace:
                    try:
                        ctx.run_generator()
                    except Exception as exc:
                        raised = f"{type(exc).__name__}: {exc}"
                self.check(ctx.tracker_core.multiworld is None, "Baseline unexpectedly generated a world")
                self.check(trace["player_path_reads"] > 0, "Baseline did not reach the required Players property")
                if contents == "missing":
                    self.check("FileNotFoundError" in ctx.tracker_core.gen_error, "Missing Players failure not reproduced")
                    self.equal(trace["gmain"], 0, "Missing folder must fail before GMain")
                    self.check(raised is not None and "use_split" in raised, "Context's startup exception not reproduced")
                else:
                    self.check("No individual player files found" in ctx.tracker_core.gen_error,
                               "Empty Players startup scan failure not reproduced")
                    self.equal(trace["gmain"], 1, "Expected actual GMain scan")
                    self.check(str(players) in trace["local_scans"], "Actual Players scan not observed")
                self.report["cases"].append({"name": f"baseline_1.8.13_{contents}",
                    "status": "expected_failure_reproduced", "trace": trace,
                    "generator_error": ctx.tracker_core.gen_error.splitlines()[-1],
                    "context_exception": raised})
                await self.close_context(ctx)

    async def independent_players_cases(self):
        for mode in ("standalone", "managed"):
            for contents in ("missing", "empty", "invalid", "unrelated", "wrong"):
                print(f"  {mode}: {contents} Players", flush=True)
                with tempfile.TemporaryDirectory(prefix="soh-ut-yamlless-") as root:
                    players, forbidden = self.configure(root, contents, poison=True)
                    connected_case = ((mode, contents) in (("standalone", "missing"), ("managed", "wrong")))
                    if connected_case and contents == "wrong":
                        (players / "broken.yaml").write_text("[bad: yaml: [\n")
                        (players / "someone_else.yaml").write_text(json.dumps(
                            {"name": "SomeoneElse", "game": "Archipelago", "Archipelago": {}}))
                    ctx = await self.context(mode)
                    initial_argv = list(sys.argv)
                    with self.trace_generation(forbidden) as trace:
                        ctx.run_generator()
                        self.check(ctx.tracker_core.multiworld is None, "Startup fabricated a preconnection seed")
                        self.check(not ctx.tracker_core.tracker_disabled, "Startup disabled waiting tracker")
                        self.equal(trace["tmain"], 0, "Startup must wait for Connected")
                        waiting_lines = deepcopy(ctx.tracker_core.log_lines)
                        self.check(ctx.updateTracker().state is None, "Preconnect refresh invented tracker state")
                        self.equal(ctx.tracker_core.log_lines, waiting_lines, "Preconnect refresh replaced waiting status")
                        self.check(ctx._mirror_packet is None, "Preconnect refresh published a snapshot")
                        details = {"scope": "preconnection startup and refresh only"}
                        if connected_case:
                            await self.connect(ctx, self.snapshots["adult"])
                            details, _, _ = self.verify_world(ctx, self.snapshots["adult"])
                            details["scope"] = "Connected -> real UT.TMain -> real UT.updateTracker"
                    self.no_local_yaml(trace, generations=int(connected_case))
                    self.equal(sys.argv, initial_argv, "Slot bootstrap must not strip launcher arguments")
                    if mode == "managed":
                        self.equal(ctx.worker_exit_code, 0, "Managed valid Connected exit code")
                        self.check(not ctx.exit_event.is_set(), "Managed tracker exited after valid initialization")
                    self.report["cases"].append({"name": f"{mode}_{contents}_Players_poison_weights_meta",
                                                  "status": "passed", "trace": trace, **details})
                    print(f"    passed: TMain {trace['tmain_seconds']}; evaluations {trace['evaluation_seconds']}", flush=True)
                    await self.close_context(ctx)

    async def generic_upstream_case(self):
        with tempfile.TemporaryDirectory(prefix="soh-ut-stock-") as root:
            _, forbidden = self.configure(root, "empty")
            ctx = await self.context("generic")
            with self.trace_generation(forbidden) as trace:
                # Generic UT retains its own preconnection startup behavior.
                # Its real supported YAML-less Connected bootstrap is distinct.
                ctx.run_generator()
                startup_error = ctx.tracker_core.gen_error.splitlines()[-1]
                await self.connect(ctx, self.snapshots["adult"])
                details, _, _ = self.verify_world(ctx, self.snapshots["adult"])
            self.equal(trace["gmain"], 2, "Generic UT uses real preconnection and temp-YAML generators")
            self.equal(trace["tmain"], 1, "Generic UT connected generation")
            self.equal(trace["local_file_reads"], [], "Generic UT must not need any personal YAML")
            self.report["cases"].append({"name": "generic_upstream_UT_empty_Players_Connected",
                "status": "passed", "startup_error_retained_upstream": startup_error,
                "trace": trace, **details})
            await self.close_context(ctx)

    async def controlled_entrance_case(self):
        snapshot = deepcopy(self.snapshots["adult"])
        snapshot["extreme_all_options"]["shuffle_warp_songs"] = snapshot["shuffle_warp_songs"] = 1
        snapshot["extreme_all_options"]["mixed_entrance_pools"] = snapshot["mixed_entrance_pools"] = ["all"]
        ER = self.r["EntranceRandomizer"]
        mapping = {row["id"]: row["id"] for row in ER.CATALOG if row["category"] == "warp_songs"}
        # A controlled nonvanilla pair of safe overworld arrivals, avoiding old
        # maps with now-invalid child access to Dampé's adult-only house.
        mapping[1536], mapping[1540] = 1540, 1536
        snapshot["entrance_randomizer"] = {
            "revision": ER.REVISION, "destination_policy_revision": ER.Safety.POLICY_REVISION,
            "pool_policy_revision": ER.POOL_POLICY_REVISION,
            "river_path_revision": ER.RIVER_PATH_REVISION,
            "effective_mixed_categories": ["warp_songs"], "dungeon_door_mixed_outside": 0,
            "disabled_actions": [], "connections": {str(k): v for k, v in mapping.items()},
        }
        with tempfile.TemporaryDirectory(prefix="soh-ut-entrances-") as root:
            _, forbidden = self.configure(root, "missing", poison=True)
            ctx = await self.context("standalone")
            with self.trace_generation(forbidden) as trace:
                ctx.run_generator()
                await self.connect(ctx, snapshot)
                details, world, _ = self.verify_world(ctx, snapshot)
                self.equal(world._er_mapping[1536], 1540, "Nonvanilla Minuet destination")
                self.equal(world._er_mapping[1540], 1536, "Nonvanilla Serenade destination")
                ER.validate_mapping(world, world._er_mapping)
                for source in (1536, 1540):
                    edge = world.get_entrance("EXTREME Shuffled Entrance " + str(source))
                    target = ER.region_name(ER.ENDPOINTS[world._er_mapping[source]]["target"])
                    self.equal(edge.connected_region.name, target, "Saved map must reconnect the real graph")
            self.no_local_yaml(trace)
            self.report["cases"].append({"name": "controlled_valid_nonvanilla_entrance_map", "status": "passed",
                "fixture_scope": "Current real seed slot plus controlled valid warp-song map; not a new ER fill",
                "trace": trace, **details})
            self.snapshots["controlled_er"] = snapshot
            fixture_path = self.args.report.parent / "tracker_yamlless_1814_controlled_er_slot.json"
            fixture_path.write_text(json.dumps(snapshot, sort_keys=True, indent=2) + "\n")
            self.evidence[fixture_path.name] = {"path": str(fixture_path), "sha256": file_hash(fixture_path)}
            await self.close_context(ctx)

    async def reconnect_and_item_cases(self):
        with tempfile.TemporaryDirectory(prefix="soh-ut-reconnect-") as root:
            _, forbidden = self.configure(root, "wrong", poison=True)
            ctx = await self.context("standalone")
            with self.trace_generation(forbidden) as trace:
                ctx.run_generator()
                await self.connect(ctx, self.snapshots["adult"])
                first = ctx.tracker_core.multiworld
                _, world, result = self.verify_world(ctx, self.snapshots["adult"])
                name = "Progressive Bomb Bag"
                received = self.r["NetUtils"].NetworkItem(world.item_name_to_id[name], -2, 7, 1)
                await self.r["CommonClient"].process_server_cmd(ctx, {
                    "cmd": "ReceivedItems", "index": 0, "items": [received]})
                result = ctx.updateTracker()
                self.equal(result.all_items[name], 1, "Server starting item must be counted exactly once")
                ctx.tracker_core.manual_items = ["Progressive Hookshot"]
                ctx.tracker_core.ignored_locations = {self.snapshots["adult"]["extreme_active_locations"][0]}
                old_watcher = ctx.watcher_task
                ctx.reset_server_state()
                self.check(ctx.tracker_core.multiworld is None, "Network reset kept stale seed graph")
                self.equal(ctx.tracker_core.manual_items, [], "Network reset kept manual overrides")
                self.equal(ctx.tracker_core.ignored_locations, set(), "Network reset kept ignored locations")
                self.check(old_watcher.cancelling() or old_watcher.done(), "Network reset kept old watcher")
                await self.connect(ctx, self.snapshots["child"], "YamlLessChild", slot=9, seed="YamlLess-1814002")
                details, _, result = self.verify_world(ctx, self.snapshots["child"])
                self.check(ctx.tracker_core.multiworld is not first, "Reconnect reused prior context's cached world")
                self.equal(result.all_items["Progressive Bomb Bag"], 0, "Reconnect retained previous slot's received item")
                self.equal(ctx.tracker_core.get_current_world().options.starting_age.value, 0, "Reconnect child's age")
                self.equal(ctx.tracker_core.common_option_overrides, {}, "Local common options leaked into slot data")
                self.equal(ctx.tracker_core.cached_multiworlds, [], "Per-context adapter used upstream mutable cache")
            self.no_local_yaml(trace, generations=2)
            self.report["cases"].append({"name": "network_reset_reconnect_received_items", "status": "passed",
                                          "trace": trace, **details})
            await self.close_context(ctx)

    async def failed_snapshot_cases(self):
        variants = {}
        missing = deepcopy(self.snapshots["adult"])
        missing["extreme_all_options"].pop("shuffle_climb")
        missing.pop("shuffle_climb")
        variants["missing_option"] = missing
        unresolved = deepcopy(self.snapshots["adult"])
        unresolved["extreme_all_options"]["starting_age"] = "random"
        variants["unresolved_random"] = unresolved
        manifest = deepcopy(self.snapshots["adult"])
        manifest["extreme_active_locations"].append(999999999)
        variants["wrong_active_manifest"] = manifest
        with tempfile.TemporaryDirectory(prefix="soh-ut-invalid-") as root:
            _, forbidden = self.configure(root, "missing", poison=True)
            ctx = await self.context("managed")
            with self.trace_generation(forbidden) as trace:
                ctx.run_generator()
                await self.connect(ctx, self.snapshots["adult"])
                self.check(ctx.tracker_core.multiworld is not None, "Initial valid seed missing")
                for label, snapshot in variants.items():
                    await self.connect(ctx, snapshot, seed="YamlLess-invalid")
                    self.check(ctx.tracker_core.multiworld is None, "Rejected snapshot retained previous graph")
                    self.check(ctx.tracker_core.tracker_disabled, "Incomplete snapshot must not silently use defaults")
                    self.equal(ctx.worker_exit_code, 23, "Managed seed reconstruction failure code")
                    self.check(ctx.exit_event.is_set(), "Managed failed snapshot remained active")
                    self.check(bool(ctx.tracker_core.gen_error), "No actionable reconstruction error")
                    failure = ctx.tracker_core.gen_error.splitlines()[-1]
                    self.report["cases"].append({"name": "invalid_snapshot_" + label, "status": "passed",
                        "rejection": failure, "scope": "One prior valid graph, followed by three rejected snapshots"})
            self.no_local_yaml(trace, generations=2)
            self.report["invalid_snapshot_group_trace"] = trace
            await self.close_context(ctx)

    async def managed_mirror_case(self):
        with tempfile.TemporaryDirectory(prefix="soh-ut-mirror-") as root:
            _, forbidden = self.configure(root, "missing", poison=True)
            ctx = await self.context("managed")
            # A standalone user's saved manual items may not contaminate the
            # game-owned Check Finder's inventory or hide its active checks.
            self.r["storage"].setdefault("universal_tracker", {})["YamlLess-1814001:0:7"] = {
                "manual_items": ["Progressive Hookshot"], "ignored_locations": [self.snapshots["adult"]["extreme_active_locations"][0]]}
            with self.trace_generation(forbidden) as trace:
                ctx.run_generator()
                await self.connect(ctx, self.snapshots["adult"])
                details, world, _ = self.verify_world(ctx, self.snapshots["adult"])
                self.equal(ctx.tracker_core.manual_items, [], "Check Finder imported persisted manual items")
                self.equal(ctx.tracker_core.ignored_locations, set(), "Check Finder imported persisted ignored checks")
                packet = {"cmd": "Bounced", "data": {
                    "soh_extreme_tracker": self.r["TrackerMirror"].PROTOCOL,
                    "kind": "request", "slot": 7, "nonce": NONCE, "request": 1,
                    "live_shields": 0, "live_time": 1, "live_clock": 0xD000,
                    "live_time_flags": 0}}
                await self.r["CommonClient"].process_server_cmd(ctx, packet)
                self.check(ctx._mirror_packet is not None, "No Check Finder snapshot from actual UT state")
                task = getattr(ctx, "_mirror_sender", None)
                if task is not None:
                    await task
                result = ctx._mirror_last_state
                self.check(result.state is not None, "Mirror did not use an evaluated UT state")
                rows = self.r["TrackerMirror"].snapshot_rows(
                    ctx.tracker_core, result, world, ctx.server_locations, ctx.checked_locations)
                self.equal({row["id"] for row in rows},
                           {world.get_location(name).address for name in result.in_logic_locations + result.glitched_locations},
                           "Check Finder rows must match actual UT evaluation")
                sent = [packet for call in ctx.send_msgs.call_args_list for packet in call.args[0]]
                self.check(any(packet.get("cmd") == "Bounce" and packet.get("data", {}).get("kind") == "snapshot"
                               for packet in sent), "Check Finder result did not reach outbound transport")
            self.no_local_yaml(trace)
            self.report["cases"].append({"name": "managed_check_finder_real_UT_mirror", "status": "passed",
                                          "mirror_rows": len(rows), "trace": trace, **details})
            self.r["storage"].get("universal_tracker", {}).clear()
            await self.close_context(ctx)

    def launcher_cases(self):
        from worlds.LauncherComponents import components, Type
        worker, client = self.r["TrackerWorker"], self.r["TrackerClient"]
        selected = [component for component in components if component.display_name == worker.WORKER_COMPONENT]
        self.equal(len(selected), 1, "Exactly one SOH tracker launcher component")
        self.equal(selected[0].type, Type.CLIENT, "Standalone tracker must be visible in AP launcher")
        self.check(selected[0].func is worker.launch_tracker, "Launcher must route through shared dispatcher")
        with patch.object(client, "launch") as public, patch.object(worker, "run_worker") as private:
            worker.launch_tracker()
            public.assert_called_once_with()
            public.reset_mock()
            worker.launch_tracker("--connect", "fixture.invalid:38281", "--name", "YamlLessAdult", "--nogui")
            public.assert_called_once_with("--connect", "fixture.invalid:38281", "--name", "YamlLessAdult", "--nogui")
            worker.launch_tracker("--game-owned", "--nogui")
            private.assert_called_once_with("--game-owned", "--nogui")
        for flags in (("--game-owned",), ("--game-owned", "--nogui", "--name", "unsafe")):
            with patch.object(worker, "read_config") as read:
                try:
                    worker.launch_tracker(*flags)
                except SystemExit as exc:
                    self.equal(exc.code, 20, "Malformed worker invocation exit code")
                else:
                    self.check(False, "Malformed worker arguments were accepted")
                read.assert_not_called()
        self.report["cases"].append({"name": "public_and_managed_launcher_dispatch", "status": "passed"})

    async def run(self):
        await self.baseline_cases()
        self.snapshots["adult"] = self.make_snapshot(1814001, "YamlLessAdult")
        self.snapshots["child"] = self.make_snapshot(1814002, "YamlLessChild", {
            "starting_age": "child", "frozen_starting_time": "dawn", "shuffle_shops_item_amount": 2,
            "ganons_trials_count": 2, "song_note_songs": ["all"],
            "key_rings": 1, "key_rings_count": 3,
        })
        for method in (self.independent_players_cases, self.generic_upstream_case,
                       self.controlled_entrance_case, self.reconnect_and_item_cases,
                       self.failed_snapshot_cases, self.managed_mirror_case):
            print("Running", method.__name__, flush=True)
            await method()
        self.launcher_cases()
        return self.report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", type=Path, default=WORK / "tests/tracker_bootstrap_1814_upstream")
    parser.add_argument("--ap-dependencies", type=Path, default=WORK / "tests/tracker_bootstrap_1814_ap_dependencies")
    parser.add_argument("--baseline", type=Path, default=WORK / "delivery/SOH-EXTREME-1.8.13-source-files.zip")
    parser.add_argument("--report", type=Path, default=WORK / "tests/tracker_yamlless_1814_integration.json")
    args = parser.parse_args()
    for field in ("upstream", "ap_dependencies", "baseline", "report"):
        setattr(args, field, getattr(args, field).resolve())
    before = production_hashes()
    upstream_before = {str(path.relative_to(args.upstream)): file_hash(path)
                       for path in sorted(args.upstream.rglob("*")) if path.is_file() and path.suffix in (".py", ".json", ".md")}
    runtime = load_runtime(args)
    suite = Suite(args, runtime)
    started = time.monotonic()
    ok = False
    async def run_and_close():
        try:
            await suite.run()
        finally:
            for ctx in list(suite.contexts):
                await suite.close_context(ctx)
    try:
        asyncio.run(run_and_close())
        suite.equal(production_hashes(), before, "Production files changed while integration tests were running")
        for path, checksum in upstream_before.items():
            suite.equal(file_hash(args.upstream / path), checksum, "Upstream input mutated: " + path)
        ok = True
    except Exception:
        suite.report["failures"].append(traceback.format_exc())
        traceback.print_exc()
    runtime_paths = ("BaseClasses.py", "CommonClient.py", "Generate.py", "MultiServer.py", "NetUtils.py",
                     "Options.py", "settings.py", "Utils.py", "worlds/AutoWorld.py", "test/general/__init__.py")
    runtime_root = Path(runtime["CommonClient"].__file__).parent
    suite.report.update({
        "status": "passed" if ok else "failed", "duration_seconds": round(time.monotonic() - started, 3),
        "ap_runtime_version": runtime["Utils"].__version__, "ut_version": runtime["upstream"].UT_VERSION,
        "upstream_provenance": json.loads((args.upstream / "UPSTREAM.json").read_text()),
        "upstream_hashes": upstream_before,
        "ap_dependency_provenance": json.loads((args.ap_dependencies / "UPSTREAM.json").read_text()),
        "ap_runtime_hashes": {path: file_hash(runtime_root / path) for path in runtime_paths},
        "source_hashes": before,
        "test_hashes": {str(Path(__file__).resolve().relative_to(SOURCE)): file_hash(__file__)},
        "baseline_archive_sha256": file_hash(args.baseline),
        "baseline_tracker_client_sha256": sha256(runtime["legacy_bytes"]).hexdigest(),
        "snapshot_digests": {name: digest(snapshot) for name, snapshot in suite.snapshots.items()},
        "evidence": suite.evidence,
        "seed_options": SEED_OPTIONS,
        "boundaries": [
            "Real upstream TrackerGameContext and TrackerCore including real TMain and updateTracker; no engine stub.",
            "Real AP CommonClient.process_server_cmd with Connected slot-data encode/decode and ReceivedItems packets.",
            "Production world generates current slot snapshots through generate_basic and fill_slot_data; no full item fill or beatability claim.",
            "Public/managed paths prove zero Players/weights/meta settings reads, file reads or scans; direct UT TMain builds their graph.",
            "Generic upstream UT retains its own eager startup scan but reconstructs SOH on Connected with an empty existing Players folder and no personal YAML.",
            "GUI never started; socket sends and persistent UI storage are isolated. No live server or Windows executable is run.",
            "Controlled ER fixture uses an explicitly valid nonvanilla warp-song map; no historical unsafe maps or broad random ER generation.",
        ],
    })
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(suite.report, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": suite.report["status"], "cases": len(suite.report["cases"]),
                      "assertions": suite.report["assertions"], "report": str(args.report)}, indent=2), flush=True)
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
