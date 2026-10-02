SOH-EXTREME 0.11.51 - Deku Theater leader

The Skull Mask reward requires NPC Soul when shuffled. The audience may still
be visible while the leader who gives the reward is missing. Its automatic
textbox does not require Speak. Mask of Truth still needs Deku speech.

Close SOH before copying the Windows package into the game directory. Install
soh_extreme.apworld into Archipelago/custom_worlds, then restart the AP client
and tracker. The SOH and APWorld versions must match (.51). Existing saves,
check IDs, and placements are preserved. No need to regenerate to use the
tracker correction. Back up the existing game directory before replacing it.

This package includes the ROM extractor assets and all prior fixes through
.50. It contains no ROM or oot.o2r. The separate Source Patch ZIP contains the
cumulative source overlay and a checked patch against repository commit
9bc10e7191b546754a50da6463e074276d33862f.

Validation: 182 AP/Universal Tracker assertions, restored-slot tests, and a
native Release build. No live gameplay test was performed.

Seed 10112245550148649225 was generated using .46. Auditing its exact original
placements under the corrected rules stalls at 7 of the required 30 pieces,
from a fresh start and from the saved room progress snapshot. This update
corrects the Skull Mask tracker entry but DOES NOT repair that seed's existing
progression cycles. See SEED-10112245550148649225-AUDIT.txt for details.
