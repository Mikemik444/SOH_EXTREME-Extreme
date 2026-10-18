"""Server hint metadata and completed-message reveals for the private AP host.

CommonClient supplies the authoritative read-only hint subscription. This
transport never infers progression from names or writes server data-storage
keys. CreateHints is used only for a disclosed, validated progression target.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time

PROTOCOL = "SOHExtremeFinder1"
MAX_HINTS = 20000
MAX_BYTES = 8 * 1024 * 1024
MAX_REVEALS = 256
_ID_MAX = (1 << 63) - 1
_REQUEST_MAX = (1 << 63) - 1
_LOG = logging.getLogger("Client")


def _integer(value, low, high):
    return type(value) is int and low <= value <= high


def _text(value, *, empty=False):
    return (isinstance(value, str) and (empty or bool(value))
            and not any(ord(c) < 32 or ord(c) == 127 for c in value))


def hint_target(row):
    """Normalize actual numeric provenance; absent flags never imply progress."""
    if not isinstance(row, dict) or row.get("starting", False):
        return None
    names = ("finding_player", "location_id", "receiving_player", "item_id", "item_flags")
    if not all(name in row for name in names):
        return None
    finder, location, recipient, item, flags = (row[name] for name in names)
    if (not _integer(finder, 1, 0x7fffffff) or not _integer(recipient, 1, 0x7fffffff)
            or not _integer(location, 0, _ID_MAX) or not _integer(item, 0, _ID_MAX)
            or not _integer(flags, 0, 0x7fffffff) or not flags & 1 or flags & 4):
        return None
    return dict(zip(names, (finder, location, recipient, item, flags)))


def _server_target(row):
    if not isinstance(row, dict):
        return None
    return hint_target({"finding_player": row.get("finding_player"), "location_id": row.get("location"),
                        "receiving_player": row.get("receiving_player"), "item_id": row.get("item"),
                        "item_flags": row.get("item_flags")})


def _key(target):
    return target["finding_player"], target["location_id"]


def _concerns_slot(ctx, target):
    return (target["finding_player"] in ctx.slot_info and target["receiving_player"] in ctx.slot_info
            and (target["finding_player"] == ctx.slot or ctx.slot_concerns_self(target["receiving_player"])))


def progression_hint_rows(ctx, hints):
    """Resolve each ID in its owner's game, keeping only known progression."""
    if not isinstance(hints, (list, tuple)) or len(hints) > MAX_HINTS:
        raise ValueError("Invalid server hint snapshot")
    result = []
    seen = set()
    for raw in hints:
        target = _server_target(raw)
        if target is None or not _concerns_slot(ctx, target) or type(raw.get("found")) is not bool:
            continue
        status = raw.get("status", 0)  # NetUtils.Hint's documented legacy default.
        entrance = raw.get("entrance", "")
        if not _integer(status, 0, 0xffffffff) or not _text(entrance, empty=True):
            continue
        finder, recipient = target["finding_player"], target["receiving_player"]
        item_game = ctx.slot_info[recipient].game
        location_game = ctx.slot_info[finder].game
        # Membership is checked before lookup: NameLookupDict otherwise creates
        # an "Unknown ..." fallback when a datapackage has not arrived yet.
        if (not _text(item_game) or not _text(location_game)
                or target["item_id"] not in ctx.item_names[item_game]
                or target["location_id"] not in ctx.location_names[location_game]):
            continue
        names = {
            "item": ctx.item_names.lookup_in_slot(target["item_id"], recipient),
            "location": ctx.location_names.lookup_in_slot(target["location_id"], finder),
            "recipient": ctx.player_names.get(recipient), "finder": ctx.player_names.get(finder),
            "item_game": item_game, "location_game": location_game,
        }
        if not all(_text(value) for value in names.values()):
            continue
        identity = _key(target)
        if identity in seen:
            raise ValueError("Duplicate server hint location")
        seen.add(identity)
        result.append({**target, **names, "found": raw["found"], "status": status, "entrance": entrance})
    return sorted(result, key=lambda row: (row["found"], row["item"], row["finder"],
                                           row["finding_player"], row["location_id"]))


class HintBridge:
    def __init__(self, context):
        self.ctx = context
        self.revision = 0  # Remains monotonic if this context reconnects.
        self.sender = None
        self.reset()

    def reset(self):
        if self.sender is not None and not self.sender.done():
            self.sender.cancel()
        self.sender = None
        self.subscription = None
        self.last_requests = {}
        self.raw_hints = None
        self.disclosed = {}
        self.pending = {}
        self.last_attempt = {}
        self.queued_scouts = set()
        self.queued_creates = {}
        self.queued_get = False
        self.queued_snapshot = None
        self.last_get = 0.0

    async def close(self):
        sender = self.sender
        self.reset()
        if sender is not None:
            await asyncio.gather(sender, return_exceptions=True)

    def on_package(self, cmd, args):
        if cmd in ("RoomInfo", "Connected", "ConnectionRefused"):
            self.reset()
            if cmd == "Connected":
                slot_data = args.get("slot_data", {})
                data = slot_data.get("extreme_hint_data", {}) if isinstance(slot_data, dict) else {}
                if isinstance(data, dict):
                    for rows in data.values():
                        if not isinstance(rows, list):
                            continue
                        for row in rows:
                            target = hint_target(row)
                            if target is not None and _concerns_slot(self.ctx, target):
                                self.disclosed[_key(target)] = target
            return
        if self.ctx.slot is None or self.ctx.team is None:
            return
        key = self.hint_key
        if ((cmd == "Retrieved" and key in args.get("keys", {}))
                or (cmd == "SetReply" and args.get("key") == key)):
            # CommonClient retains stored_data across disconnects. Only a new
            # response for this connection's exact key makes a snapshot fresh.
            value = args["keys"][key] if cmd == "Retrieved" else args.get("value")
            self.raw_hints = value if isinstance(value, list) and len(value) <= MAX_HINTS else None
            self._process_pending()
            self._publish()
        elif cmd == "LocationInfo":
            self._process_pending()
        elif cmd == "DataPackage" or (cmd == "RoomUpdate" and "players" in args):
            self._publish()

    @property
    def hint_key(self):
        return f"_read_hints_{self.ctx.team}_{self.ctx.slot}"

    def on_bounce(self, data):
        if not isinstance(data, dict) or data.get("soh_extreme_tracker") != PROTOCOL:
            return
        kind = data.get("kind")
        if kind not in ("request", "hint_request", "hint_reveal"):
            return
        nonce, request = data.get("nonce"), data.get("request")
        if (self.ctx.game != "SOH-EXTREME" or self.ctx.slot is None or self.ctx.team is None
                or type(data.get("slot")) is not int or data["slot"] != self.ctx.slot
                or not isinstance(nonce, str) or re.fullmatch(r"[a-f0-9]{32}", nonce) is None
                or nonce != getattr(self.ctx, "_managed_nonce", None)
                or not _integer(request, 1, _REQUEST_MAX)
                or request < self.last_requests.get(kind, 0)):
            return
        targets = data.get("targets")
        if kind == "hint_reveal" and (not isinstance(targets, list) or not 0 < len(targets) <= MAX_REVEALS):
            return
        self.last_requests[kind] = request
        self.subscription = (nonce, request)
        if kind == "hint_reveal":
            for raw in targets:
                target = hint_target(raw)
                if target is None or not _concerns_slot(self.ctx, target):
                    continue
                identity = _key(target)
                if target["finding_player"] == self.ctx.slot:
                    if target["location_id"] not in self.ctx.server_locations:
                        continue
                elif self.disclosed.get(identity) != target:
                    # Never scout unknown foreign locations to turn an
                    # unverified claim into knowledge of their contents.
                    continue
                if len(self.pending) < MAX_HINTS or identity in self.pending:
                    self.pending[identity] = target
            self._process_pending()
        # SetNotify provides live changes; periodic read-only retrieval also
        # repairs a missed initial reply and confirms completed reveal batches.
        if self.raw_hints is None or time.monotonic() - self.last_get >= 10.0:
            self.queued_get = True
        self._publish()
        self._start_sender()

    def _known_hints(self):
        return {_key(target): target for row in self.raw_hints or ()
                if (target := _server_target(row)) is not None}

    def _process_pending(self):
        if self.subscription is None:
            return
        known = self._known_hints()
        now = time.monotonic()
        for identity, target in tuple(self.pending.items()):
            if known.get(identity) == target:
                del self.pending[identity]
                self.last_attempt.pop(identity, None)
                continue
            finder, location = identity
            verified = self.disclosed.get(identity) == target
            if not verified and finder == self.ctx.slot:
                scout = self.ctx.locations_info.get(location)
                if scout is not None:
                    verified = (scout.item == target["item_id"] and scout.player == target["receiving_player"]
                                and scout.flags == target["item_flags"])
                    if not verified:
                        del self.pending[identity]
                        continue
                elif now - self.last_attempt.get(("scout", identity), -10.0) >= 10.0:
                    self.queued_scouts.add(location)
                    self.last_attempt[("scout", identity)] = now
            if verified and now - self.last_attempt.get(identity, -10.0) >= 10.0:
                self.queued_creates.setdefault(finder, set()).add(location)
                self.last_attempt[identity] = now
                self.queued_get = True
        self._start_sender()

    def _publish(self):
        if self.subscription is None or self.raw_hints is None:
            return
        nonce, request = self.subscription
        try:
            if self.revision >= _REQUEST_MAX:
                raise ValueError("Server hint revision is out of range")
            rows = progression_hint_rows(self.ctx, self.raw_hints)
            data = {"soh_extreme_tracker": PROTOCOL, "kind": "hint_snapshot", "slot": self.ctx.slot,
                    "nonce": nonce, "producer": self.ctx._mirror_producer, "request": request,
                    "revision": self.revision + 1, "rows": rows}
            if len(json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")) > MAX_BYTES:
                raise ValueError("Server hint snapshot is too large")
        except (ValueError, KeyError, AttributeError, TypeError):
            _LOG.exception("SOH-EXTREME rejected an invalid server hint snapshot")
            return
        self.revision += 1
        self.queued_snapshot = {"cmd": "Bounce", "slots": [self.ctx.slot], "data": data}
        self._start_sender()

    def _start_sender(self):
        if (self.queued_scouts or self.queued_creates or self.queued_get or self.queued_snapshot is not None):
            if self.sender is None or self.sender.done():
                self.sender = asyncio.create_task(self._send(), name="SOH server hints")

    async def _send(self):
        try:
            while self.queued_scouts or self.queued_creates or self.queued_get or self.queued_snapshot is not None:
                messages = []
                if self.queued_scouts:
                    messages.append({"cmd": "LocationScouts", "locations": sorted(self.queued_scouts),
                                     "create_as_hint": 0})
                    self.queued_scouts.clear()
                for player, locations in sorted(self.queued_creates.items()):
                    # Unspecified status is required for another player's item
                    # at one of our locations. Server applies its own checks.
                    messages.append({"cmd": "CreateHints", "player": player, "locations": sorted(locations)})
                self.queued_creates.clear()
                if self.queued_get:
                    messages.append({"cmd": "Get", "keys": [self.hint_key]})
                    self.queued_get = False
                    self.last_get = time.monotonic()
                if self.queued_snapshot is not None:
                    messages.append(self.queued_snapshot)
                    self.queued_snapshot = None
                await self.ctx.send_msgs(messages)
        except Exception:
            _LOG.exception("SOH-EXTREME server hint transport failed")
        finally:
            if self.sender is asyncio.current_task():
                self.sender = None
