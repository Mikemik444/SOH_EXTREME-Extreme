"""Read-only replay of actual SOH + Jigsaw multidata, without remote pregrants.

Restores SOH's slot data and original placements. Jigsaw uses its saved merge
thresholds, verified against PuzzleBoard from the supplied Jigsaw APWorld.
Only initial inventory and checks reached in earlier spheres grant items.
This checks the installed rule graphs, not live actors/collision or server state.
"""
from run_case import setup, BOOTSTRAP
from BaseClasses import CollectionState
from Utils import restricted_loads
from pathlib import Path
from collections import Counter
import argparse, hashlib, json, zipfile, zlib

p = argparse.ArgumentParser(parents=[BOOTSTRAP])
p.add_argument('--multidata', type=Path, required=True)
p.add_argument('--jigsaw-apworld', type=Path, required=True)
p.add_argument('--slot', type=int, required=True)
p.add_argument('--report', type=Path, required=True)
a = p.parse_args()
raw = a.multidata.read_bytes()
assert raw[0] == 3
d = restricted_loads(zlib.decompress(raw[1:]))
assert d['slot_info'][a.slot].game == 'SOH-EXTREME'
other = set(d['locations']) - {a.slot}
assert all(d['slot_info'][i].game == 'Jigsaw' for i in other)
with zipfile.ZipFile(a.jigsaw_apworld) as z:
    rules, items, options = (z.read('jigsaw/' + name).decode() for name in
                             ('Rules.py', 'Items.py', 'Options.py'))
rule_ns, item_ns, option_ns = {}, {}, {}
exec(compile(rules, 'jigsaw/Rules.py', 'exec'), rule_ns)
exec(compile(items, 'jigsaw/Items.py', 'exec'), item_ns)
exec(compile(options, 'jigsaw/Options.py', 'exec'), option_ns)
jigsaw_items = {data.code: (name, data.classification) for name, data in item_ns['item_table'].items()}
for i in sorted(other):
    slot = d['slot_data'][i]
    assert slot['ap_world_version_2'] == '0.10.0'
    board = rule_ns['PuzzleBoard'](slot['nx'], slot['ny'],
        slot['grid_type'] == option_ns['GridType'].option_hexagonal)
    physical_merges = [0]
    for piece in slot['piece_order']:
        board.add_piece(piece - 1)
        physical_merges.append(board.merges_count)
    assert physical_merges == list(slot['actual_possible_merges']), i
    assert all(logic <= physical for logic, physical in zip(slot['possible_merges'], physical_merges))
    assert len(physical_merges) == slot['nx'] * slot['ny'] + 1

m = setup(290932, passthrough=d['slot_data'][a.slot], stop_before='pre_fill')
w = m.worlds[1]
locations = {l.address: l for l in w.get_locations() if type(l.address) is int}
assert set(locations) == set(d['locations'][a.slot])
by_id = {v: k for k, v in w.item_name_to_id.items()}
# Native starting abilities/equipment are represented as code-less events.
# Network-coded inventory comes only from this exact multidata, once.
m.precollected_items[1][:] = [it for it in m.precollected_items[1] if it.code is None]
s = CollectionState(m)
piece_counts = Counter()

def receive(item_id, player):
    if player == a.slot:
        s.collect(w.create_item(by_id[item_id]), True)
    else:
        name, classification = jigsaw_items[item_id]
        if classification & 1 and 'Piece' in name:
            piece_counts[player] += int(name.split()[0])

for player, ids in d['precollected_items'].items():
    for item_id in ids:
        receive(item_id, player)
remaining = {(player, i) for player, checks in d['locations'].items() for i in checks}
waves, first_goal = [], {}
events = [l for l in w.get_locations() if l.address is None]
while True:
    s.sweep_for_advancements(events)
    reachable = []
    for player, i in sorted(remaining):
        if player == a.slot:
            can_reach = locations[i].can_reach(s)
        else:
            thresholds = d['slot_data'][player]['possible_merges']
            can_reach = thresholds[min(piece_counts[player], len(thresholds)-1)] >= i - 234782000
        if can_reach:
            reachable.append((player, i))
    goals = {a.slot: m.has_beaten_game(s)}
    for player in other:
        slot = d['slot_data'][player]
        goals[player] = piece_counts[player] >= slot['nx'] * slot['ny']
    for player, goal in goals.items():
        if goal:
            first_goal.setdefault(player, len(waves))
    if not reachable:
        break
    wave = dict(index=len(waves), counts=dict(Counter(p for p, _ in reachable)), checks=[])
    for player, i in reachable:
        item_id, recipient, *_ = d['locations'][player][i]
        item_name = by_id[item_id] if recipient == a.slot else jigsaw_items[item_id][0]
        wave['checks'].append(dict(player=player, id=i,
            location=locations[i].name if player == a.slot else f'Merge {i-234782000} times',
            recipient=recipient, item=item_name))
        receive(item_id, recipient)
    remaining.difference_update(reachable)
    waves.append(wave)
result = dict(passed=not remaining and all(goals.values()), seed=d['seed_name'],
    scope=__doc__, soh_version=d['slot_data'][a.slot]['apworld_version'],
    multidata_sha256=hashlib.sha256(raw).hexdigest(),
    jigsaw_apworld_sha256=hashlib.sha256(a.jigsaw_apworld.read_bytes()).hexdigest(),
    optimistic_remote_pregrants=0, extra_recovery_items=0,
    total_checks=sum(len(v) for v in d['locations'].values()),
    soh_checks=len(locations), remaining=sorted(remaining),
    goals=goals, goal_spheres=first_goal, sphere_count=len(waves), waves=waves)
a.report.write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps({k: v for k, v in result.items() if k != 'waves'}, indent=2))
raise SystemExit(not result['passed'])
