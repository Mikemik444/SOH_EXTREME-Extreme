"""Exercise real stock/EXTREME APWorld hooks, plando sweeps and age/health state.

Run against an AP core with both oot_soh.apworld and soh_extreme.apworld installed.
The core's normal loader must load both packages; no fake stock mixin is used.
"""
from run_case import setup, BOOTSTRAP
from BaseClasses import CollectionState, MultiWorld
from Fill import resolve_early_locations_for_planned
from Generate import roll_settings
from worlds.AutoWorld import AutoWorldRegister, call_all
from worlds.soh_extreme._vendor_oot_soh.Enums import Ages, Items
from pathlib import Path
import argparse
import json


def main():
    parser = argparse.ArgumentParser(parents=[BOOTSTRAP])
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    tests = []

    def check(name, condition):
        tests.append({'test': name, 'passed': bool(condition)})
        assert condition, name

    check('regular SoH APWorld really loaded', 'Ship of Harkinian' in AutoWorldRegister.world_types)
    init_hooks = CollectionState.additional_init_functions[:]
    copy_hooks = CollectionState.additional_copy_functions[:]
    check('real stock age hook present', any(f.__module__ == 'worlds.oot_soh.RegionAgeAccess' for f in init_hooks))
    check('real stock health hook present', any(f.__module__ == 'worlds.oot_soh.LogicHelpers' for f in init_hooks))
    mw = setup(1016009, stop_before='pre_fill')
    for order in ('extreme-first', 'stock-first'):
        # Hooks are global in AP. Exercise both legitimate registration orders
        # while preserving relative hook order within each package.
        stock_last = order == 'extreme-first'
        key = lambda f: (f.__module__.startswith('worlds.oot_soh')) == stock_last
        CollectionState.additional_init_functions[:] = sorted(init_hooks, key=key)
        CollectionState.additional_copy_functions[:] = sorted(copy_hooks, key=key)
        try:
            mw.state = state = CollectionState(mw)
            check(order + ' EXTREME age initialized', state._soh_extreme_age[1] == Ages.null)
            check(order + ' stock age stays empty for solo EXTREME', state._soh_age == {})
            check(order + ' starting hearts retained',
                  state._soh_extreme_heart_count[1] == mw.worlds[1].options.starting_hearts.value)
            # This is the exact AP entry point in the reported traceback.
            resolve_early_locations_for_planned(mw)
            state.sweep_for_advancements()
            before = {loc.name for loc in mw.get_locations() if loc.can_reach(state)}
            copied = state.copy()
            check(order + ' copied reachability matches',
                  before == {loc.name for loc in mw.get_locations() if loc.can_reach(copied)})
            check(order + ' sweep restores age context', state._soh_extreme_age[1] == Ages.null)
            for field in ('child_reachable_regions', 'adult_reachable_regions',
                          'child_blocked_regions', 'adult_blocked_regions'):
                original = getattr(state, '_soh_extreme_' + field)[1]
                clone = getattr(copied, '_soh_extreme_' + field)[1]
                check(order + ' independent ' + field, original is not clone and original == clone)
            hearts = state._soh_extreme_heart_count[1]
            item = mw.worlds[1].create_item(Items.HEART_CONTAINER)
            copied.collect(item, True)
            check(order + ' health copy independent', state._soh_extreme_heart_count[1] == hearts
                  and copied._soh_extreme_heart_count[1] == hearts + 1)
            copied.remove(item)
            check(order + ' remove restores health', copied._soh_extreme_heart_count[1] == hearts)
            check(order + ' stock health untouched', dict(state.soh_heart_count) == {})
        finally:
            CollectionState.additional_init_functions[:] = init_hooks
            CollectionState.additional_copy_functions[:] = copy_hooks

    # A room containing both games must preserve each slot's own ages/hearts,
    # including when one game's state is copied and its inventory changes.
    mixed = MultiWorld(2)
    mixed.game = {1: 'SOH-EXTREME', 2: 'Ship of Harkinian'}
    mixed.player_name = {1: 'Extreme', 2: 'Regular'}
    mixed.set_seed(1016010)
    mixed.seed_name = '1016010'
    rolled = {p: roll_settings({'game': game, 'name': mixed.player_name[p],
                              game: {'starting_hearts': 5 if p == 1 else 3}})
              for p, game in mixed.game.items()}
    options = argparse.Namespace()
    for p, game in mixed.game.items():
        for name in AutoWorldRegister.world_types[game].options_dataclass.type_hints:
            if not hasattr(options, name):
                setattr(options, name, {})
            getattr(options, name)[p] = getattr(rolled[p], name)
    mixed.set_options(options)
    mixed.state = CollectionState(mixed)
    for step in ('generate_early', 'create_regions', 'create_items', 'set_rules'):
        call_all(mixed, step)
    state = CollectionState(mixed)
    check('mixed ages belong to separate slots', set(state._soh_extreme_age) == {1} and set(state._soh_age) == {2})
    check('mixed hearts initialized independently', state._soh_extreme_heart_count[1] == 5 and state.soh_heart_count[2] == 3)
    resolve_early_locations_for_planned(mixed)
    state.sweep_for_advancements()
    copied = state.copy()
    before = {(loc.player, loc.name) for loc in mixed.get_locations() if loc.can_reach(state)}
    check('mixed copied age rules agree', before == {(loc.player, loc.name) for loc in mixed.get_locations() if loc.can_reach(copied)})
    for p, field in ((1, '_soh_extreme_heart_count'), (2, 'soh_heart_count')):
        other = 'soh_heart_count' if p == 1 else '_soh_extreme_heart_count'
        old = getattr(copied, field)[p]
        other_before = dict(getattr(copied, other))
        pieces = [mixed.worlds[p].create_item(Items.PIECE_OF_HEART) for _ in range(4)]
        for item in pieces:
            copied.collect(item, True)
        check(f'player {p} four pieces grant one heart', getattr(copied, field)[p] == old + 1)
        check(f'player {p} preserves other game health', dict(getattr(copied, other)) == other_before)
        for item in pieces:
            copied.remove(item)
        check(f'player {p} piece removal restores health', getattr(copied, field)[p] == old)

    result = {'passed': True, 'checks': len(tests), 'tests': tests,
              'init_hooks': [f.__module__ + '.' + f.__qualname__ for f in init_hooks]}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print('RESULT', result['passed'], result['checks'], flush=True)


if __name__ == '__main__':
    main()
