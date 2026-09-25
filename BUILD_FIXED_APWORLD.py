from __future__ import annotations
from pathlib import Path
import zipfile, tempfile, shutil, re, sys

root = Path(__file__).resolve().parent
candidates = sorted(root.glob('soh_extreme_*.apworld'), key=lambda p: p.stat().st_mtime, reverse=True)
if not candidates:
    candidates = sorted((root / 'apworld').glob('*.apworld'), key=lambda p: p.stat().st_mtime, reverse=True) if (root/'apworld').exists() else []
if not candidates:
    print('ERROR: Put your current soh_extreme_*.apworld beside this script, then run it again.')
    sys.exit(1)
base = candidates[0]
out = root / 'soh_extreme_fixed.apworld'

with tempfile.TemporaryDirectory() as td:
    work = Path(td)
    with zipfile.ZipFile(base, 'r') as z:
        z.extractall(work)
    pkg = work / 'soh_extreme'
    options = pkg / 'Options.py'
    init = pkg / '__init__.py'
    if not options.exists() or not init.exists():
        raise SystemExit(f'ERROR: {base.name} is not a SOH-EXTREME apworld package.')

    s = options.read_text(encoding='utf-8')
    old = '''class ShuffleEnemySoul(Toggle):\n    display_name = "Shuffle Enemy Soul"'''
    new = '''class ShuffleEnemySoul(Choice):\n    \"\"\"Enemy Soul behavior while the soul is missing.\"\"\"\n    display_name = "Shuffle Enemy Soul"\n    option_off = 0\n    option_gone_until_found = 1\n    option_invincible_until_found = 2\n    default = 0'''
    if old in s:
        s = s.replace(old, new, 1)
    elif 'option_gone_until_found' not in s:
        raise SystemExit('ERROR: Could not patch ShuffleEnemySoul in Options.py; base apworld is unexpected.')
    options.write_text(s, encoding='utf-8')

    s = init.read_text(encoding='utf-8')
    anchor = '''            if o.shuffle_npc_soul.value and (tags & npc_tags):\n                require(location, 'NPC Soul')\n'''
    inject = anchor + '''\n            # Shovel gates every grotto in SOH-EXTREME, including vanilla-open holes.\n            if o.shuffle_shovel.value and (\n                'Grotto' in location.name or\n                location.name in ('Deku Theater Skull Mask', 'Deku Theater Mask of Truth', 'Theater Rectangle Sign')\n            ):\n                require(location, 'Shovel')\n\n            # Lost Woods underwater shortcut rupees are deep enough to require\n            # the second Progressive Scale upgrade (Golden Scale).\n            if location.name.startswith('Underwater Shortcut Rupee '):\n                require(location, 'Progressive Scale', 2)\n\n            # Infinite-day seeds cannot logically expose the Market night-balcony\n            # checks until Flow of Time has been received.\n            if o.shuffle_flow_of_time.value and location.name in (\n                'Wonder Night Balcony 1', 'Wonder Night Balcony 2'\n            ):\n                require(location, 'Flow of Time')\n'''
    if 'Lost Woods underwater shortcut rupees are deep enough' not in s:
        if anchor not in s:
            raise SystemExit('ERROR: Could not locate set_rules insertion point in __init__.py.')
        s = s.replace(anchor, inject, 1)

    # Deku Theater is physically a grotto in this fork; ensure all known spellings are covered.
    old_special = "'Graveyard Dampe Gravedigging Tour': [('Shovel', o.shuffle_shovel.value)],"
    if old_special in s and "'Theater Rectangle Sign': [('Shovel'" not in s:
        s = s.replace(old_special, old_special + "\n            'Theater Rectangle Sign': [('Shovel', o.shuffle_shovel.value)],")

    init.write_text(s, encoding='utf-8')

    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for path in work.rglob('*'):
            if path.is_file():
                z.write(path, path.relative_to(work).as_posix())

print(f'Built: {out.name}')
print(f'Base:  {base.name}')
