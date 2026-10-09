"""Build a deterministic BPS conversion from two developer-supplied ROMs.

Players only supply the source ROM. Neither reference ROM belongs in a release.
BPS format: https://github.com/Alcaro/Flips/blob/master/bps_spec.md (public domain).
"""
from pathlib import Path
import argparse
import binascii
import hashlib
import json
import struct


def normalize(data):
    if data[:4] == bytes.fromhex('37804012'):
        b = bytearray(data)
        b[0::2], b[1::2] = data[1::2], data[0::2]
        return bytes(b)
    if data[:4] == bytes.fromhex('40123780'):
        b = bytearray(data)
        for i in range(4):
            b[i::4] = data[3-i::4]
        return bytes(b)
    if data[:4] != bytes.fromhex('80371240'):
        raise ValueError('Not a recognized N64 ROM byte order')
    return data


def number(value):
    out = bytearray()
    while True:
        byte = value & 127
        value >>= 7
        if not value:
            out.append(byte | 128)
            return out
        out.append(byte)
        value -= 1


def create_patch(source, target):
    # Aligned source anchors, scanning every target position, also find relocated
    # compressed files. Runs extend to their actual end, independently of alignment.
    width = 16
    lookup = {}
    for i in range(0, len(source) - width + 1, width):
        lookup.setdefault(source[i:i+width], i)
    out = bytearray(b'BPS1') + number(len(source)) + number(len(target)) + number(0)
    pos = literal = relative = 0
    while pos < len(target):
        at = lookup.get(target[pos:pos+width]) if pos + width <= len(target) else None
        if at is None:
            pos += 1
            continue
        end = width
        limit = min(len(source)-at, len(target)-pos)
        while end + 1024 <= limit and source[at+end:at+end+1024] == target[pos+end:pos+end+1024]:
            end += 1024
        while end < limit and source[at+end] == target[pos+end]:
            end += 1
        if pos > literal:
            out += number(((pos-literal-1) << 2) | 1)
            out += target[literal:pos]
        if at == pos:
            out += number((end-1) << 2)
        else:
            out += number(((end-1) << 2) | 2)
            delta = at-relative
            out += number((abs(delta) << 1) | (delta < 0))
            relative = at+end
        pos += end
        literal = pos
    if pos > literal:
        out += number(((pos-literal-1) << 2) | 1)
        out += target[literal:pos]
    out += struct.pack('<II', binascii.crc32(source), binascii.crc32(target))
    out += struct.pack('<I', binascii.crc32(out))
    return bytes(out)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--target', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    source, target = normalize(a.source.read_bytes()), normalize(a.target.read_bytes())
    # This conversion is deliberately tied to the reference pair validated here.
    assert hashlib.sha1(source).hexdigest() == 'f46239439f59a2a594ef83cf68ef65043b1bffe2'
    assert hashlib.sha1(target).hexdigest() == 'ad69c91157f6705e8ab06c79fe08aad47bb57ba7'
    patch = create_patch(source, target)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_bytes(patch)
    report = {'format': 'BPS1', 'source': 'PAL GameCube Master Quest', 'target': 'NTSC-US 1.0',
              'source_sha1': hashlib.sha1(source).hexdigest(), 'target_sha1': hashlib.sha1(target).hexdigest(),
              'patch_sha256': hashlib.sha256(patch).hexdigest(), 'patch_bytes': len(patch)}
    a.output.with_suffix('.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
