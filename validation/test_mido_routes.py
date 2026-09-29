"""Mido's path: real AP rules and installed UT receipt evaluation.

The controlled states model child Link before Mido has moved. Native region
catalogue parity and combat are checked separately by test_mido_native.py.
"""
from run_case import setup, BOOTSTRAP
from BaseClasses import CollectionState, ItemClassification, LocationProgressType
from pathlib import Path
from types import SimpleNamespace as NS
import argparse, ast, collections, hashlib, json, logging

p=argparse.ArgumentParser(parents=[BOOTSTRAP])
p.add_argument('--ut-core',type=Path,required=True)
p.add_argument('--report',type=Path,required=True)
a=p.parse_args(); tests=[]
def ck(name,actual,expected):
    row=dict(test=name,actual=actual,expected=expected,passed=actual==expected)
    tests.append(row)
    if not row['passed']: print('FAIL',row,flush=True)

tree=ast.parse(a.ut_core.read_text(encoding='utf-8'))
cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='TrackerCore')
update=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='updateTracker')
scope=dict(CollectionState=CollectionState,Counter=collections.Counter,
    LocationProgressType=LocationProgressType,ItemClassification=ItemClassification,
    DeferredEntranceMode=NS(disabled='disabled'),
    CurrentTrackerState=collections.namedtuple('TrackerState',
        'all_items prog_items glitched_locations events event_locations in_logic_locations regions unconnected readable hinted state glitches_state'),
    TrackerLogLine=lambda *args: args,
    TrackerLogLineGroup=NS(**{n:n for n in ('UT_ERROR','DEFAULT','HINTED','EXCLUDED','EXCLUDED_GLITCHED','HINTED_GLITCHED','GLITCHED','UNCONNECTED','UT_STATUS')}))
exec(compile(ast.Module(body=[update],type_ignores=[]),str(a.ut_core),'exec'),scope)

for forest in ('on','deku_only','off'):
    m=setup(290931,overrides={'closed_forest':forest,'shuffle_speak':'individual_languages',
        'shuffle_npc_soul':True,'shuffle_enemy_soul':'individual_enemies','shuffle_enemy_drops':True},stop_before='pre_fill')
    w=m.worlds[1]
    active={l.address for l in w.get_locations() if type(l.address) is int}
    core=NS(game=w.game,tracker_disabled=False,player_id=1,multiworld=m,slot=1,
        manual_items=[],ignored_locations=set(),enable_glitched_logic=False,location_alias_map={},
        enforce_deferred_connections='disabled',hide_excluded=False,missing_locations=active,
        hints={},logger=logging.getLogger('Mido test'),get_readable_locations=lambda: {})
    for method in ('clear_page','add_log_line','sort_log_lines','log_all_to_tab'):
        setattr(core,method,lambda *args:None)
    locations=[w.get_location(f'Enemy Defeat: Kokiri Forest Room 1 Withered Deku Baba {i}') for i in range(1,6)]
    for i,l in enumerate(locations):
        ck(f'{forest} stable ID {i}',l.address,9800531+i)
        ck(f'{forest} physical region {i}',l.parent_region.name,'KF Outside Deku Tree')
    for mask in range(32):
        names=[name for i,name in enumerate(('Kokiri Sword','Deku Shield','NPC Soul','Speak Kokiri','Deku Baba Soul')) if mask&(1<<i)]
        w._extreme_live_shields=1 if mask&2 else 0
        core.tracker_items_received=[NS(item=w.item_name_to_id[n],flags=0,location=-1,player=1) for n in names]
        result=scope['updateTracker'](core)
        expected=(mask&17)==17 and (forest=='off' or mask==31)
        for l in locations:
            ck(f'UT {forest} inventory={mask} {l.name}',l.name in result.in_logic_locations,expected)
            ck(f'AP {forest} inventory={mask} {l.name}',l.can_reach(result.state),expected)
        ck(f'main forest stays reachable {forest}/{mask}',w.get_region('Kokiri Forest').can_reach(result.state),True)
    # Boomerang kills Babas but does not substitute for showing Mido the sword.
    for extra,expected in [(['Boomerang','Deku Shield','NPC Soul','Speak Kokiri'],forest=='off'),
                           (['Kokiri Sword','Deku Shield','NPC Soul','Speak Hylian'],forest=='off')]:
        w._extreme_live_shields=1
        core.tracker_items_received=[NS(item=w.item_name_to_id[n],flags=0,location=-1,player=1) for n in extra+['Deku Baba Soul']]
        result=scope['updateTracker'](core)
        for l in locations:ck(f'{forest} alternate {extra} {l.name}',l.name in result.in_logic_locations,expected)

passed=all(t['passed'] for t in tests)
a.report.parent.mkdir(parents=True,exist_ok=True)
a.report.write_text(json.dumps(dict(passed=passed,checks=len(tests),tests=tests,
    ut_source_sha256=hashlib.sha256(a.ut_core.read_bytes()).hexdigest()),indent=2),encoding='utf-8')
print(f'{"PASS" if passed else "FAIL"} {len(tests)} Mido route checks')
raise SystemExit(0 if passed else 1)
