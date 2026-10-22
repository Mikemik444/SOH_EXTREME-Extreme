"""Authoritative, conservative repeatable ammunition sources for a live AP save.

Only the managed UT worker calls this module. Each probe keeps owned containers,
removes the target ammunition, discards previously derived events, and resweeps
actual AP topology. Neither an assigned AP reward nor a nominal pot item proves
renewability. Unknown source parameters retain last-unit protection.
"""
from __future__ import annotations
from copy import copy
from dataclasses import dataclass
from importlib.resources import files
import json

from rule_builder.rules import And, False_, Has, NestedRule, Or, True_, WrapperRule
from ._vendor_oot_soh import LogicHelpers as H
from ._vendor_oot_soh.Enums import Ages, Items, Locations, Regions
from ._vendor_oot_soh.Locations import (
    SohLocation, scrubs_location_table, pots_overworld_location_table,
    pots_dungeon_location_table, crates_overworld_location_table,
    crates_dungeon_location_table,
)
from ._vendor_oot_soh.ShopItems import all_shop_locations, vanilla_shop_prices
from .EnemyDropLocations import ENEMY_DROP_LOCATIONS
from .EnemyDropRules import enemy_drop_rule
from .EnemyRoomLogic import NativeEnemyRegions, resolve_enemy_region
from .EntranceRandomizer import DUNGEON_ROUTES

STICK, NUT, BOMB, BOMBCHU, ARROWS = 1, 2, 4, 8, 16
ALL_AMMO = 31
RAW_SEEDS = 32
MAX_OBSERVED_SOURCES = 2048
# Bits 0..5: raw fixed ammo, 6..7: pot/small crate/large crate,
# 8..9: observed child/adult. Native params prove collectible flag zero.
RAW_SOURCE_MASK = STICK | NUT | BOMB | ARROWS | RAW_SEEDS
SOURCE_CATALOG = json.loads(files(__package__).joinpath('AmmoRefillSources.json').read_text())
SOURCE_TABLES = (scrubs_location_table, pots_overworld_location_table,
                 pots_dungeon_location_table, crates_overworld_location_table,
                 crates_dungeon_location_table)
SOURCE_NAMES = {data.loc_id: str(name) for table in SOURCE_TABLES for name, data in table.items()}
SHOP_MASKS = {
    str(Items.BUY_DEKU_STICK1): STICK,
    str(Items.BUY_DEKU_NUTS5): NUT, str(Items.BUY_DEKU_NUTS10): NUT,
    **{str(getattr(Items, key)): BOMB for key in
       ('BUY_BOMBS525', 'BUY_BOMBS535', 'BUY_BOMBS10', 'BUY_BOMBS20', 'BUY_BOMBS30')},
    str(Items.BUY_BOMBCHUS10): BOMBCHU, str(Items.BUY_BOMBCHUS20): BOMBCHU,
    **{str(getattr(Items, key)): ARROWS for key in ('BUY_ARROWS10', 'BUY_ARROWS30', 'BUY_ARROWS50')},
}


def validate_observed_sources(rows):
    """Validate bounded native facts before accepting the live request."""
    if not isinstance(rows, list) or len(rows) > MAX_OBSERVED_SOURCES:
        raise ValueError('invalid observed ammo source list')
    result = []
    seen = set()
    for row in rows:
        if not isinstance(row, (list, tuple)) or len(row) != 2:
            raise ValueError('invalid observed ammo source')
        address, flags = row
        if type(address) is not int or not 0 < address <= 0x7fffffffffffffff:
            raise ValueError('invalid observed source ID')
        if type(flags) is not int or flags <= 0 or flags & ~0x3f7:
            raise ValueError('invalid observed source flags')
        raw, kind, age = flags & 63, (flags >> 6) & 3, (flags >> 8) & 3
        if raw & ~RAW_SOURCE_MASK or not raw or kind not in (1, 2, 3) or age not in (1, 2):
            raise ValueError('invalid observed source kind/age/drop')
        key = address, age
        if key in seen:
            raise ValueError('duplicate observed ammo source')
        seen.add(key)
        result.append((address, flags))
    return tuple(sorted(result))


@dataclass(frozen=True)
class Source:
    name: str
    ammo: int
    locations: tuple
    price: int = 0
    required_check: int | None = None
    random_drop: bool = False
    raw_drop: bool = False
    age: Ages | None = None


def _location(world, name, parent, rule):
    location = SohLocation(world.player, 'Ammo refill: ' + name, None, world.get_region(str(parent)))
    location.access_rule = rule.resolve(world)
    return location


def _reusable_melee(bundle):
    return (H.can_use(Items.KOKIRI_SWORD, bundle) | H.can_use(Items.MASTER_SWORD, bundle)
            | H.can_use(Items.BIGGORONS_SWORD, bundle) | H.can_use(Items.MEGATON_HAMMER, bundle))


def _reusable_break(bundle, kind):
    # A random drop farm must not spend another finite ammo supply. Pots and
    # small crates can also be lifted with the actual Grab capability.
    rule = _reusable_melee(bundle)
    if kind == 1:
        rule |= (H.can_use(Items.BOOMERANG, bundle) | H.can_use(Items.HOOKSHOT, bundle)
                 | H.extreme_requirement(bundle, 'shuffle_grab', 'Grab / Power Bracelet'))
    elif kind == 2:
        rule |= (H.extreme_requirement(bundle, 'shuffle_grab', 'Grab / Power Bracelet')
                 | H.extreme_requirement(bundle, 'shuffle_roll', 'Roll'))
    else:
        # Large crates permit the native roll hit; their sword/Hookshot hits do
        # not break the actor. Keep only the repeatable physical action.
        rule = H.extreme_requirement(bundle, 'shuffle_roll', 'Roll')
    return rule


def _native_stock_price(rule, name, price):
    """Replace only this inactive scrub's absent AP shelf-price predicate.

    The authored physical rule is retained. CanAffordSlot consults the live
    world price table at evaluation time; inactive slots have no entry and
    otherwise fall back to 500. Copying that one node keeps the real native
    wallet requirement without altering any generation or tracker price.
    The caller separately checks actual carried rupees against this price.
    """
    if isinstance(rule, H.CanAffordSlot) and str(rule.location) == name:
        keywords = {'options': rule.options, 'filtered_resolution': rule.filtered_resolution}
        if price == 0:
            return True_(**keywords)
        for count, wallet in enumerate(H.progressive_items[Items.PROGRESSIVE_WALLET], 1):
            if H.wallet_capacities[wallet] >= price:
                return Has(Items.PROGRESSIVE_WALLET, count, **keywords)
        return False_(**keywords)
    if isinstance(rule, (NestedRule, WrapperRule)):
        result = copy(rule)
        if isinstance(rule, NestedRule):
            result.children = tuple(_native_stock_price(child, name, price) for child in rule.children)
        else:
            result.child = _native_stock_price(rule.child, name, price)
        return result
    return rule


def _source_locations(world, address, name, extra, stock_price=None):
    """Use final AP collection rules, or the same authored inactive rules."""
    locations = getattr(world, '_extreme_ammo_locations', None)
    if locations is None:
        locations = {loc.address: loc for loc in world.get_locations() if loc.address is not None}
        world._extreme_ammo_locations = locations
    if address in locations:
        original = locations[address]
        region = original.parent_region
        bundle = (region.name, world)
        location = _location(world, name, region.name, extra(bundle))
        base_rule = original.access_rule
        own_rule = location.access_rule
        location.access_rule = lambda state, base=base_rule, own=own_rule: base(state) and own(state)
        return (location,)

    captured = getattr(world, '_extreme_refill_source_rules', {}).get(name)
    if captured is None:
        return ()
    routes = DUNGEON_ROUTES.get(str(address))
    if routes:
        # Inactive dungeon pots/scrubs must still use the precise native room
        # graph, including shuffled door connections and inter-room switches.
        compiler = world._extreme_room_compiler
        previous = getattr(compiler, 'location', None)
        result = []
        try:
            compiler.location = name
            for row in routes:
                parent = NativeEnemyRegions[row['region']]
                bundle = (parent, world)
                rule = compiler.expr(row['condition'], row['region']) & extra(bundle)
                result.append(_location(world, name, parent, rule))
        finally:
            compiler.location = previous
        return tuple(result)
    parent, original_rule = captured
    if stock_price is not None:
        original_rule = _native_stock_price(original_rule, name, stock_price)
    return (_location(world, name, parent, original_rule & extra((parent, world))),)


def _build_sources(world, observed):
    result = []
    actual = {loc.name: loc for loc in world.get_locations()}
    # Retained shop stock is an event location. An addressed AP shelf remains
    # one-time even if its assigned item happens to be Buy Bombs or Buy Arrows.
    for parent, shop in all_shop_locations:
        language = ('Kokiri' if parent == Regions.KF_KOKIRI_SHOP else
                    'Goron' if parent == Regions.GC_SHOP else
                    'Zora' if parent == Regions.ZD_SHOP else 'Hylian')
        for name in shop:
            location = actual.get(str(name))
            if location is None or location.address is not None or location.item is None:
                continue
            mask = SHOP_MASKS.get(location.item.name, 0)
            if not mask:
                continue
            price = world.shop_prices.get(name, vanilla_shop_prices.get(Items(location.item.name)))
            if type(price) is not int or price < 0:
                continue
            bundle = (location.parent_region.name, world)
            proxy = _location(world, str(name), location.parent_region.name, H.can_interact_npc(bundle, language))
            original, extra = location.access_rule, proxy.access_rule
            proxy.access_rule = lambda state, original=original, extra=extra: original(state) and extra(state)
            result.append(Source(str(name), mask, (proxy,), price=price))

    # Native unshuffled ammo scrubs respawn and sell the same stock on a new
    # visit. Shuffled scrub checks despawn after their sale and never qualify.
    if world.options.shuffle_scrubs.value != 2:
        for row in SOURCE_CATALOG['scrubs']:
            name = SOURCE_NAMES.get(row['address'])
            if name is None or (name in actual and actual[name].address is not None):
                continue
            def scrub_rule(bundle, mask=row['ammo']):
                rule = (H.extreme_requirement(bundle, 'shuffle_business_scrub_soul', 'Scrub Soul')
                        & H.can_interact_npc(bundle, 'Deku') & H.can_reflect_nuts(bundle))
                if mask == ARROWS:
                    rule &= H.is_adult(bundle)  # child receives seeds instead
                return rule
            proxies = _source_locations(world, row['address'], name, scrub_rule, stock_price=row['price'])
            if proxies:
                result.append(Source(name, row['ammo'], proxies, row['price']))

    # Carpet Merchant returns to repeatable vanilla stock only after its first
    # shuffled purchase. Its refill is always ten Bombchus for 200 rupees.
    name = str(Locations.WASTELAND_CARPET_SALESMAN)
    original = actual.get(name)
    address = original.address if original is not None else world.location_name_to_id.get(name)
    shuffled = world.options.shuffle_merchants.value in (2, 3)
    parent = Regions.HAUNTED_WASTELAND
    b = (parent, world)
    rule = (H.has_item(Items.ADULT_WALLET, b) & H.can_interact_npc(b, 'Hylian')
            & (H.can_jump_slash(b) | H.can_use(Items.HOVER_BOOTS, b)))
    result.append(Source(name + ' repeat stock', BOMBCHU, (_location(world, name, parent, rule),),
                         200, address if shuffled else None))

    # Authored overworld Red Tektites have no one-time room-clear flag or
    # collectible flag, and reappear on scene reload. Do not infer renewability
    # from dungeon enemies, bosses, controller spawns, or arbitrary enemy names.
    # Kokiri child Withered Babas regrow naturally and also reload normally.
    for entry in ENEMY_DROP_LOCATIONS:
        tektite = entry.scene_id == 96 and entry.actor_id == 27 and entry.params == 65535
        baba = entry.scene_id == 85 and entry.actor_id == 199 and entry.spawn_mask == 3
        if not (tektite or baba):
            continue
        parent = resolve_enemy_region(entry.region_token)
        b = (parent, world)
        reusable = _reusable_melee(b)
        if baba:
            reusable |= H.can_use(Items.BOOMERANG, b)
        rule = enemy_drop_rule(world, entry) & reusable
        proxy = _location(world, entry.name, parent, rule)
        if baba:
            # EnKarebaba's direct GI_STICKS_1 reward survives both enemy-check
            # shuffling and NoRandomDrops, and the actor regrows in place.
            result.append(Source(entry.name + ' native stick', STICK, (proxy,)))
        if world.options.shuffle_enemy_drops.value:
            result.append(Source(entry.name + ' repeat loot', RAW_SOURCE_MASK, (proxy,),
                                 required_check=entry.address, random_drop=True, raw_drop=True))

    for address, flags in observed:
        name = SOURCE_NAMES.get(address)
        if name is None:
            continue  # unknown/retired identity cannot grant gameplay authority
        raw, kind, age_value = flags & 63, (flags >> 6) & 3, (flags >> 8) & 3
        age = Ages.CHILD if age_value == 1 else Ages.ADULT
        def pot_rule(bundle, kind=kind, age=age):
            soul = 'Pot Soul' if kind == 1 else 'Crate Soul'
            option = 'shuffle_pot_soul' if kind == 1 else 'shuffle_crate_soul'
            return (H.extreme_requirement(bundle, option, soul) & _reusable_break(bundle, kind)
                    & (H.is_child(bundle) if age == Ages.CHILD else H.is_adult(bundle)))
        # Identity classes must agree with the existing AP source catalog.
        pot = address in {v.loc_id for t in SOURCE_TABLES[1:3] for v in t.values()}
        crate = address in {v.loc_id for t in SOURCE_TABLES[3:5] for v in t.values()}
        if not ((kind == 1 and pot) or (kind in (2, 3) and crate)):
            continue
        proxies = _source_locations(world, address, name, pot_rule)
        if proxies:
            # An inactive pot is ordinary immediately; an active first check
            # must be collected before that actor releases its native ammo.
            loc = actual.get(name)
            pending = address if loc is not None and loc.address is not None else None
            result.append(Source(name + ' observed flag 0', raw, proxies,
                                 required_check=pending, raw_drop=True, age=age))
    return tuple(result)


def _fresh_probe(world, original):
    state = original.copy()
    player = world.player
    derived = {loc for loc in state.advancements
               if loc.player == player and loc.address is None and loc.item is not None}
    for loc in derived:
        state.remove(loc.item)
    state.advancements.difference_update(derived)
    state.locations_checked.difference_update(derived)
    state.reachable_regions[player].clear()
    state.blocked_connections[player].clear()
    state.stale[player] = True
    state._soh_extreme_invalidate(player)
    state.rule_builder_cache[player].clear()
    return state


def _drop_mask(world, raw, age, owned, flags):
    mask = raw & (STICK | NUT | BOMB)
    if age == Ages.CHILD:
        # Ordinary arrow bundles become seeds for child, not usable bow ammo.
        pass
    else:
        if not flags & 2:  # TreesDropSticks also disables adult stick conversion
            mask &= ~STICK
        if raw & (ARROWS | RAW_SEEDS):
            mask |= ARROWS
    if mask & BOMB and not owned & BOMB:
        mask &= ~BOMB
        # Native bag modes retain bombs when both bags are owned. A Bombchu-
        # only owned bag can convert ordinary bomb drops when enabled.
        if owned & BOMBCHU and world.options.bombchu_bag.value != 0 and world.options.bombchu_drops.value:
            mask |= BOMBCHU
    return mask & owned


def refill_mask(world, original, *, live_ammo, owned, rupees, flags, checked, live_age, observed=()):
    """Return only proven renewable ammo types; failures are handled by caller."""
    if (type(live_ammo) is not int or type(owned) is not int
            or live_ammo & ~ALL_AMMO or owned & ~ALL_AMMO or live_ammo & ~owned
            or type(rupees) is not int or not 0 <= rupees <= 65535
            or type(flags) is not int or not 0 <= flags <= 3
            or type(live_age) is not int or live_age not in (1, 2)):
        raise ValueError('invalid live refill inputs')
    observed = validate_observed_sources(list(observed))
    if not owned:
        return 0
    cache = getattr(world, '_extreme_ammo_sources', None)
    if cache is None or cache[0] != observed:
        cache = (observed, _build_sources(world, observed))
        world._extreme_ammo_sources = cache
    sources = cache[1]
    events = tuple(loc for loc in world.get_locations() if loc.address is None and loc.item is not None)
    checked = frozenset(checked)
    previous = getattr(world, '_extreme_live_ammo', None)
    result = 0
    try:
        for target in (STICK, NUT, BOMB, BOMBCHU, ARROWS):
            if not owned & target:
                continue
            candidates = [source for source in sources if rupees >= source.price
                          and (source.required_check is None or source.required_check in checked)
                          and not (source.random_drop and flags & 1)]
            if not candidates:
                continue
            world._extreme_live_ammo = live_ammo & ~target
            state = _fresh_probe(world, original)
            state.sweep_for_advancements(events)
            found = False
            for source in candidates:
                for age in (Ages.CHILD if live_age == 1 else Ages.ADULT,):
                    if source.age is not None and source.age != age:
                        continue
                    mask = (_drop_mask(world, source.ammo, age, owned, flags)
                            if source.raw_drop else source.ammo & owned)
                    if not mask & target:
                        continue
                    if any(location.can_reach_as_age(state, age) for location in source.locations):
                        found = True
                        break
                if found:
                    break
            if found:
                result |= target
    finally:
        world._extreme_live_ammo = previous
    return result
