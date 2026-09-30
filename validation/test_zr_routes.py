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

for soul_mode, abilities in [('individual_animals', True), ('all_animals_as_1', True), ('off', True), ('off', False)]:
    m = setup(290935, overrides={
        'closed_forest':'off', 'starting_age':'child', 'door_of_time':'song_only',
        'shuffle_swim':abilities, 'shuffle_grab':abilities, 'shuffle_climb':abilities,
        'shuffle_animal_soul':soul_mode, 'shuffle_rock_boulder_soul':True,
        'shuffle_rocks':True, 'shuffle_boulders':'all', 'shuffle_wonder_items':'all',
        'shuffle_fountain_fairies':True, 'shuffle_open_chest':'on',
        'shuffle_fish':'all', 'shuffle_beehives':True, 'shuffle_grass':'all',
        'lock_overworld_doors':False, 'shuffle_speak':'off', 'shuffle_npc_soul':False,
        'shuffle_flow_of_time':False, 'shuffle_ocarina_buttons':False,
        'song_note_shuffle':'off', 'enable_all_tricks':False, 'tricks_in_logic':[],
    }, stop_before='pre_fill')
    w = m.worlds[1]
    active = {l.address for l in w.get_locations() if type(l.address) is int}
    core = NS(game=w.game, tracker_disabled=False, player_id=1, multiworld=m, slot=1,
        manual_items=[], ignored_locations=set(), enable_glitched_logic=False, location_alias_map={},
        enforce_deferred_connections='disabled', hide_excluded=False, missing_locations=active,
        hints={}, logger=logging.getLogger('ZR test'), get_readable_locations=lambda: {})
    for method in ('clear_page','add_log_line','sort_log_lines','log_all_to_tab'):
        setattr(core, method, lambda *args: None)

    def evaluate(names):
        core.tracker_items_received = [NS(item=w.item_name_to_id[n], flags=0, location=-1, player=1) for n in names]
        return scope['updateTracker'](core)

    wonders = [w.get_location(f'EXTREME Zr Wonder Near Cucco {i}') for i in range(1,4)]
    upper = [w.get_location('EXTREME Zr Upper Circle Boulder')] + [
        w.get_location(f'EXTREME Zr Upper Circle Rock {i}') for i in range(1,9)]
    grotto_regions = [w.get_region(str(r)) for r in (Regions.ZR_OPEN_GROTTO, Regions.ZR_FAIRY_GROTTO)]
    grotto_checks = [l for region in grotto_regions for l in region.locations if type(l.address) is int]
    fairy_checks = [w.get_location(f'ZR Fairy Grotto Fairy {i}') for i in range(1,9)]
    chest = w.get_location('ZR Open Grotto Chest')
    for loc, address in zip(upper + wonders, list(range(9700685,9700694)) + list(range(9700715,9700718))):
        ck(f'{soul_mode}/{abilities} stable ID {loc.name}', loc.address, address)
    for mask in range(32):
        swim, grab, cucco, climb, adult = [bool(mask & (1 << i)) for i in range(5)]
        names = ['Progressive Bomb Bag','Rock / Boulder Soul','Shovel']
        if swim: names += ['Progressive Scale']  # first shuffled scale unlocks Swim
        if grab: names += ['Strength Upgrade']  # first shuffled strength unlocks Grab
        if cucco and soul_mode != 'off': names += ['Cucco Soul' if soul_mode == 'individual_animals' else 'Animal Soul']
        if climb: names += ['Climb']
        if adult: names += ['Progressive Ocarina','Song of Time']
        # Adult equipment by itself must never pretend that time travel is open.
        names += ['Master Sword','Hover Boots','Megaton Hammer']
        result = evaluate(names)
        label = f'{soul_mode}/{abilities}/inventory={mask}'
        ck(label+' river accessible', w.get_region('Zora River').can_reach(result.state), True)
        ck(label+' actual adult route', result.state._soh_extreme_can_reach_as_age(Regions.ZORA_RIVER, Ages.ADULT, 1), adult)
        can_swim = swim or not abilities
        can_grab = grab or not abilities
        can_climb = climb or not abilities
        has_cucco = cucco or soul_mode == 'off'
        for loc in wonders + upper:
            expected = can_swim if loc in wonders else can_climb and (adult or can_grab and has_cucco)
            ck(label+' AP '+loc.name, loc.can_reach(result.state), expected)
            ck(label+' UT '+loc.name, loc.name in result.in_logic_locations, expected)
        ledge = can_climb and (adult or can_grab and has_cucco)
        for region in grotto_regions:
            ck(label+' physical entrance '+region.name, region.can_reach(result.state), ledge)
        for loc in fairy_checks:
            ck(label+' AP '+loc.name, loc.can_reach(result.state), ledge)
            ck(label+' UT '+loc.name, loc.name in result.in_logic_locations, ledge)
        ck(label+' chest still needs Open Chest', chest.can_reach(result.state), False)
        opened = evaluate(names + ['Open Chest'])
        ck(label+' chest with Open Chest', chest.name in opened.in_logic_locations, ledge)
        if not ledge:
            for loc in grotto_checks:
                ck(label+' all contents inherit entrance '+loc.name, loc.can_reach(opened.state), False)
    # Rock Soul remains required even after the physical ledge is accessible.
    result = evaluate(['Progressive Bomb Bag','Progressive Ocarina','Song of Time','Climb','Shovel'])
    for loc in upper: ck(f'{soul_mode}/{abilities} missing rock soul {loc.name}', loc.can_reach(result.state), False)
    ck(f'{soul_mode}/{abilities} open grotto does not need Rock Soul', grotto_regions[0].can_reach(result.state), True)
    ck(f'{soul_mode}/{abilities} fairy entrance needs Rock Soul', grotto_regions[1].can_reach(result.state), False)
    # Preserve native Grab as a way to clear the fairy grotto cover without
    # bombs; it still needs the physical ledge and Rock/Boulder Soul.
    result = evaluate(['Progressive Ocarina','Song of Time','Climb','Strength Upgrade','Rock / Boulder Soul','Shovel'])
    ck(f'{soul_mode}/{abilities} Grab clears fairy entrance without explosives', grotto_regions[1].can_reach(result.state), True)

passed = all(t['passed'] for t in tests)
a.report.parent.mkdir(parents=True, exist_ok=True)
a.report.write_text(json.dumps(dict(passed=passed, checks=len(tests), tests=tests,
    ut_source_sha256=hashlib.sha256(a.ut_core.read_bytes()).hexdigest()), indent=2), encoding='utf-8')
print(f'{"PASS" if passed else "FAIL"} {len(tests)} Zora River assertions')
for row in [t for t in tests if not t['passed']][:12]: print(row)
raise SystemExit(0 if passed else 1)
