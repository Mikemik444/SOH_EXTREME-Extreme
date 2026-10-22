"""Refresh only Water Temple's exact AP graph from the native region macros.

This is a deliberately scoped source extractor, not a general C++ exporter.
It rejects missing/added region or location identities and leaves every other
dungeon's data unchanged. --check verifies the checked-in exports without
writing them. Runtime behavior is checked separately by the actual AP tests.
"""
from __future__ import annotations

import argparse
import ast
from collections import defaultdict
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import re


SOURCE = Path(__file__).resolve().parents[1]
AP = SOURCE / 'archipelago/soh_extreme'
NATIVE_PATH = 'soh/Enhancements/randomizer/location_access/dungeons/water_temple.cpp'
NATIVE = SOURCE / NATIVE_PATH
STRING_OR_COMMENT = re.compile(r'"(?:\\.|[^"\\])*"|//[^\n]*|/\*.*?\*/', re.S)


def without_comments(text):
    return STRING_OR_COMMENT.sub(
        lambda match: match[0] if match[0].startswith('"') else
        ''.join('\n' if char == '\n' else ' ' for char in match[0]), text)


def compact(text):
    return ''.join(without_comments(text).split())


def closing_paren(text, opening):
    assert text[opening] == '('
    depth = 0
    quoted = escaped = False
    for index in range(opening, len(text)):
        char = text[index]
        if quoted:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char == '"':
            quoted = True
        elif char == '(':
            depth += 1
        elif char == ')':
            depth -= 1
            if depth == 0:
                return index
    raise ValueError('Unclosed native macro')


def native_regions():
    """Return exact regions, physical exits, local events and check actions."""
    text = without_comments(NATIVE.read_text())
    regions = {}
    locations = []
    pattern = re.compile(r'areaTable\[(RR_WATER_TEMPLE_\w+)\]\s*=\s*Region\(')
    macro = re.compile(r'\b(ENTRANCE|EVENT_ACCESS|LOCATION)\s*\(')
    for match in pattern.finditer(text):
        token = match[1]
        # This AP graph supports the normal dungeon layout. Its entry decider
        # keeps the explicit disabled MQ edge, but has no MQ room identities.
        if token.startswith('RR_WATER_TEMPLE_MQ_'):
            continue
        assert token not in regions, token
        end = closing_paren(text, match.end() - 1)
        name = re.match(r'\s*("(?:\\.|[^"\\])*")\s*,', text[match.end():end])
        assert name is not None, token
        row = {'name': json.loads(name[1]), 'exits': [], 'events': [],
               'file': NATIVE_PATH, 'line': text.count('\n', 0, match.start()) + 1}
        for entry in macro.finditer(text, match.end(), end):
            close = closing_paren(text, entry.end() - 1)
            assert close < end, token
            args = text[entry.end():close]
            first, condition = args.split(',', 1)
            first = first.strip()
            assert re.fullmatch(r'(?:RR|RC|LOGIC)_\w+', first), (token, first)
            condition = condition.strip()
            if entry[1] == 'LOCATION':
                locations.append({'rc': first, 'region': token, 'condition': condition})
                continue
            key, group = ('target', 'exits') if entry[1] == 'ENTRANCE' else ('event', 'events')
            row[group].append({key: first, 'region': token, 'condition': condition,
                               'file': NATIVE_PATH.replace('/', '\\'),
                               'line': text.count('\n', 0, entry.start()) + 1})
        regions[token] = row
    assert regions and locations
    return regions, locations


def expected_exports():
    parsed, locations = native_regions()
    graph_path = AP / 'EnemyRoomGraph.json'
    old_graph = json.loads(graph_path.read_text())
    scope = {key for key, row in old_graph.items() if row['file'] == NATIVE_PATH}
    assert scope == parsed.keys(), ('Water region identities changed', scope ^ parsed.keys())
    graph = deepcopy(old_graph)
    for token, row in parsed.items():
        # Keep the existing formatting of unchanged expressions. New source
        # line references and changed conditions still come from native code.
        for group, key in (('exits', 'target'), ('events', 'event')):
            old = {(item[key], compact(item['condition'])): item['condition']
                   for item in old_graph[token][group]}
            for item in row[group]:
                item['condition'] = old.get((item[key], compact(item['condition'])), item['condition'])
        graph[token] = row
    assert all(graph[key] == value for key, value in old_graph.items() if key not in scope)

    id_text = (SOURCE / 'soh/Network/Archipelago/ArchipelagoLocationMap.inc').read_text()
    ids = {token: int(address) for token, address in re.findall(
        r'static_cast<int>\((RC_\w+)\),\s*(\d+)LL', id_text)}
    extracted = defaultdict(list)
    for row in locations:
        if row['rc'] in ids:
            extracted[str(ids[row['rc']])].append({'region': row['region'], 'condition': row['condition']})
    route_path = AP / 'DungeonLocationRoutes.json'
    old_routes = json.loads(route_path.read_text())
    routes = deepcopy(old_routes)
    old_locations = {(key, row['region']) for key, values in old_routes.items()
                     for row in values if row['region'] in scope}
    new_locations = {(key, row['region']) for key, values in extracted.items() for row in values}
    assert old_locations == new_locations, ('Water location identities changed', old_locations ^ new_locations)
    for key, values in extracted.items():
        old = {(row['region'], compact(row['condition'])): row['condition'] for row in old_routes[key]}
        for row in values:
            row['condition'] = old.get((row['region'], compact(row['condition'])), row['condition'])
        other = [row for row in old_routes[key] if row['region'] not in scope]
        assert not other, ('Cross-dungeon location identity', key)
        routes[key] = values
    assert all(routes[key] == values for key, values in old_routes.items() if key not in extracted)

    # The old custom-only projections do not encode ordinary scale/boots or
    # water-state requirements. Exact expressions above supply those semantics;
    # update only the structural relation used by the legacy path projection.
    native_path = AP / 'NativeLogic.py'
    native_bytes = native_path.read_bytes()
    native_tree = ast.parse(native_bytes.decode())
    assignment = next(node for node in native_tree.body if isinstance(node, ast.Assign)
                      and isinstance(node.targets[0], ast.Name)
                      and node.targets[0].id == 'NATIVE_REGION_EDGES')
    old_edges = ast.literal_eval(assignment.value)
    edges = tuple(sorted(set(edge for edge in old_edges if edge[0] not in scope) |
                         {(token, row['target']) for token, region in parsed.items() for row in region['exits']}))
    marker = b'NATIVE_REGION_EDGES = (\r\n'
    start = native_bytes.index(marker)
    end = native_bytes.index(b'\r\n)', start) + len(b'\r\n)')
    replacement = 'NATIVE_REGION_EDGES = (\r\n' + ''.join('    ' + repr(row) + ',\r\n' for row in edges) + ')'
    native_export = native_bytes[:start] + replacement.encode() + native_bytes[end:]
    output = {
        graph_path: (json.dumps(graph, indent=2) + '\n').encode(),
        route_path: (json.dumps(routes, indent=2) + '\n').encode(),
        native_path: native_export,
    }
    facts = {'native_regions': len(parsed),
             'native_exits': sum(len(row['exits']) for row in parsed.values()),
             'native_events': sum(len(row['events']) for row in parsed.values()),
             'native_mapped_location_routes': len(new_locations),
             'unrelated_graph_regions_unchanged': len(old_graph) - len(scope),
             'structural_edges_added': [list(edge) for edge in edges if edge not in old_edges],
             'structural_edges_removed': [list(edge) for edge in old_edges if edge not in edges]}
    return output, facts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    exports, facts = expected_exports()
    changed = [str(path.relative_to(SOURCE)) for path, data in exports.items() if path.read_bytes() != data]
    if not args.check:
        for path, data in exports.items():
            if path.read_bytes() != data:
                path.write_bytes(data)
    report = {'status': 'mismatch' if args.check and changed else 'passed',
              'mode': 'check' if args.check else 'update', 'changed_exports': changed, **facts,
              'source_sha256': {str(path.relative_to(SOURCE)): sha256(path.read_bytes()).hexdigest()
                                for path in (NATIVE, Path(__file__).resolve(), *exports)}}
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    return int(args.check and bool(changed))


if __name__ == '__main__':
    raise SystemExit(main())
