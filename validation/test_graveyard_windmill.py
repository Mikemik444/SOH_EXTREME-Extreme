"""Graveyard/Windmill physical routes through fresh AP and real UT evaluation."""
from run_case import setup, BOOTSTRAP
from ut_harness import tracker
from pathlib import Path
from NetUtils import convert_to_base_types
from worlds.soh_extreme.EnemyDropLocations import ENEMY_DROP_LOCATIONS
import argparse, json

p = argparse.ArgumentParser(parents=[BOOTSTRAP])
p.add_argument('--ut-core', type=Path, required=True)
p.add_argument('--report', type=Path, required=True)
a = p.parse_args(); checks = []

def ck(name, actual, expected=True):
    checks.append(dict(test=name, actual=actual, expected=expected, passed=actual == expected))
    if actual != expected: print('FAIL', name, actual, expected, flush=True)

options = dict(closed_forest='off', door_of_time='open', starting_age='child',
    shuffle_bean_souls=True, shuffle_npc_soul=True, shuffle_speak='individual_languages',
    lock_overworld_doors=True, shuffle_crates='all', shuffle_crate_soul=True,
    song_note_shuffle='individual_notes', shuffle_ocarina_buttons=True,
    shuffle_enemy_drops=True, rocs_feather=True, tricks_in_logic=[], enable_all_tricks=False)
m = setup(93040, overrides=options, stop_before='pre_fill'); w = m.worlds[1]
evaluate = tracker(w, a.ut_core)
physical = [it.name for it in m.itempool] + [l.item.name for l in w.get_locations()
    if l.address is not None and l.item is not None and l.item.name in w.item_name_to_id]

def state(excluded=(), extra=()):
    return evaluate([n for n in physical if n not in set(excluded)] + list(extra))

def location(result, name, expected):
    ck('AP ' + name, w.get_location(name).can_reach(result.state), expected)
    ck('UT ' + name, name in result.in_logic_locations, expected)

targets = ('Graveyard Freestanding PoH', 'Graveyard Freestanding PoH Crate')
missing = {'Graveyard Bean Soul', 'Progressive Hookshot', "Roc's Feather"}
for route, extra, expected in (
        ('none', [], False), ('wrong soul', ['Kokiri Forest Bean Soul'], False),
        ('bean', ['Graveyard Bean Soul'], True), ('short hook', ['Progressive Hookshot'], False),
        ('longshot', ['Progressive Hookshot'] * 2, True), ('feather', ["Roc's Feather"], True)):
    for crate in (False, True):
        result = state(missing | (set() if crate else {'Crate Soul'}), extra)
        for name in targets:
            location(result, name, expected and crate)

# Every real planted event must carry its own soul, not just the final crate.
beans = {
    'DMC Bean Patch': 'Death Mountain Crater Bean Soul',
    'DMT Bean Patch': 'Death Mountain Trail Bean Soul',
    'Desert Colossus Bean Patch': 'Desert Colossus Bean Soul',
    'GV Bean Patch': 'Gerudo Valley Bean Soul', 'Graveyard Bean Patch': 'Graveyard Bean Soul',
    'KF Soft Soil': 'Kokiri Forest Bean Soul', 'LH Bean Patch': 'Lake Hylia Bean Soul',
    'LW Bridge Bean Patch': 'Lost Woods Bridge Bean Soul',
    'LW Theater Bean Patch': 'Lost Woods Bean Soul', 'ZR Bean Patch': "Zora's River Bean Soul",
}
all_beans = set(beans.values())
for name, soul in beans.items():
    event = w.get_location(name)
    for extra in ([], [soul]):
        result = state(all_beans, extra)
        ck(name + ' correct soul ' + str(bool(extra)), result.state.has(event.item.name, 1), bool(extra))

windmill = 'Song from Windmill'
for excluded, expected in (
        ({'NPC Soul'}, False), ({'Speak Hylian'}, False), ({'Progressive Ocarina'}, False),
        ({'Windmill Key', 'Skeleton Key', *w.SONG_NOTE_GROUPS['Song of Time']}, False),
        ({'Windmill Key'}, True), # genuine DampÃ© race + playable Song of Time
        ({*w.SONG_NOTE_GROUPS['Song of Time']}, True), # front door with key
        (set(), True)):
    location(state(excluded), windmill, expected)
result = state({'NPC Soul', 'Windmill Key', 'Skeleton Key'})
ck('No NPC cannot borrow Dampes passage to bypass locked Windmill',
   w.get_region('Kak Windmill').can_reach(result.state), False)

# The real tomb scene is gated; unused exterior entries are excluded from new seeds.
no_lullaby = set(w.SONG_NOTE_GROUPS["Zelda's Lullaby"]) | {"Zelda's Lullaby"}
for excluded, expected in ((no_lullaby, False), ({w.SONG_NOTE_GROUPS["Zelda's Lullaby"][0]}, False),
                           ({'Progressive Ocarina'}, False), ({'Ocarina C Left Button'}, False), (set(), True)):
    result = state(excluded)
    for e in ENEMY_DROP_LOCATIONS:
        if e.scene_id == 0x41:
            location(result, e.name, expected)
exterior = [e for e in ENEMY_DROP_LOCATIONS if e.scene_id == 0x53 and e.actor_id in (0x13, 0x95)]
ck('Historical exterior identities reserved', len(exterior), 7)
for e in exterior: ck('Unused entry absent: ' + e.name, e.name in {l.name for l in w.get_locations()}, False)

# Disabled shuffles are innate. An unrelated shared language item is sufficient
# only in shared mode; a shuffled NPC Soul stays independently required.
for mode in ('off', 'on', 'individual_languages'):
    mm = setup(93041, overrides=dict(options, shuffle_bean_souls=False,
               shuffle_speak=mode, shuffle_npc_soul=False), stop_before='pre_fill')
    ww = mm.worlds[1]; ev = tracker(ww, a.ut_core)
    names = [it.name for it in mm.itempool if it.name not in all_beans | {'Progressive Hookshot', "Roc's Feather"}]
    rr = ev(names)
    for name in targets: ck('unshuffled beans ' + mode + name, ww.get_location(name).can_reach(rr.state))
    ck('unshuffled NPC Windmill ' + mode, ww.get_location(windmill).can_reach(rr.state))

# Reconstruct the tracker from server slot data, not this test's local defaults.
slot = convert_to_base_types(w.fill_slot_data())
mm = setup(93042, overrides=dict(options, shuffle_npc_soul=False, shuffle_bean_souls=False),
           passthrough=slot, stop_before='pre_fill')
ww = mm.worlds[1]; ev = tracker(ww, a.ut_core)
for excluded in (missing, {'NPC Soul', 'Windmill Key', 'Skeleton Key'}, no_lullaby, set()):
    rr = ev([n for n in physical if n not in excluded]); original = state(excluded)
    for name in (*targets, windmill):
        ck('slot reconstruction ' + name, name in rr.in_logic_locations, name in original.in_logic_locations)

report = dict(passed=all(c['passed'] for c in checks), assertions=len(checks),
              failures=[c for c in checks if not c['passed']], scope=__doc__)
a.report.parent.mkdir(parents=True, exist_ok=True); a.report.write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2)); raise SystemExit(not report['passed'])
