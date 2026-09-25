SOH-EXTREME 0.11.2 — standalone APWorld dependency fix
========================================================

Problem fixed
-------------
0.11.2 still imported `worlds.oot_soh.*`, so Archipelago failed before generation
when the stock oot_soh APWorld was not installed.

How this fix works
------------------
Run BUILD-STANDALONE-APWORLD.cmd once.

The builder downloads the official SoH 1.4.2 APWorld source bundle, vendors its
helper/data modules privately inside SOH-EXTREME as:

    soh_extreme/_vendor_oot_soh/

It then rewrites SOH-EXTREME's imports to that private package, empties the
vendored stock __init__.py so the stock AutoWorld is NOT registered, validates
that no `worlds.oot_soh` imports remain, builds the final APWorld, backs up the
existing installed file, and installs the new one at:

    C:\ProgramData\Archipelago\custom_worlds\soh_extreme.apworld

Output copy is also saved at:

    apworld\soh_extreme-0.11.2-standalone.apworld

This is a build-time source vendoring step only. Once built, SOH-EXTREME does not
need oot_soh.apworld installed alongside it.

The Forest Temple / Wall Skulltula / Poe / battle-arena changes from 0.11.2 are
retained because 0.11.2 is built from the complete 0.11.2 patch.
