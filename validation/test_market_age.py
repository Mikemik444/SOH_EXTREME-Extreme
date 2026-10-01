"""Market Ruins require actual adult access in AP and the real UT mirror."""
from run_case import setup, BOOTSTRAP
from ut_harness import tracker
from pathlib import Path
from NetUtils import convert_to_base_types
from worlds.soh_extreme._vendor_oot_soh.Enums import Events
import argparse, json
p = argparse.ArgumentParser(parents=[BOOTSTRAP])
p.add_argument('--ut-core', type=Path, required=True)
p.add_argument('--report', type=Path, required=True)
a = p.parse_args(); tests = []
def ck(label, actual, expected):
    tests.append(dict(test=label, actual=bool(actual), expected=expected, passed=bool(actual)==expected))
    if bool(actual)!=expected: print('FAIL', label, flush=True)
options = dict(closed_forest='off', door_of_time='song_only', starting_age='child',
    shuffle_enemy_drops=True, shuffle_enemy_soul='individual_enemies',
    song_note_shuffle='off', shuffle_ocarina_buttons=False, start_with_ocarina='off',
    start_with_song_of_time=False, start_inventory={}, start_inventory_from_pool={},
    tricks_in_logic=[], enable_all_tricks=False, shuffle_master_sword=True, start_with_master_sword=False)
def run(w, tag, adult=False):
    ev = tracker(w, a.ut_core)
    names = [i.name for i in w.multiworld.itempool if i.player==w.player]+[
        l.item.name for l in w.get_locations() if l.address is not None and l.item and l.item.name in w.item_name_to_id]
    names = [n for n in names if n not in {'Progressive Ocarina', 'Song of Time', 'Redead and Gibdo Soul'}]
    for unlock in (False, True):
        for soul in (False, True):
            result = ev(names+(['Progressive Ocarina', 'Song of Time'] if unlock else [])+
                (['Redead and Gibdo Soul'] if soul else []))
            ck(f'{tag} time travel {unlock} {soul}', result.state.has(Events.TIME_TRAVEL, 1), unlock)
            for i in range(1,9):
                name = f'Enemy Defeat: Market Ruins Room 0 Redead/Gibdo {i}'
                expected = soul and (adult or unlock)
                ck(f'{tag} AP {i} {unlock} {soul}', w.get_location(name).can_reach(result.state), expected)
                ck(f'{tag} UT {i} {unlock} {soul}', name in result.in_logic_locations, expected)
w = setup(930444, overrides=options, stop_before='pre_fill').worlds[1]
run(w, 'child')
slot = convert_to_base_types(w.fill_slot_data())
run(setup(930444, overrides=options, passthrough=slot, stop_before='pre_fill').worlds[1], 'reconstructed child')
run(setup(930445, overrides=dict(options, starting_age='adult'), stop_before='pre_fill').worlds[1], 'adult start', True)
report = dict(passed=all(t['passed'] for t in tests), assertions=len(tests), tests=tests, scope=__doc__)
a.report.parent.mkdir(parents=True, exist_ok=True)
a.report.write_text(json.dumps(report, indent=2))
print('PASS' if report['passed'] else 'FAIL', len(tests), 'Market age assertions')
raise SystemExit(not report['passed'])
