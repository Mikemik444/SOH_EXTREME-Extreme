SOH-EXTREME 0.11.43 - Letter bottle logic and uncollected enemy glow
Repository: https://github.com/Mikemik444/SOH_EXTREME-Extreme

LETTER BOTTLE
Ruto's Letter counts as a reusable bottle only when child Link can reach King
Zora and perform the exchange. NPC Soul and Zora speech are required when
shuffled. Shared Speak counts in shared-language mode; a different individual
language does not count. Adult-only access to Zoras Domain is insufficient.

The missing requirements were on the delivery event, which feeds every bottle
rule. Both AP/Universal Tracker and native logic now gate that event correctly.
This fixes downstream fish/bottle checks together. An ordinary usable bottle
still works without King Zora. The Lake Hylia shortcut remains an alternative
to the waterfall route; Zelda's Lullaby is not imposed on every possible route.

ENEMY GLOW
Enemies with an active, uncollected AP Enemy Defeat drop now display a small
pulsing gold glow. It appears only after that enemy's required soul is owned
when souls are shuffled. Shared Enemy Soul and individual species souls follow
the existing runtime rules; ordinary Skulltulas use Skulltula Soul.

The indicator tracks collection, not merely defeating the enemy. It stops
when the physical drop is collected, including before server acknowledgment.
It is an uncollected-check marker, not a promise that you currently have every
combat or route requirement. Inactive, retired and untracked enemy checks do
not glow. Hidden/culled actors follow the game's normal draw behavior.
The enemy model/damage tint remain intact. No additional actors or saved actor
pointers are used, and the glow sends no network messages.

WINDOWS DRAG-AND-DROP
1. Close SOH. Extract the Windows ZIP into the folder containing the soh.exe
   you launch (E:\test\bb\x64\Release in the previously inspected installation).
   Replace both soh.exe and APCpp.dll. Keep existing assets, saves and settings.
2. Install the included soh_extreme.apworld with Archipelago's installer, or
   replace its existing copy in custom_worlds. Restart Archipelago/Universal
   Tracker and the in-game AP tracker so both sides use .43.
3. Reconnect and refresh the AP tracker. The startup log should identify
   SOH-EXTREME runtime 0.11.43. Re-enter the area if necessary.

SOURCE DRAG-AND-DROP
Extract the Source-Patch ZIP beside build.cmd, replacing the included files.
Run build.cmd in a fresh Command Prompt and wait for BUILD SUCCESS. Use the
generated runtime and install the matching .43 APWorld. The cumulative overlay
targets commit 9bc10e7191b546754a50da6463e074276d33862f; preserve unrelated edits.
The Windows ZIP is already built and does not require running build.cmd.

EXISTING SEEDS
No item or location IDs changed. Existing seeds and saves can load this update,
and their tracker uses the corrected rules. Their item placements do not move.
An old placement that depended on the incorrect letter-bottle rule is not
automatically repaired. Generate new seeds with .43 for corrected placement.
This update does not establish whether your current seed has such a dependency.

VALIDATION
Windows Release build; 624 AP/UT bottle assertions, including slot-data
reconstruction; 1793 native bottle assertions; 2027 enemy glow assertions
covering 51 mapped actor types; enemy pickup/model regression and DLL ABI tests;
104-file APWorld/source parity, package integrity and cumulative patch checks.
Fresh generation and source-aware replay using the saved supplied-settings
fixture reached the goal and all 3311 modeled checks, with no blocked checks.

Render/allocation/network services are controlled test substitutes. The glow
was not visually inspected in a running game. These tests are not a complete
physical playthrough or a guarantee that every remaining route is correct.
Prior .42 boulder/delivery fixes and earlier crash safeguards are included.
See VALIDATION-0.11.43-FIXES.json, TEST-EVIDENCE-0.11.43-FIXES.json and
SOH_AP_FIX_HISTORY.txt for evidence and earlier limitations.
