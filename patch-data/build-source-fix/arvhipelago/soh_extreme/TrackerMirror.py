"""Bounded, read-only UT -> C++ Check Finder transport.

The payload contains evaluated location IDs, not a second set of access rules.
No locations/items are granted or checked by this module. Strings use UTF-8.
"""
from __future__ import annotations
import base64
import struct
from typing import Any

PROTOCOL = "SOHExtremeFinder1"
VERSION = "0.11.22"
TAG = "SOHExtremeUT"
MAX_ENTRIES = 20000
MAX_BYTES = 750000
MAGIC = b"SEFT1\0"


def _integer(value: Any, low: int, high: int) -> int:
    if type(value) is not int or not low <= value <= high:
        raise ValueError("Invalid tracker protocol integer")
    return value


def encode_snapshot(*, nonce: str, request: int, revision: int, slot: int,
                    producer: str, received: int, active: set[int], checked: set[int],
                    rows: list[dict], manual_count: int = 0, ignored_count: int = 0,
                    version: str = VERSION) -> str:
    if not nonce or len(nonce) > 64 or not producer or len(producer) > 64:
        raise ValueError("Invalid tracker session identity")
    if len(active) > MAX_ENTRIES or len(rows) > MAX_ENTRIES or not checked <= active:
        raise ValueError("Invalid tracker location manifest")
    out = bytearray(MAGIC)
    def u32(n): out.extend(struct.pack("<I", _integer(n, 0, 0xffffffff)))
    def u64(n): out.extend(struct.pack("<Q", _integer(n, 0, 0xffffffffffffffff)))
    def text(s):
        if not isinstance(s, str) or any(ord(c) < 32 or ord(c) == 127 for c in s):
            raise ValueError("Invalid tracker label")
        b = s.encode("utf-8")
        if len(b) > 2048: raise ValueError("Tracker label too long")
        out.extend(struct.pack("<H",len(b)));out.extend(b)
    text(nonce); text(producer); text(version)
    u32(slot);u64(request);u64(revision);u64(received)
    u32(manual_count);u32(ignored_count)
    for ids in (active, checked):
        u32(len(ids))
        for i in sorted(ids):u64(_integer(i, 1, 0x7fffffffffffffff))
    u32(len(rows));seen=set()
    for row in rows:
        i=_integer(row['id'],1,0x7fffffffffffffff)
        if i in seen or i not in active or i in checked:
            raise ValueError("Duplicate, inactive, or checked tracker row")
        seen.add(i);u64(i)
        out.append(_integer(row['state'],1,2))
        text(row['name']);text(row['region'])
    if len(out)>MAX_BYTES:raise ValueError("Tracker snapshot too large")
    return base64.b64encode(out).decode('ascii')


def snapshot_rows(core, tracker_state, world, active: set[int], checked: set[int]) -> list[dict]:
    """Use the exact returned normal/glitched lists displayed by UT.

    Do not recompute location.can_reach here. This preserves UT's ignored and
    excluded-location filters and manual inventory, instead of approximating it.
    """
    normal=list(tracker_state.in_logic_locations)
    glitched=list(tracker_state.glitched_locations) if core.enable_glitched_logic else []
    aliases=getattr(core,'location_alias_map',{})
    rows=[];seen=set()
    for status,names in ((1,normal),(2,glitched)):
        for name in names:
            loc=world.get_location(name)
            i=loc.address
            if type(i) is not int or i not in active or i in checked:
                raise ValueError('UT returned a non-active network check: '+str(name))
            if i in seen:raise ValueError('UT returned duplicate network check: '+str(name))
            seen.add(i)
            label=str(loc.name)
            if i in aliases:label+=' ('+str(aliases[i])+')'
            rows.append({'id':i,'state':status,'name':label,
                         'region':str(loc.parent_region.name) if loc.parent_region else ''})
    rows.sort(key=lambda r:(r['state'],r['region'],r['name'],r['id']))
    return rows
