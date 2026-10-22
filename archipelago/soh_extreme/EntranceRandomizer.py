"""Authoritative, coupled physical entrance shuffle shared by AP and UT.

Traversal predicates belong to source endpoints. A routed arrival adds its own
physical hazards, never the old source's requirements. Crossing checks retain
source-only credit. One-way routes add exactly one directed edge.
"""
from collections import defaultdict
from importlib.resources import files
import json

from BaseClasses import CollectionState, ItemClassification, LocationProgressType
from Options import OptionError
from rule_builder.rules import True_, And, Has, Or, Rule
from .EntranceOptions import ENTRANCE_OPTIONS
from . import EntranceSafety as Safety
from .SceneTransitions import region_name
from .CheckDescriptions import shuffled_check_label
from ._vendor_oot_soh.Enums import Regions, Items, Events, Ages
from ._vendor_oot_soh.Regions import SohRegion
from ._vendor_oot_soh.Items import SohItem
from ._vendor_oot_soh import LogicHelpers as H
from .EnemyRoomLogic import GRAPH, NativeEnemyRegions

REVISION = 1
# Revision 1 partitions unmixed room doors by their physical dungeon scene.
# Keep topology revision separate so earlier saved maps can still be restored.
POOL_POLICY_REVISION = 1
RIVER_PATH_REVISION = 1
# These are four physical crossings. Earlier seeds stored only the land pair.
# The aliases below are for restoring those saved destinations, never new pools.
RIVER_WATER_ALIASES = {473: 234, 785: 385}
CATALOG = tuple(json.loads(files(__package__).joinpath('EntranceCatalog.json').read_text()))
Safety.validate_catalog(CATALOG)
ENDPOINTS = {e['id']: e for e in CATALOG}
# These six Jabu doors carry Ruto between her rescue rooms, the corridor,
# the Stinger room and Big Octo. A full shuffled scene load deletes held actors.
# Keep their two directions as explicit identity routes and let the native
# door/check path cross rooms without reloading the scene. Their checks remain
# in the pool. Keep this contract aligned with IsLocalCarrierDoor in C++.
LOCAL_CARRIER_DOORS = frozenset(e['id'] for e in CATALOG
                              if e['source_scene'] == 2 and e['door'] in {2, 4, 11, 12, 14, 21})
KEY_DOORS = {3: ('FOREST_TEMPLE', 5), 4: ('FIRE_TEMPLE', 8), 5: ('WATER_TEMPLE', 6),
             6: ('SPIRIT_TEMPLE', 5), 7: ('SHADOW_TEMPLE', 5), 8: ('BOTTOM_OF_THE_WELL', 3),
             11: ('TRAINING_GROUND', 9), 13: ('GANONS_CASTLE', 2)}
DUNGEON_ROUTES = json.loads(files(__package__).joinpath('DungeonLocationRoutes.json').read_text())
# Reviewed main-water-body arrivals: the lower doors are dry at Low, and the
# middle doors are dry at Low or Mid. Otherwise the landing is submerged.
# Usable Iron Boots include Swim and the actual age requirement. Upper ledges
# and separate basement puzzle ledges must not inherit a scene-wide water gate.
WATER_ARRIVAL_LEVELS = {
    8860: 'WL_LOW', 8861: 'WL_LOW',
    8878: 'WL_LOW', 8879: 'WL_LOW',
    8862: 'WL_LOW_OR_MID', 8863: 'WL_LOW_OR_MID',
    8866: 'WL_LOW_OR_MID', 8867: 'WL_LOW_OR_MID',
}
CATEGORIES = {
    'overworld': 'shuffle_overworld_entrances',
    'interiors': 'shuffle_interior_entrances',
    'dungeons': 'shuffle_dungeon_entrances',
    'grottos': 'shuffle_grotto_entrances',
    'bosses': 'shuffle_boss_entrances',
    'one_ways': 'shuffle_one_way_entrances',
    'owls': 'shuffle_owl_drops',
    'warp_songs': 'shuffle_warp_songs',
    'child_spawn': 'shuffle_child_spawn',
    'adult_spawn': 'shuffle_adult_spawn',
    'dungeon_doors': 'shuffle_dungeon_doors',
}


def enabled(world):
    return any(getattr(world.options, option).value for option in CATEGORIES.values())


def enabled_categories(world):
    return {key for key, option in CATEGORIES.items() if getattr(world.options, option).value}


# Stable bits exported with the slot's native settings. Append future categories
# instead of reordering these; old saves retain their exact metadata.
MIXED_CATEGORY_BITS = {name: 1 << bit for bit, name in enumerate((
    'overworld', 'interiors', 'dungeons', 'grottos', 'bosses', 'one_ways',
    'owls', 'warp_songs', 'child_spawn', 'adult_spawn', 'dungeon_doors',
))}
DUNGEON_CATEGORIES = frozenset({'dungeons', 'bosses', 'dungeon_doors'})


def mixed_categories(world):
    """Return the enabled categories selected to mix; 'all' enables no shuffle."""
    selected = set(world.options.mixed_entrance_pools.value)
    enabled = enabled_categories(world)
    return enabled if 'all' in selected else selected & enabled


def dungeon_doors_are_mixed(world):
    mixed = mixed_categories(world)
    return 'dungeon_doors' in mixed and len(mixed) > 1


def dungeon_doors_mix_outside(world):
    mixed = mixed_categories(world)
    return 'dungeon_doors' in mixed and bool(mixed - DUNGEON_CATEGORIES)


def _paired_pool_key(row, mixed):
    # Selecting only room doors has no second category to mix with. Those doors
    # keep the same per-dungeon behavior as an empty mixed-pool selection.
    if row['category'] == 'dungeon_doors' and not ('dungeon_doors' in mixed and len(mixed) > 1):
        return ('dungeon_doors', row['source_scene'])
    return 'mixed' if row['category'] in mixed else row['category']


def _pool_policy_revision(world):
    if world.using_ut:
        return world.passthrough.get('entrance_randomizer', {}).get('pool_policy_revision', 0)
    return POOL_POLICY_REVISION


def _river_path_revision(world):
    if not world.using_ut:
        return RIVER_PATH_REVISION
    saved = world.passthrough.get('entrance_randomizer', {})
    revision = saved.get('river_path_revision')
    if revision is None:
        # Permit maps assembled by older tools that already carry explicit
        # water IDs; truly old server maps have neither water endpoint.
        connections = saved.get('connections', {})
        revision = int(any(str(endpoint) in connections or endpoint in connections
                           for endpoint in RIVER_WATER_ALIASES)
                       or any(target in RIVER_WATER_ALIASES for target in connections.values()))
    if type(revision) is not int or revision not in (0, RIVER_PATH_REVISION):
        raise OptionError("Unsupported Zora's River entrance policy")
    return revision


def _routed_destination(world, mapping, source):
    if source not in mapping and source in RIVER_WATER_ALIASES and _river_path_revision(world) == 0:
        return mapping.get(RIVER_WATER_ALIASES[source], source)
    return mapping.get(source, source)


def restore_legacy_defaults(world):
    if not world.using_ut: return
    if 'entrance_randomizer' not in world.passthrough:
        for key, cls in ENTRANCE_OPTIONS.items():
            setattr(world.options, key, cls.from_any(set() if key == 'mixed_entrance_pools' else 0))
        return
    # Earlier mapped seeds did not have a paired overworld pool. A new local
    # template must not add endpoints that are absent from the server's map.
    snapshot = world.passthrough.get('extreme_all_options', world.passthrough)
    option = 'shuffle_overworld_entrances'
    if option not in snapshot and option not in world.passthrough:
        setattr(world.options, option, ENTRANCE_OPTIONS[option].from_any(0))


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
    source_key = (NativeEnemyRegions[row['source']] if row['source'].startswith('RR_')
                  else Regions[row['source']])
    bundle = (source_key, world)
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
            extras.append(H.small_keys(Items[dungeon+'_SMALL_KEY'], count, bundle).resolve(world))
    early_pot_door = row['source_scene'] == 10 and row['door'] in (6, 7) and world.options.shuffle_pots.value in (1, 3)
    if 'extra_condition' in row and not early_pot_door:
        extras.append(world._extreme_room_compiler.expr(row['extra_condition'], row['source']).resolve(world))
    if row.get('gate') == 'swim': extras.append(H.can_swim(bundle).resolve(world))
    if row.get('gate') == 'horse': extras.append(H.can_use(Items.EPONA, bundle).resolve(world))
    components = (rule, *extras)
    dependencies = tuple(part for part in components if isinstance(part, Rule.Resolved))
    for part in dependencies:
        # These physical predicates are newly compiled outside create_entrance.
        # Without registration a cached "missing key/soul" result never changes
        # when that item is received, despite a fresh full-inventory state passing.
        world.register_rule_dependencies(part)
    def combined(state):
        return all(part(state) for part in components)
    combined._er_dependencies = dependencies
    return combined


def _arrival_rule(world, row):
    if row.get('arrival_gate') == 'swim':
        # A dry source can be paired with a water landing. Its crossing check
        # still uses the dry source rule, but entering the destination needs Swim.
        rule = H.can_swim((Regions[row['target']], world)).resolve(world)
    else:
        level = WATER_ARRIVAL_LEVELS.get(row['id'])
        if level is None:
            return None
        rule = world._extreme_room_compiler.expr(
            f'WaterLevel({level}) || CanUse(RG_IRON_BOOTS)', row['target']).resolve(world)
    world.register_rule_dependencies(rule)
    return rule


def _routed_rule(source_rule, arrival_rule):
    if arrival_rule is None:
        return source_rule
    def combined(state):
        return source_rule(state) and arrival_rule(state)
    combined._er_dependencies = (*getattr(source_rule, '_er_dependencies', ()), arrival_rule)
    return combined


def _eligible(world):
    cats = enabled_categories(world)
    result = []
    for e in CATALOG:
        if e['category'] not in cats: continue
        if e['id'] in RIVER_WATER_ALIASES and _river_path_revision(world) == 0: continue
        if e['category'] == 'dungeon_doors' and e['reverse'] < 0:
            # A physically unopenable reverse stays unopenable. Forward-only
            # dungeon shutters join the directed pool when one-ways is enabled.
            if 'one_ways' not in cats: continue
        result.append(e)
    return result


def validate_mapping(world, mapping, *, legacy_dungeon_pools=False):
    eligible = {e['id'] for e in _eligible(world)}
    if set(mapping) != eligible:
        raise OptionError('Entrance mapping does not match the enabled source pools')
    mixed = mixed_categories(world)
    for source, dest in mapping.items():
        if type(source) is not int or type(dest) is not int:
            raise OptionError('Entrance mapping endpoints must be integers')
        a, b = ENDPOINTS[source], ENDPOINTS.get(dest)
        if b is None: raise OptionError(f'Unknown entrance destination {dest}')
        if not Safety.allowed_route(source, dest):
            raise OptionError('Entrance destination is unreviewed or incompatible with the source age')
        if (not legacy_dungeon_pools and a['category'] == 'dungeon_doors'
                and not dungeon_doors_are_mixed(world)
                and (b['category'] != 'dungeon_doors' or b['source_scene'] != a['source_scene'])):
            raise OptionError('Unmixed dungeon room doors must stay inside their own dungeon')
        if source in LOCAL_CARRIER_DOORS and dest != source:
            raise OptionError(
                'This seed shuffles a Jabu-Jabu door needed to carry Ruto. '
                'Generate a new seed with the matching SOH-EXTREME APWorld.'
            )
        if a['reverse'] >= 0:
            if b['reverse'] < 0 or mapping.get(b['reverse']) != a['reverse']:
                raise OptionError('Unpaired entrance mapping; decoupled entrances are not supported')
            if a['category'] != b['category'] and not {a['category'], b['category']} <= mixed:
                raise OptionError('Entrance destination crosses pools without mixed entrances enabled')
        elif dest != source and dest not in {e['id'] for e in _one_way_targets(
                world, a, legacy_dungeon_pools=legacy_dungeon_pools)}:
            raise OptionError('One-way destination is outside its selected pool')


def _one_way_targets(world, source, *, legacy_dungeon_pools=False):
    mixed = mixed_categories(world)
    if (source['category'] == 'dungeon_doors' and not legacy_dungeon_pools
            and not dungeon_doors_are_mixed(world)):
        # Forward-only shutters remain dungeon doors, even though the one-way
        # option is needed to shuffle them. They must not inherit the ordinary
        # river/fence destinations outside their dungeon.
        targets = [e for e in CATALOG if e['category'] == 'dungeon_doors'
                   and e['source_scene'] == source['source_scene'] and e['primary']]
    elif source['category'] in mixed:
        targets = [e for e in CATALOG if e['category'] in mixed & enabled_categories(world) and e['primary']]
    else:
        targets = [e for e in CATALOG if e['category'] in ('overworld', 'owls', 'warp_songs')]
    return [e for e in targets if Safety.allowed_route(source['id'], e['id'])
            and not (e['id'] in RIVER_WATER_ALIASES and _river_path_revision(world) == 0)]


def _candidate(world):
    eligible = _eligible(world); mixed = mixed_categories(world)
    pools = defaultdict(list); one_ways = []
    for e in eligible:
        if e['reverse'] < 0: one_ways.append(e)
        elif e['primary'] and e['id'] not in LOCAL_CARRIER_DOORS:
            pools[_paired_pool_key(e, mixed)].append(e)
    mapping = {e['id']: e['id'] for e in eligible if e['id'] in LOCAL_CARRIER_DOORS}
    for pool in pools.values():
        targets = pool.copy(); world.random.shuffle(targets)
        for source, dest in zip(pool, targets):
            mapping[source['id']] = dest['id']
            mapping[dest['reverse']] = source['reverse']
    for source in one_ways:
        targets = _one_way_targets(world, source)
        if not targets:
            raise OptionError('No reviewed, age-compatible one-way destination is enabled')
        mapping[source['id']] = world.random.choice(targets)['id']
    return mapping


def _is_default_spawn(source, target):
    # Physical aliases share a scene: child spawn and house entry; adult spawn,
    # Temple entrance and Prelude pad. Fresh shuffled spawns must leave home.
    return (source['category'] in ('child_spawn', 'adult_spawn')
            and ENDPOINTS[target]['scene'] == source['scene'])


def _validate_spawn_pools(world, rows):
    for source in rows:
        if source['category'] not in ('child_spawn', 'adult_spawn'): continue
        if not any(not _is_default_spawn(source, target['id'])
                   for target in _one_way_targets(world, source)):
            name = source['category'].replace('_', ' ')
            raise OptionError(
                f'No alternate {name} destination exists in the enabled mixed entrance pools. '
                'Enable another destination category or use separate pools '
                '(mixed_entrance_pools: []).'
            )


def _place_one_way(world, mapping, source, viable, *, allow_failure=False):
    """Try each allowed arrival once in seeded random order.

    Sampling a few times with replacement can miss the only playable starts in
    a large mixed pool. Draw destinations directly, without generating and
    discarding unrelated paired mappings or another age's spawn.
    """
    targets = list(dict.fromkeys(target['id'] for target in _one_way_targets(world, source)
                                 if not _is_default_spawn(source, target['id'])))
    world.random.shuffle(targets)
    for target in targets:
        candidate = dict(mapping)
        candidate[source['id']] = target
        if viable(candidate): return candidate
    if source['category'] in ('child_spawn', 'adult_spawn') and not allow_failure:
        name = source['category'].replace('_', ' ')
        raise OptionError(
            f'No playable alternate {name} was found after checking all '
            f'{len(targets)} allowed destinations. A start needs reachable '
            'progression beyond Link\'s Pocket, a usable return, and a route '
            'to Hyrule Field with the configured starting inventory.'
        )
    return None


def _place_spawns(world, mapping, rows, viable, *, allow_failure=False):
    """Establish the actual starting age first, then the other enabled spawn."""
    starting = 'adult_spawn' if world.options.starting_age == 'adult' else 'child_spawn'
    spawns = [row for row in rows if row['category'] in ('child_spawn', 'adult_spawn')]
    spawns.sort(key=lambda row: row['category'] != starting)
    result = mapping
    for source in spawns:
        candidate = _place_one_way(world, result, source, viable, allow_failure=allow_failure)
        if candidate is None: return None
        result = candidate
    return result


def _reachable_as_age(world, state, spot, age):
    """Use one age's own region fixed point and restore the caller's context."""
    previous = state._soh_extreme_age[world.player]
    try:
        state._soh_extreme_age[world.player] = age
        if hasattr(spot, 'can_reach_as_age'):
            return spot.can_reach_as_age(state, age)
        return spot.can_reach(state)
    finally:
        state._soh_extreme_age[world.player] = previous


def _reachable_at_starting_age(world, state, spot):
    """Use the selected age, including the world's normal age-specific rules."""
    age = Ages.ADULT if world.options.starting_age == 'adult' else Ages.CHILD
    return _reachable_as_age(world, state, spot, age)


def _age_routes_are_safe(world, mapping, edges, state):
    """Prove that every physically reachable route accepts its actual age.

    Interior return doors are not inherently child-only or adult-only. A mixed
    entrance, song or spawn can expose them to a different age. Check the
    candidate's fresh, fully swept inventory state, including restricted
    identity exits whose shuffle category is disabled. Do not hide a bad
    physical route by adding a destination age predicate to the AP graph.
    """
    for row in CATALOG:
        target = mapping.get(row['id'], row['id'])
        allowed = Safety.arrival_age_mask(target)
        if not allowed:
            return False
        if allowed == Safety.BOTH:
            continue
        edge = edges.get(row['id'])
        if edge is not None:
            physical_edges = (edge,)
        elif row['category'] == 'bosses' and not row['primary']:
            # This synthetic return has no physical door. The actual boss exit
            # is the derived blue warp, which is checked separately.
            continue
        else:
            source = world.get_region(region_name(row['source']))
            physical_edges = tuple(edge for edge in source.exits
                                   if edge.connected_region is not None
                                   and edge.connected_region.name == region_name(row['target']))
            if not physical_edges:
                raise OptionError('Cannot verify the age requirements of entrance: ' + row['name'])
        for age, bit in ((Ages.CHILD, Safety.CHILD), (Ages.ADULT, Safety.ADULT)):
            if not allowed & bit and any(_reachable_as_age(world, state, edge, age)
                                         for edge in physical_edges):
                return False
    return True


def _initial_state_for_age(world, age):
    """A fresh private spawn probe with only configured items and local prefill.

    Testing the later age assumes only that time travel has occurred. This
    private event opens that age's root; it adds no equipment, song, ability,
    soul, starting item or event to the generated seed or its real state.
    """
    state = CollectionState(world.multiworld)
    starting_age = Ages.ADULT if world.options.starting_age == 'adult' else Ages.CHILD
    if age != starting_age:
        state.collect(SohItem(str(Events.TIME_TRAVEL), ItemClassification.progression,
                              None, world.player), True)
    state.sweep_for_advancements(locations=[
        loc for loc in world.get_locations()
        if loc.item is not None and loc.item.player == world.player
    ])
    return state


def _spawn_return_is_usable(world, state, target, edges, age):
    if target['reverse'] < 0:
        return True
    # A paired arrival must leave its actual reverse usable. Synthetic boss
    # returns are not physical doors and cannot certify a safe spawn.
    reverse = ENDPOINTS[target['reverse']]
    return_edge = edges.get(reverse['id'])
    if return_edge is None:
        source = world.get_region(region_name(reverse['source']))
        destination = region_name(reverse['target'])
        return_edges = [edge for edge in source.exits
                        if edge.connected_region is not None
                        and edge.connected_region.name == destination]
    else:
        return_edges = (return_edge,)
    return any(_reachable_as_age(world, state, edge, age) for edge in return_edges)


def _starting_state_is_viable(world, mapping, edges, fill_locations):
    """Prove the selected start and each enabled age's own save/spawn escape.

    Rebuild these states after every topology change. A full-inventory route,
    another age's reachability, or Link's Pocket cannot certify a playable
    spawn. Unmapped vanilla starts retain their ordinary progression rules.
    """
    starting_age = Ages.ADULT if world.options.starting_age == 'adult' else Ages.CHILD
    state = _initial_state_for_age(world, starting_age)
    category = 'adult_spawn' if starting_age == Ages.ADULT else 'child_spawn'
    spawn = next(e for e in CATALOG if e['category'] == category)

    # The Water Temple's ordinary entrance and room-door arrivals can start
    # submerged. Both spawns must be safe with the configured initial Swim.
    if world.options.shuffle_swim.value and not state.has('Swim', world.player):
        for row in CATALOG:
            if row['category'] not in ('child_spawn', 'adult_spawn'):
                continue
            if row['id'] != spawn['id'] and row['id'] not in mapping:
                continue
            if ENDPOINTS[mapping.get(row['id'], row['id'])]['scene'] == 5:
                return False

    for row in CATALOG:
        if row['category'] not in ('child_spawn', 'adult_spawn') or row['id'] not in mapping:
            continue
        age = Ages.CHILD if row['category'] == 'child_spawn' else Ages.ADULT
        bit = Safety.CHILD if age == Ages.CHILD else Safety.ADULT
        target = ENDPOINTS[mapping[row['id']]]
        if not Safety.allowed_age(target['id'], bit):
            return False
        probe = state if age == starting_age else _initial_state_for_age(world, age)
        if not _spawn_return_is_usable(world, probe, target, edges, age):
            return False
        # Door checks in a closed component are not a usable way out. The
        # other age is tested with its own root and physical exit predicates.
        if not _reachable_as_age(world, probe, world.get_region(str(Regions.HYRULE_FIELD)), age):
            return False

    if not fill_locations:
        return True
    return any(loc.parent_region.name != str(Regions.ROOT)
               and loc.progress_type != LocationProgressType.EXCLUDED
               and _reachable_as_age(world, state, loc, starting_age)
               for loc in fill_locations)


def _physical_start_is_connected(world, inventory, age=None):
    """Keep one age's start connected to the physical overworld.

    A small isolated room component can appear connected when a full-inventory
    probe assumes all warp songs, notes and buttons. Require a route to Hyrule
    Field without Ocarina in this private structural probe. Real starting-item,
    return-path and safe-water checks remain separate and are still mandatory.
    """
    starting_age = Ages.ADULT if world.options.starting_age == 'adult' else Ages.CHILD
    if age is None:
        age = starting_age
    state = inventory.copy()
    if age != starting_age:
        # This structural probe starts after that age has become available;
        # it must not need an instrument just to activate the other age's root.
        state.collect(SohItem(str(Events.TIME_TRAVEL), ItemClassification.progression,
                              None, world.player), True)
    ocarina_name = str(Items.PROGRESSIVE_OCARINA)
    if state.has(ocarina_name, world.player):
        ocarina = world.create_item(ocarina_name)
        while state.has(ocarina_name, world.player):
            state.remove(ocarina)
    # Do not regain an instrument from prefill while sweeping. This also keeps
    # the probe independent of remote players' future sends. Each candidate gets
    # a new unswept inventory copy, so rejected topology/events cannot leak in.
    state.sweep_for_advancements(locations=[
        loc for loc in world.get_locations()
        if loc.item is not None and loc.item.player == world.player
        and loc.item.name != ocarina_name
    ])
    return _reachable_as_age(world, state, world.get_region(str(Regions.HYRULE_FIELD)), age)


def connect(world):
    if not enabled(world):
        world._er_mapping = {}; return
    rows = _eligible(world)
    baseline = world.multiworld.get_all_state(False)
    required = [loc for loc in world.get_locations() if loc.address is not None and loc.can_reach(baseline)]
    # Include blue warps: defeating a shuffled boss must lead back through its
    # paired route, including a boss chamber reached from a house or room door.
    blue = [e for e in CATALOG if e['category'] == 'blue_warps']
    # Old maps share their land destinations with the omitted water crossings.
    # Materialize both physical sources for their own Swim/check rules while
    # keeping the saved map and its coupled land returns unchanged.
    legacy_water = ([ENDPOINTS[endpoint] for endpoint in RIVER_WATER_ALIASES]
                    if _river_path_revision(world) == 0 and 'overworld' in enabled_categories(world) else [])
    sources = rows + blue + legacy_water
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
        for dependency in getattr(edge.access_rule, '_er_dependencies', ()):
            world._register_rule_indirects(dependency, edge)
        edge.connect(target)
        edges[row['id']] = edge
    arrival_rules = {row['id']: _arrival_rule(world, row) for row in CATALOG
                     if row['id'] in WATER_ARRIVAL_LEVELS or row.get('arrival_gate')}
    routed_rules = {}
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
                              and boss and e['source_scene'] == boss['source_scene']), None)
                if entry and entry['id'] in mapping: routes[warp['id']] = mapping[entry['id']]
        for id, edge in edges.items():
            destination = _routed_destination(world, routes, id)
            edge.connected_region.entrances.remove(edge)
            edge.connect(world.get_region(region_name(ENDPOINTS[destination]['target'])))
            key = (id, destination)
            if key not in routed_rules:
                # Always compose from the immutable physical source predicate.
                # Candidate remaps must not retain a previous landing's gate.
                rule = _routed_rule(rules[id], arrival_rules.get(destination))
                for dependency in getattr(rule, '_er_dependencies', ()):
                    world._register_rule_indirects(dependency, edge)
                routed_rules[key] = rule
            edge.access_rule = routed_rules[key]
        world.multiworld._all_state_cache = None
        world._er_mapping = routes
        display_routes = dict(routes)
        display_routes.update({row['id']: _routed_destination(world, routes, row['id'])
                               for row in legacy_water})
        world._er_labels = {ENDPOINTS[k]["check_id"]: shuffled_check_label(ENDPOINTS[k], ENDPOINTS[v])
                            for k, v in display_routes.items() if ENDPOINTS[k]["check_id"]}
    if world.using_ut:
        saved = world.passthrough.get('entrance_randomizer', {})
        if saved.get('revision') != REVISION: raise OptionError('Unsupported entrance mapping revision')
        if saved.get('destination_policy_revision', Safety.POLICY_REVISION) != Safety.POLICY_REVISION:
            raise OptionError('Unsupported entrance destination safety policy')
        pool_revision = saved.get('pool_policy_revision', 0)
        if type(pool_revision) is not int or pool_revision not in (0, POOL_POLICY_REVISION):
            raise OptionError('Unsupported dungeon entrance pool policy')
        mapping = {int(k): v for k, v in saved.get('connections', {}).items() if int(k) in {e['id'] for e in rows}}
        validate_mapping(world, mapping, legacy_dungeon_pools=pool_revision == 0); apply(mapping)
        if world._er_mapping != {int(k): v for k, v in saved['connections'].items()}:
            raise OptionError('Entrance mapping blue-warp return data differs from this world')
        state = world.multiworld.get_all_state(False, perform_sweep=False).copy()
        state.sweep_for_advancements()
        if not _age_routes_are_safe(world, world._er_mapping, edges, state):
            raise OptionError('This entrance map can reach an age-incompatible arrival. '
                              'Generate a new seed with the matching SOH-EXTREME APWorld.')
        return
    # These fresh-generation guards never rewrite or reject an older saved
    # spawn merely because it legitimately used a default-home destination.
    _validate_spawn_pools(world, rows)
    # Use the actual fully configured AP rules, including abilities/souls and
    # native action events. A topological graph-only check is insufficient.
    # Start with the known connected topology and randomize by validated pair
    # swaps. This avoids exponentially unlikely whole-pool retries when many
    # interiors have age restrictions or several physical exits.
    mapping = {e['id']: e['id'] for e in rows}
    mixed = mixed_categories(world)
    pools = defaultdict(list)
    for e in rows:
        if e['primary'] and e['reverse'] >= 0 and e['id'] not in LOCAL_CARRIER_DOORS:
            pools[_paired_pool_key(e, mixed)].append(e['id'])
    accepted = 0
    inventory = world.multiworld.get_all_state(False, perform_sweep=False)
    fill_locations = [loc for loc in world.get_locations()
                      if loc.address is not None and loc.item is None]
    def viable(candidate):
        if any(not Safety.allowed_route(source, target) for source, target in candidate.items()):
            return False
        apply(candidate)
        if not _starting_state_is_viable(world, candidate, edges, fill_locations):
            return False
        probe_ages = {Ages.ADULT if world.options.starting_age == 'adult' else Ages.CHILD}
        probe_ages.update(Ages.CHILD if row['category'] == 'child_spawn' else Ages.ADULT
                          for row in rows if row['category'] in ('child_spawn', 'adult_spawn'))
        if any(not _physical_start_is_connected(world, inventory, age) for age in probe_ages):
            return False
        state = inventory.copy()
        state.sweep_for_advancements()
        return (_age_routes_are_safe(world, world._er_mapping, edges, state)
                and all(loc.can_reach(state) for loc in required))
    # Choose the real spawns on the connected base graph. Every later accepted
    # swap must preserve their starting access, rather than protecting a house
    # spawn that will be replaced at the end. If restrictive pools need a
    # rearranged graph before an alternate is possible, retain one bounded
    # fallback through the ordinary validated pair pass and retry all targets.
    spawn_mapping = _place_spawns(world, mapping, rows, viable, allow_failure=True)
    if spawn_mapping is not None:
        mapping = spawn_mapping
        accepted += sum(row['category'] in ('child_spawn', 'adult_spawn') for row in rows)
    else:
        apply(mapping)
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
    if spawn_mapping is None:
        mapping = _place_spawns(world, mapping, rows, viable)
        accepted += sum(row['category'] in ('child_spawn', 'adult_spawn') for row in rows)
    for source in (e for e in rows if e['reverse'] < 0
                   and e['category'] not in ('child_spawn', 'adult_spawn')):
        candidate = _place_one_way(world, mapping, source, viable)
        if candidate is not None: mapping = candidate; accepted += 1
    validate_mapping(world, mapping)
    apply(mapping)
    final_state = inventory.copy()
    final_state.sweep_for_advancements()
    if not _age_routes_are_safe(world, world._er_mapping, edges, final_state):
        raise OptionError('The entrance map contains a route to an age-incompatible arrival. '
                          'No unsafe entrance map was emitted.')
    if not _starting_state_is_viable(world, mapping, edges, fill_locations):
        raise OptionError(
            'No playable entrance start was found for the selected starting age and inventory. '
            'A start needs a reachable progression check beyond Link\'s Pocket, '
            'and a shuffled spawn must have a usable return and a route to '
            'Hyrule Field with the configured starting inventory.'
        )
    world._er_generation_attempts = accepted



def slot_data(world):
    return {'revision': REVISION, 'destination_policy_revision': Safety.POLICY_REVISION,
            'pool_policy_revision': _pool_policy_revision(world),
            'river_path_revision': _river_path_revision(world),
            'effective_mixed_categories': sorted(mixed_categories(world)),
            'dungeon_door_mixed_outside': int(dungeon_doors_mix_outside(world)),
            'disabled_actions': getattr(world, '_er_disabled_actions', []),
            'connections': {str(k): v for k, v in sorted(getattr(world, '_er_mapping', {}).items())}}


def native_settings(world):
    cats = enabled_categories(world); mixed = mixed_categories(world)
    result = {'EntranceRandomizerRevision': REVISION if cats else 0,
              'EntranceDestinationPolicyRevision': Safety.POLICY_REVISION if cats else 0,
              'EntrancePoolPolicyRevision': _pool_policy_revision(world) if cats else 0,
              'EntranceRiverPathsRevision': _river_path_revision(world) if cats else 0,
              'EntranceMixedPoolMask': sum(MIXED_CATEGORY_BITS[category] for category in mixed),
              'DungeonDoorMixedOutside': int(dungeon_doors_mix_outside(world)),
              'DecoupleEntrances': 0,
              'ShuffleInteriorsEntrances': 2 if 'interiors' in cats else 0,
              'ShuffleThievesHideoutEntrances': int('interiors' in cats),
              'ShuffleDungeonsEntrances': 2 if 'dungeons' in cats else 0,
              'ShuffleGanonTowerEntrance': int('dungeons' in cats),
              'ShuffleBossEntrances': 2 if 'bosses' in cats else 0,
              'ShuffleGrottosEntrances': int(bool(cats)),
              'ShuffleOverworldEntrances': int(bool(cats & {'overworld', 'one_ways'})),
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
