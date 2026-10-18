"""Verify Jabu's carried-Ruto routes and item/action gates with the real APWorld.

Run with the official AP runtime on PYTHONPATH. This executes generation through
set_rules and probes the compiled native predicates; it does not perform fill or
claim an in-game playthrough. Complete fill is covered by validate_user_full_fill.
"""
from pathlib import Path
import argparse
import hashlib
import json
import random
import time

import ModuleUpdate
ModuleUpdate.update_ran = True
import settings
settings.no_gui = True
settings.skip_autosave = True
import yaml
from BaseClasses import CollectionState, Item, ItemClassification
from Generate import roll_settings
from test.general import setup_multiworld
from worlds.AutoWorld import call_all
from worlds.soh_extreme import SohExtremeWorld
from worlds.soh_extreme import EntranceRandomizer as ER
from worlds.soh_extreme.EnemyRoomLogic import GRAPH, event_item, NativeEnemyRegions
from worlds.soh_extreme._vendor_oot_soh.Enums import Ages, Items
from worlds.soh_extreme._vendor_oot_soh import LogicHelpers as H
from Options import OptionError


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--yaml', type=Path, required=True)
parser.add_argument('--report', type=Path, required=True)
args = parser.parse_args()
source_root = Path(__file__).resolve().parents[2]
yaml_path = args.yaml.resolve()
started = time.monotonic()
random.seed(1)
rolled = roll_settings(yaml.safe_load(yaml_path.read_text(encoding='utf-8-sig')))
options = {name: getattr(rolled, name).value for name in SohExtremeWorld.options_dataclass.type_hints}
options = {name: dict(value) if isinstance(value, dict) else value for name, value in options.items()}
options['starting_age'] = 'adult'
mw = setup_multiworld(SohExtremeWorld, steps=(), seed=1, options=options)
world = mw.worlds[1]
for stage in ('generate_early', 'create_regions', 'create_items', 'set_rules'):
    print(stage, flush=True)
    call_all(mw, stage)


def state_for(age, items=(), flags=()):
    state = CollectionState(mw)
    for name in items:
        state.collect(world.create_item(str(name)), True)
    for flag in flags:
        state.collect(Item(event_item(flag), ItemClassification.progression, None, 1), True)
    state._soh_extreme_age[1] = Ages[age.upper()]
    return state


physical_ids = (8456, 8458, 8460, 8462, 8469, 8471)
rules = {endpoint: ER._source_rule(world, ER.ENDPOINTS[endpoint]) for endpoint in physical_ids}
cases = []
for age in ('child', 'adult'):
    state = state_for(age)
    allowed = {str(endpoint): bool(rule(state)) for endpoint, rule in rules.items()}
    assert [endpoint for endpoint, yes in allowed.items() if yes] == ['8456'], allowed
    cases.append({'age': age, 'inventory': 'actual precollected only', 'allowed_doors': allowed})
    for flag, expected in (
        ('LOGIC_JABU_RUTO_IN_1F', {8456, 8469, 8471}),
        ('LOGIC_JABU_WEST_TENTACLE', {8456, 8458, 8462}),
        ('LOGIC_JABU_EAST_TENTACLE', {8456, 8460}),
    ):
        state = state_for(age, flags=(flag,))
        allowed = {endpoint for endpoint, rule in rules.items() if rule(state)}
        assert allowed == expected, (age, flag, allowed)
        cases.append({'age': age, 'local_event': flag, 'allowed_door_ids': sorted(allowed)})

compiler = world._extreme_room_compiler
fork = 'RR_JABU_JABUS_BELLY_FORK_WEST'
tentacle = compiler.expr('logic->CanKillEnemy(RE_TENTACLE, ED_BOOMERANG)', fork).resolve(world)
combat = []
for age in ('child', 'adult'):
    for items in ((), (Items.BOOMERANG,), (Items.BOOMERANG, 'Jabu Jabu Tentacle Soul')):
        result = bool(tentacle(state_for(age, items)))
        expected = age == 'child' and len(items) == 2
        assert result == expected, (age, items, result)
        combat.append({'age': age, 'items': [str(item) for item in items], 'can_kill_tentacle': result})

ruto_region = 'RR_JABU_JABUS_BELLY_WATER_SWITCH_ROOM_NORTH'
ruto_expr = next(row['condition'] for row in GRAPH[ruto_region]['events'] if row['event'] == 'LOGIC_JABU_RUTO_IN_1F')
ruto = compiler.expr(ruto_expr, ruto_region).resolve(world)
ruto_items = ('Progressive Scale', 'Grab / Power Bracelet', 'Speak Zora', 'NPC Soul', 'Climb')
ruto_cases = []
for age in ('child', 'adult'):
    for missing in (*ruto_items, None):
        items = tuple(item for item in ruto_items if item != missing)
        state = state_for(age, items, ('LOGIC_JABU_RUTO_IN_B1',))
        result = bool(ruto(state))
        assert result == (missing is None), (age, missing, result)
        ruto_cases.append({'age': age, 'missing': missing, 'ruto_can_reach_1f': result})

# Link's earlier access to Holes or Lift does not establish a carried-Ruto route.
# Both actual escape alternatives must be available from the Water Switch side.
south = 'RR_JABU_JABUS_BELLY_WATER_SWITCH_ROOM_SOUTH'
ledge = 'RR_JABU_JABUS_BELLY_WATER_SWITCH_ROOM_LEDGE'
lift = 'RR_JABU_JABUS_BELLY_LIFT_ROOM'
south_to_lift = ER._source_rule(world, ER.ENDPOINTS[8477])
ledge_rule = compiler.expr(next(edge['condition'] for edge in GRAPH[ruto_region]['exits']
                               if edge['target'] == ledge), ruto_region).resolve(world)
ledge_to_lift = compiler.expr(next(edge['condition'] for edge in GRAPH[ledge]['exits']
                                  if edge['target'] == lift), ledge).resolve(world)
escape_cases = []
for age in ('child', 'adult'):
    base = tuple(item for item in ruto_items if item != 'Climb')
    projectile = str(Items.BOOMERANG if age == 'child' else Items.PROGRESSIVE_HOOKSHOT)
    for label, items, expected in (
        ('no escape action', base, False),
        ('climb and carried Ruto', ruto_items, True),
        ('usable projectile', (*base, projectile), True),
    ):
        state = state_for(age, items, ('LOGIC_JABU_RUTO_IN_B1',))
        result = bool(ruto(state))
        door_result = bool(south_to_lift(state))
        assert result == expected and door_result == expected, (age, label, result, door_result)
        escape_cases.append({'age': age, 'case': label, 'ruto_1f_event': result,
                             'physical_south_door': door_result,
                             'ledge_access': bool(ledge_rule(state)),
                             'ledge_lift_action': bool(ledge_to_lift(state))})

throw_object_cases = []
for age in ('child', 'adult'):
    common = ('Progressive Scale', 'Grab / Power Bracelet', 'Climb')
    for label, more, flags, expected in (
        ('no available object', (), (), False),
        ('pot is available', ('Pot Soul',), (), True),
        ('Ruto is available', ('NPC Soul', 'Speak Zora'), ('LOGIC_JABU_RUTO_IN_B1',), True),
        ('Ruto has no NPC Soul', ('Speak Zora',), ('LOGIC_JABU_RUTO_IN_B1',), False),
        ('Ruto has no speech ability', ('NPC Soul',), ('LOGIC_JABU_RUTO_IN_B1',), False),
        ('Ruto has not been met', ('NPC Soul', 'Speak Zora'), (), False),
    ):
        state = state_for(age, (*common, *more), flags)
        door_result = bool(south_to_lift(state))
        ledge_result = bool(ledge_to_lift(state))
        assert door_result == expected and ledge_result == expected, (
            age, label, door_result, ledge_result)
        throw_object_cases.append({'age': age, 'case': label,
                                   'physical_south_door': door_result,
                                   'ledge_lift_action': ledge_result})

boomerang_route = ER.DUNGEON_ROUTES['167'][0]
boomerang_chest = compiler.expr(boomerang_route['condition'], boomerang_route['region']).resolve(world)
stinger_cases = []
for age in ('child', 'adult'):
    for soul in (False, True):
        items = (*ruto_items, 'Open Chest', 'Open Chest', *(('Stinger Soul',) if soul else ()))
        state = state_for(age, items, ('LOGIC_JABU_RUTO_IN_B1', 'LOGIC_JABU_RUTO_IN_1F'))
        result = bool(boomerang_chest(state))
        assert result == soul, (age, soul, result)
        stinger_cases.append({'age': age, 'Stinger Soul': soul,
                              'Ruto combat can open Boomerang Chest': result})

# The AP export must carry the same action formulas as the native authoring
# source. This catches stale graph/catalog text in addition to runtime behavior.
native_path = source_root / 'soh/Enhancements/randomizer/location_access/dungeons/jabujabus_belly.cpp'
native = native_path.read_text()
compact = lambda text: ''.join(text.split())
native_compact = compact(native)
assert compact(f'EVENT_ACCESS(LOGIC_JABU_RUTO_IN_1F,{ruto_expr})') in native_compact
for rr in (south, ledge):
    body = native.split(f'areaTable[{rr}]', 1)[1].split('areaTable[', 1)[0]
    condition = next(edge['condition'] for edge in GRAPH[rr]['exits'] if edge['target'] == lift)
    assert compact(f'ENTRANCE({lift},{condition})') in compact(body), rr
assert compact('LOCATION(RC_JABU_JABUS_BELLY_BOOMERANG_CHEST,' + boomerang_route['condition'] + ')') in native_compact

expected_carrier_doors = {8452, 8453, 8456, 8457, 8470, 8471, 8472, 8473,
                          8476, 8477, 8490, 8491}
assert ER.LOCAL_CARRIER_DOORS == expected_carrier_doors
identity = {row['id']: row['id'] for row in ER._eligible(world)}
ER.validate_mapping(world, identity)
for _ in range(20):
    candidate = ER._candidate(world)
    assert all(candidate[endpoint] == endpoint for endpoint in expected_carrier_doors)
    ER.validate_mapping(world, candidate)
rejected_moves = []
for endpoint in sorted(expected_carrier_doors):
    changed = dict(identity)
    other = 8450  # An enabled, ordinary paired Jabu door outside the carry corridor.
    a, b = ER.ENDPOINTS[endpoint], ER.ENDPOINTS[other]
    changed[endpoint] = other
    changed[b['reverse']] = a['reverse']
    changed[other] = endpoint
    changed[a['reverse']] = b['reverse']
    try:
        ER.validate_mapping(world, changed)
    except OptionError as error:
        assert 'Ruto' in str(error), str(error)
        rejected_moves.append(endpoint)
    else:
        raise AssertionError(f'Carrier-critical source {endpoint} was shuffled')

scrub = next(location for location in world.get_locations() if location.address == 724)
compiler.location = scrub.name
scrub_route = json.loads((source_root / 'archipelago/soh_extreme/DungeonLocationRoutes.json').read_text())['724'][0]
scrub_physical = compiler.expr(scrub_route['condition'], scrub_route['region']).resolve(world)
bundle = (NativeEnemyRegions[scrub_route['region']], world)
scrub_soul = H.extreme_requirement(bundle, 'shuffle_business_scrub_soul', 'Scrub Soul').resolve(world)
scrub_cases = []
for age in ('child', 'adult'):
    state = state_for(age)
    assert not scrub_physical(state)
    assert not scrub_soul(state)
    # Direct action preconditions only; room reachability is owned by the AP
    # graph and the native doorway investigation, not assumed by this probe.
    predicates = {
        'swim': H.can_swim(bundle).resolve(world),
        'speech_and_npc_soul': H.can_interact_npc(bundle, 'Deku').resolve(world),
        'scrub_soul': scrub_soul,
        'stun_deku': H.can_stun_deku(bundle).resolve(world),
        'physical_collection_route': scrub_physical,
    }
    scrub_cases.append({'age': age, 'preconditions': {name: bool(rule(state)) for name, rule in predicates.items()}})

scrub_positive_cases = []
for age in ('child', 'adult'):
    # A known usable projectile supplies the surrender action. Two Scale items
    # give adult Link the authored Silver Scale route; child only needs Swim.
    weapon = str(Items.BOOMERANG if age == 'child' else Items.PROGRESSIVE_HOOKSHOT)
    scales = ('Progressive Scale',) * (1 if age == 'child' else 2)
    items = (*scales, weapon, 'Speak Deku', 'NPC Soul', 'Scrub Soul',
             'Progressive Wallet', 'Progressive Wallet', 'Progressive Wallet')
    for missing in (None, 'Progressive Scale', weapon, 'Speak Deku', 'NPC Soul', 'Scrub Soul'):
        kept = tuple(item for item in items if item != missing)
        state = state_for(age, kept)
        physical = bool(scrub_physical(state))
        soul = bool(scrub_soul(state))
        complete = physical and soul
        assert complete == (missing is None), (age, missing, physical, soul)
        scrub_positive_cases.append({'age': age, 'missing': missing,
                                     'physical_route': physical, 'scrub_soul': soul,
                                     'collectible_in_room': complete})

assert all(any(location.address == ER.ENDPOINTS[endpoint]['check_id']
               for location in world.get_locations()) for endpoint in expected_carrier_doors)

report = {
    'status': 'passed', 'scope': 'Local compiled source predicates only; no actual user seed/map or received-item snapshot supplied.',
    'world_version': world.world_version.as_simple_string(),
    'yaml_sha256': hashlib.sha256(yaml_path.read_bytes()).hexdigest(),
    'elapsed_seconds': round(time.monotonic() - started, 3),
    'starting_hearts': world.options.starting_hearts.value,
    'precollected': [item.name for item in mw.precollected_items[1]],
    'door_cases': cases, 'tentacle_combat': combat, 'ruto_requirements': ruto_cases,
    'ruto_escape_cases': escape_cases,
    'throw_object_cases': throw_object_cases,
    'stinger_soul_cases': stinger_cases,
    'carrier_corridor': {'identity_ids': sorted(expected_carrier_doors),
                         'all_checks_present': True, 'candidate_maps_checked': 20,
                         'shuffled_sources_rejected': rejected_moves},
    'scrub': {'name': scrub.name, 'address': scrub.address, 'exists': True,
              'price': world.shop_prices.get(scrub.name), 'physical_route': scrub_route,
              'cases': scrub_cases, 'positive_and_missing_item_cases': scrub_positive_cases},
    'door_definitions': {str(endpoint): ER.ENDPOINTS[endpoint] for endpoint in physical_ids},
    'source_sha256': {str(path.relative_to(source_root)): hashlib.sha256(path.read_bytes()).hexdigest()
                      for path in (
                          native_path,
                          source_root / 'archipelago/soh_extreme/EnemyRoomGraph.json',
                          source_root / 'archipelago/soh_extreme/DungeonLocationRoutes.json',
                          source_root / 'archipelago/soh_extreme/EntranceRandomizer.py',
                          source_root / 'archipelago/soh_extreme/EntranceCatalog.json',
                          source_root / 'archipelago/soh_extreme/EnemyRoomLogic.py',
                          source_root / 'archipelago/soh_extreme/_vendor_oot_soh/LogicHelpers.py',
                      )},
}
report_path = args.report.resolve()
report_path.parent.mkdir(parents=True, exist_ok=True)
report_path.write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2), flush=True)
