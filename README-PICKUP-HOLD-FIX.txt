SOH-EXTREME 0.11.37 - Important pickups and courtyard window removal
Repository: https://github.com/Mikemik444/SOH_EXTREME-Extreme

WINDOWS REPLACEMENT
Close SOH. Extract the Windows ZIP into the folder of the soh.exe you actually
launch, replacing soh.exe and APCpp.dll. For a source build this may be
x64\Release rather than the source root. Keep your existing assets and saves.
Install the included soh_extreme.apworld through Archipelago's installer, or
replace the existing copy in custom_worlds. Restart the AP/Universal Tracker
clients. Runtime and APWorld both use version 0.11.37 for the tracker handshake.

SOURCE REPLACEMENT
Extract the Source-Patch ZIP into your SOH_EXTREME-Extreme source root, beside
build.cmd, and replace the included files. Run build.cmd from a fresh Command
Prompt. Wait for BUILD SUCCESS. This source patch is cumulative against Git
commit 9bc10e7191b546754a50da6463e074276d33862f and includes earlier fixes.
Merge any independent edits you made to the same source files.

FIXES
- Permanently excludes EXTREME Hc Wonder Courtyard Left Window and Right
  Window from new AP seeds in every Wonder Items mode and from hint groups.
  They do not appear as checks in the tracker for a newly generated seed.
  Their original IDs remain reserved for old server compatibility.
  Native window/guard reward overrides respect the AP seed's active checks.
- Fast Pickup Text no longer skips important AP drop animations. Major items
  and keys retain the overhead animation from rock, grass and enemy actors.
  Ordinary refills remain quick. The Fast Pickup Text setting can stay enabled.
- Enemy-defeat AP-only pickups now queue remote-item overhead presentations,
  including important Jigsaw pieces. Saved journal/reconnect retries are silent.
- Souls, abilities, door keys and adult trade items now wait for the matching
  engine receipt before being marked delivered. An accepted animation offer
  alone can no longer consume a reward or permit a later reward to overwrite it.
- Combined Speak correctly signals receipt completion after granting its six
  language flags. Animation attempts interrupted before the grant remain pending.
- Progressive Wallets also hold overhead. Full Wallets fills the actual new
  capacity when the engine grants the upgrade, including capped repeats.
  Gold Skulltula Tokens use the overhead path when native logic marks them
  important for a token-based bridge or boss-key requirement.
- Important remote rewards use the AP model and name the item and recipient.
  Same-slot rewards use the native received-item presentation. Both wait until
  Link is in a safe state; swimming, carrying, pause and cutscenes defer them.
- Retains 0.11.36: ability/soul overhead entries, song-note and Silver Rupee
  counts, proximity Wonder rupee rules, Peahat daytime logic, and Sun's Song
  changing day/night then freezing at the new phase until Flow of Time is found.

EXISTING SAVES
The pickup fixes work on existing seeds and saves without regeneration.
REMOVING THE TWO WINDOW CHECKS REQUIRES A NEW SEED generated with this APWorld.
An existing server already has items assigned to its locations. For those old
seeds the client/tracker retains both placements rather than hiding owed items.
Do not expect replacing files alone to rewrite an existing server's seed.
Previously received items are not given again just to replay the animation.
Updating does not repair circular placements generated under older rules.

VALIDATION
See VALIDATION-PICKUP-HOLD-FIX.json and CHECK-AUDIT-PICKUP-HOLD-FIX.json.
The engine animation-decision regression fails 45 cases on 0.11.36 and passes
all 384 on this release. Native receipt and presentation functions were tested
with controlled engine/network services, and a Windows Release build completed.
Castle regressions check new-seed exclusion, all four shuffle modes, tracker
restoration and unchanged legacy server manifests. A fresh full seed is checked
with the AP generator and independent progression replay; see the report for
its exact result and the harness's scope.
No rendered in-game or connected-server playthrough was performed.
