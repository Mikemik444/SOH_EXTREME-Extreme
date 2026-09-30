"""Zora River physical routes through real AP collection and installed UT logic.

The matrix uses network receipts, including actual progressive ability tiers.
It does not force region reachability or inject the Time Travel event.
"""
from run_case import setup, BOOTSTRAP
from BaseClasses import CollectionState, ItemClassification, LocationProgressType
from worlds.soh_extreme._vendor_oot_soh.Enums import Regions, Ages
from pathlib import Path
from types import SimpleNamespace as NS
import argparse, ast, collections, hashlib, json, logging

p = argparse.ArgumentParser(parents=[BOOTSTRAP])
p.add_argument('--ut-core', type=Path, required=True)
p.add_argument('--report', type=Path, required=True)
a = p.parse_args(); tests = []

def ck(name, actual, expected):
    tests.append(dict(test=name, actual=actual, expected=expected, passed=actual == expected))

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


for age, shuffled_crawl, wonder_mode in [('child', True, 'all'), ('child', False, 'all'),
                                       ('adult', True, 'all'), ('child', True, 'off')]:
    m = setup(300936, overrides={
        'closed_forest':'off' if age == 'adult' else 'on', 'starting_age':age,
        'door_of_time':'closed', 'start_with_links_pocket':'nothing',
        'skip_child_zelda':False, 'shuffle_crawl':shuffled_crawl,
        'shuffle_grab':True, 'shuffle_climb':True, 'shuffle_swim':True,
        'shuffle_grass_bush_soul':True, 'shuffle_grass':'all',
        'shuffle_wonder_items':wonder_mode, 'shuffle_npc_soul':True,
        'shuffle_speak':'individual_languages', 'shuffle_enemy_soul':'individual_enemies',
        'shuffle_open_chest':'progressive', 'shuffle_deku_stick_bag':True,
        'start_with_kokiri_sword':False, 'start_with_master_sword':False,
        'enable_all_tricks':False, 'tricks_in_logic':[],
    }, stop_before='pre_fill')
    w=m.worlds[1]
    active={l.address for l in w.get_locations() if type(l.address) is int}
    core=NS(game=w.game, tracker_disabled=False, player_id=1, multiworld=m, slot=1,
        manual_items=[], ignored_locations=set(), enable_glitched_logic=False, location_alias_map={},
        enforce_deferred_connections='disabled', hide_excluded=False, missing_locations=active,
        hints={}, logger=logging.getLogger('Wonder test'), get_readable_locations=lambda: {})
    for method in ('clear_page','add_log_line','sort_log_lines','log_all_to_tab'):
        setattr(core,method,lambda *args:None)
    wonder_names=[f'EXTREME Kf Wonder Crawl Grass {i}' for i in (1,2)]+[
        f'EXTREME Lw Wonder Back Skull Kids Grass {i}' for i in (1,2)]+[
        'EXTREME Lw Wonder Front Skull Kids Grass']
    present={l.name for l in w.get_locations() if type(l.address) is int}
    ck(f'{age}/{wonder_mode} includes exactly enabled wonders',
       all(n in present for n in wonder_names), wonder_mode != 'off')
    if wonder_mode == 'off':continue
    for crawl in (False,True):
      for sword in (False,True):
       for soul in (False,True):
        names=['Climb']+(['Crawl'] if crawl else [])+(['Kokiri Sword'] if sword else [])+(['Grass / Bush Soul'] if soul else [])
        core.tracker_items_received=[NS(item=w.item_name_to_id[n],flags=0,location=-1,player=1) for n in names]
        result=scope['updateTracker'](core)
        state=CollectionState(m)
        for name in names:state.collect(w.create_item(name),True)
        state.sweep_for_advancements([l for l in w.get_locations() if l.address is None and l.item])
        label=f'{age}/shuffleCrawl={shuffled_crawl}/Crawl={crawl}/sword={sword}/grassSoul={soul}'
        for name in wonder_names:
            expected=age=='child' and (name.startswith('EXTREME Lw') or crawl or not shuffled_crawl)
            ck(label+'/AP/'+name, w.get_location(name).can_reach(state),expected)
            ck(label+'/UT/'+name, name in result.in_logic_locations,expected)
        # Actual En_Kusa checks still require a cutting/lifting method and soul.
        regular='KF Child Grass Maze 1'
        expected=age=='child' and (crawl or not shuffled_crawl) and sword and soul
        ck(label+'/AP/real grass',w.get_location(regular).can_reach(state),expected)
        ck(label+'/UT/real grass',regular in result.in_logic_locations,expected)
passed=all(t['passed'] for t in tests)
a.report.parent.mkdir(parents=True,exist_ok=True)
a.report.write_text(json.dumps(dict(passed=passed,assertions=len(tests),
    scope='Actual AP reachability and installed UT updateTracker with fresh inventory receipts; no forced region access',tests=tests),indent=2))
print('PASS' if passed else 'FAIL',len(tests),'checks',flush=True)
for t in tests:
    if not t['passed']:print(t)
raise SystemExit(0 if passed else 1)
