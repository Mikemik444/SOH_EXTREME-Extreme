SOH-EXTREME 0.11.35 - Physical requirements and progression fix
Repository: https://github.com/Mikemik444/SOH_EXTREME-Extreme

WINDOWS DRAG-AND-DROP
Close SOH and the Archipelago/Universal Tracker clients first.
Back up your current game files and saves. Extract the Windows ZIP into the
folder containing soh.exe, replacing soh.exe and APCpp.dll.
Keep your existing soh.o2r, game assets, configuration and save files.
Install the included soh_extreme.apworld through Archipelago's APWorld
installer (or replace its existing copy in custom_worlds). Restart AP clients
so they load 0.11.35. The game and tracker must use the matching version.

SOURCE DRAG-AND-DROP
Extract the Source-Patch ZIP into the root of your SOH_EXTREME-Extreme source
checkout (the folder containing build.cmd). Accept replacement of the included
source files, then run build.cmd from a fresh Command Prompt. Wait for the full
BUILD SUCCESS result. This is cumulative against repository commit
9bc10e7191b546754a50da6463e074276d33862f and includes previous fixes.
If you edited these same files yourself, compare/merge them before overwriting.

FIXES
- All 179 mapped chest actors use their native chest types by persistent AP ID.
  Large chests require the second Open Chest receipt in progressive mode.
  This covers differently named chests and dynamically spawned minigame chests.
- Treasure Chest Game contributes six Small Keys to the pool when shuffled.
  Rooms 1-5 require their respective key counts; the final reward requires six.
  Skeleton Key and the minigame Key Ring substitute for the small keys.
  Neither substitutes for Open Chest. Owner conversation/payment is separate.
- Start With dungeon small keys grants the eight dungeon key sets without
  silently granting Fortress or Treasure Chest Game keys from other settings.
- Shadow Temple, GTG and Ganon's Castle enemy-guarded chests require the actual
  enemy combat/soul conditions, including their valid weapon alternatives.
- Spirit Temple Sun Block and Silver Gauntlets checks require Grab. The outer
  hand route also requires explosives and Climb or usable Longshot.
- The Sun Block stick route requires its completed silver-rupee group. Usable
  Din's Fire or Fire Arrows remain alternative fire sources.
- Eleven crater rock/boulder checks inherit their native heat requirement.
- Goron City's maze rock requires a way through the blocking boulders; simply
  owning Grab no longer makes that isolated rock reachable.
- Forest Temple's first-room ledge uses Climb or Longshot. The DMT Skulltula
  near Kakariko also needs a way to reach/collect it after blasting the wall.
- Hidden Skulltulas require a usable collection/attack method. The Market
  Guard House Skulltula and Anju's cucco reward include their crate requirement.
- Ice Cavern's blocked heart-piece alcove checks require clearing the obstacle;
  Giant's Knife remains a valid way to break stalagmites. The Water Temple river
  Skulltula's underwater route includes its breathing/tunic condition.

EXISTING SEEDS
An update changes rules; it cannot rearrange an already generated multiworld.
A (28329797861162018978) stalls before any player goal. Its second Open Chest,
Shovel and Skulltula Soul form a circular dependency. Regenerate this multiworld.
C (56771124513727284418) reaches Link's Triforce goal but leaves the Jigsaw
players unfinished and many checks inaccessible. Regenerate for full access.
B (15869480947154709792) completes all four goals and every check in the tested
replay. This is evidence from its placements and the audited requirements, not
a claim that every actor/collision or settings combination has been playtested.
Do not use a pre-fix spoiler's spheres as proof under the corrected rules.

VALIDATION
See VALIDATION-PHYSICAL-LOGIC-FIX.json and THREE-SEED-BEATABILITY-AUDIT.txt.
Regression tests compare native identities and local conditions with AP and
Universal Tracker. Fresh-inventory tests cover souls, abilities, item counts,
weapons and alternative methods. The generation matrix independently checks
source-derived interaction conditions at each progression sphere.
The final interaction audit covers 569 inventory scenarios, including partial
progressive upgrades and 128 reproducible combinations of missing receipts.
Untranslated source expressions remain explicitly listed in the audit data;
they are not counted as verified physical behavior. No live connected
playthrough, save modification or recovery item grant was performed.
