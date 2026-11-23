"""Conservative SOH-EXTREME area hints using finalized AP placements.

A Way of the Hero region must block SOH's completion after progression is
swept across all player locations with the region's checks withheld. This is
optional hint proofing, not a separate seed-validity audit. Barren denotes a
complete named check group without any advancement items.
"""

from collections import defaultdict
import random

from BaseClasses import CollectionState
from .NpcSpeech import BY_NAME as SPEECH_BY_NAME, display_region
from ._vendor_oot_soh.Enums import Regions


MAX_WOTH_PROOFS = 12
MAX_WOTH_HINTS = 4
MAX_BARREN_HINTS = 4


def physical_check_groups(world):
    groups = defaultdict(set)
    for location in world.get_locations():
        if location.address is None or location.item is None:
            continue
        speech = SPEECH_BY_NAME.get(location.name)
        if speech and speech.get('routes'):
            # Moving NPC checks can be encountered in several regions. Include
            # them in each complete check group so no route is called barren
            # while that NPC can hold progression there.
            names = {str(Regions[route['region']]) for route in speech['routes']}
        else:
            names = {display_region(location)}
        for name in names:
            if name and name != str(Regions.ROOT):
                groups[name].add(location)
    return dict(groups)


def prepare_hint_areas(world):
    world._extreme_area_hints = []
    world._extreme_area_hint_audit = {'proofs': [], 'barren': [], 'scope': 'SOH-EXTREME player goal'}
    if world.using_ut or not world.options.gossip_stone_hints.value:
        return
    multiworld = world.multiworld
    groups = physical_check_groups(world)
    # Single isolated checks remain clearer as direct item hints.
    groups = {name: checks for name, checks in groups.items() if len(checks) >= 2}
    rng = random.Random(f'{multiworld.seed_name}:{world.player}:soh-area-hints-v1')
    candidates = sorted(groups)
    rng.shuffle(candidates)
    barren = [name for name in candidates if not any(loc.item.advancement for loc in groups[name])]
    candidates = [name for name in candidates if any(loc.item.advancement for loc in groups[name])]
    # Test substantial check groups first, with stable random tie ordering.
    # This only prioritizes bounded probes; the goal sweep is the proof.
    candidates.sort(key=lambda name: -sum(loc.item.advancement for loc in groups[name]))
    proven = []
    for name in candidates[:MAX_WOTH_PROOFS]:
        withheld = groups[name]
        state = CollectionState(multiworld)
        state.locations_checked.update(withheld)
        state.advancements.update(withheld)
        # Collect legitimate remote progression, but test only this SOH slot's
        # completion condition. Other games are validated by AP core.
        if not multiworld.has_beaten_game(state, world.player):
            state.sweep_for_advancements(checked_locations=state.locations_checked)
        beatable = multiworld.has_beaten_game(state, world.player)
        world._extreme_area_hint_audit['proofs'].append({
            'area': name, 'locations': sorted(loc.address for loc in withheld),
            'soh_goal_reachable_without_area': beatable,
        })
        if not beatable:
            proven.append(name)
            if len(proven) >= MAX_WOTH_HINTS:
                break
    for name in barren[:MAX_BARREN_HINTS]:
        world._extreme_area_hint_audit['barren'].append({
            'area': name, 'locations': sorted(loc.address for loc in groups[name]),
            'advancement_items': 0,
        })
    for hint_type, names in (('woth', proven), ('barren', barren[:MAX_BARREN_HINTS])):
        for name in names:
            world._extreme_area_hints.append({
                'type': hint_type, 'area': name, 'finder': multiworld.player_name[world.player],
                'game': multiworld.game[world.player], 'finding_player': world.player,
                'scope': 'checks_in_region',
            })


def apply_area_hints(world, result, stones):
    areas = getattr(world, '_extreme_area_hints', ())
    if not areas:
        return
    # Only replace some stones. Keep direct item hints, nonlocal NPC hints,
    # and the world's generation random stream unchanged.
    stones = list(stones)
    random.Random(f'{world.multiworld.seed_name}:{world.player}:soh-area-stones-v1').shuffle(stones)
    limit = min(len(areas), len(stones) // 3)
    for stone, row in zip(stones[:limit], areas):
        result[stone.value] = [dict(row)]
