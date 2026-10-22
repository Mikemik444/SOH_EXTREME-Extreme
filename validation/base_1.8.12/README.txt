SOH-EXTREME 1.8.12 - Complete source files
========================================

GROTTO LANDING AND RETURN HISTORY
--------------------------------
The exterior grotto table stores the beginning of the native exit jump. It is
not a standing return position. Exterior returns now resolve the native neutral
exit trajectory against the destination collision before placing Link at its
landing point. The checks cover floor support, slope and hazards, water, walls,
ceilings, the hole trigger, and nearby collision actors. If the destination
cannot prove a clear stationary landing, the native exit jump runs and its first
safe grounded landing becomes the checkpoint.

The landed position replaces the current room's death checkpoint and native
return data. Dying before the landing retains the emergence start mode. Dying
afterward restores the room checkpoint while retaining the previous-scene
history. Return to Previous Scene restores the last clear source-side position
and facing, including beside a grotto hole. A falling/on-hole position cannot
replace that clear departure point.

An existing interior grotto spawn remains inside that grotto. In particular,
the retained seed's child spawn 187 -> 1806 remains the HF Stone Bridge Tree
Grotto interior; it is not rewritten to the exterior return 2062.

ZORA'S RIVER LAND AND WATER CONNECTIONS
--------------------------------------
The land and water crossings between Hyrule Field and Zora's River are four
separate directed endpoints, grouped into two coupled entrance/exit pairs:

  Hyrule Field -> Zora's River, land: 234 / 0x00EA
  Zora's River -> Hyrule Field, land: 385 / 0x0181
  Hyrule Field -> Zora's River, water: 473 / 0x01D9
  Zora's River -> Hyrule Field, water: 785 / 0x0311

Both source and arrival water routes require Swim. Age and day/night arrival
layers are validated independently. Crossing/check credit and entrance discovery
retain the exact physical path. The entrance catalog now has 721 endpoints,
including 54 overworld endpoints and 300 native indexed endpoints.

New seeds export an explicit river-path revision and may shuffle these two pairs
independently. Older saved maps retain their original land/water alias routing,
without adding or changing saved entrance targets. Independent water/land
shuffling requires generating a new seed with the included APWorld.

AMMO PROTECTION
---------------
Deku Sticks, Deku Nuts, Bombs, Bombchus and arrows automatically keep their last
carried unit usable until the managed tracker proves a renewable refill for that
specific ammunition. Ordinary use still spends quantities above one. The rule
also covers stick breakage/burning and ammo-reducing traps. It does not create a
unit in an empty inventory, grant a missing bag or weapon, or extend finite
minigame counters. A source of arrows does not remove bomb protection.

The proof uses the current age, live inventory, rupees, Soul and interaction
requirements, and the seed's actual AP entrance/room graph. It removes the target
ammo while testing source access, clears previously derived route events, and
resweeps those events. A route cannot prove refill access merely because Link
owns its Bomb Bag or Bow while the route needs that same spent ammunition.

Verified sources include retained renewable shop stock, ordinary unshuffled
ammo scrubs, the Carpet Merchant's renewable stock after any required first
purchase, reviewed renewable overworld enemy drops, and observed fixed-drop pots
and crates. Source-specific prices, item-use and break/kill requirements apply.
One-time AP ammo packs, randomized shop/scrub rewards and uncleared first checks
do not count as repeatable stock.

For pots and crates, the game records the exact check identity, observed age,
native drop parameters and collectible flag. Only proven fixed drops with flag
zero qualify, after the worker verifies that exact source's room access and any
first AP check completion. Loading an actor by itself never grants refill access.
Persistent or unknown drop settings, unverified grass/bush drops and Bowling
refill cycles retain protection; they are not guessed to be renewable sources.

The worker continues running with Check Finder closed. The native client accepts
only a fresh proof tied to this save, its current inventory/source state and its
applied AP receipts. Age, source, inventory, rupee or relevant setting changes
invalidate the previous permission. Manual or ignored tracker edits cannot
change gameplay refill permission. If the worker is unavailable, disconnected,
or has no verified refill, the last carried unit remains protected.

Use both the updated native sources and included APWorld for this feature.
Existing seeds can use the protection without regenerating their item placement.

INSTALL AND BUILD
-----------------
1. Merge soh, src, archipelago and tools into your complete checkout, replacing
   the corresponding files. Copy SOURCE_FILES.json, BUILD_RELEASE.cmd and
   BUILD_RELEASE.ps1 into the checkout root as well.
2. For E:\test\bb, run:

   cd /d E:\test\bb
   BUILD_RELEASE.cmd -RepositoryPath "E:\test\bb" -BuildDirectory "build-vs"

   The helper verifies every replacement source and performs a clean Release
   build. Run the executable path printed by that successful build.
3. Install the root soh_extreme.apworld at:
   C:\ProgramData\Archipelago\custom_worlds\soh_extreme.apworld
   Restart the Archipelago client/generator so the updated world is loaded.
4. Existing seeds can retain their saved entrance mappings. Generate a new seed
   to obtain independent Zora's River land/water shuffling.

The package contains cumulative complete replacement sources, including the
previous Check Finder, entrance-label, Soul, dungeon-return, Dodongo and
CVarGetInteger declaration fixes. Source verification uses the included manifest.

VALIDATION AND SCOPE
--------------------
The current source-bound tests passed:
  - Ammo use: 1,001 native cases / 1,239 assertions.
  - Pot/crate source identity: 6,269 native cases / 27,852 assertions.
  - Refill logic: 10 AP groups / 284 decisions / 55 actual refill probes.
  - Tracker transport: 97 wire cases, 19 encoder assertions, 127 native cases
    / 311 assertions, and 48 Python handler cases / 103 assertions.
  - Renewable drop bounds: 983 native cases / 3,143 assertions.
  - Grotto landing: 143 native scenarios / 2,106 assertions.
  - Room-return/death integration: 938 native cases.
  - River paths: 93 native cases / 2,726 assertions and 6 AP tests
    / 851 decisions, including exact legacy-map replay and fresh generation.
  - The official Archipelago 0.6.8 archive loader verified all 123 APWorld
    entries and version 1.8.12 parity. The shipped PowerShell source preflight
    verified all 235 complete replacement files.

VALIDATION.txt explains scope and limitations. The current report JSON, source
hashes, native fixture dependencies, regression baselines and replay instructions
are supplied under validation/landing_river_1812.

A Windows game build and an in-game controller playthrough were not available
in this partial-source environment. Native fixtures execute production function
bodies with explicit engine I/O shims. Actual scene geometry is checked by the
game at runtime; the fixture geometry is controlled test input.

Earlier release evidence remains under validation with its original bytes. The
old full item-placement/44-sphere seed reconstruction is historical. The current
river regression replays its exact 719-route map and separately generates a new
721-route entrance map; it does not claim a new complete item fill or playthrough.
Use the current APWorld at the ZIP root for installation. Older APWorld copies
inside validation folders are retained solely as historical test evidence.
