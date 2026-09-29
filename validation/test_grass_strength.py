"""Grass lifting versus basic Grab, through AP rules and the installed UT evaluator.

Uses real AP collection, including the shuffled first-Strength virtual Grab tier.
UT display/network services are controlled; this is not a live game playthrough.
"""
from run_case import setup, BOOTSTRAP
from BaseClasses import CollectionState, ItemClassification, LocationProgressType
from worlds.soh_extreme._vendor_oot_soh.Enums import Items, Regions, Ages
from worlds.soh_extreme._vendor_oot_soh.LogicHelpers import can_collect_grass, can_break_rocks
from pathlib import Path
from types import SimpleNamespace as NS
import argparse, ast, collections, hashlib, json, logging

p = argparse.ArgumentParser(parents=[BOOTSTRAP])
p.add_argument('--report', type=Path, required=True)
p.add_argument('--ut-core', type=Path, required=True)
a = p.parse_args()
tests = []

def ck(name, actual, expected):
    row = dict(test=name, actual=actual, expected=expected, passed=actual == expected)
    tests.append(row)
    if not row['passed']: print('FAIL', row, flush=True)

tree = ast.parse(a.ut_core.read_text(encoding='utf-8'))
cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'TrackerCore')
update = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'updateTracker')
scope = dict(CollectionState=CollectionState, Counter=collections.Counter,
    LocationProgressType=LocationProgressType, ItemClassification=ItemClassification,
    DeferredEntranceMode=NS(disabled='disabled'),
    CurrentTrackerState=collections.namedtuple('TrackerState',
        'all_items prog_items glitched_locations events event_locations in_logic_locations regions unconnected readable hinted state glitches_state'),
    TrackerLogLine=lambda *args: args,
    TrackerLogLineGroup=NS(**{n:n for n in ('UT_ERROR','DEFAULT','HINTED','EXCLUDED','EXCLUDED_GLITCHED','HINTED_GLITCHED','GLITCHED','UNCONNECTED','UT_STATUS')}))
exec(compile(ast.Module(body=[update], type_ignores=[]), str(a.ut_core), 'exec'), scope)

for shuffled in (False, True):
    m = setup(290930, overrides={'shuffle_grab': shuffled, 'shuffle_grass_bush_soul': True,
                                'shuffle_grass': 'all', 'shuffle_rocks': True}, stop_before='pre_fill')
    w = m.worlds[1]
    bundle = (Regions.KOKIRI_FOREST, w)
    for age in (Ages.CHILD, Ages.ADULT):
        for soul in (False, True):
            for copies in range(5):
                s = CollectionState(m)
                for item in m.precollected_items[1]: s.remove(item)
                if soul: s.collect(w.create_item('Grass / Bush Soul'), True)
                for _ in range(copies): s.collect(w.create_item('Strength Upgrade'), True)
                s._soh_age[1] = age
                ck(f'helper grab={shuffled} age={age} soul={soul} strength={copies}',
                   can_collect_grass(bundle).resolve(w)(s), soul and copies >= (2 if shuffled else 1))
                ck(f'rocks keep basic Grab gate {shuffled}/{age}/{soul}/{copies}',
                   can_break_rocks(bundle).resolve(w)(s), not shuffled or copies >= 1)
    # Real location rules and UT receipts, with all unrelated route capabilities.
    # Leave sticks available: sticks alone are not a valid grass-cutting method.
    excluded = {n for n in w.item_name_to_id if any(t in n.lower() for t in
        ('sword', 'knife', 'hammer', 'boomerang', 'bomb', 'hookshot', 'slingshot', 'bow', 'arrow', "din's"))}
    excluded |= {'Strength Upgrade', 'Grab / Power Bracelet', 'Grass / Bush Soul'}
    base_items = [n for n in w.item_name_to_id if n not in excluded
                  for _ in range(100 if n == 'Gold Skulltula Token' else 10)]
    active = {l.address for l in w.get_locations() if type(l.address) is int}
    core = NS(game=w.game, tracker_disabled=False, player_id=1, multiworld=m, slot=1,
        manual_items=[], ignored_locations=set(), enable_glitched_logic=False, location_alias_map={},
        enforce_deferred_connections='disabled', hide_excluded=False, missing_locations=active,
        hints={}, logger=logging.getLogger('Grass test'), get_readable_locations=lambda: {})
    for method in ('clear_page','add_log_line','sort_log_lines','log_all_to_tab'):
        setattr(core, method, lambda *args: None)
    scenarios = [(f'strength-{i}', ['Strength Upgrade']*i, i >= (2 if shuffled else 1)) for i in range(5)]
    scenarios += [('sword-without-grab', ['Kokiri Sword'], True),
                  ('boomerang-without-grab', ['Boomerang'], True),
                  ('bombs-without-grab', ['Progressive Bomb Bag'], True)]
    for label, added, expected in scenarios:
        for soul in (False, True):
            names = base_items + added + (['Grass / Bush Soul'] if soul else [])
            core.tracker_items_received = [NS(item=w.item_name_to_id[n], flags=0, location=-1, player=1) for n in names]
            result = scope['updateTracker'](core)
            for i in range(1, 13):
                name = f'KF Child Grass {i}'
                ck(f'UT grab={shuffled} soul={soul} {label}: {name}', name in result.in_logic_locations, soul and expected)
                ck(f'AP grab={shuffled} soul={soul} {label}: {name}', w.get_location(name).can_reach(result.state), soul and expected)
    # A removed real Strength tier must not leave cached grass access behind.
    s = CollectionState(m)
    for name in ['Grass / Bush Soul'] + ['Strength Upgrade']*(2 if shuffled else 1):
        s.collect(w.create_item(name), True)
    s._soh_age[1] = Ages.CHILD
    rule = can_collect_grass(bundle).resolve(w)
    ck(f'grass before strength removal {shuffled}', rule(s), True)
    s.remove(w.create_item('Strength Upgrade'))
    ck(f'grass after strength removal {shuffled}', rule(s), False)

a.report.parent.mkdir(parents=True, exist_ok=True)
passed = all(t['passed'] for t in tests)
a.report.write_text(json.dumps(dict(passed=passed, checks=len(tests), tests=tests,
    ut_source_sha256=hashlib.sha256(a.ut_core.read_bytes()).hexdigest()), indent=2), encoding='utf-8')
print(f'{"PASS" if passed else "FAIL"} {len(tests)} grass strength checks')
raise SystemExit(0 if passed else 1)
