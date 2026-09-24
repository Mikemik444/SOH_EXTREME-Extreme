"""Private, windowless Universal Tracker host owned by a running SoH game.

The game starts this through the installed AP runtime. Credentials arrive only
through an inherited anonymous pipe; no user launcher action or console is used.
UT still obtains the authoritative slot data and received-item stream from AP
and performs its own evaluation. This module does not duplicate world rules.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import sys
import time
from urllib.parse import urlsplit

MAX_CONFIG = 16001
WORKER_COMPONENT = "SOH-EXTREME Universal Tracker"


def parse_config(raw: bytes) -> dict:
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_CONFIG:
        raise ValueError("Invalid startup payload size")
    config = json.loads(raw.decode("utf-8"))
    if not isinstance(config, dict) or set(config) != {"server", "slot_name", "password", "slot", "nonce"}:
        raise ValueError("Invalid startup payload fields")
    for key, maximum in (("server", 4096), ("slot_name", 128), ("password", 4096), ("nonce", 32)):
        value = config[key]
        if not isinstance(value, str) or len(value) > maximum or any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise ValueError("Invalid startup string")
    if not config["slot_name"] or not re.fullmatch(r"[0-9a-f]{32}", config["nonce"]):
        raise ValueError("Invalid startup identity")
    if type(config["slot"]) is not int or not 1 <= config["slot"] <= 65535:
        raise ValueError("Invalid startup slot")
    server = config["server"]
    address = urlsplit(server if "://" in server else "ws://" + server)
    if (address.scheme not in {"ws", "wss"} or not address.hostname or address.username is not None
            or address.password is not None or address.fragment):
        raise ValueError("Invalid startup server")
    # Validate port syntax/range as well as the hostname. Never echo credentials.
    _ = address.port
    return config


def read_config(stream=None) -> dict:
    if stream is not None:
        return parse_config(stream.readline(MAX_CONFIG + 1))
    if os.name == "nt":
        # Frozen GUI launchers may set sys.stdin to None even though the OS
        # inherited a valid pipe. Read that OS handle directly in both builds.
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetStdHandle.argtypes = [wintypes.DWORD]
        kernel.GetStdHandle.restype = wintypes.HANDLE
        kernel.ReadFile.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
                                    ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
        kernel.ReadFile.restype = wintypes.BOOL
        handle = kernel.GetStdHandle(-10 & 0xffffffff)
        chunks = bytearray()
        while len(chunks) <= MAX_CONFIG:
            buffer = ctypes.create_string_buffer(4096)
            count = wintypes.DWORD()
            ok = kernel.ReadFile(handle, buffer, len(buffer), ctypes.byref(count), None)
            if not ok:
                if ctypes.get_last_error() == 109:  # EOF on anonymous pipe
                    break
                raise ValueError("Startup pipe unavailable")
            if not count.value:
                break
            chunks.extend(buffer.raw[:count.value])
            if b"\n" in chunks:
                break
        return parse_config(bytes(chunks))
    return parse_config(sys.stdin.buffer.readline(MAX_CONFIG + 1))


def make_managed_context(base, config):
    """The subclass owns lifecycle/auth only; base supplies all UT evaluation."""
    class ManagedTracker(base):
        def __init__(self, *args, **kwargs):
            self.worker_exit_code = 0
            super().__init__(*args, **kwargs)
            self._managed_nonce = config["nonce"]

        @property
        def _persistence_enabled(self):
            # A private game tracker must not inherit an old UT /manually_collect
            # or /ignore override and silently alter the game's availability.
            return False

        def load_seed_data(self):
            self.tracker_core.manual_items = []
            self.tracker_core.ignored_locations = set()

        async def console_input(self):
            self.worker_exit_code = 22
            self.exit_event.set()
            raise RuntimeError("The managed tracker cannot prompt for credentials")

        async def server_auth(self, password_requested=False):
            if password_requested and not self.password:
                self.worker_exit_code = 22
                self.exit_event.set()
                return
            await self.send_connect(game="SOH-EXTREME")

        def on_package(self, cmd, args):
            if cmd == "Connected":
                slot = args.get("slot")
                info = args.get("slot_info", {}).get(str(slot))
                if slot != config["slot"] or not info or info[1] != "SOH-EXTREME":
                    self.worker_exit_code = 22
                    self.exit_event.set()
                    return
            super().on_package(cmd, args)
            if cmd == "Connected" and (not self.tracker_core.multiworld or self.tracker_core.tracker_disabled):
                self.worker_exit_code = 23
                self.exit_event.set()

        def make_gui(self):
            raise RuntimeError("No GUI belongs to the managed tracker")

        def run_cli(self):
            raise RuntimeError("No interactive console belongs to the managed tracker")

    return ManagedTracker


async def run_managed(config, ut):
    from .TrackerClient import make_context_class
    context_type = make_managed_context(make_context_class(ut.TrackerGameContext), config)
    ctx = context_type(config["server"], config["password"] or None, print_count=False, print_list=False)
    ctx.auth = config["slot_name"]
    tasks = []
    try:
        ctx.run_generator()
        ctx.server_task = asyncio.create_task(ut.server_loop(ctx), name="managed UT connection")
        tasks.append(ctx.server_task)

        async def lifetime():
            # The Windows Job is the primary lifetime boundary. This watchdog is
            # a backup if a host is started outside the game's process manager.
            started = time.monotonic()
            while not ctx.exit_event.is_set():
                await asyncio.sleep(5)
                last_request = max(started, ctx._mirror_last_request_time)
                if time.monotonic() - last_request > 180:
                    ctx.exit_event.set()
                if getattr(ctx, "disconnected_intentionally", False):
                    ctx.worker_exit_code = ctx.worker_exit_code or 22
                    ctx.exit_event.set()
        tasks.append(asyncio.create_task(lifetime(), name="managed UT lifetime"))
        await ctx.exit_event.wait()
        return ctx.worker_exit_code
    except Exception:
        logging.getLogger("Client").exception("Managed Universal Tracker failed")
        return 23
    finally:
        watcher = getattr(ctx, "watcher_task", None)
        if watcher is not None:
            tasks.append(watcher)
        for task in tasks:
            if not task.done():
                task.cancel()
        sender = getattr(ctx, "_mirror_sender", None)
        if sender is not None and not sender.done():
            sender.cancel()
            tasks.append(sender)
        await asyncio.gather(*tasks, return_exceptions=True)
        # CommonContext.shutdown awaits server_task; do not await a cancelled
        # task a second time and replace our intended exit code with CancelledError.
        ctx.server_task = None
        await ctx.shutdown()


def run_worker(*args):
    # No commands, credentials, arbitrary scripts, or eval come from argv.
    if list(args) != ["--game-owned", "--nogui"]:
        raise SystemExit(20)
    try:
        config = read_config()
    except (ValueError, OSError, UnicodeError):
        raise SystemExit(20) from None
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")
    import Utils
    # Utils was imported by the Launcher before dispatch. A GUI-frozen launcher
    # with no sys.stdout would otherwise consider its own GUI enabled.
    Utils.gui_enabled = False
    try:
        from worlds.tracker import TrackerClient as ut
    except ImportError:
        raise SystemExit(21) from None
    ut.gui_enabled = False
    Utils.init_logging("SOH-EXTREME-InGameTracker", exception_logger="Client")
    raise SystemExit(asyncio.run(run_managed(config, ut)))


def register_worker():
    from worlds.LauncherComponents import Component, Type, components
    if not any(component.display_name == WORKER_COMPONENT for component in components):
        components.append(Component(WORKER_COMPONENT, func=run_worker, component_type=Type.HIDDEN,
                                    description="Private Universal Tracker host managed by the SoH game"))
