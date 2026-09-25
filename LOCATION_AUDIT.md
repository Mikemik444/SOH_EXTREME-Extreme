# Location audit — 0.11.17

## Order of work

Correct existing definitions and test their requirements before expanding the
location set. This increment adds **zero new locations**. It retires two
nonfunctional AP-only pot entries while retaining their reserved enum IDs.
The enemy catalogue stays at 753 active checks; offspring spawned by enemies
or bosses remain excluded. Saved receipt indices are unchanged.

## Source inventory and configured graph

The native index contains 3,717 LOCATION definitions covering 3,461 distinct RC
identifiers, across both standard and MQ branches. This is a source inventory,
not 3,461 verified playable checks. `native-source-index.json` is the baseline
source inventory; `source-audit-final.json` records current native expressions.
The generated graph depends on the YAML,
layout and options; not every indexed source definition is active at once.

`validation/results/source-audit-final.json` contains all 3,502 configured graph
rows. The census is taken before `pre_fill`:

| Kind | Entries |
|---|---:|
| Stock locations | 1,673 |
| Fork locations | 726 |
| First-talk checks | 114 |
| Enemy checks | 753 |
| Events | 236 |
| Total | 3,502 |

The 2,399 stock/fork locations have explicit native/fork ID associations.
Speech and enemy checks use their own runtime/placement catalogues. Source
bindings do not establish that all controller, collection or respawn paths
work in a live game. Final tested seeds contain 3,258 network checks after
shop pre-fill; pre-fill changes eight addressed shops into events.

Each row records the AP region, native RC and source condition where available,
source file/line, identity basis and findings. `physical_verified` stays false:
no row is labeled physically verified merely because its predicate passed.

## Corrected findings

| Audit | 0.11.16 failures | Final failures in tested scope |
|---|---:|---:|
| Direct ability/soul prerequisites extracted from native source | 7 | 0 |
| Direct equipment/song/helper dependencies extracted from native source | 22 | 0 |
| Mandatory age, evaluated in the opposite age | 72 | 0 |
| Mandatory phase, evaluated in the opposite frozen phase | 6 | 0 |

These are audit assertions, not four disjoint sets of physical locations. The
final tests include some extra cases as coverage improved. See before/after
reports for individual check names and conditions.

The source parser strips comments, recognizes selected necessary expressions,
intersects OR alternatives and combines AND requirements. Unrecognized code
produces no inferred requirement. This avoids inventing restrictions, but
means a pass cannot certify unrecognized helpers, all route dependencies, or
all interactions. Whole-graph reachability and targeted alternatives are
separate tests, not substitutes for missing physical verification.

### Identity corrections

Existing mappings grow from 1,502 to 2,404 entries, with 902 unique explicit
bindings for already-existing checks. They use an unambiguous native enum or
runtime spoiler-name match, not proximity or another enemy's nearest check.
The beehive alias `RC_ZR_DEKU_SCRUB_GROTTO_BEEHIVE` maps to existing AP ID 787
(`ZR Storms Grotto Beehive`). The mapping table is compiled against actual native
enums and checked for one-to-one bindings.

IDs 943 and 944 are removed from active AP data/regions because no native
randomizer definition was found for Side Room Pots 5 and 6 in Dodongo's Cavern.
They are not renumbered or reused. An existing seed is not migrated.

### Positive alternatives

Missing-item tests alone can encourage over-restrictive logic. This pass also
tests positive alternatives: lifting grass without a cutting weapon, usable
Cucco routes, supported equipment alternatives, and material-specific boulder
methods. Other local requirements remain conjunctive; for example, changing
Deku Tree grass collection does not remove the scrub shield or web puzzle.

## Remaining route and runtime work

The report deliberately retains these flags:

| Finding | Rows | Interpretation |
|---|---:|---|
| `room_route_unreviewed` | 413 | Enemy checks still use broad entryway region parents. Their exact room approaches are not complete. |
| `native_ap_region_crosswalk_requires_review` | 729 | Region spellings, aliases or graph contraction do not match directly. Some may be equivalent; these are not 729 proven route bugs. |
| `first_talk_runtime_identity_requires_review` | 114 | Source identity exists, but the full live dialogue/quest-state lifecycle has not been playtested. |
| `physical_encounter_not_playtested` | 340 | Other enemy checks have more specific parents but have not been physically playtested. |
| `neutral_parent_requires_explicit_complete_route` | 2 | A neutral parent needs its full explicit access condition checked; parent naming alone is not a verdict. |

Flags overlap. They must not be added together as a count of distinct broken
checks. Clearing a naming/crosswalk flag is not proof of physical accessibility.
The exact 413 enemy rows are also listed in `catalogue-final.json`.

Irreversible quest-state changes, scene clearing/despawning, finite scripted
encounters, full Master Quest routes, and complete resource-renewal assumptions
remain part of the unfinished audit. Existing unresolved entries have not all
been disabled by this patch. Consequently this is not a 'certified checks only'
world, and current model replay success is not a guarantee of a beatable game.

Before adding an excluded check, establish its native placement/controller,
finite identity, precise region and complete approach, soul/action prerequisites,
actual collection and persistence behavior, and matching AP/native rules. Enemy-
created offspring remain intentionally excluded even when their source is known.
