SOH-EXTREME 0.7.58 targeted source/APWorld patch

Implemented in this patch:
- Grass logic now uses the Grab / Power Bracelet tier only. Goron Bracelet is no
  longer incorrectly required just to lift grass.
- Strength progression remains shifted as:
    1 Grab / Power Bracelet
    2 Goron Bracelet
    3 Silver Gauntlets
    4 Golden Gauntlets
- Important SOH-EXTREME/AP items and keys are forced through Link's normal
  hold-above-head get-item presentation.
- Custom ability/Soul get-items no longer deadlock the AP receive queue if their
  synthetic item does not emit OnItemReceive. This is the reload-required grass
  reward freeze seen after Shovel/new abilities/Souls.
- Speak modes: Off / On / Individual Languages.
- Enemy Soul topology: Off / All Enemies as 1 / Individual Enemies.
- Enemy Soul locked behavior remains separately configurable:
  Gone Until Found / Invincible Until Found.
- Animal Soul topology: Off / All Animals as 1 / Individual Animals.
- APWorld includes individual Speak, Enemy Soul, and Animal Soul progression
  items and publishes the new settings to the native client.
- Removed the incorrect AP logic that made Gold Skulltula/Boss checks depend on
  the ordinary Enemy Soul.

Enemy Drops:
The supplied SOH-EXTREME native source still contains only the ShuffleEnemyDrops
setting/logic helper, not the original randomizer's EnemyDrop location table or
runtime actor->location reporting implementation. The reference randomizer uses
explicit per-enemy EnemyDrop locations. This patch does NOT invent fake enemy
location IDs, because doing so would create server/client desync. Enemy Drops
therefore remain the one unfinished subsystem in this archive.

Updated APWorld:
  apworld/soh_extreme_0.7.58.apworld

Extract over the SOH-EXTREME repository root. Only paths present in this archive
are replaced. No assets are included.

0.7.59 APWorld hotfix
---------------------
Fixed infinite recursion introduced in the topology-aware rule helpers:
- require_speak() now calls the base require(location, "Speak") in combined mode.
- require_animal() now calls the base require(location, "Animal Soul") in combined mode.

The prior 0.7.58 helper accidentally called itself in both branches, producing
RecursionError during set_rules. Python syntax validation passes after this fix.

0.7.60 shop prefill hotfix
--------------------------
Fixed the Pre Main Fill crash in oot_soh.ShopItems.fill_shop_items when a
non-shuffled vanilla shop shelf still has item=None. SOH-EXTREME now repairs
only empty official Shop slots before calling the stock helper, preferring
vanilla/default metadata when available and falling back to Buy Heart when the
installed oot_soh version does not expose that metadata.

0.7.61 shop prefill hotfix
--------------------------
The 0.7.60 repair used LocTag.Shop, but oot_soh 1.4.x does not consistently tag
all stock Bazaar/Potion/Bombchu shelves that way. 0.7.61 identifies the actual
eight-shelf shop locations from their canonical location names, repairs every
empty vanilla shelf before fill_shop_items(), and performs an explicit pre-call
assertion so any remaining shelf is reported by name instead of crashing on
location.item.name.

0.7.62 Archipelago generator shop prefill fix
----------------------------------------------
This error was entirely in Generate.exe / the APWorld pre-fill stage.

Removed the previous "repair empty shop shelves" workaround. It was incorrect
because stock oot_soh.fill_shop_items() intentionally clears its reservations
before running a restrictive prefill.

SOH-EXTREME now uses oot_soh's own:
- get_vanilla_shop_pool()
- get_vanilla_shop_locations()
- remove_vanilla_shop_reservations()
- vanilla_shop_prices

and directly places those reserved vanilla shop items. This avoids the
NoneType location.item crash while preserving the stock selected pool, selected
reserved slots, randomization, prices, shop_vanilla_items, and prefill bookkeeping.

0.7.63 item/location balance + Bean Souls hotfix
-------------------------------------------------
The Generate.exe failure was an exact +607 item-pool overflow:
- 95 exact NPC Speech locations
- 512 fallback Speech locations
- total = 607

super().create_items() already counted those 607 dynamic locations when it
created stock filler. SOH-EXTREME then added another 607 Recovery Hearts, so the
seed had 607 more items than locations. That duplicate filler injection is gone.

Also restored the missing shuffle_bean_souls option and all ten native per-area
Bean Soul AP items (IDs 9500095..9500104), matching the existing C++ client.

0.7.65 preserve checks / trim junk only
---------------------------------------
Reverted the 0.7.64 idea of disabling provisional checks. All enabled Speech
Sanity and fork-native checks remain present.

The official oot_soh create_items() result is now treated as the fill-capacity
target. EXTREME items must replace existing filler. If a future combination of
settings still creates an overflow, SOH-EXTREME trims only junk/filler items
(recovery hearts, rupees, ammo, traps, then other non-progression filler) until
the original capacity is met. Progression/useful items are never silently
deleted; generation raises a clear error instead if junk is insufficient.

0.7.66 pool rebalancing fix
---------------------------
0.7.65 only recognized 47 removable junk items because it trusted oot_soh item
classification. Some stock rupees/ammo/hearts are classified useful even though
they are safe junk for EXTREME pool balancing.

0.7.66 computes overflow against actual fillable AP locations and removes local
known junk by name first. If needed, it then removes other local non-advancement
items. Progression/advancement items are never removed.

0.7.67 individual topology logic hotfix
----------------------------------------
The 0.7.66 seed filled successfully, then failed the final accessibility check.

Cause:
- Individual Languages does not create the wildcard `Speak` item.
- Individual Enemies does not create the wildcard `Enemy Soul` item.
- Individual Animals does not create the wildcard `Animal Soul` item.
- Several inherited/native overlay rules still required those wildcard items,
  making those rules permanently false.

Fixes:
- Native DNF overlays no longer require wildcard Speak/Enemy/Animal items when
  the corresponding Individual topology is selected.
- Exact Speech Sanity checks use require_speak() and therefore the proper language.
- Cucco interactions use Cucco Soul in Individual Animals mode.
- Deku Baba stick/nut events use Deku Baba Soul in Individual Enemies mode.
- Exact enemy-backed metadata now uses a concrete per-enemy Soul when its actor
  identity can be determined from the location name.

0.7.68 symmetric item-pool balancing
------------------------------------
The pool now always targets the exact per-player capacity captured from stock
oot_soh after all dynamic SOH-EXTREME locations exist.

- If there are too many items, remove junk/non-progression filler only.
- If there are too few items, add Recovery Heart junk filler until every enabled
  check has an item.
- Progression/advancement items are never removed.
- A final consistency check verifies the pool matches the target before fill.

0.7.69 global-pool balancing fix
--------------------------------
0.7.68 compared len(self.item_pool) against its pre-EXTREME value. That was
wrong because stock oot_soh puts much of its filler directly into
multiworld.itempool instead of self.item_pool. EXTREME replacement correctly
removed filler from the global pool, but the final check looked at the smaller
local list and falsely reported +166 items.

0.7.69 captures and balances the actual per-player global itempool size:
- extras replace junk in multiworld.itempool
- underflow adds Recovery Hearts
- overflow removes junk/non-advancement only
- progression is never removed
