"""First traversal of physical scene portals and dungeon room doors.

The catalogue is shared with the native client. A directed crossing inherits
the fully resolved source entrance rule, after all ability/key/soul overlays.
Reaching a destination through some other entrance does not check this one.
"""
import json
from importlib.resources import files
from Options import OptionError
from worlds.generic.Rules import add_rule
from ._vendor_oot_soh import LogicHelpers as H
from ._vendor_oot_soh.Enums import Regions, Items, Ages
from ._vendor_oot_soh.Locations import SohLocation
from .CheckDescriptions import check_name
from .BoulderEntrances import BOULDER_BLOCKED_SCENE_CHECKS
from . import EntranceSafety as Safety

# Shared location IDs never change. Age-mode IDs are disjoint, permanent
# extensions; the native client uses the exact same offsets.
CATALOG_VERSION = 3
CHILD_CHECK_OFFSET = 20_000_000
ADULT_CHECK_OFFSET = 40_000_000
CATALOG = tuple(e for filename in ('SceneTransitionCatalog.json','DungeonDoorCatalog.json')
                for e in json.loads(files(__package__).joinpath(filename).read_text(encoding='utf-8')))
CATALOG = tuple(dict(entry, name=check_name(entry['id'], entry['name'])) for entry in CATALOG)

# Index age-independent identities too, so historical slot data and hint links
# stay stable. Age-specific entries have unique names and IDs.
NAME_TO_ID = {e['name']: e['id'] for e in CATALOG}
for _entry in CATALOG:
    NAME_TO_ID[_entry['name'] + ' [Child]'] = _entry['id'] + CHILD_CHECK_OFFSET
    NAME_TO_ID[_entry['name'] + ' [Adult]'] = _entry['id'] + ADULT_CHECK_OFFSET


class AgeDependentTransitionLocation(SohLocation):
    """An age-specific check may not be reached through the opposite age."""
    def __init__(self, player, name, address, parent, age):
        super().__init__(player, name, address, parent)
        self.transition_age = age

    def can_reach_as_age(self, state, age):
        return age == self.transition_age and super().can_reach_as_age(state, age)


def _eligible_catalog(world):
    # Triforce Hunt omits checks behind its permanently sealed final door.
    hunt = bool(world.options.triforce_hunt.value)
    pots = world.options.shuffle_pots.value in (1, 3)
    return tuple(e for e in CATALOG if not (hunt and (
        e.get('requires_final_ganon_key') or e['index'] == 'ENTR_GANONDORF_BOSS_0' or
        (e['mode'] == 'door' and e['source_scene'] == 10 and
         (e['door'] == 8 or (e['door'] in (6, 7) and not pots))))))


def _by_age(entry):
    # Unsupported ages cannot physically use the crossing even if an ER route
    # later sends that age to the same scene. Dungeon room door source policies
    # are reviewed in EntranceDestinationPolicy just like overworld endpoints.
    base_id = entry['id']
    if entry['mode'] == 'door':
        # All door sides exist for both ages unless their own access rule
        # explicitly limits the age. Age-specific reachability keeps that rule.
        mask = Safety.BOTH
    else:
        # Each scene/grotto check uses the original entrance endpoint identity.
        mask = Safety.source_age_mask(base_id - 11_000_000)
        if not mask:
            mask = Safety.BOTH
    for age, bit, offset, name in ((Ages.CHILD, Safety.CHILD, CHILD_CHECK_OFFSET, 'Child'),
                                   (Ages.ADULT, Safety.ADULT, ADULT_CHECK_OFFSET, 'Adult')):
        if mask & bit:
            yield dict(entry, id=base_id + offset, name=entry['name'] + ' [' + name + ']',
                       base_id=base_id, transition_age=age)


def active_entries(world):
    mode = int(world.options.scene_transition_checks.value)
    if mode == 0:
        return ()
    base = _eligible_catalog(world)
    entries = tuple(variant for entry in base for variant in _by_age(entry)) if mode == 2 else base
    if world.using_ut:
        # The real server manifest decides which checks exist for every mode,
        # including legacy seeds without this option.
        active = set(world.passthrough.get('extreme_active_locations', ()))
        return tuple(entry for entry in entries if entry['id'] in active)
    return entries


def create_locations(world):
    world._scene_transition_entries = active_entries(world)
    for entry in world._scene_transition_entries:
        source = world.get_region(region_name(entry['source']))
        if 'transition_age' in entry:
            location = AgeDependentTransitionLocation(world.player, entry['name'], entry['id'],
                                                      source, entry['transition_age'])
        else:
            location = SohLocation(world.player, entry['name'], entry['id'], source)
        source.locations.append(location)


def locations_for_base(world, base_id):
    """Return *all* active variants of the same physical crossing."""
    return tuple(world.get_location(e['name']) for e in world._scene_transition_entries
                 if e.get('base_id', e['id']) == base_id)


def retire_unreachable_age_checks(world):
    """Remove only age-specific crossings impossible with the final entrance map.

    Age Dependent builds both child/adult candidates in create_regions, before
    connect_entrances changes the topology.  After all local prefill items are
    placed, a crossing may never be usable by a particular age even with every
    shuffled item.  Such a crossing is *not a check* under the option contract
    ("if you can get to it") and must not consume a Full-accessibility slot.

    This is NOT a replacement for the normal AP fill/accessibility checks.  It
    only removes structurally impossible, otherwise empty age-variant checks,
    never regular item checks and never a check with a reserved/placed item.
    """
    if world.using_ut or int(world.options.scene_transition_checks.value) != 2:
        return 0

    from BaseClasses import ItemClassification

    state = world.multiworld.get_all_state(False, allow_partial_entrances=True)
    candidates = [
        world.get_location(entry['name']) for entry in world._scene_transition_entries
        if 'transition_age' in entry
    ]
    unreachable = [location for location in candidates if not location.can_reach(state)]
    # A location collectible at the actual start cannot be structurally
    # impossible. Preserve it even if the complete-inventory probe has an
    # inconsistent age/topology cache; otherwise it vanishes from both the
    # server's location manifest and the connected Check Finder.
    if unreachable:
        from BaseClasses import CollectionState
        start_state = CollectionState(world.multiworld)
        start_state.sweep_for_advancements()
        unreachable = [location for location in unreachable
                       if not location.can_reach(start_state)]
    if not unreachable:
        return 0

    reserved = [location.name for location in unreachable if location.item is not None]
    if reserved:
        raise OptionError(
            'SOH-EXTREME cannot retire unreachable age-specific transition '
            'checks because they already contain items: ' + ', '.join(reserved[:12])
            + '. Remove the impossible check from your item plando.'
        )

    # Do not remove progression, useful equipment, boss rewards or keys to
    # compensate for locations which are absent from this entrance map.
    # Ordinary junk and Ice Traps are safe to shrink by exactly this amount.
    replaceable = [
        item for item in world.multiworld.itempool
        if item.player == world.player
        and not (item.classification & (ItemClassification.progression | ItemClassification.useful))
    ]
    if len(replaceable) < len(unreachable):
        raise OptionError(
            f'SOH-EXTREME has {len(unreachable)} unreachable age-dependent '
            f'transition checks but only {len(replaceable)} removable filler '
            'items. Cannot safely adjust the item pool.'
        )

    # Stable removal: do not depend on location-set iteration order or Python
    # hash randomization, and avoid moving any progression item.
    replaceable.sort(key=lambda item: (item.name != 'Recovery Heart',
                                       item.name not in ('Blue Rupee', 'Red Rupee', 'Purple Rupee', 'Huge Rupee'),
                                       item.name, item.code or 0))
    for item in replaceable[:len(unreachable)]:
        world.multiworld.itempool.remove(item)
        if item in world.item_pool:
            world.item_pool.remove(item)

    removed_names = {location.name for location in unreachable}
    for location in unreachable:
        location.parent_region.locations.remove(location)
    world._scene_transition_entries = tuple(
        entry for entry in world._scene_transition_entries
        if entry['name'] not in removed_names
    )

    # fill_slot_data() builds the native active-location manifest from the
    # actual AP location cache.  The Region.LocationRegister.remove call above
    # removes these from that cache, and the trimmed entry list keeps Universal
    # Tracker's scene-check lookup consistent with the final generated seed.
    import logging
    logging.getLogger('SOH_EXTREME').info(
        'SOH-EXTREME Age Dependent: omitted %d transition check(s) whose age '
        'cannot traverse the final map even with all items; removed %d filler '
        'item(s). All reachable age checks remain enabled.',
        len(unreachable), len(unreachable)
    )
    return len(unreachable)


def retire_unreachable_goal_checks(world):
    """Implement Goal Reachable + Full without changing AP's global setting.

    Goal Reachable explicitly permits disconnected *optional* destinations.
    Full accessibility cannot include locations that no age can access even
    with the complete inventory.  Such locations cannot hold a progression
    item, so remove their unfilled check slots and an equal amount of junk
    before core AP fill, leaving every possible check in the normal AP Full
    progression algorithm. Never touch locked locations, preplaced items,
    events, or another player's items. All Destinations mode changes nothing.

    This is one full-inventory reachability query per generated map, not one
    query per candidate entrance swap. It runs only for Goal + Full worlds.
    """
    from .EntranceRandomizer import _is_full_accessibility, _is_goal_reachability
    if (world.using_ut or not _is_goal_reachability(world)
            or not _is_full_accessibility(world)):
        return 0

    from BaseClasses import ItemClassification
    from Options import OptionError
    from BaseClasses import LocationProgressType

    state = world.multiworld.get_all_state(False, allow_partial_entrances=True)
    # Materialize and test only network check slots for THIS SOH player. Event
    # nodes and the other worlds' checks must remain in the graph.
    eligible = [loc for loc in world.get_locations()
                if loc.address is not None and loc.item is None
                and loc.progress_type != LocationProgressType.EXCLUDED]
    missing = [loc for loc in eligible if not loc.can_reach(state)]
    if missing:
        from BaseClasses import CollectionState
        start_state = CollectionState(world.multiworld)
        start_state.sweep_for_advancements()
        missing = [loc for loc in missing if not loc.can_reach(start_state)]
    if not missing:
        return 0

    replaceable = [item for item in world.multiworld.itempool
                   if item.player == world.player
                   and not (item.classification & (ItemClassification.progression |
                                                 ItemClassification.useful))]
    if len(replaceable) < len(missing):
        raise OptionError(
            'SOH-EXTREME Goal Reachable cannot retire '
            f'{len(missing)} structurally unreachable optional checks: '
            f'only {len(replaceable)} removable filler items exist. '
            'Use All Destinations mode or lower the enabled check count.')

    replaceable.sort(key=lambda item: (item.name != 'Recovery Heart',
                                        item.name not in ('Blue Rupee', 'Red Rupee',
                                                          'Purple Rupee', 'Huge Rupee'),
                                        item.name, item.code or 0))
    for item in replaceable[:len(missing)]:
        world.multiworld.itempool.remove(item)
        if item in world.item_pool:
            world.item_pool.remove(item)
    removed_ids = {loc.address for loc in missing}
    for loc in missing:
        loc.parent_region.locations.remove(loc)
    # The native client and Universal Tracker obtain their active check list
    # from the live AP location cache; remove old source names as well so the
    # scene/door metadata never advertises an omitted age variant.
    world._scene_transition_entries = tuple(
        entry for entry in world._scene_transition_entries
        if entry['id'] not in removed_ids)

    import logging
    logging.getLogger('SOH_EXTREME').info(
        'SOH-EXTREME Goal Reachable + Full: omitted %d optional check(s) '
        'unreachable even with all items, and removed %d filler item(s). '
        'AP Full accessibility remains active for all surviving checks.',
        len(missing), len(missing))
    return len(missing)


def region_name(key):
    if key.startswith('RR_'):
        from .EnemyRoomLogic import NativeEnemyRegions
        return str(NativeEnemyRegions[key])
    return str(Regions[key])

def install_rules(world):
    errors=[]
    for entry in world._scene_transition_entries:
        source=world.get_region(region_name(entry['source']))
        target=region_name(entry['target'])
        location=world.get_location(entry['name'])
        if 'traversal_rule' in entry:
            from rule_builder.rules import True_
            bundle=(Regions[entry['source']],world)
            world.set_rule(location,H.at_day(bundle) if entry['traversal_rule']=='day' else True_())
            continue
        if (entry.get('source_scene') in (14, 15, 26) and
                entry.get('condition') == 'CanKillEnemy(RE_STALFOS, ED_CLOSE, true, 2)'):
            # Zelda's scripted escape Stalfos cannot be Soul-locked at runtime.
            # Keep the real two-Stalfos combat requirement, but not the AP
            # Stalfos Soul requirement that would otherwise hide these portals.
            from .EnemyRoomLogic import resolve_enemy_region
            from ._vendor_oot_soh.Enums import Enemies
            bundle = (resolve_enemy_region(entry['source']), world)
            world.set_rule(location, H._can_kill_enemy_combat(bundle, Enemies.STALFOS, quantity=2))
            continue
        if 'condition' in entry:
            world.set_rule(location,world._extreme_room_compiler.expr(entry['condition'],entry['source']))
            continue
        exits=[e for e in source.exits if e.connected_region and e.connected_region.name==target]
        if len(exits)!=1:
            errors.append(f"{entry['index']}: {source.name} -> {target} ({len(exits)})")
            continue
        location.access_rule=exits[0].access_rule
        early_pot_door=(entry['mode']=='door' and entry['source_scene']==10 and
                        entry['door'] in (6,7) and world.options.shuffle_pots.value in (1,3))
        if 'extra_condition' in entry and not early_pot_door:
            extra=world._extreme_room_compiler.expr(entry['extra_condition'],entry['source']).resolve(world)
            world.register_rule_dependencies(extra)
            # Inherited vanilla entrance rules may be plain Python callables,
            # not Rule.Resolved nodes. add_rule handles both without weakening
            # the original traversal requirement.
            add_rule(location, extra)
        if entry.get('gate')=='swim':
            swim=H.can_swim((Regions[entry['source']],world)).resolve(world)
            world.register_rule_dependencies(swim)
            add_rule(location, swim)
        if entry.get('gate')=='horse':
            horse=H.can_use(Items.EPONA,(Regions[entry['source']],world)).resolve(world)
            world.register_rule_dependencies(horse)
            add_rule(location, horse)

    # Standalone scene checks must agree with the ER source crossing even
    # when entrance randomization is disabled.  Do not gate the reverse exit.
    if world.options.shuffle_rock_boulder_soul.value:
        from rule_builder.rules import Has
        soul = Has("Rock / Boulder Soul").resolve(world)
        world.register_rule_dependencies(soul)
        for entry in world._scene_transition_entries:
            if entry.get('base_id', entry['id']) in BOULDER_BLOCKED_SCENE_CHECKS:
                location = world.get_location(entry['name'])
                # Some source entrance rules are legacy callables, so they
                # cannot be children of And.Resolved. Preserve the inherited
                # route, then require Soul for this *source* crossing only.
                add_rule(location, soul)

    if errors:raise OptionError("Unmapped physical portals: "+"; ".join(errors))
