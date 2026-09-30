"""Check the APCpp model patch on clean, repeated and incompatible input."""
from pathlib import Path
import argparse, hashlib, json, subprocess
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--apcpp-source', type=Path, required=True)
p.add_argument('--cmake', required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args(); out = a.output.resolve(); out.mkdir(parents=True, exist_ok=True)
patch = Path(__file__).resolve().parent.parent / 'Cmake/SohExtremeAPCppModels.cmake'
header = (a.apcpp_source / 'Archipelago.h').read_text()
cpp = (a.apcpp_source / 'Archipelago.cpp').read_text()
header = header.replace('    // SOH-EXTREME: authoritative recipient game, copied with the scout.\n    std::string itemGame;\n', '')
cpp = cpp.replace('                item.itemGame = player.game;\n', '')
assert 'itemGame' not in header and 'item.itemGame' not in cpp
target = out / 'clean'; target.mkdir(exist_ok=True)
def write(h, c):
    (target/'Archipelago.h').write_text(h)
    (target/'Archipelago.cpp').write_text(c)
def read(): return [(target/n).read_bytes() for n in ('Archipelago.h','Archipelago.cpp')]
def run(): return subprocess.run([a.cmake, '-Dapcpp_SOURCE_DIR='+str(target), '-P', str(patch)], capture_output=True, text=True)
write(header, cpp)
first = run(); assert first.returncode == 0, first.stderr
fixed = read(); assert b'std::string itemGame;' in fixed[0] and b'item.itemGame = player.game;' in fixed[1]
second = run(); assert second.returncode == 0 and read() == fixed, second.stderr
# A bad source anchor must not partially update the header.
write(header, cpp.replace('item.itemName = getItemName(player.game, item.item);', 'CHANGED_ANCHOR;'))
before = read(); bad_cpp = run(); assert bad_cpp.returncode != 0 and read() == before
write(header.replace('    std::string playerName;', '    std::string CHANGED_ANCHOR;'), cpp)
before = read(); bad_header = run(); assert bad_header.returncode != 0 and read() == before
report = dict(passed=True, cases=['clean pinned source','idempotent repeat','incompatible cpp leaves both files intact','incompatible header leaves both files intact'],
              patched_sha256=[hashlib.sha256(x).hexdigest() for x in fixed])
(out/'patch.json').write_text(json.dumps(report, indent=2)); print(json.dumps(report, indent=2))
