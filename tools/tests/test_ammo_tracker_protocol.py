"""Exercise last-ammo transport and closed-window worker authority.

The production Python encoder feeds the production C++ decoder/mirror. Native
snapshot consumption and worker servicing use their complete production bodies;
authentication, clock, storage and process/network IO are explicit boundaries.
The real Python request handler is exercised with an isolated UT/network host.
Actual refill graph decisions are covered by test_ammo_refill.py; real UT
bootstrap and server-slot reconstruction are covered by test_tracker_yamlless.py.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

from test_zora_river_native import function

SOURCE = Path(__file__).resolve().parents[2]
NONCE = "a" * 32
SOURCES = (
    "archipelago/soh_extreme/TrackerMirror.py",
    "archipelago/soh_extreme/TrackerClient.py",
    "archipelago/soh_extreme/TrackerBootstrap.py",
    "archipelago/soh_extreme/TrackerWorker.py",
    "archipelago/soh_extreme/AmmoRefillRules.py",
    "soh/Network/Archipelago/TrackerMirror.h",
    "soh/Network/Archipelago/ArchipelagoClient.cpp",
    "soh/Network/Archipelago/ArchipelagoClient.h",
    "soh/Network/Archipelago/AmmoPolicy.h",
    "soh/SohExtremeVersion.h",
)
TESTS = (
    "tools/tests/test_ammo_tracker_protocol.py",
    "tools/tests/ammo_tracker_protocol_tests.cpp.in",
    "tools/tests/test_zora_river_native.py",
)


def hashes(paths):
    return {name: hashlib.sha256((SOURCE / name).read_bytes()).hexdigest() for name in paths}


def python_modules():
    import ModuleUpdate
    ModuleUpdate.update_ran = True
    import settings
    settings.no_gui = True
    settings.skip_autosave = True
    from worlds.soh_extreme import TrackerMirror, TrackerClient, AmmoRefillRules
    return TrackerMirror, TrackerClient, AmmoRefillRules


def wire_cases(protocol):
    base = dict(nonce=NONCE, request=1, revision=1, slot=1, producer="native-test-worker",
                received=7, active={100, 101}, checked={100},
                rows=[dict(id=101, state=1, name="Main room transition", region="Dungeon")],
                live_shields=3, live_time=0, live_clock=0x8000, live_time_flags=0,
                live_ammo=31, live_ammo_owned=31, live_rupees=120, live_ammo_flags=0,
                live_ammo_state=987, ammo_refills=31)
    cases = []
    py_assertions = 0

    def add(name, *, updates=None, payload=None, valid=True):
        values = dict(base, **(updates or {}))
        if payload is None:
            payload = protocol.encode_snapshot(**values)
        expected = (values.get("live_ammo"), values.get("live_ammo_owned", 0),
                    values.get("ammo_refills", 0))
        if expected[0] is None:
            expected = (0xffffffff, 0, 0)
        cases.append((name, payload, valid, *expected))
        return payload

    good = add("live")
    add("legacy", updates=dict(live_ammo=None, live_clock=None, live_time=None))
    add("time_only", updates=dict(live_ammo=None, live_clock=None))
    add("clock_only", updates=dict(live_ammo=None))
    add("future_release", updates=dict(version="99.0.0"))
    add("manual", updates=dict(manual_count=1))
    add("ignored", updates=dict(ignored_count=1))
    add("wrong_owned", updates=dict(live_ammo=15, live_ammo_owned=15))
    add("wrong_rupees", updates=dict(live_rupees=119))
    add("wrong_flags", updates=dict(live_ammo_flags=1))
    add("wrong_token", updates=dict(live_ammo_state=988))
    add("wrong_received", updates=dict(received=6))
    add("wrong_checked", updates=dict(checked=set()))
    add("wrong_nonce", updates=dict(nonce="b" * 32))
    add("wrong_slot", updates=dict(slot=2))
    add("partial", updates=dict(ammo_refills=5))
    add("none", updates=dict(ammo_refills=0))
    for bit in (1, 2, 4, 8, 16):
        add(f"ammo_{bit}", updates=dict(live_ammo=bit, live_ammo_owned=bit, ammo_refills=bit))
    for owned in range(32):
        add(f"owned_{owned}", updates=dict(live_ammo=owned, live_ammo_owned=owned, ammo_refills=owned))
    add("max_token", updates=dict(live_ammo_state=(1 << 64) - 1, live_rupees=65535, live_ammo_flags=3))
    raw = base64.b64decode(good)
    offset = raw.rindex(b"AMMO")
    assert len(raw) - offset == 32
    py_assertions += 1
    for end in range(offset, len(raw)):
        # Exactly removing the optional extension is a valid older snapshot.
        add(f"truncated_{end-offset}", payload=base64.b64encode(raw[:end]).decode(),
            valid=(end == offset), updates=dict(live_ammo=None) if end == offset else {})
    for field, position, value in (("mask", 4, 32), ("owned", 8, 32), ("rupees", 12, 65536),
                                   ("flags", 16, 4), ("refills", 28, 32)):
        damaged = bytearray(raw)
        struct.pack_into("<I", damaged, offset + position, value)
        add("bad_" + field, payload=base64.b64encode(damaged).decode(), valid=False)
    for name, changed in (
        ("bad_tag", raw[:offset] + b"FAIL" + raw[offset+4:]),
        ("zero_token", raw[:offset+20] + b"\0" * 8 + raw[offset+28:]),
        ("unowned_ammo", raw[:offset+8] + b"\0" * 4 + raw[offset+12:]),
        ("trailing", raw + b"\0"),
        ("duplicate_extension", raw + raw[offset:]),
    ):
        add(name, payload=base64.b64encode(changed).decode(), valid=False)
    invalid = [dict(live_ammo=32), dict(live_ammo=-1), dict(live_ammo=True),
               dict(live_ammo_owned=0), dict(live_ammo_owned=32),
               dict(live_rupees=65536), dict(live_rupees=-1), dict(live_rupees=True),
               dict(live_ammo_flags=4), dict(live_ammo_flags=True),
               dict(live_ammo_state=0), dict(live_ammo_state=1 << 64), dict(live_ammo_state=True),
               dict(ammo_refills=32), dict(ammo_refills=-1), dict(ammo_refills=True),
               dict(live_clock=None), dict(live_time=None)]
    for changes in invalid:
        try:
            protocol.encode_snapshot(**dict(base, **changes))
        except (ValueError, TypeError):
            py_assertions += 1
        else:
            raise AssertionError(("Encoder accepted invalid ammo fields", changes))
    return cases, py_assertions


def native_test(cases):
    compiler = shutil.which("g++") or shutil.which("c++")
    if not compiler:
        raise SystemExit("A C++20 compiler is required")
    client = (SOURCE / "soh/Network/Archipelago/ArchipelagoClient.cpp").read_text()
    methods = "\n\n".join(function(client, signature) for signature in (
        "std::string ArchipelagoClient::AmmoSourcesJson() const {",
        "void ArchipelagoClient::ServiceFinderWorker() {",
        "const SohExtreme::TrackerSnapshot* ArchipelagoClient::GetFinderSnapshot(std::string& status) {",
    ))
    update = function(client, "void ArchipelagoClient::Update() {")
    assert update.count("ServiceFinderWorker();") == 1
    assert update.index("ServiceFinderWorker();") < update.index("if (!enabled.load()) return;")
    assert "CheckFinder" not in methods and "ImGui" not in methods
    rows = ",\n".join("{" + ", ".join((json.dumps(name), json.dumps(payload),
                       "true" if valid else "false", str(ammo) + "u", str(owned) + "u",
                       str(refills) + "u")) + "}" for name, payload, valid, ammo, owned, refills in cases)
    template = (SOURCE / "tools/tests/ammo_tracker_protocol_tests.cpp.in").read_text()
    cpp = template.replace("@PAYLOADS@", rows).replace("@NATIVE_METHODS@", methods)
    if re.search(r"@[A-Z_]+@", cpp):
        raise AssertionError("Unexpanded native protocol fixture")
    with tempfile.TemporaryDirectory(prefix="soh-ammo-protocol-") as temp:
        work = Path(temp)
        (work / "fixture.cpp").write_text(cpp)
        command = [compiler, "-std=c++20", "-O1", "-g", "-fsanitize=address,undefined",
                   "-fno-omit-frame-pointer", "-fno-pie", "-no-pie", "-I" + str(SOURCE),
                   str(work / "fixture.cpp"), "-o", str(work / "fixture")]
        built = subprocess.run(command, text=True, capture_output=True, timeout=60)
        if built.returncode:
            raise AssertionError(built.stdout + built.stderr)
        env = dict(os.environ, ASAN_OPTIONS="detect_leaks=0:halt_on_error=1",
                   UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=1")
        ran = subprocess.run([str(work / "fixture")], text=True, capture_output=True, env=env, timeout=30)
        if ran.returncode:
            raise AssertionError(ran.stdout + ran.stderr)
    return json.loads(ran.stdout)


async def client_test(protocol, client, rules):
    counts = dict(cases=0, assertions=0, proof_calls=0)
    clock = [100.0]

    def check(condition, message):
        counts["assertions"] += 1
        assert condition, message

    class HintIO:
        def __init__(self, context): pass
        def reset(self): pass
        def on_package(self, cmd, args): pass
        def on_bounce(self, data): pass
        async def close(self): pass

    class HostIO:
        tags = set()
        def __init__(self, *args, **kwargs):
            self.game = "SOH-EXTREME"
            self.slot, self.team = 1, 0
            self.server_locations, self.checked_locations = {100, 101}, {100}
            self.tracker_items_received = list(range(7))
            self.world = SimpleNamespace(player=1)
            self.tracker_core = SimpleNamespace(
                get_current_world=lambda: self.world, enable_glitched_logic=False,
                location_alias_map={}, manual_items=[], ignored_locations=[],
                disconnect=lambda: None)
            self.result = SimpleNamespace(state=object(), in_logic_locations=[], glitched_locations=[])
            self.updates, self.sent, self.resets = 0, [], 0
        def on_package(self, cmd, args): pass
        def updateTracker(self):
            self.updates += 1
            return self.result
        def reset_server_state(self): self.resets += 1
        async def send_msgs(self, packets): self.sent.extend(packets)
        async def disconnect(self, allow_autoreconnect=False): pass
        async def shutdown(self): pass

    calls = []
    behavior = [5]
    def proof(world, state, **kwargs):
        counts["proof_calls"] += 1
        calls.append((world, state, kwargs))
        if isinstance(behavior[0], Exception):
            raise behavior[0]
        return behavior[0]

    request = dict(soh_extreme_tracker=protocol.PROTOCOL, kind="request", slot=1,
                   nonce=NONCE, request=1, live_shields=3, live_time=0,
                   live_clock=0x8000, live_time_flags=0, ammo_protocol=1,
                   live_ammo=31, live_ammo_owned=31, live_rupees=120,
                   live_ammo_flags=0, live_ammo_state=987, live_age=1,
                   ammo_sources=[[9001, 1 | (1 << 6) | (1 << 8)]])

    def fields(packet):
        raw = base64.b64decode(packet["data"]["payload"])
        if len(raw) < 32 or raw[-32:-28] != b"AMMO":
            return None
        return struct.unpack("<IIIIQI", raw[-28:])

    with patch.object(client, "install_slot_data_core", return_value=None), \
            patch.object(client, "HintBridge", HintIO), \
            patch.object(client, "refill_mask", side_effect=proof), \
            patch.object(client, "time", SimpleNamespace(monotonic=lambda: clock[0])):
        context_type = client.make_context_class(HostIO)
        def context(managed=True):
            ctx = context_type()
            if managed: ctx._managed_nonce = NONCE
            return ctx

        async def send(ctx, changes=None, remove=()):
            clock[0] += 0.2
            packet = dict(request, **(changes or {}))
            for key in remove: packet.pop(key, None)
            before = len(ctx.sent)
            ctx.on_package("Bounced", {"data": packet})
            if ctx._mirror_sender is not None:
                await asyncio.gather(ctx._mirror_sender)
            return ctx.sent[before:]

        counts["cases"] += 1
        ctx = context()
        packets = await send(ctx)
        check(len(packets) == 1 and ctx.updates == 1, "managed request evaluates and publishes without a GUI")
        check(ctx.world._extreme_live_ammo == 31, "actual live ammo reaches the UT evaluation")
        check(fields(packets[0]) == (31, 31, 120, 0, 987, 5), "refill proof and exact inputs reach the wire")
        check(calls[-1][0] is ctx.world and calls[-1][1] is ctx.result.state,
              "proof consumes UT's actual returned state and world")
        proof_inputs = calls[-1][2]
        for key, value in (("live_ammo", 31), ("owned", 31), ("rupees", 120),
                           ("flags", 0), ("live_age", 1), ("checked", {100})):
            check(proof_inputs[key] == value, "exact request/provenance forwarded: " + key)
        check(tuple(proof_inputs["observed"]) == ((9001, 321),), "validated native source facts reach proof")

        counts["cases"] += 1
        previous_calls = len(calls)
        await send(ctx, dict(request=2))
        check(len(calls) == previous_calls, "unchanged authoritative input reuses bounded proof")
        await send(ctx, dict(request=3, live_ammo_state=988, live_rupees=119))
        check(len(calls) == previous_calls + 1 and calls[-1][2]["rupees"] == 119,
              "changed native state invalidates cached proof")
        await send(ctx, dict(request=4, live_ammo_state=989, live_age=2))
        check(calls[-1][2]["live_age"] == 2, "age change reaches current-age proof")
        ctx.checked_locations.add(101)
        await send(ctx, dict(request=5, live_ammo_state=989, live_age=2))
        check(calls[-1][2]["checked"] == {100, 101}, "cleared first AP check refreshes source proof")
        before_calls = len(calls)
        ctx.tracker_items_received.append(7)
        await send(ctx, dict(request=6, live_ammo_state=989, live_age=2))
        check(len(calls) == before_calls + 1, "new AP receipt refreshes proof")
        await send(ctx, dict(request=7, live_ammo_state=990,
                             ammo_sources=[[9002, 2 | (2 << 6) | (1 << 8)]]))
        check(tuple(calls[-1][2]["observed"]) == ((9002, 386),), "new observed source refreshes proof")

        counts["cases"] += 1
        ctx = context()
        before_calls = len(calls)
        packets = await send(ctx, dict(live_clock=0xB887))
        check(len(calls) == before_calls + 1 and fields(packets[0])[-1] == 5,
              "courtyard-open clock evaluates initial proof")
        await send(ctx, dict(request=2, live_clock=0xB888))
        check(len(calls) == before_calls + 1, "ordinary motion within courtyard window reuses proof")
        behavior[0] = 0
        packets = await send(ctx, dict(request=3, live_clock=0xB889))
        check(len(calls) == before_calls + 2 and fields(packets[0])[-1] == 0,
              "courtyard closing invalidates Python cache even with unchanged state token")
        await send(ctx, dict(request=4, live_clock=0xB88A))
        check(len(calls) == before_calls + 2, "ordinary late-day clock motion reuses closed proof")
        behavior[0] = 5
        packets = await send(ctx, dict(request=5, live_clock=0xB888))
        check(len(calls) == before_calls + 3 and fields(packets[0])[-1] == 5,
              "returning to courtyard-open time recomputes refill proof")

        for field in ("manual_items", "ignored_locations"):
            counts["cases"] += 1
            ctx = context()
            setattr(ctx.tracker_core, field, ["display-only edit"])
            before_calls = len(calls)
            packets = await send(ctx)
            check(len(packets) == 1 and fields(packets[0])[-1] == 0,
                  "manual/ignored tracker edits cannot authorize ammo consumption")
            check(len(calls) == before_calls, "edited state never enters gameplay refill proof")

        counts["cases"] += 1
        behavior[0] = RuntimeError("intentional unavailable proof")
        ctx = context()
        with patch.object(client.logging.getLogger("Client"), "exception"):
            packets = await send(ctx)
        check(len(packets) == 1 and fields(packets[0])[-1] == 0,
              "proof failure retains last ammo and ordinary Finder snapshot")
        behavior[0] = 5

        invalid = [
            ({"ammo_protocol": 0}, ()), ({"ammo_protocol": True}, ()),
            ({"live_ammo": -1}, ()), ({"live_ammo": 32}, ()), ({"live_ammo": True}, ()),
            ({"live_ammo_owned": 0}, ()), ({"live_ammo_owned": 32}, ()),
            ({"live_rupees": -1}, ()), ({"live_rupees": 65536}, ()), ({"live_rupees": True}, ()),
            ({"live_ammo_flags": 4}, ()), ({"live_ammo_flags": True}, ()),
            ({"live_ammo_state": 0}, ()), ({"live_ammo_state": 1 << 64}, ()),
            ({"live_ammo_state": True}, ()), ({"live_age": 0}, ()), ({"live_age": 3}, ()),
            ({"live_age": True}, ()), ({}, ("live_age",)),
            ({}, ("live_ammo",)), ({}, ("live_ammo_owned",)), ({}, ("live_rupees",)),
            ({}, ("live_ammo_flags",)), ({}, ("live_ammo_state",)), ({}, ("live_clock",)),
            ({"ammo_sources": None}, ()), ({"ammo_sources": [[0, 321]]}, ()),
            ({"ammo_sources": [[9001, 321], [9001, 321]]}, ()),
            ({"ammo_sources": [[9001, 321]] * 2049}, ()),
            ({"ammo_sources": [[True, 321]]}, ()), ({"ammo_sources": [[9001, True]]}, ()),
            ({"ammo_sources": [[9001, 1 | (1 << 6) | (3 << 8)]]}, ()),
            ({"ammo_sources": [[9001, 8 | (1 << 6) | (1 << 8)]]}, ()),
            ({"nonce": "b" * 32}, ()), ({"request": 0}, ()), ({"slot": 2}, ()),
        ]
        for changes, remove in invalid:
            counts["cases"] += 1
            ctx = context()
            before_calls = len(calls)
            packets = await send(ctx, changes, remove)
            check(not packets and ctx.updates == 0 and len(calls) == before_calls,
                  "invalid request rejected before evaluation: " + repr((changes, remove))[:160])
            check(ctx._mirror_subscription is None, "invalid request does not replace subscription")

        counts["cases"] += 1
        ctx = context(False)
        packets = await send(ctx)
        check(not packets and ctx.updates == 0, "standalone tracker cannot assert live ammo authority")
        no_ammo = tuple(key for key in request if key.startswith("live_ammo") or key in
                        ("ammo_protocol", "live_rupees", "live_age", "ammo_sources"))
        packets = await send(ctx, remove=no_ammo)
        check(len(packets) == 1 and fields(packets[0]) is None,
              "older standalone tracker still receives original display protocol")
        check(ctx.world._extreme_live_ammo is None, "standalone generation resource semantics retained")

        counts["cases"] += 1
        ctx = context()
        await send(ctx, dict(request=5))
        before_calls = len(calls)
        packets = await send(ctx, dict(request=4, live_ammo_state=999))
        check(not packets and len(calls) == before_calls and ctx._mirror_subscription == (NONCE, 5),
              "older request cannot replace current live inventory")

        for event in ("RoomInfo", "Connected", "ConnectionRefused"):
            counts["cases"] += 1
            ctx = context()
            await send(ctx)
            ctx.on_package(event, {})
            check(ctx._mirror_live_ammo is None and ctx._mirror_ammo_cache is None
                  and ctx._mirror_subscription is None,
                  "server identity boundary resets ammo proof")
        counts["cases"] += 1
        ctx = context()
        await send(ctx)
        await ctx.disconnect()
        check(ctx._mirror_live_ammo is None and ctx._mirror_ammo_cache is None
              and ctx.world._extreme_live_ammo is None and ctx._mirror_subscription is None,
              "disconnect clears all live refill state")

    # Use the real bounded validator independently of the host boundary.
    counts["cases"] += 1
    check(len(rules.validate_observed_sources([[i + 1, 321] for i in range(2048)])) == 2048,
          "maximum distinct observed source list accepted")
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    before, tests_before = hashes(SOURCES), hashes(TESTS)
    protocol, client, rules = python_modules()
    cases, encoder_assertions = wire_cases(protocol)
    native = native_test(cases)
    worker = asyncio.run(client_test(protocol, client, rules))
    assert before == hashes(SOURCES) and tests_before == hashes(TESTS), "Source changed during validation"
    report = dict(status="passed", source_sha256=before, test_sha256=tests_before,
                  source_unchanged_during_tests=True, wire_cases=len(cases),
                  encoder_assertions=encoder_assertions, native=native, worker=worker,
                  sanitizers=["AddressSanitizer", "UndefinedBehaviorSanitizer"],
                  native_windows_build=False, in_game_playthrough=False,
                  scope="Production Python encoder and request/publish handler, C++ decoder and mirror, "
                        "complete native GetFinderSnapshot and ServiceFinderWorker. "
                        "Network/process IO, UT evaluation, clock and native storage are isolated; "
                        "actual AP refill reachability has its separate test_ammo_refill.py suite. "
                        "The real UT slot bootstrap and launcher dispatch are covered by test_tracker_yamlless.py.",
                  replay_command="PYTHONPATH=<AP-dependencies>:<AP-0.6.8-runtime> python3 "
                                 "source/tools/tests/test_ammo_tracker_protocol.py --report <REPORT>")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ("status", "wire_cases", "encoder_assertions", "native", "worker")}))


if __name__ == "__main__":
    main()
