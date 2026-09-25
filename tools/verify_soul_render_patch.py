#!/usr/bin/env python3
"""Audit this rendering patch against the source checkout; no files are changed.

Run from any directory with Python 3.9+: python tools/verify_soul_render_patch.py
This is a source/mapping check, not a graphics or executable test.
"""
from __future__ import annotations

from pathlib import Path
import re
import sys
from collections import Counter


def read_required(path: Path) -> str:
    if not path.is_file():
        raise RuntimeError(f"Required source file is missing: {path}")
    return path.read_text(encoding="utf-8-sig")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    rando = root / "soh" / "Enhancements" / "randomizer"
    enum_text = read_required(rando / "randomizerEnums" / "RandomizerGet.h")
    header = read_required(rando / "EnemySoulIcons.h")
    renderer = read_required(rando / "EnemySoulDraw.cpp")
    items = read_required(rando / "item_list.cpp")

    enum_ids = set(re.findall(r"RANDO_ENUM_ITEM\(\s*(RG_[A-Z0-9_]+)", enum_text))
    expected = {item for item in enum_ids if "_SOUL" in item}
    entries = re.findall(
        r"^\s*\{\s*(RG_[A-Z0-9_]+)\s*,\s*(\w+)\s*,\s*(SOH_SOUL_\w+)\s*,",
        header, re.MULTILINE,
    )
    counts = Counter(entry[0] for entry in entries)
    mapped = set(counts)
    errors = []
    if not expected:
        errors.append("No soul IDs were found in the native enum; its format may have changed.")
    if expected - mapped:
        errors.append("Unmapped native souls: " + ", ".join(sorted(expected - mapped)))
    if mapped - expected:
        errors.append("Unexpected/removed soul IDs: " + ", ".join(sorted(mapped - expected)))
    duplicates = sorted(item for item, count in counts.items() if count > 1)
    if duplicates:
        errors.append("Duplicate mappings: " + ", ".join(duplicates))

    registration = re.compile(
        r"for\s*\(auto&\s+item\s*:\s*itemTable\)\s*\{\s*"
        r"const\s+char\*\s+icon\s*=\s*SohExtreme_GetEnemySoulIcon\(item\.GetRandomizerGet\(\)\);\s*"
        r"if\s*\(icon\s*!=\s*nullptr\)\s*\{\s*item\.CustomIcon\(icon\);\s*"
        r"item\.SetCustomDrawFunc\(Randomizer_DrawEnemySoul\);",
        re.MULTILINE,
    )
    if not registration.search(items):
        errors.append("Expected soul draw-function registration loop was not found in item_list.cpp.")

    # Ignore explanatory comments when checking for a live raw-pointer call.
    without_comments = re.sub(r"/\*.*?\*/|//[^\n]*", "", renderer, flags=re.DOTALL)
    if re.search(r"ResourceMgr_LoadTexOrDListByName\s*\(", without_comments):
        errors.append("A raw texture-pointer conversion is still present in the renderer.")
    for required in ("gGiBlueFireFlameDL", "gBossSoulSkullDL", "Randomizer_DrawBossSoul",
                     "Randomizer_DrawBeanSprout", "G_CYC_1CYCLE", "G_CC_MODULATEIA_PRIM"):
        if required not in without_comments:
            errors.append(f"Renderer is missing {required}.")

    if errors:
        for error in errors:
            print("FAIL:", error)
        return 1

    print(f"PASS: {len(mapped)}/{len(expected)} native soul IDs mapped, with no duplicates or extra IDs.")
    for kind, count in sorted(Counter(entry[2] for entry in entries).items()):
        print(f"  {kind}: {count}")
    print("PASS: native item-table registration and metadata-preserving render path present.")

    # Source assets may live at assets/ or soh/assets/ in this fork. Their absence
    # in a source-only checkout doesn't prove absence in an installed archive.
    roots = [root / "assets" / "custom", root / "soh" / "assets" / "custom"]
    tokens = re.findall(r'"__OTR__(textures/parameter_static/gExtremeSoul_[A-Z0-9_]+)"', header)
    if any(folder.is_dir() for folder in roots):
        missing = [token for token in tokens
                   if not any((folder / (token + ".rgba32.png")).is_file() for folder in roots)]
        if missing:
            print(f"WARNING: {len(missing)} portrait source PNGs were not found. Installed archives may still contain them.")
            print("The in-game renderer uses the native skull when an optional portrait is absent from loaded archives.")
        else:
            print(f"PASS: all {len(tokens)} existing portrait source PNGs found.")
    print("This audit does not compile or run SoH. Rebuild with your existing build.cmd.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, UnicodeError, RuntimeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
