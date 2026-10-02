"""Owl perches and rides use actual age access, NPC Soul and Hylian speech.

Exercises AP and the installed Universal Tracker evaluator, including restored
slot settings. Inventories never inject reachability or code-less events.
"""
from run_case import setup, BOOTSTRAP
from ut_harness import tracker
from NetUtils import convert_to_base_types
from worlds.soh_extreme import SOH_ITEM_ALIASES
from pathlib import Path
import argparse, json

p = argparse.ArgumentParser(parents=[BOOTSTRAP])
p.add_argument('--ut-core', type=Path, required=True)
p.add_argument('--report', type=Path, required=True)
a = p.parse_args(); tests = []
options = dict(closed_forest='off', door_of_time='song_only', starting_age='child',
    shuffle_grab=True, shuffle_climb=True, shuffle_shovel=True,
    shuffle_npc_soul=True, shuffle_speak='individual_languages',
    shuffle_sign_soul=True, shuffle_rock_boulder_soul=True,
    song_note_shuffle='off', shuffle_ocarina_buttons=False,
    start_with_song_of_time=False, start_inventory={}, start_inventory_from_pool={},
    tricks_in_logic=[], enable_all_tricks=False)

def ck(label, actual, expected):
    tests.append(dict(test=label, actual=actual, expected=expected, passed=actual == expected))

def verify(w, label, npc_shuffle, mode, adult=False):
    ev = tracker(w, a.ut_core)
    base = [it.name for it in w.multiworld.itempool if it.name not in
            ('Song of Time', 'NPC Soul', 'Speak Hylian', 'Speak')]
    def check(inv, prefix, owl, grave=None, sign=None):
        r = ev(inv)
        ck(prefix+' no time travel', r.state.has('Time Travel', 1), False)
        for region in ('Lake Hylia', 'Death Mountain Summit'):
            ck(prefix+' approach '+region, r.state.can_reach(region, 'Region', 1), True)
        for region in ('LH Owl Flight', 'DMT Owl Flight'):
            ck(prefix+' ride '+region, r.state.can_reach(region, 'Region', 1), owl and not adult)
        for name, expected in (
            ('LH Deku Scrub Grotto Beehive', (adult or owl) if grave is None else grave),
            ('EXTREME Dmt Upper Exit Arrow Sign', (adult or owl) if sign is None else sign),
            ('NPC Speech: Kaepora Gaebora', owl and not adult),
            ('EXTREME Lh North Exit Arrow Sign', True),
        ):
            ck(prefix+' AP '+name, w.get_location(name).can_reach(r.state), expected)
            ck(prefix+' UT '+name, name in r.in_logic_locations, expected)
        return r
    for npc in (False, True):
        for speak in (False, True):
            inv = base + (['NPC Soul'] if npc else []) + (
                ['Speak' if mode == 'on' else 'Speak Hylian'] if speak else [])
            owl = (npc or not npc_shuffle) and (speak or mode == 'off')
            check(inv, f'{label}/{npc}/{speak}', owl)
    full = base + ['NPC Soul', 'Speak' if mode == 'on' else 'Speak Hylian']
    # The first physical Strength Upgrade grants the shuffled Grab tier.
    check([n for n in full if n not in ('Grab / Power Bracelet', *SOH_ITEM_ALIASES['Strength Upgrade'])],
          label+' missing Grab', True, grave=False)
    check([n for n in full if n != 'Shovel'], label+' missing Shovel', True, grave=False)
    r = ev([n for n in full if n not in ('Rock / Boulder Soul', 'Scrub Soul', 'Progressive Bomb Bag', 'Bombchu Bag')])
    name = 'LH Deku Scrub Grotto Beehive'
    ck(label+' grave is not a rock AP', w.get_location(name).can_reach(r.state), True)
    ck(label+' grave is not a rock UT', name in r.in_logic_locations, True)
    for side in ('Left', 'Center', 'Right'):
        name = 'LH Deku Scrub Grotto '+side
        ck(label+' merchant still needs Scrub Soul AP '+side, w.get_location(name).can_reach(r.state), False)
        ck(label+' merchant still needs Scrub Soul UT '+side, name in r.in_logic_locations, False)
    if mode == 'individual_languages':
        # Other languages remain in base; none may substitute for Hylian.
        check(base + ['NPC Soul'], label+' wrong languages', False)

for mode, soul in (('individual_languages', True), ('on', True), ('off', True),
                   ('individual_languages', False), ('on', False), ('off', False)):
    opts = {**options, 'shuffle_speak': mode, 'shuffle_npc_soul': soul}
    w = setup(100152, overrides=opts, stop_before='pre_fill').worlds[1]
    verify(w, f'{mode}/{soul}/child', soul, mode)
    if mode == 'individual_languages' and soul:
        slot = convert_to_base_types(w.fill_slot_data())
        restored = setup(100152, overrides={**opts, 'shuffle_speak': 'off', 'shuffle_npc_soul': False},
                         passthrough=slot, stop_before='pre_fill').worlds[1]
        verify(restored, 'restored shuffled settings', True, mode)
    adult = setup(100152, overrides={**opts, 'starting_age': 'adult'}, stop_before='pre_fill').worlds[1]
    verify(adult, f'{mode}/{soul}/adult', soul, mode, adult=True)

passed = all(t['passed'] for t in tests)
a.report.parent.mkdir(parents=True, exist_ok=True)
a.report.write_text(json.dumps(dict(passed=passed, checks=len(tests), tests=tests), indent=2))
print('RESULT', passed, len(tests), flush=True)
for t in [t for t in tests if not t['passed']][:20]: print(t)
raise SystemExit(not passed)
