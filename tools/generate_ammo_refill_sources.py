"""Export repeatable native Business Scrub stock; never AP assigned rewards."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'archipelago/soh_extreme/AmmoRefillSources.json'
INPUTS = ('soh/Enhancements/randomizer/location_list.cpp',
          'soh/Network/Archipelago/ArchipelagoLocationMap.inc',
          'src/overlays/actors/ovl_En_Dns/z_en_dns.c')


def document():
    source = (ROOT / INPUTS[0]).read_text()
    mapping = {name: int(address) for name, address in re.findall(
        r'\{\s*static_cast<int>\((RC_\w+)\),\s*(\d+)LL\s*\}', (ROOT / INPUTS[1]).read_text())}
    # EnDns_Init converts its arrow seller to seeds for Child. Its ordinary
    # purchases use these prices, not a randomized first-check price.
    stock = {'RG_BUY_DEKU_STICK_1': (1, 15), 'RG_BUY_DEKU_NUTS_5': (2, 20),
             'RG_BUY_BOMBS_535': (4, 40), 'RG_BUY_ARROWS_30': (16, 70)}
    rows = []
    for line in source.splitlines():
        if 'Location::Base(' not in line or 'RCTYPE_SCRUB' not in line:
            continue
        rc = re.search(r'locationTable\[(RC_\w+)\]', line).group(1)
        item = re.search(r'\b(RG_\w+)\b', line).group(1)
        if rc not in mapping or item not in stock:
            continue
        mask, price = stock[item]
        rows.append({'location_key': rc[3:], 'address': mapping[rc],
                     'native_check': rc, 'stock': item, 'ammo': mask, 'price': price})
    assert rows and len({row['address'] for row in rows}) == len(rows)
    return {'revision': 1, 'source_sha256': {name: sha256((ROOT / name).read_bytes()).hexdigest()
                                          for name in INPUTS},
            'scrubs': sorted(rows, key=lambda row: row['address'])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    expected = json.dumps(document(), indent=2) + '\n'
    if args.check:
        if OUTPUT.read_text() != expected:
            raise SystemExit('Ammo refill source catalog is stale')
    else:
        OUTPUT.write_text(expected)
    print(f"Verified {len(document()['scrubs'])} native repeatable scrub stocks")


if __name__ == '__main__':
    main()
