SOH-EXTREME 0.11.58 - Bottom of the Well Crawl and AP shop purchases

Bottom of the Well:
The normal child entrance now requires Crawl before the corridor spider and
perimeter. The six EXTREME Botw Boulder checks now inherit basement access,
instead of being attached to the entryway before the crawlspace. Their IDs
9700003-9700008 are unchanged. Rock / Boulder Soul and usable explosives remain
required when shuffled. Child cannot use an owned adult Hammer. Climb is not
added to the route down to the basement; the return ladder does require it.

The old name-based Crawl workaround covered "Bottom of the Well" checks but
missed "EXTREME Botw" boulders. The entrance now gates every stock check and
event beyond it. Enemy and silver checks keep their native room graph.
Disabled ability/soul shuffles remain innate.

AP shops:
AP-owned shelves always use the one-time check purchase callbacks, including
the original shield position while its item scout is still pending. An owned
item, a missing bottle/upgrade, a remote display model, or an Ice Trap disguise
can no longer block purchase of an uncollected AP check. Prices and already
purchased flags are still checked. Native/non-AP shop restrictions are retained.

The supplied AP YAML specifies seven randomized items per shop. This APWorld
supports 0-7; Ship's local eighth-item setting does not add a location to the
server's existing seed. This release does not invent an eighth AP placement or
certify the reported eighth-shelf symptom as reproduced in live gameplay.

Install:
Close SOH, copy the Windows package contents into the game directory, install
soh_extreme.apworld into Archipelago/custom_worlds, and restart the AP client
and tracker. Use matching .58 versions. Saves, check IDs and existing placements
are retained. Corrected placement logic applies to new seed generation; updating
an old seed does not move its items or guarantee that it remains completable.

Includes all fixes through .57 and the ROM extractor assets. No ROM or oot.o2r
is included. The source ZIP contains the cumulative source overlay and a verified
patch against commit 9bc10e7191b546754a50da6463e074276d33862f.

Validation:
60,612 real AP/Universal Tracker assertions cover six boulders, blocked Well
checks of every enabled family, water drainage, Crawl, Climb, Rock Soul, Bombs,
Bombchus, unusable child Hammer, both starting ages, disabled shuffles, absent
private room graphs and restored slot settings. Old .57 fails 608 assertions.
182,402 compiled production shelf identity, eligibility and payment assertions
cover eight shop scenes and all eight shelf positions, delayed scouts, every
local rejection category, purchased checks, free/priced items and native stock.
Old .57 fails 15,680 assertions. Four existing price/payment regressions pass.
Windows Release build and packaged source/runtime integrity are verified.
No live game playtest was performed.
