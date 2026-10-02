"""All thirty bean fairies need the exact patch, beans and a playable storm song.

Uses real AP reachability and Universal Tracker; no fabricated planted events.
Other progression items allow each site's physical approach independently.
"""
from run_case import setup, BOOTSTRAP
from ut_harness import tracker
from NetUtils import convert_to_base_types
from pathlib import Path
import argparse, json

p = argparse.ArgumentParser(parents=[BOOTSTRAP])
p.add_argument('--ut-core', type=Path, required=True)
p.add_argument('--report', type=Path, required=True)
a = p.parse_args(); tests = []
plots = {
    'DMC': 'Death Mountain Crater Bean Soul',
    'DMT': 'Death Mountain Trail Bean Soul',
    'Colossus': 'Desert Colossus Bean Soul',
    'GV': 'Gerudo Valley Bean Soul',
    'Graveyard': 'Graveyard Bean Soul',
    'KF': 'Kokiri Forest Bean Soul',
    'LH': 'Lake Hylia Bean Soul',
    'LW Bean Sprout Near Bridge': 'Lost Woods Bridge Bean Soul',
    'LW Bean Sprout Near Theatre': 'Lost Woods Bean Soul',
    'ZR': "Zora's River Bean Soul",
}
locations = {(prefix if prefix.startswith('LW ') else prefix+' Bean Sprout')+f' Fairy {i}': soul
             for prefix,soul in plots.items() for i in range(1,4)}
buttons = ['Ocarina A Button', 'Ocarina C Up Button', 'Ocarina C Down Button']
opts = dict(closed_forest='off', kakariko_gate='open', door_of_time='song_only',
    starting_age='child', lock_overworld_doors=False, shuffle_bean_fairies=True,
    shuffle_bean_souls=True, shuffle_ocarinas=True, shuffle_ocarina_buttons=True,
    song_note_shuffle='individual_notes', start_with_song_of_time=False,
    start_with_magic_beans=False, shuffle_merchants='all',
    start_inventory={}, start_inventory_from_pool={}, tricks_in_logic=[], enable_all_tricks=False)

def ck(label, actual, expected):
    tests.append(dict(test=label, actual=actual, expected=expected, passed=actual == expected))

def verify(w, label, child=True, souls=True, shuffled_buttons=True, notes=True):
    w._extreme_live_shields = 2
    ev = tracker(w, a.ut_core)
    storm = list(w.SONG_NOTE_GROUPS['Song of Storms']) if notes else ['Song of Storms']
    excluded = {'Song of Time', *w.SONG_NOTE_GROUPS['Song of Time']}
    base = [item.name for item in w.multiworld.itempool if item.name not in excluded]
    present = [loc.name for loc in w.get_locations() if 'Bean Sprout' in loc.name and 'Fairy' in loc.name]
    ck(label+' all thirty checks present', sorted(present), sorted(locations))
    cases = [('complete', set(), child), ('no beans', {'Magic Bean Pack'}, False),
             ('no ocarina', {'Progressive Ocarina'}, False),
             ('no storm song', set(storm), False),
             ('no passive clock', {'Flow of Time'}, child)]
    cases += [('missing '+button, {button}, child and not shuffled_buttons) for button in buttons]
    if notes:
        cases += [('missing '+note, {note}, False) for note in storm]
    for case, missing, expected in cases:
        result = ev([name for name in base if name not in missing])
        ck(label+'/'+case+' no time travel', result.state.has('Time Travel',1), False)
        for name in locations:
            ck(label+'/'+case+' AP '+name, w.get_location(name).can_reach(result.state), expected)
            ck(label+'/'+case+' UT '+name, name in result.in_logic_locations, expected)
    for soul in plots.values():
        # Having every OTHER soil plot cannot substitute for this one.
        result = ev([name for name in base if name != soul])
        for name, required in locations.items():
            expected = child and (not souls or required != soul)
            ck(label+'/missing '+soul+' AP '+name, w.get_location(name).can_reach(result.state), expected)
            ck(label+'/missing '+soul+' UT '+name, name in result.in_logic_locations, expected)

w = setup(100155, overrides=opts, stop_before='pre_fill').worlds[1]
verify(w, 'notes/buttons/souls on')
slot = convert_to_base_types(w.fill_slot_data())
restored = setup(100155, overrides={**opts, 'shuffle_bean_souls':False,
    'shuffle_ocarina_buttons':False, 'song_note_shuffle':'off'},
    passthrough=slot, stop_before='pre_fill').worlds[1]
verify(restored, 'restored current settings')
for option, value in (('shuffle_bean_souls',False), ('shuffle_ocarina_buttons',False),
                      ('song_note_shuffle','off'), ('starting_age','adult')):
    w = setup(100155, overrides={**opts,option:value}, stop_before='pre_fill').worlds[1]
    verify(w, option+'='+str(value), child=option!='starting_age',
           souls=option!='shuffle_bean_souls', shuffled_buttons=option!='shuffle_ocarina_buttons',
           notes=option!='song_note_shuffle')

passed = all(t['passed'] for t in tests)
a.report.parent.mkdir(parents=True, exist_ok=True)
a.report.write_text(json.dumps(dict(passed=passed, checks=len(tests),
    failures=sum(not t['passed'] for t in tests), tests=tests), indent=2))
print('RESULT', passed, len(tests), flush=True)
for t in [t for t in tests if not t['passed']][:25]: print(t)
raise SystemExit(not passed)
