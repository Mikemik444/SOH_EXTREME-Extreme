# Enemy coverage — 0.11.13

## Rule and scope

**753 active checks across 53 catalogued actor types.** There are still 786
append-only native receipt slots. The 21 old Peahat-larva locations
`9800765..9800785` are reserved, inactive and not reused. Together with ten
structural Armos and two noncombat Skull Kid helper slots, 33 slots are inactive.
The complete receipt table is byte-for-byte identical to 0.11.12.

Enemies created by enemies or bosses are not additional checks. This applies
both to `Actor_SpawnAsChild` and raw `Actor_Spawn`, including nested actor init,
update, draw, destruction and actor-hook calls. The creator's original hostile
classification remains valid after its params or category are transformed.
Enemy-created non-enemy helpers also carry that provenance, so they cannot
launder an offspring into a legitimate controller encounter. Mutable or cyclic
parent pointers are not used to determine origin.

Gohma larvae placed in scene data still count. Larvae created by the Gohma boss
and Peahat offspring do not. Bari's spawned Biri, extra Stinger bodies, extra
Floormaster fragments, Meg decoys and other monster-generated actors do not
receive independent locations. This does not delete their ordinary gameplay
or normal loot, and does not remove the existing Soul system.

Non-enemy puzzle/room-controller encounters remain supported, including the
three Forest Bow-room Stalfos, real Poe Sisters, Anubis, Dark Link, Big Octo,
coffin/grave enemies, Field Poe source sites and bounded Stalchild/Leever lanes.
All forty catalogued Forest Temple checks retain their room-specific rules.

## What was actually checked

The mixed C/C++ test compiles the real C spawn path and the real C++ source,
identity, classification and resolver functions together. It exercises 705
static aliases, 95 non-enemy scripted aliases, 14 physical grotto identities
and four real-sister identities: 818 positive alias/encounter cases. These are
aliases of the 753 checks, not 818 distinct locations. It also tests all 53
catalogued actor types as hostile creators against all 786 receipt slots:
41,658 offspring-rejection combinations, including attempted pooled rebinds.

A static audit finds native defeat callbacks for all 53 catalogued actor types.
The callback file/line matrix is `validation/results/source-audit.json`.
Callback presence is not proof that every damage, animation, collision or
scripted branch executes correctly. Complete runtime tests are not available
for every actor implementation.

## Remaining incomplete coverage

- Zelda's collapse-escape Stalfos and chance-spawned skull-jar Keese still have
  no newly defined finite checks in this package. They are not enemy offspring;
  they remain unfinished encounter/opportunity mappings, not intentional
  exclusions under the new rule. Boss-created Gohma larvae, in contrast, are
  now explicitly excluded by the requested policy.
- **413 AP enemy checks still use broad ENTRYWAY region assignments.** This
  patch does not finish exact native/AP/Universal Tracker room-by-room logic
  parity for those checks. Their full list is in
  `validation/results/catalog-tests.json`.
- Irreversible quest-state population changes remain unaudited. Recovering an
  earned-but-uncollected pickup does not recreate an enemy that disappeared
  before the player ever defeated it. There is no new Master Quest catalogue.
- There was no full MSVC/Windows game build, live-server/UT client session,
  resource/object-bank test, collision/animation test or complete playthrough.

This package enforces the origin rule and corrects identified lifecycle bugs.
It must not be described as every enemy or every physical seed fully verified.
