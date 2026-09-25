# SOH-EXTREME 0.11.20 — automatic AP tracker and region groups

Apply over **0.11.19**. This is a tracker integration/display update, not a
new location-logic audit. The AP world rules, location IDs, enemy identities,
item receipts, souls, and the no-enemy-offspring rule are unchanged.

## Use

1. Close SoH and Archipelago/Universal Tracker while replacing their files.
2. Merge `soh` into your project root (`E:\test\bb`) and overwrite the included
   files. Do not delete the existing `soh` or `src` directories.
3. Rebuild from your working command prompt:

   ```bat
   cd /d E:\test\bb
   cmake --build build-vs --config Release --parallel 8
   ```

4. Replace `C:\ProgramData\Archipelago\custom_worlds\soh_extreme.apworld`
   with the included file. Leave `tracker.apworld` installed beside it.
   Use one installed SOH-EXTREME world, not multiple renamed copies.
5. Start the game and load/connect your Archipelago save normally. Do not
   launch the special tracker entry or a separate Universal Tracker window.

**No new seed, YAML edits, or asset regeneration are required for this update.**
The source archive under `source` is the complete AP world source, not another
file you need to install beside the ready-made `.apworld`.

## What runs automatically

For Windows AP gameplay saves, the game owns a windowless Universal Tracker
worker, using the Python/runtime already in the installed Archipelago program.
It reuses the installed `tracker.apworld` and SOH-EXTREME AP rules; there is no
second C++ approximation of those rules. No extra Python installation is needed.
This is a managed helper process, **not Python embedded in the SoH executable**.

The worker receives the game's server, slot and password through a private
inherited anonymous pipe. Credentials are not put in its command line or a
new configuration file. It connects as a read-only Tracker client, obtains slot
data and the AP received-item history itself, evaluates with Universal Tracker,
and publishes results bound to that game session. It does not grant items,
complete checks, or change generation rules.

The Windows Job controls only this game's worker process tree. Returning to file
select, loading a non-AP save, disconnecting, or closing the game stops it.
Startup failures have bounded retries and an in-game error; no guessed native
availability replaces a missing result. The old public special-tracker card
is now a hidden implementation entry rather than a user launch step.

Normal local randomizer saves keep the native C++ tracker and do not start this
worker. Automatic process hosting in this patch targets Windows.

## Region view

- Checks are grouped under collapsible **AP region names**, with normal and
  glitched counts for each group. Checked locations remain excluded.
- **Current area first** is enabled initially; all other regions remain visible.
  Highlighting uses the AP-ID-to-native-area mapping only, never for availability.
- **Only current area** and a region/check search are available. While area
  metadata is still loading, the current-area filter does not silently drop checks.
- Ordinary checks appear before separately labelled glitched checks within each
  region. Changing sorting/filtering does not change a check's logic result.

"Current area" means the game's tracked scene area, not an assertion that every
listed subregion is the exact room where Link is standing. The AP region names
remain visible so the player can distinguish their subareas.

## Runtime detection and troubleshooting

The game searches the Archipelago installation registry entries and common
installation directories. A portable/custom installation can be selected in
**Check Tracker > Archipelago runtime location** by entering its full folder or
`ArchipelagoLauncherDebug.exe` path and pressing **Use path and retry**. This is
an in-game runtime setting, not a request to manually launch another program.
An empty field restores automatic detection.

The detected installation must contain both the updated `soh_extreme.apworld`
and the user's normal `tracker.apworld`. The game verifies that the managed
worker module is installed before starting the launcher, preventing an old or
missing component from opening the Launcher GUI instead.

**Refresh AP checks** requests a current result. **Restart AP tracker** resets
only the owned worker and its session. The Archipelago logs include a
`SOH-EXTREME-InGameTracker` log when the worker gets far enough to initialize UT.

The automatic view uses AP's received items, like UT. It warns when the game
save has not yet applied every delivered item. Manually granted game inventory
is not treated as an AP receipt. For an independent UT comparison, use the same
slot/settings and no `/manually_collect` or `/ignore` overrides: the private
worker deliberately does not import old persisted hypothetical inventory or
ignored-location commands from another UT window.

## Validation limits

See `VALIDATION.md`. No full Windows/MSVC executable build, live AP/UT connection,
or visual gameplay session was performed in this environment. The included
controlled tests verify the changed integration and grouping paths, not every
physical location or Windows runtime dependency.
