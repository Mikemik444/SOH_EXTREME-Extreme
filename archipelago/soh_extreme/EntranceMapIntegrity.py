"""Deterministic source/destination checksum for SOH-EXTREME slot entrance maps.

The native client recomputes the same FNV-1a-32 value from its parsed route
map. The upper bit is dropped because AP's native settings transport signed
32-bit integers. This detects silent partial/stale slot data; it does not by
itself establish physical playability or progression logic correctness.
"""
from __future__ import annotations

FNV_OFFSET = 2166136261
FNV_PRIME = 16777619


def fingerprint(mapping: dict[int, int]) -> int:
    value = FNV_OFFSET
    for source, destination in sorted(mapping.items()):
        if type(source) is not int or type(destination) is not int or not (0 <= source < 2**32 and 0 <= destination < 2**32):
            raise ValueError('Invalid entrance source/destination ID')
        for integer in (source, destination):
            for shift in (0, 8, 16, 24):
                value = ((value ^ ((integer >> shift) & 255)) * FNV_PRIME) & 0xFFFFFFFF
    return value & 0x7FFFFFFF


def validate_complete(mapping: dict[int, int], expected_sources: set[int]) -> None:
    if set(mapping) != expected_sources:
        missing = sorted(expected_sources - set(mapping))
        extra = sorted(set(mapping) - expected_sources)
        raise ValueError(f'Incomplete entrance map: {len(missing)} missing source(s), {len(extra)} extra source(s); '
                         f'missing examples: {missing[:12]}, extras: {extra[:12]}')
