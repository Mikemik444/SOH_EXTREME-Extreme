"""Check every exported enemy-room entrance/event against the current C++ source."""
from pathlib import Path
import argparse
import json

from source_index import native_sources

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--report', type=Path, required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
_, native = native_sources(root)
graph = json.loads((root / 'archipelago/soh_extreme/EnemyRoomGraph.json').read_text())
differences = []
predicates = 0
for key, row in graph.items():
    for kind in ('exits', 'events'):
        fields = ('target', 'condition') if kind == 'exits' else ('event', 'condition')
        expected = [{f: e[f] for f in fields} for e in native[key][kind]]
        actual = [{f: e[f] for f in fields} for e in row[kind]]
        predicates += len(actual)
        if actual != expected:
            differences.append(dict(region=key, kind=kind, expected=expected, actual=actual))
report = dict(passed=not differences, regions=len(graph), predicates=predicates,
              differences=differences, scope=__doc__)
args.report.parent.mkdir(parents=True, exist_ok=True)
args.report.write_text(json.dumps(report, indent=2), encoding='utf-8')
print('Room graph:', len(graph), 'regions,', predicates, 'predicates,', len(differences), 'differences')
raise SystemExit(not report['passed'])
