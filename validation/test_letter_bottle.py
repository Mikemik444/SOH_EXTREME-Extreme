"""Ruto's Letter usability through AP rules and the real Universal Tracker evaluator.

Tests the delivery event, downstream bottle use, actual region/age access,
speech/soul options and tracker reconstruction from server slot data.
"""
from run_case import setup, BOOTSTRAP
from ut_harness import tracker
from pathlib import Path
from NetUtils import convert_to_base_types
from worlds.soh_extreme._vendor_oot_soh.Enums import Events, Items
from worlds.soh_extreme._vendor_oot_soh.Items import no_rules_bottles
from worlds.soh_extreme._vendor_oot_soh.LogicHelpers import has_bottle_count
import argparse, json

p = argparse.ArgumentParser(parents=[BOOTSTRAP])
p.add_argument('--ut-core', type=Path, required=True)
p.add_argument('--report', type=Path, required=True)
a = p.parse_args(); tests = []

def ck(name, actual, expected=True):
    tests.append(dict(test=name, actual=actual, expected=expected, passed=actual == expected))
    if actual != expected: print('FAIL', name, actual, expected, flush=True)

base_options = dict(closed_forest='off', door_of_time='open', starting_age='child', zoras_fountain='closed',
    sleeping_waterfall='closed', shuffle_npc_soul=True, shuffle_speak='individual_languages',
    shuffle_fish='all', shuffle_swim=True, shuffle_ocarina_buttons=True,
    song_note_shuffle='individual_notes', shuffle_fishing_pole=False,
    tricks_in_logic=[], enable_all_tricks=False, start_inventory={}, start_inventory_from_pool={})
all_bottles = {*no_rules_bottles, Items.BOTTLE_WITH_RUTOS_LETTER, Items.BOTTLE_WITH_BIG_POE}
letter = str(Items.BOTTLE_WITH_RUTOS_LETTER)
empty = str(Items.EMPTY_BOTTLE)
event_name = "ZD Deliver Ruto's Letter"

def inventory(w):
    return [it.name for it in w.multiworld.itempool if it.player == w.player] + [l.item.name for l in w.get_locations()
        if l.address is not None and l.item is not None and l.item.name in w.item_name_to_id]

def run_world(w, tag):
    evaluate = tracker(w, a.ut_core)
    physical = inventory(w)
    fish = [l.name for l in w.get_locations() if l.address is not None and
            (l.name.startswith('ZD Fish') or 'Grotto Fish' in l.name)]
    ck(tag + ' real fish targets exist', len(fish) >= 6)
    bottle_rule = has_bottle_count(1).resolve(w)
    two_rule = has_bottle_count(2).resolve(w)
    no_bottles = [n for n in physical if n not in all_bottles]
    for removed, extra, expected in (
        ({'NPC Soul'}, [letter], False), ({'Speak Zora'}, [letter], False),
        ({'NPC Soul', 'Speak Zora'}, [letter], False),
        ({'Speak Zora'}, [letter, 'Speak Hylian'], False),
        (set(), [letter], True), (set(), [], False),
        ({'NPC Soul', 'Speak Zora'}, [empty], True),
        ({'NPC Soul', 'Speak Zora'}, [letter, empty], True),
    ):
        label = tag + ' ' + repr((sorted(removed), extra))
        result = evaluate([n for n in no_bottles if n not in removed] + extra)
        can_deliver = letter in extra and not (removed & {'NPC Soul', 'Speak Zora'})
        ck(label + ' delivery event', result.state.has(Events.DELIVER_LETTER, 1), can_deliver)
        ck(label + ' usable bottle', bottle_rule(result.state), expected)
        ck(label + ' second usable bottle', two_rule(result.state), can_deliver and empty in extra)
        for name in fish:
            ck(label + ' AP ' + name, w.get_location(name).can_reach(result.state), expected)
            ck(label + ' UT ' + name, name in result.in_logic_locations, expected)
    # Close both the waterfall and underwater shortcut routes for child Link.
    # Removing just one route must not erase a valid alternative.
    route_items = {'Progressive Scale', 'Swim', 'Iron Boots', 'Progressive Ocarina',
                   "Zelda's Lullaby", *w.SONG_NOTE_GROUPS["Zelda's Lullaby"]}
    no_route = [n for n in no_bottles if n not in route_items]
    result = evaluate(no_route + [letter])
    ck(tag + ' no child route to Domain', w.get_location(event_name).can_reach(result.state), False)
    ck(tag + ' inaccessible King Zora cannot empty letter', bottle_rule(result.state), False)
    for name in fish:
        if 'Grotto Fish' in name:
            ck(tag + ' isolated letter cannot bottle ' + name, name in result.in_logic_locations, False)
    # Waterfall and Lake Hylia are alternatives: removing the song alone must not
    # block delivery if the underwater shortcut and its abilities are available.
    no_song = {"Zelda's Lullaby", *w.SONG_NOTE_GROUPS["Zelda's Lullaby"], 'Progressive Ocarina'}
    result = evaluate([n for n in no_bottles if n not in no_song] + [letter])
    ck(tag + ' Lake Hylia shortcut can reach delivery without Lullaby', result.state.has(Events.DELIVER_LETTER, 1))
    ck(tag + ' Lake Hylia shortcut frees bottle', bottle_rule(result.state))
    return physical

m = setup(93043, overrides=base_options, stop_before='pre_fill'); w = m.worlds[1]
run_world(w, 'fresh')

# Use actual child/adult search, not just overriding an age variable on a location.
adult = setup(93044, overrides=dict(base_options, starting_age='adult', door_of_time='closed'), stop_before='pre_fill')
aw = adult.worlds[1]; ev = tracker(aw, a.ut_core)
excluded = {*all_bottles, 'Progressive Ocarina', 'Master Sword', 'Kokiri Sword', 'Song of Time', *aw.SONG_NOTE_GROUPS['Song of Time']}
result = ev([n for n in inventory(aw) if n not in excluded] + [letter])
ck('Adult-only access cannot deliver the letter', result.state.has(Events.DELIVER_LETTER, 1), False)
ck('Adult-only letter is not an empty bottle', has_bottle_count(1).resolve(aw)(result.state), False)

# Disabled shuffles are innate; shared Speak and individual Zora speech differ.
for soul in (False, True):
    for mode in ('off', 'on', 'individual_languages'):
        mm = setup(93100 + len(tests), overrides=dict(base_options, shuffle_npc_soul=soul,
            shuffle_speak=mode, zoras_fountain='closed_as_child'), stop_before='pre_fill')
        ww = mm.worlds[1]; ev = tracker(ww, a.ut_core)
        names = [n for n in inventory(ww) if n not in all_bottles and n not in {'NPC Soul', 'Speak', 'Speak Zora'}]
        for give_soul in (False, True):
            for speech in ([], ['Speak Hylian'], ['Speak'], ['Speak Zora']):
                expected = (not soul or give_soul) and (mode == 'off' or (mode == 'on' and 'Speak' in speech)
                    or (mode == 'individual_languages' and 'Speak Zora' in speech))
                rr = ev(names + [letter] + (['NPC Soul'] if give_soul else []) + speech)
                label = f'options soul={soul} speech={mode} received={give_soul,speech}'
                ck(label + ' delivery', rr.state.has(Events.DELIVER_LETTER, 1), expected)
                ck(label + ' bottle', has_bottle_count(1).resolve(ww)(rr.state), expected)

slot = convert_to_base_types(w.fill_slot_data())
rebuilt = setup(93199, overrides=dict(base_options, shuffle_npc_soul=False, shuffle_speak='off'),
    passthrough=slot, stop_before='pre_fill').worlds[1]
ck('Slot restores NPC Soul option', rebuilt.options.shuffle_npc_soul.value, 1)
ck('Slot restores individual speech option', rebuilt.options.shuffle_speak.value, 2)
run_world(rebuilt, 'slot reconstructed')

report = dict(passed=all(t['passed'] for t in tests), assertions=len(tests), tests=tests, scope=__doc__)
a.report.parent.mkdir(parents=True, exist_ok=True)
a.report.write_text(json.dumps(report, indent=2), encoding='utf-8')
print('PASS' if report['passed'] else 'FAIL', len(tests), 'letter bottle assertions', flush=True)
raise SystemExit(not report['passed'])
