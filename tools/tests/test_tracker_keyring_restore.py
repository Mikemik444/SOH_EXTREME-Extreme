"""Compare saved Count keyrings before/after the tracker restoration fix.

Uses the current production world and the pinned, unmodified real Universal
Tracker TMain.  The old foundation method is read from the delivered 1.8.13
source archive and substituted only in a scoped baseline run.  This measures
resolved flags, required trials, reserved items and foundation RNG state; it is
not a gameplay, item-fill or beatability test.

Run from the workspace containing source and the AP 0.6.8 runtime:
  PYTHONPATH=ap-deps:ap-runtime-068 python source/tools/tests/test_tracker_keyring_restore.py
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
from copy import deepcopy
from hashlib import sha256
import json
import logging
from pathlib import Path
import time
import traceback
from types import SimpleNamespace
from unittest.mock import patch
import zipfile

from test_tracker_yamlless import (GAME, SOURCE, WORK, SEED_OPTIONS, canonical,
                                  digest, file_hash, load_runtime, production_hashes)


def flags(world):
    return {name: getattr(world.options, name).value
            for name in world.options_dataclass.type_hints if name.endswith("_key_ring")}


def pool(world):
    return dict(sorted(Counter(str(item) for item in world.pre_fill_pool).items()))


def old_foundation(archive_path, current_method):
    with zipfile.ZipFile(archive_path) as archive:
        text = archive.read("archipelago/soh_extreme/__init__.py").decode("utf-8-sig")
    module = ast.parse(text)
    world = next(node for node in module.body if isinstance(node, ast.ClassDef)
                 and node.name == "SohExtremeWorld")
    method = next(node for node in world.body if isinstance(node, ast.FunctionDef)
                  and node.name == "_generate_stock_foundation")
    source = ast.get_source_segment(text, method)
    namespace = dict(current_method.__globals__)
    code = ast.fix_missing_locations(ast.Module(body=[deepcopy(method)], type_ignores=[]))
    exec(compile(code, str(archive_path) + "!/_generate_stock_foundation", "exec"), namespace)
    return namespace[method.name], sha256(source.encode()).hexdigest()


def observe(method, observations):
    def observed(world):
        before = world.random.getstate()
        result = method(world)
        observations.append({"using_ut": world.using_ut,
                             "rng_changed": before != world.random.getstate(),
                             "keyrings": flags(world),
                             "required_trials": list(world.ganons_trials),
                             "pre_fill_pool": pool(world)})
        return result
    return observed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", type=Path, default=WORK / "tests/tracker_bootstrap_1814_upstream")
    parser.add_argument("--ap-dependencies", type=Path,
                        default=WORK / "tests/tracker_bootstrap_1814_ap_dependencies")
    parser.add_argument("--baseline", type=Path, default=WORK / "delivery/SOH-EXTREME-1.8.13-source-files.zip")
    parser.add_argument("--report", type=Path, default=WORK / "tests/tracker_yamlless_1814_keyring_restore.json")
    args = parser.parse_args()
    for name in ("upstream", "ap_dependencies", "baseline", "report"):
        setattr(args, name, getattr(args, name).resolve())
    started = time.monotonic()
    hashes = production_hashes()
    tests = {str(Path(__file__).resolve().relative_to(SOURCE)): file_hash(__file__),
             "tools/tests/test_tracker_yamlless.py": file_hash(Path(__file__).with_name("test_tracker_yamlless.py"))}
    upstream = {str(path.relative_to(args.upstream)): file_hash(path)
                for path in sorted(args.upstream.rglob("*"))
                if path.is_file() and path.suffix in (".py", ".json", ".md")}
    report = {"status": "failed", "assertions": 0, "failures": []}

    def check(condition, message):
        report["assertions"] += 1
        if not condition:
            raise AssertionError(message)

    try:
        runtime = load_runtime(args)
        world_type = runtime["SohExtremeWorld"]
        current = world_type._generate_stock_foundation
        baseline, baseline_method_hash = old_foundation(args.baseline, current)
        options = deepcopy(SEED_OPTIONS)
        options.update(key_rings="count", key_rings_count=4, small_key_shuffle="own_dungeon")
        make_world = runtime["setup_multiworld"]
        call_all = runtime["call_all"]

        # A normal generation must keep exactly the same RNG position and
        # resolved setup as before this tracker-only change.
        normal_old = make_world(world_type, steps=(), seed=123, options=deepcopy(options))
        with patch.object(world_type, "_generate_stock_foundation", baseline):
            call_all(normal_old, "generate_early")
        normal = make_world(world_type, steps=(), seed=123, options=deepcopy(options))
        normal.player_name[1] = "KeyringCountProbe"
        call_all(normal, "generate_early")
        old_world, world = normal_old.worlds[1], normal.worlds[1]
        check(pool(old_world) == pool(world), "Fresh generation reserved items changed")
        check(flags(old_world) == flags(world), "Fresh generation keyring selection changed")
        check(old_world.ganons_trials == world.ganons_trials, "Fresh generation trials changed")
        check(old_world.random.getstate() == world.random.getstate(), "Fresh generation RNG order changed")
        check({name: canonical(getattr(old_world.options, name).value)
               for name in world.options_dataclass.type_hints}
              == {name: canonical(getattr(world.options, name).value)
                  for name in world.options_dataclass.type_hints}, "Fresh generation resolved options changed")
        for stage in ("create_regions", "create_items", "set_rules", "connect_entrances", "generate_basic"):
            call_all(normal, stage)
        snapshot = json.loads(runtime["NetUtils"].encode(world.fill_slot_data()))
        expected_pool, expected_flags = pool(world), flags(world)

        from worlds.soh_extreme.TrackerBootstrap import install_slot_data_core

        def rebuild(method):
            context = SimpleNamespace(
                tracker_core=runtime["TrackerCore"].TrackerCore(logging.getLogger("keyring-restore"), False, False),
                seed_name="KeyringCountProbe")
            core = install_slot_data_core(context)
            core.set_slot_params(GAME, 1, "KeyringCountProbe", 0)
            observed = []
            with patch.object(world_type, "_generate_stock_foundation", observe(method, observed)):
                core.run_generator(deepcopy(snapshot))
            check(core.multiworld is not None, "Real UT generation failed: " + core.gen_error)
            check(len(observed) == 1, "Expected one real UT foundation call")
            rebuilt = core.get_current_world()
            check(flags(rebuilt) == expected_flags, "Saved resolved keyring flags were not restored")
            check(rebuilt.ganons_trials == snapshot["required_trials"], "Saved required trials changed")
            check({loc.address for loc in rebuilt.get_locations() if isinstance(loc.address, int)}
                  == set(snapshot["extreme_active_locations"]), "Saved active location IDs changed")
            return rebuilt, observed[0]

        before, before_observation = rebuild(baseline)
        after, after_observation = rebuild(current)
        check(pool(before) != expected_pool, "The baseline keyring reservation defect was not reproduced")
        check(pool(after) == expected_pool, "Tracker reserved items differ from the generated seed")
        check(before_observation["rng_changed"], "Baseline did not reroll the foundation")
        check(not after_observation["rng_changed"], "Tracker still rerolls saved keyrings or trials")
        check(production_hashes() == hashes, "Production files changed while this test was running")
        check(all(file_hash(SOURCE / path) == checksum for path, checksum in tests.items()),
              "Regression test files changed while running")
        check(all(file_hash(args.upstream / path) == checksum for path, checksum in upstream.items()),
              "Pinned Universal Tracker source changed while running")
        report.update({
            "status": "passed", "original_seed": 123, "bootstrap_seed": snapshot["archipelago_seed"],
            "snapshot_digest": digest(snapshot), "fresh_generation_unchanged": True,
            "expected_keyring_flags": expected_flags, "expected_required_trials": snapshot["required_trials"],
            "expected_pre_fill_pool": expected_pool, "before_pre_fill_pool": pool(before),
            "after_pre_fill_pool": pool(after), "before_foundation": before_observation,
            "after_foundation": after_observation,
            "before_missing_items": dict(Counter(expected_pool) - Counter(pool(before))),
            "before_unexpected_items": dict(Counter(pool(before)) - Counter(expected_pool)),
            "baseline_method_sha256": baseline_method_hash,
            "ap_runtime_version": runtime["Utils"].__version__,
            "ut_version": runtime["upstream"].UT_VERSION,
        })
    except Exception:
        report["failures"].append(traceback.format_exc())
        traceback.print_exc()
    report.update({
        "source_hashes": hashes, "test_hashes": tests, "upstream_hashes": upstream,
        "baseline_archive_sha256": file_hash(args.baseline),
        "upstream_provenance": json.loads((args.upstream / "UPSTREAM.json").read_text()),
        "duration_seconds": round(time.monotonic() - started, 3),
        "boundary": "Real UT TMain and actual world setup; no item fill, gameplay, live server or beatability claim.",
    })
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "assertions": report["assertions"],
                      "report": str(args.report)}, indent=2), flush=True)
    raise SystemExit(0 if report["status"] == "passed" else 1)


if __name__ == "__main__":
    main()
