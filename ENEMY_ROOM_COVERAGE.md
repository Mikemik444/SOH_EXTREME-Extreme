# Enemy-room coverage — 0.11.18

## The previous 413-entry gap

The old AP data attached 413 enemies to a dungeon-entry region, while native
Check Finder used an unrelated whole-dungeon equipment/key requirement for many
of them. Both mechanisms are removed from the affected paths.

All 413 are now in `source/soh_extreme/EnemyRoomMap.json`, together with the other
122 dungeon entries brought onto the same graph. There are **535 mapped entries**
and **zero active enemy parents named ENTRYWAY**. This statement concerns graph
assignments; it does not label every physical encounter as playtested.

| Scene | Existing enemy entries mapped |
|---|---:|
| Deku Tree | 32 |
| Dodongo's Cavern | 38 |
| Jabu-Jabu's Belly | 61 |
| Forest Temple | 40 |
| Fire Temple | 66 |
| Water Temple | 54 |
| Spirit Temple | 77 |
| Shadow Temple | 47 |
| Bottom of the Well | 34 |
| Ice Cavern | 21 |
| Ganon's Tower | 13 |
| Gerudo Training Ground | 25 |
| Ganon's Castle | 26 |
| Spirit boss-room Iron Knuckle encounter | 1 |
| **Total** | **535** |

## Evidence and identity

The room crosswalk uses authored room numbers, door connections, exact existing
chest/Skulltula identifiers and actor-list placement coordinates from the supplied
`oot(1).o2r`. It does not select the nearest enemy or nearest randomizer check.

The manifest records the network ID, immutable actor identity, room, native
region, source file/line and additional local condition. Of the 535 records,
**511 directly match the canonical actor-list index/id/parameters** extracted
from the main room header. The other **24 use the existing finite controller or
alternate-header alias catalogue**; they are not presented as 24 newly verified
main-header placements. Their identity fields are unchanged.

`physical_playtest` remains **false** in every manifest record. The uploaded
resource archive is not included in this patch.

## Route graph

`EnemyRoomGraph.json` is an exact snapshot of the 429 selected vanilla C++
region definitions, including 1,130 internal connection/event predicates.
`EnemyRoomLogic.py` translates the supported expression grammar and game helpers
into real AP rules. Deferred age/time actions are represented by local events.
Unknown helper/syntax/dependency errors stop generation rather than granting
unconditional access.

The private AP regions only receive bindings from their established dungeon
entrances. They do not create shortcuts back into the original overworld graph.
Room switches, age-dependent actions, water levels and trial state are not
replaced by a generic full-equipment test.

Native-only optional tricks with no exposed AP option are disabled and listed in
`validation/results/enemy-regressions-packaged.json`. They are not assumed to be
selected or copied from local randomizer menu settings. The supplied AP option
surface does not expose a native Master Quest/entrance-shuffle configuration for
this enemy catalogue; those are not claimed as covered.

## Optional internal action sites

A native flag can have several activation sites, including disabled tricks or
child-only reverse routes. AP full accessibility must not require every
impossible alternative site. At pre-fill, a full-inventory fixed point removes
only unreachable **unaddressed internal action sites** from that requirement.

This does **not** remove a network check, grant its flag, relax its condition or
make a blocked dependency accessible. Tests compare network IDs and reachability
before/after. The exact internal site list is saved in slot data and reused by UT,
not recomputed from the player's received inventory. The tested default/six-trial
case removes five such internal alternative sites.

## Remaining physical verification

Source-derived routing is stronger than dungeon-entry placement, but still
inherits limitations of the native graph and its helper functions. In-room
position subdivisions, combat alternatives, collision, ammo/health timing,
one-time quest transitions and permanent actor despawns still require engine
and playthrough validation. This patch does not change those runtime systems or
claim their complete verification.

Enemy-created offspring remain excluded. Previously unmapped escape-sequence
Stalfos and chance-spawned skull-jar Keese are not newly added by this patch.
