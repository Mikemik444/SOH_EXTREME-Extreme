# SOH-EXTREME

Install `soh_extreme.apworld` in Archipelago's `custom_worlds` folder. This world includes its own SoH foundation.

## Generate the full YAML template

Use Archipelago Launcher -> **Generate Template Options**.
The generated `SOH-EXTREME.yaml` is produced from `SohExtremeOptions`, which inherits the complete official `SohOptions` dataclass and adds the SOH-EXTREME options.

The Options Creator likewise exposes the complete inherited stock SoH option set plus the custom Extreme option groups.

## Track a connected slot without a YAML

Keep `tracker.apworld` installed alongside `soh_extreme.apworld`. Select **SOH-EXTREME Universal Tracker** in Archipelago Launcher for a separate tracker window, or use the game's Check Finder for the background tracker.

Both SOH entry points load the generated slot's resolved settings and saved entrance destinations from the server. They do not read your `Players` folder, `weights.yaml`, or `meta.yaml`; your personal YAML is only needed to generate a seed. Connect with the room address and slot name as usual.

The SOH tracker waits for the server before creating its logic graph. If the installed APWorld cannot reconstruct the slot's saved options and active check list, it reports that mismatch instead of using local defaults. Keep the game source and SOH APWorld versions matched.

The generic Universal Tracker launcher also supports this world's slot-data regeneration after connecting, but retains upstream's separate preconnection folder scan. Use **SOH-EXTREME Universal Tracker** to avoid that startup dependency entirely.
