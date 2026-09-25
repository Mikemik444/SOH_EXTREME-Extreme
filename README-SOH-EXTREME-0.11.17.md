# SOH-EXTREME 0.11.17 — existing-location corrections

**Apply over 0.11.16. This is an incremental patch, not a complete game source tree.**

This release prioritizes existing checks. No new checks were added. It includes
24 complete changed/new native files under `soh/`, a ready-to-install
`soh_extreme.apworld`, complete matching AP sources under `source/soh_extreme/`,
source diffs, and actual validation results. No `src/` or asset files change in
this increment; keep all of your existing files from 0.11.16 and earlier patches.

## Installation

1. Close the game. Merge the archive into `E:\test\bb`, overwriting the included
   files. **Do not delete or replace your whole `soh` or `src` directories.**
2. Build using your existing configuration:

   ```bat
   cd /d E:\test\bb
   cmake --build build-vs --config Release --parallel 8
   ```

3. Close Archipelago and Universal Tracker. Replace the installed world with the
   archive's `soh_extreme.apworld`, normally at:

   ```text
   C:\ProgramData\Archipelago\custom_worlds\soh_extreme.apworld
   ```

   Keep only one installed SOH-EXTREME world. Use the same 0.11.17 world in every
   installation that runs generation or Universal Tracker, then restart them.
4. **Generate a new seed.** Your existing YAML needs no edits. Updating a client
   or tracker cannot move progression already placed behind an incorrect rule.
   Two AP-only pot entries without native check definitions have also been
   retired; an older server seed can still expect them.

No asset regeneration, dependency updates or new build configuration are
required by these source changes. A full Windows build was not run here.

## Principal corrections

- Grass collection now permits cutting **or** a supported Grab/lift method.
  This changes 344 native grass location expressions and 259 corresponding AP
  expressions. It does not turn walking through grass into a valid action,
  broaden cutting-only resource events, or remove other puzzle requirements.
  Existing contact-bush behavior remains distinct.
- 175 source-derived fork age gates close the wrong-age failures; 13 necessary
  day/night gates close frozen-phase failures. Alternatives are intersected:
  a requirement is mandatory only when every native alternative requires it.
- Existing checks have 902 additional explicit native-to-AP bindings, yielding
  2,404 unique mappings. These are mappings for existing IDs, NOT 902 new checks.
  The Zora's River scrub/storms-grotto beehive alias is explicit.
- Lost Woods underwater rupees, Gerudo Training Ground silver-rupee actions,
  Ganon's fire-trial under-pillar silver rupee, the Zora's Fountain underground
  boulder, and six beggar bottle-content checks have corrected prerequisites.
- Talon's chicken check uses the actual location spelling and requires its
  Cucco/Animal Soul, Grab, NPC Soul and speech. Zora's River heart-piece routes
  retain complete Cucco and legitimate equipment alternatives. Mask of Truth
  at the Deku Theater requires the corresponding NPC/language interaction.
- Business-scrub interaction cannot bypass NPC Soul merely because speech
  shuffle is disabled. The Chest Game fee requires wallet capacity.
- The generic native boulder gate no longer overrides material-specific
  location methods with an extra explosives-or-Grab requirement. Bronze
  boulders can use their Hammer route without unrelated Grab. Ordinary small
  rocks retain the explicit native explosives-or-Grab policy.
- Light Arrow cutscene requirements are shared between the native rule and
  physical save trigger. AP Triforce Hunt keeps the vanilla Shadow + Spirit
  condition; non-hunt AP seeds use the selected milestone. Save identity is
  checked independently of whether the AP connection is enabled.

The retired entries are `Dodongos Cavern Side Room Pot 5` (943) and
`Dodongos Cavern Side Room Pot 6` (944). They had no corresponding native
randomizer check/receipt definition in the supplied project. This is not a
claim that a similarly named physical prop can never exist. Their numeric
identifiers remain reserved; other checks and enemy receipt slots are unchanged.

## What the audit does and does not establish

The supplied-YAML graph has an audit row for every configured location:
3,502 graph locations, including 3,266 network-addressed entries before shop
pre-fill. Eight shop entries become events during this generation setup,
leaving 3,258 network checks in each final tested seed.

Source identity, local prerequisites and AP reachability tests are not physical
room verification. **413 enemy entries still have broad entry-region parents.**
Other route crosswalks, first-talk lifecycles, quest-state changes and Master
Quest coverage are unfinished. No new checks are enabled as a claim that those
areas are complete. See `LOCATION_AUDIT.md` and `VALIDATION.md`.

The ready AP world was loaded from its actual ZIP and two full fills plus
independent progression replays passed within its model. No complete Windows
executable build, live tracker UI session or in-game completion was performed.
