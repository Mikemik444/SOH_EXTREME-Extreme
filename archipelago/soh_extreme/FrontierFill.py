"""SOH-EXTREME progression-frontier safety fill.

This module does not guess from location names.  It asks the AP Location/Region
rules that were installed by SohExtremeWorld.set_rules().  The same rule set is
also what spoiler spheres and Universal Tracker consume.

The safety fill builds a guaranteed local progression backbone for SOH-EXTREME:
while some of this player's fill locations are still blocked, it reserves an
advancement item (or, when necessary, the smallest synergistic bundle it can
find) in locations that are reachable *before* those items are collected.

If every remaining advancement item together still cannot open another check,
or if a required bundle is larger than the reachable frontier, generation fails
instead of emitting a soft-locked seed.
"""
from __future__ import annotations

import logging
from typing import Iterable, List, Sequence, Tuple

from BaseClasses import CollectionState, Item, Location

logger = logging.getLogger("SOH_EXTREME")


def _own_fill_locations(world, fill_locations: Sequence[Location]) -> List[Location]:
    return [
        loc for loc in fill_locations
        if loc.player == world.player and loc.item is None
    ]


def _reachable(state: CollectionState, locations: Sequence[Location]) -> List[Location]:
    return [loc for loc in locations if loc.item is None and loc.can_reach(state)]


def _collect_bundle(state: CollectionState, bundle: Iterable[Item]) -> CollectionState:
    test = state.copy()
    for item in bundle:
        test.collect(item, True)
    # Collect already-placed event/prefill advancement items opened by the bundle.
    test.sweep_for_advancements()
    return test


def _makes_progress(world, state: CollectionState, remaining_locations: Sequence[Location],
                    bundle: Sequence[Item]) -> bool:
    if not bundle:
        return False

    before = {id(loc) for loc in _reachable(state, remaining_locations)}
    before_beaten = world.multiworld.has_beaten_game(state, world.player)
    test = _collect_bundle(state, bundle)

    if not before_beaten and world.multiworld.has_beaten_game(test, world.player):
        return True

    for loc in remaining_locations:
        if id(loc) not in before and loc.item is None and loc.can_reach(test):
            return True
    return False


def _minimal_unlock_bundle(world, state: CollectionState,
                           remaining_locations: Sequence[Location],
                           candidates: Sequence[Item]) -> List[Item]:
    """Find a 1-minimal set of remaining advancement items that opens progress.

    Fast path: most gates have one immediate unlocker, so test single items first.
    For compound gates (multiple keys, Soul + ability, note thresholds, etc.),
    start with every remaining advancement item and greedily remove items that are
    not needed.  Because duplicate item instances are kept separately this also
    discovers exact counts such as 5 Small Keys.
    """
    ordered = list(candidates)
    world.random.shuffle(ordered)

    for item in ordered:
        if _makes_progress(world, state, remaining_locations, [item]):
            return [item]

    if not _makes_progress(world, state, remaining_locations, ordered):
        return []

    bundle = ordered
    index = 0
    while index < len(bundle):
        trial = bundle[:index] + bundle[index + 1:]
        if trial and _makes_progress(world, state, remaining_locations, trial):
            bundle = trial
            # A new item moved into this index; test it too.
            continue
        index += 1

    return bundle


def _assign_bundle(world, state: CollectionState, bundle: Sequence[Item],
                   frontier: Sequence[Location]) -> List[Tuple[Location, Item]]:
    """Assign every bundle item to a distinct currently-reachable legal location."""
    open_locations = list(frontier)
    result: List[Tuple[Location, Item]] = []

    # Most constrained items first.  This is a small bipartite matching problem;
    # recomputing candidate counts after every assignment avoids common greedy
    # failures without the cost/complexity of a full generic matcher.
    remaining_items = list(bundle)
    while remaining_items:
        choices = []
        for item in remaining_items:
            legal = [loc for loc in open_locations if loc.can_fill(state, item, True)]
            choices.append((len(legal), item, legal))
        choices.sort(key=lambda row: row[0])
        count, item, legal = choices[0]
        if count == 0:
            return []
        world.random.shuffle(legal)
        loc = legal[0]
        result.append((loc, item))
        open_locations.remove(loc)
        remaining_items.remove(item)

    return result


def frontier_fill(world, progitempool: List[Item], fill_locations: List[Location]) -> None:
    """Fast pre-fill sanity check; core AP restrictive fill owns placement.

    AP's normal restrictive fill already performs progression-aware placement using
    the world's installed access rules.  0.8.09 duplicated that work by repeatedly
    simulating every remaining advancement item (and compound bundles) against
    thousands of checks.  That was safe but extremely expensive.

    0.8.12 keeps the fail-closed safety model without brute-force pre-placement:
      * verify that the starting state has at least one real fill location (after
        collecting reachable event/prefill advancements);
      * let AP's optimized restrictive fill place progression;
      * validate the completed world with validate_filled_world() afterwards.

    If AP ever creates a progression self-lock according to the SOH-EXTREME rule
    graph, post-fill validation rejects the seed instead of outputting it.
    """
    from Fill import FillError

    # Cross-player placement is handled by AP core.  The local sanity check is
    # meaningful only for the single-player fork configuration.
    if len(world.multiworld.player_ids) != 1:
        return

    state = CollectionState(world.multiworld)
    state.sweep_for_advancements()

    own_locations = _own_fill_locations(world, fill_locations)
    if not own_locations:
        return

    # Stop after the first reachable location; do not materialize/scans sets or
    # test candidate items here.  This keeps the hook effectively O(start checks).
    for loc in own_locations:
        if loc.can_reach(state):
            logger.info(
                "SOH-EXTREME fast frontier guard: initial reachable check confirmed; "
                "using Archipelago restrictive fill + post-fill validation"
            )
            return

    # With no reachable fill location after event sweeping, no placement strategy
    # can bootstrap the seed.  Fail immediately with useful examples.
    sample = ", ".join(loc.name for loc in own_locations[:20])
    raise FillError(
        "SOH-EXTREME has no reachable fill location from the starting state. "
        "This is a logic/bootstrap mismatch, not a fill-order problem. "
        f"Location examples: {sample}", multiworld=world.multiworld
    )

def validate_filled_world(world) -> None:
    """Reject a stalled single-player fill without counting any pickup twice.

    Event locations are included in the same traversal as ordinary locations.
    Collection uses prevent_sweep=True, so automatic advancement sweeping cannot
    grant a location that is still waiting in the manual remaining-location list.
    This validates the AP rule graph; it is not a runtime playthrough guarantee.
    """
    from Fill import FillError

    if len(world.multiworld.player_ids) != 1:
        return

    state = CollectionState(world.multiworld)
    remaining = [
        loc for loc in world.multiworld.get_locations(world.player)
        if loc.item is not None
    ]
    while remaining:
        # Respect locations already collected by CollectionState initialization
        # or a world hook, without granting those items a second time.
        collected = getattr(state, "advancements", set())
        remaining = [loc for loc in remaining if loc not in collected]
        sphere = [loc for loc in remaining if loc.can_reach(state)]
        if not sphere:
            break
        for loc in sphere:
            remaining.remove(loc)
            if loc not in getattr(state, "advancements", set()):
                state.collect(loc.item, True, loc)

    if not world.multiworld.has_beaten_game(state, world.player):
        sample = ", ".join(loc.name for loc in remaining[:25])
        raise FillError(
            "SOH-EXTREME post-fill validation stalled before the completion condition. "
            f"Blocked examples: {sample}", multiworld=world.multiworld
        )

    accessibility_key = getattr(world.options.accessibility, "current_key", "full")
    if str(accessibility_key).lower() == "full" and remaining:
        # Full inventory is for diagnostics only, never proof that the real
        # progression sequence is valid.
        all_state = world.multiworld.get_all_state(False)
        all_state.sweep_for_advancements()
        structural = [loc for loc in remaining if not loc.can_reach(all_state)]
        fill_locked = [loc for loc in remaining if loc.can_reach(all_state)]
        ordered = sorted(structural, key=lambda loc: loc.name)
        ordered += sorted(fill_locked, key=lambda loc: loc.name)
        sample = ", ".join(loc.name for loc in ordered[:40])
        raise FillError(
            "SOH-EXTREME Full accessibility validation failed: "
            f"{len(remaining)} filled location(s) never became reachable "
            f"({len(structural)} structural rule mismatch(es), "
            f"{len(fill_locked)} placement/frontier lock(s)). "
            f"Blocked examples: {sample}", multiworld=world.multiworld
        )
