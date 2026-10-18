"""Authoritative, coupled physical entrance shuffle shared by AP and UT.

Predicates belong to source endpoints. Destinations never carry the old source's
access requirements. One-way routes add exactly one directed edge.
"""
from collections import defaultdict
from importlib.resources import files
import json

from BaseClasses import CollectionState
from Options import OptionError
from rule_builder.rules import True_, And, Has, Or
from .EntranceOptions import ENTRANCE_OPTIONS
from .SceneTransitions import region_name
from ._vendor_oot_soh.Enums import Regions, Items, Events
from ._vendor_oot_soh.Regions import SohRegion
from ._vendor_oot_soh import LogicHelpers as H
from .EnemyRoomLogic import GRAPH, NativeEnemyRegions

REVISION = 1
CATALOG = tuple(json.loads(files(__package__).joinpath('EntranceCatalog.json').read_text()))
ENDPOINTS = {e['id']: e for e in CATALOG}
KEY_DOORS = {3: ('FOREST_TEMPLE', 5), 4: ('FIRE_TEMPLE', 8), 5: ('WATER_TEMPLE', 6),
             6: ('SPIRIT_TEMPLE', 5), 7: ('SHADOW_TEMPLE', 5), 8: ('BOTTOM_OF_THE_WELL', 3),
             11: ('TRAINING_GROUND', 9), 13: ('GANONS_CASTLE', 2)}
DUNGEON_ROUTES = json.loads(files(__package__).joinpath('DungeonLocationRoutes.json').read_text())
CATEGORIES = dict(zip(('interiors', 'dungeons', 'grottos', 'bosses', 'one_ways', 'owls',
                      'warp_songs', 'child_spawn', 'adult_spawn', 'dungeon_doors'), ENTRANCE_OPTIONS))


def enabled(world):
    return any(getattr(world.options, option).value for option in CATEGORIES.values())


def enabled_categories(world):
    return {key for key, option in CATEGORIES.items() if getattr(world.options, option).value}


def restore_legacy_defaults(world):
    if world.using_ut and 'entrance_randomizer' not in world.passthrough:
        for key, cls in ENTRANCE_OPTIONS.items():
            setattr(world.options, key, cls.from_any(set() if key == 'mixed_entrance_pools' else 0))


def prepare_location_routes(world):
    """Compile exact local collection routes before native action sites install."""
    if not enabled(world): return
    world._er_local_item_rules = defaultdict(list)
    world._er_locations = {}
    compiler = world._extreme_room_compiler
    for location in world.get_locations():
        address = location.address if location.address is not None else world.location_name_to_id.get(location.name)
        routes = DUNGEON_ROUTES.get(str(address))
        if not routes: continue
        compiler.location = location.name
        proxy = SohRegion('EXTREME Entrance Collection: '+location.name, world.player, world.multiworld)
        world.multiworld.regions.append(proxy)
        alternatives = defaultdict(list)
        for route in routes:
            rr = route['region']
            alternatives[rr].append(compiler.expr(route['condition'], rr))
        for rr, rules in alternatives.items():
            H.connect_regions(NativeEnemyRegions[rr], world, [(proxy.name, Or(*rules))])
        world._er_locations[location.name] = proxy


def _disconnect(edge):
    if edge.connected_region is not None:
        edge.connected_region.entrances.remove(edge)
    edge.parent_region.exits.remove(edge)
    edge.connected_region = None


def _native_stock_bindings():
    aliases = {'BOTW': 'BOTTOM_OF_THE_WELL', 'DODONGOS_CAVERN_BOSS_AREA': 'DODONGOS_CAVERN_BOSS_REGION',
               'GANONS_TOWER_BEFORE_GANONDORF_LAIR': 'GANONS_TOWER_BEFORE_GANONDORFS_LAIR',
               'GANONS_TOWER_GANONDORF_LAIR': 'GANONDORFS_LAIR', 'GANONS_CASTLE_GANON_ARENA': 'GANONS_ARENA'}
    result = defaultdict(list)
    for rr in GRAPH:
        token = rr[3:]
        if token.startswith('BOTW_'): token = 'BOTTOM_OF_THE_WELL_'+token[5:]
        token = aliases.get(token, token)
        if token in Regions.__members__: result[str(Regions[token])].append(rr)
    return result


def finalize_room_graph(world):
    """Retire the contracted vanilla dungeon graph; never leave bypass edges.

Old region names remain as read-only reachability views for inherited local
events/helpers. All traversal uses the exact native room graph.
"""
    if not enabled(world): return
    bindings = _native_stock_bindings()
    # Include contracted parents that have no native enum equivalent. Their
    # read-only view is the union of their actual collection rooms.
    for name, proxy in world._er_locations.items():
        location = world.get_location(name)
        parent = location.parent_region
        if parent.name not in {str(r) for r in Regions} or parent.name == str(Regions.ROOT): continue
        for edge in proxy.entrances:
            rr = next(k for k, v in NativeEnemyRegions.__members__.items() if str(v) == edge.parent_region.name)
            if rr not in bindings[parent.name]: bindings[parent.name].append(rr)
    world._er_stock_to_native = bindings
    # Save source predicates before disconnecting stock exit edges.
    world._er_stock_edges = {(r.name, e.connected_region.name): e.access_rule
                             for r in world.get_regions() for e in r.exits if e.connected_region}
    for name, rr_list in bindings.items():
        stock = world.get_region(name)
        for edge in list(stock.exits): _disconnect(edge)
        for incoming in list(stock.entrances):
            # Physical external ingress is redirected to the exact native entry.
            # No stock dungeon node retains traversal into another room.
            if incoming.parent_region.name in bindings: continue
            incoming.connected_region.entrances.remove(incoming)
            incoming.connect(world.get_region(str(NativeEnemyRegions[rr_list[0]])))
        for rr in rr_list:
            H.connect_regions(NativeEnemyRegions[rr], world, [(name, True_())])
    for name, proxy in world._er_locations.items():
        location = world.get_location(name)
        location._er_display_region = location.parent_region.name
        location.parent_region.locations.remove(location)
        location.parent_region = proxy
        proxy.locations.append(location)
        rules = world._er_local_item_rules.get(name, [])
        world.set_rule(location, And(*rules) if rules else True_())
    # The private graph normally stops at dungeon boundaries. ER needs the
    # physical exits too, with the exact source action predicate.
    external = json.loads(files(__package__).joinpath('DungeonExternalEdges.json').read_text())
    for e in external:
        H.connect_regions(NativeEnemyRegions[e['source']], world,
                          [(region_name(e['target']), world._extreme_room_compiler.expr(e['condition'], e['source']))])


def _source_rule(world, row):
    source = world.get_region(region_name(row['source']))
    target = region_name(row['target'])
    if 'condition' in row:
        rule = world._extreme_room_compiler.expr(row['condition'], row['source']).resolve(world)
    elif row.get('traversal_rule') == 'day':
        rule = H.at_day((Regions[row['source']], world)).resolve(world)
    else:
        edges = [e for e in source.exits if e.connected_region and e.connected_region.name == target]
        if len(edges) != 1:
            # Synthetic boss returns have no physical reverse door. They are
            # arrival targets only; do not invent a usable exit in logic.
            if row['category'] == 'bosses' and not row['primary'] and not edges:
                return None
            raise OptionError(f"Entrance source route is ambiguous or missing: {row['name']} ({len(edges)})")
        rule = edges[0].access_rule
    extras = []
    if row['door'] >= 0 and world.options.shuffle_dungeon_doors.value:
        # A new arrival can approach either side of an unopened physical lock.
        # Vanilla cumulative counts and free reverse edges assume a particular
        # route. Require the complete key budget for shuffled small-key doors;
        # this remains safe after spending keys on any other shuffled branch.
        actor, params = row['actor'], row['params']
        small = (actor == 46 and (params >> 6) & 15 == 11) or (actor == 9 and (params >> 7) & 7 == 1)
        if small:
            dungeon, count = KEY_DOORS[row['source_scene']]
            extras.append(H.small_keys(Items[dungeon+'_SMALL_KEY'], count, (source, world)).resolve(world))
    early_pot_door = row['source_scene'] == 10 and row['door'] in (6, 7) and world.options.shuffle_pots.value in (1, 3)
    if 'extra_condition' in row and not early_pot_door:
        extras.append(world._extreme_room_compiler.expr(row['extra_condition'], row['source']).resolve(world))
    if row.get('gate') == 'swim': extras.append(H.can_swim((source, world)).resolve(world))
    if row.get('gate') == 'horse': extras.append(H.can_use(Items.EPONA, (source, world)).resolve(world))
    return (lambda state, base=rule, extras=tuple(extras): base(state) and all(e(state) for e in extras)) if extras else rule


def _eligible(world):
    cats = enabled_categories(world)
    result = []
    for e in CATALOG:
        if e['category'] not in cats: continue
        if e['category'] == 'dungeon_doors' and e['reverse'] < 0:
            # A physically unopenable reverse stays unopenable. Forward-only
            # dungeon shutters join the directed pool when one-ways is enabled.
            if 'one_ways' not in cats: continue
        result.append(e)
    return result


def validate_mapping(world, mapping):
    eligible = {e['id'] for e in _eligible(world)}
    if set(mapping) != eligible:
        raise OptionError('Entrance mapping does not match the enabled source pools')
    mixed = set(world.options.mixed_entrance_pools.value)
    for source, dest in mapping.items():
        if type(source) is not int or type(dest) is not int:
            raise OptionError('Entrance mapping endpoints must be integers')
        a, b = ENDPOINTS[source], ENDPOINTS.get(dest)
        if b is None: raise OptionError(f'Unknown entrance destination {dest}')
        if a['reverse'] >= 0:
            if b['reverse'] < 0 or mapping.get(b['reverse']) != a['reverse']:
                raise OptionError('Unpaired entrance mapping; decoupled entrances are not supported')
            if a['category'] != b['category'] and not {a['category'], b['category']} <= mixed:
                raise OptionError('Entrance destination crosses pools without mixed entrances enabled')
        elif dest != source and dest not in {e['id'] for e in _one_way_targets(world, a)}:
            raise OptionError('One-way destination is outside its selected pool')


def _one_way_targets(world, source):
    mixed = set(world.options.mixed_entrance_pools.value)
    if source['category'] in mixed:
        return [e for e in CATALOG if e['category'] in mixed & enabled_categories(world) and e['primary']]
    return [e for e in CATALOG if e['category'] in ('overworld', 'owls', 'warp_songs')]


def _candidate(world):
    eligible = _eligible(world); mixed = set(world.options.mixed_entrance_pools.value)
    pools = defaultdict(list); one_ways = []
    for e in eligible:
        if e['reverse'] < 0: one_ways.append(e)
        elif e['primary']: pools['mixed' if e['category'] in mixed else e['category']].append(e)
    mapping = {}
    for pool in pools.values():
        targets = pool.copy(); world.random.shuffle(targets)
        for source, dest in zip(pool, targets):
            mapping[source['id']] = dest['id']
            mapping[dest['reverse']] = source['reverse']
    for source in one_ways:
        if source['category'] in mixed:
            targets = [e for e in CATALOG if e['category'] in mixed & enabled_categories(world)
                       and e['primary'] and e['category'] != 'blue_warps']
        else:
            # Safe authored overworld arrival points; independently sampled, so
            # owl flights and songs may land in the same area.
            targets = [e for e in CATALOG if e['category'] in ('overworld', 'owls', 'warp_songs')]
        mapping[source['id']] = world.random.choice(targets)['id']
    return mapping


def connect(world):
    if not enabled(world):
        world._er_mapping = {}; return
    rows = _eligible(world)
    baseline = world.multiworld.get_all_state(False)
    required = [loc for loc in world.get_locations() if loc.address is not None and loc.can_reach(baseline)]
    # Include blue warps: defeating a shuffled boss must lead back through its
    # paired route, including a boss chamber reached from a house or room door.
    blue = [e for e in CATALOG if e['category'] == 'blue_warps']
    sources = rows + blue
    rules = {e['id']: _source_rule(world, e) for e in sources}
    checks = {l.address: l for l in world.get_locations() if l.address is not None}
    for row in sources:
        location = checks.get(row['check_id'])
        if location is None or rules[row['id']] is None: continue
        location.parent_region.locations.remove(location)
        location.parent_region = world.get_region(region_name(row['source']))
        location.parent_region.locations.append(location)
        location.access_rule = rules[row['id']]
    edges = {}
    # Multiple physical doorways can share an AP edge. Replace that aggregate
    # with one edge per actual source endpoint, retaining every source gate.
    for row in sources:
        if rules[row['id']] is None: continue
        source = world.get_region(region_name(row['source']))
        target = world.get_region(region_name(row['target']))
        for edge in list(source.exits):
            if edge.connected_region is target and not edge.name.startswith('EXTREME Shuffled Entrance '):
                _disconnect(edge)
        edge = source.create_exit('EXTREME Shuffled Entrance '+str(row['id']))
        edge.access_rule = rules[row['id']]
        edge.connect(target)
        edges[row['id']] = edge
    def apply(mapping):
        routes = dict(mapping)
        for warp in blue:
            boss = next((e for e in CATALOG if e['category'] == 'bosses' and e['primary']
                         and e['target'] == warp['source']), None)
            if boss and boss['reverse'] in mapping:
                routes[warp['id']] = mapping[boss['reverse']]
            elif 'dungeons' in enabled_categories(world):
                # Vanilla boss chamber in a shuffled dungeon: its blue warp
                # exits through the dungeon's paired overworld connection.
                entry = next((e for e in CATALOG if e['category'] == 'dungeons' and not e['primary']
                              and region_name(e['target']) == region_name(warp['target'])), None)
                if entry and entry['id'] in mapping: routes[warp['id']] = mapping[entry['id']]
        for id, edge in edges.items():
            edge.connected_region.entrances.remove(edge)
            edge.connect(world.get_region(region_name(ENDPOINTS[routes.get(id, id)]['target'])))
        world.multiworld._all_state_cache = None
        world._er_mapping = routes
        world._er_labels = {ENDPOINTS[k]["check_id"]: "Shuffled: "+ENDPOINTS[k]["name"].split(" -> ", 1)[0]+" -> "+ENDPOINTS[v]["name"].split(" -> ", 1)[-1]
                            for k, v in routes.items() if ENDPOINTS[k]["check_id"]}
    if world.using_ut:
        saved = world.passthrough.get('entrance_randomizer', {})
        if saved.get('revision') != REVISION: raise OptionError('Unsupported entrance mapping revision')
        mapping = {int(k): v for k, v in saved.get('connections', {}).items() if int(k) in {e['id'] for e in rows}}
        validate_mapping(world, mapping); apply(mapping)
        if world._er_mapping != {int(k): v for k, v in saved['connections'].items()}:
            raise OptionError('Entrance mapping blue-warp return data differs from this world')
        return
    # Use the actual fully configured AP rules, including abilities/souls and
    # native action events. A topological graph-only check is insufficient.
    # Start with the known connected topology and randomize by validated pair
    # swaps. This avoids exponentially unlikely whole-pool retries when many
    # interiors have age restrictions or several physical exits.
    mapping = {e['id']: e['id'] for e in rows}
    mixed = set(world.options.mixed_entrance_pools.value)
    pools = defaultdict(list)
    for e in rows:
        if e['primary'] and e['reverse'] >= 0:
            pools['mixed' if e['category'] in mixed else e['category']].append(e['id'])
    accepted = 0
    def viable(candidate):
        apply(candidate)
        state = world.multiworld.get_all_state(False)
        return all(loc.can_reach(state) for loc in required)
    for pool in pools.values():
        order = pool * 3
        world.random.shuffle(order)
        for first in order:
            second = world.random.choice(pool)
            if first == second: continue
            candidate = dict(mapping)
            a, b = mapping[first], mapping[second]
            candidate[first], candidate[second] = b, a
            candidate[ENDPOINTS[b]['reverse']] = ENDPOINTS[first]['reverse']
            candidate[ENDPOINTS[a]['reverse']] = ENDPOINTS[second]['reverse']
            if viable(candidate): mapping = candidate; accepted += 1
    for source in (e for e in rows if e['reverse'] < 0):
        for _ in range(50):
            candidate = dict(mapping)
            candidate[source['id']] = _candidate(world)[source['id']]
            if viable(candidate): mapping = candidate; accepted += 1; break
    validate_mapping(world, mapping)
    apply(mapping)
    world._er_generation_attempts = accepted



def slot_data(world):
    return {'revision': REVISION, 'disabled_actions': getattr(world, '_er_disabled_actions', []), 'connections': {str(k): v for k, v in sorted(getattr(world, '_er_mapping', {}).items())}}


def native_settings(world):
    cats = enabled_categories(world); mixed = set(world.options.mixed_entrance_pools.value)
    result = {'EntranceRandomizerRevision': REVISION if cats else 0, 'DecoupleEntrances': 0,
              'ShuffleInteriorsEntrances': 2 if 'interiors' in cats else 0,
              'ShuffleThievesHideoutEntrances': int('interiors' in cats),
              'ShuffleDungeonsEntrances': 2 if 'dungeons' in cats else 0,
              'ShuffleGanonTowerEntrance': int('dungeons' in cats),
              'ShuffleBossEntrances': 2 if 'bosses' in cats else 0,
              'ShuffleGrottosEntrances': int(bool(cats)),
              'ShuffleOverworldEntrances': int('one_ways' in cats),
              'ShuffleOwlDrops': int('owls' in cats), 'ShuffleWarpSongs': int('warp_songs' in cats),
              'ShuffleOverworldSpawns': int(bool(cats & {'child_spawn', 'adult_spawn'})),
              'MixedEntrances': int(bool(mixed)), 'MixGrottos': int(bool(cats)),
              'ShuffleDungeonDoors': int('dungeon_doors' in cats)}
    result.update({'EntranceMap.'+str(k): v for k, v in getattr(world, '_er_mapping', {}).items()})
    return result


def prune_obsolete_actions(world):
    if not enabled(world): return
    internal = {loc.name: loc for loc in world.get_locations()
                if loc.address is None and loc.locked and loc.name not in world.location_name_to_id
                and loc.item and loc.item.name != str(Events.GAME_COMPLETED)}
    if world.using_ut:
        disabled = world.passthrough['entrance_randomizer'].get('disabled_actions', [])
        if set(disabled) - internal.keys(): raise OptionError('Unknown entrance action manifest entry')
    else:
        state = world.multiworld.get_all_state(False)
        disabled = sorted(name for name, loc in internal.items() if not loc.can_reach(state))
    for name in disabled:
        loc = internal[name]
        loc.parent_region.locations.remove(loc)
    world._er_disabled_actions = disabled
