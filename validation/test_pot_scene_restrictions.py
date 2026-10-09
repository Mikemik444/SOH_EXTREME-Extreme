"""Indoor pot restrictions: engine flag audit, AP rules, and actual UT evaluation.

Controlled interaction cases fix age to isolate item usability from routes. The
UT cases retain the real region graph, options and slot-data reconstruction.
"""
from run_case import setup, BOOTSTRAP
from ut_harness import tracker
from source_index import native_metadata
from BaseClasses import CollectionState
from NetUtils import convert_to_base_types
from worlds.soh_extreme._vendor_oot_soh.Enums import Ages, Events, Regions
from worlds.soh_extreme._vendor_oot_soh.LogicHelpers import can_break_pots
from worlds.soh_extreme._vendor_oot_soh.Locations import location_data_table, LocTag
from pathlib import Path
import argparse, ast, collections, hashlib, json, re

p = argparse.ArgumentParser(parents=[BOOTSTRAP])
p.add_argument('--ut-core', type=Path, required=True)
p.add_argument('--source-root', type=Path, required=True)
p.add_argument('--inventory-log', type=Path)
p.add_argument('--report', type=Path, required=True)
a = p.parse_args(); tests = []
def ck(name, actual, expected=True):
    tests.append(dict(test=name, actual=actual, expected=expected, passed=actual == expected))
    if actual != expected: print('FAIL', name, actual, expected, flush=True)

# Expected restrictions come from the running engine's scene table, not the
# new helper's whitelist. Every native, non-MQ pot must map to an AP pot.
engine = (a.source_root/'src/code/z_parameter.c').read_text()
flags = {s:tuple(int(v, 16) for v in vs) for s,*vs in re.findall(
    r'\{\s*(SCENE_\w+),\s*(0x\w+),\s*(0x\w+),\s*(0x\w+)\s*\}', engine)}
mapping = {rc:int(i) for rc,i in re.findall(r'static_cast<int>\((RC_\w+)\),\s*(\d+)LL',
    (a.source_root/'soh/Network/Archipelago/ArchipelagoLocationMap.inc').read_text())}
catalog = {d.loc_id:(str(n),d) for n,d in location_data_table.items() if d.loc_id is not None}
pot_meta = [d for d in native_metadata(a.source_root).values()
            if d['constructor'] == 'Pot' and d['quest'] != 'RCQUEST_MQ']
region_by_name = {}
for f in (a.source_root/'archipelago/soh_extreme/_vendor_oot_soh/location_access').rglob('*.py'):
    for c in ast.walk(ast.parse(f.read_text())):
        if isinstance(c, ast.Call) and getattr(c.func, 'id', '') == 'add_locations':
            region = getattr(Regions, c.args[0].attr)
            for entry in c.args[2].elts:
                if any(isinstance(n, ast.Call) and getattr(n.func, 'id', '') == 'can_break_pots'
                       for n in ast.walk(entry)):
                    from worlds.soh_extreme._vendor_oot_soh.Enums import Locations
                    region_by_name[str(getattr(Locations, entry.elts[0].attr))] = region
scenes = collections.defaultdict(set); ids = set(); specialized = []
for d in pot_meta:
    item = catalog.get(mapping.get(d['rc']))
    ck('native pot mapped '+d['rc'], item is not None and bool(item[1].tags & LocTag.Pot))
    if item:
        name = item[0]; ids.add(mapping[d['rc']])
        if name in region_by_name:
            scenes[d['scene']].add(region_by_name[name])
        else:
            # 16 pots use distance/underwater rules or gate a combined region
            # at its entrances. They have no scene combat-button restrictions;
            # do not replace those more specific routes with the close-pot rule.
            f1, f2, f3 = flags[d['scene']]
            ck('specialized pot has no scene combat restriction '+d['rc'],
               not (f1 & 0x30 or f2 & 0x30 or f3 & 3))
            specialized.append(name)

options = dict(shuffle_pots='all', shuffle_pot_soul=True, shuffle_grab=True,
    shuffle_roll=True, shuffle_deku_stick_bag=True, bombchu_bag='single_bag', bombchu_drops=True,
    closed_forest='off', door_of_time='song_only', starting_age='child',
    start_inventory={}, start_inventory_from_pool={}, tricks_in_logic=[], enable_all_tricks=False)
m = setup(930445, overrides=options); w = m.worlds[1]
cases = [('none', [], 'none', None), ('roll', ['Roll'], 'none', None),
    ('grab', ['Strength Upgrade'], 'grab', None),
    ('child sword', ['Kokiri Sword'], 'sword', Ages.CHILD),
    ('adult sword', ['Master Sword'], 'sword', Ages.ADULT),
    ('sticks', ['Progressive Stick Capacity'], 'combat', Ages.CHILD),
    ('hammer', ['Megaton Hammer'], 'combat', Ages.ADULT),
    ('bombs', ['Progressive Bomb Bag'], 'combat', None),
    ('bombchus', ['Bombchu Bag'], 'combat', None),
    ('boomerang', ['Boomerang'], 'combat', Ages.CHILD),
    ('bow', ['Progressive Bow'], 'combat', Ages.ADULT),
    ('slingshot', ['Progressive Slingshot'], 'combat', Ages.CHILD),
    ('hookshot', ['Progressive Hookshot'], 'hookshot', Ages.ADULT)]
for scene, regions in sorted(scenes.items()):
    f1, f2, f3 = flags[scene]
    for region in sorted(regions):
        rule = can_break_pots((region, w)).resolve(w)
        for age in (Ages.CHILD, Ages.ADULT):
            for soul in (False, True):
                for label, inventory, kind, required_age in cases:
                    s = CollectionState(m)
                    for it in m.precollected_items[1]: s.remove(it)
                    for n in inventory + (['Pot Soul'] if soul else []): s.collect(w.create_item(n), True)
                    s.prog_items[1][Events.CAN_FARM_STICKS] = 1
                    s._soh_extreme_age[1] = age
                    usable = kind == 'grab' or (kind == 'sword' and not (f1 & 0x30)) or (
                        kind in ('combat', 'hookshot') and not (f3 & 3) and
                        (kind != 'hookshot' or not (f2 & 0x30)))
                    expected = soul and usable and (required_age is None or required_age == age)
                    ck(f'engine flags {scene}/{region}/{age}/{soul}/{label}', bool(rule(s)), expected)

house_names = [catalog[mapping[d['rc']]][0] for d in pot_meta if
    d['scene'] in ('SCENE_LINKS_HOUSE', 'SCENE_TWINS_HOUSE',
                  'SCENE_KNOW_IT_ALL_BROS_HOUSE', 'SCENE_BACK_ALLEY_HOUSE')]
ck('eight fully weapon-disabled house pots', len(house_names), 8)
def ut_cases(world, tag):
    ev = tracker(world, a.ut_core)
    full = [i.name for i in world.multiworld.itempool] + [l.item.name for l in world.get_locations()
        if l.address is not None and l.item and l.item.name in world.item_name_to_id]
    for soul in (False, True):
        for grab in (False, True):
            removed = (set() if soul else {'Pot Soul'}) | (set() if grab else {'Strength Upgrade', 'Grab / Power Bracelet'})
            r = ev([n for n in full if n not in removed])
            expected = (soul or not world.options.shuffle_pot_soul) and (grab or not world.options.shuffle_grab)
            for name in house_names:
                ck(f'{tag} AP {soul}/{grab} {name}', world.get_location(name).can_reach(r.state), bool(expected))
                ck(f'{tag} UT {soul}/{grab} {name}', name in r.in_logic_locations, bool(expected))
            if not soul and world.options.shuffle_pot_soul:
                for loc in world.get_locations():
                    if loc.address in ids:
                        ck(f'{tag} all pots need soul grab={grab} '+loc.name,
                           loc.name in r.in_logic_locations, False)
    r = ev(full)
    for loc in world.get_locations():
        if loc.address in ids:
            ck(tag+' full inventory '+loc.name, loc.name in r.in_logic_locations)
ut_cases(w, 'new generation')
slot = convert_to_base_types(w.fill_slot_data())
rw = setup(930445, overrides=dict(options, shuffle_grab=False, shuffle_pot_soul=False), passthrough=slot).worlds[1]
ut_cases(rw, 'existing slot reconstructed')
for soul, grab in ((False, True), (True, False), (False, False)):
    q = setup(930445, overrides=dict(options, shuffle_pot_soul=soul, shuffle_grab=grab)).worlds[1]
    ut_cases(q, f'options soul={soul} grab={grab}')

log_evidence = None
if a.inventory_log:
    data = a.inventory_log.read_bytes()
    received = re.findall(r'sent (.+) to mikemik44 \(', data.decode('utf-8-sig'))
    ck('supplied log has Pot Soul', 'Pot Soul' in received)
    ck('supplied log has Bombchu Bag', 'Bombchu Bag' in received)
    ck('supplied log has no Grab tier', not {'Strength Upgrade', 'Grab / Power Bracelet'} & set(received))
    r = tracker(w, a.ut_core)(received)
    for name in house_names[:5]: ck('supplied inventory '+name, name in r.in_logic_locations, False)
    log_evidence = dict(sha256=hashlib.sha256(data).hexdigest(), received_items=len(received))

report = dict(passed=all(t['passed'] for t in tests), assertions=len(tests),
    native_pots=len(pot_meta), pot_scenes=len(scenes), region_scene_pairs=sum(map(len, scenes.values())),
    specialized_pots=specialized,
    log=log_evidence, tests=tests, scope=__doc__)
a.report.parent.mkdir(parents=True, exist_ok=True)
a.report.write_text(json.dumps(report, indent=2))
print('RESULT', report['passed'], len(tests), 'assertions', flush=True)
raise SystemExit(not report['passed'])
