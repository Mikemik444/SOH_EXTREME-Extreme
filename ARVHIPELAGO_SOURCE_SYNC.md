# Building the SOH-EXTREME Archipelago world

`arvhipelago/` is the canonical source directory. Its spelling is intentional here
so the build matches the existing repository; no parallel `archipelago/` tree is
created. Both the main world and its patched `_vendor_oot_soh` modules live here.

Run `build.cmd` for a normal Windows client build. Its first step invokes
`tools/build_standalone_apworld.ps1`, which packages this source into the root
`soh_extreme.apworld`, verifies every entry against the source, and installs that
same archive into the detected Archipelago `custom_worlds` directory. The build
stops when source manifests, the Python tracker, and the C++ tracker disagree.

The packaging script does **not** fetch a fresh stock APWorld, replace the private
vendor folder, pick an old archive by modification date, or hard-code an older
world version. The legacy installer and `BUILD_FIXED_APWORLD.py` now delegate to
this source-based workflow. The latter only builds the root archive.

For an audit without changes, invoke the canonical PowerShell builder with
`-CheckOnly`. For a repository-only build, use `-SkipInstall`. An installation
outside the usual locations can be selected with `-ArchipelagoRoot` or the
`SOH_EXTREME_AP_ROOT` environment variable. These options do not alter gameplay.

`APWORLD_SOURCE_SYNC_REPORT.json` records the last successful package check.
This verifies file/version parity, **not** correctness of every gameplay rule;
full seed-generation and gameplay regression tests are still required for rule
changes. An old seed's placements are not relocated by installing updated logic.

The 0.11.22 source includes the Dodongo block-switch Grab requirement and the
native region alias corrections. Client-only artwork changes do not require
changing Python progression rules or incrementing the APWorld version.

After modifying a feature's AP logic, edit the files in `arvhipelago/`, build,
then commit the source and matching artifacts to GitHub. Local installers do not
commit or push on the user's behalf. Historical patch directories and old binary
archives are not sources for this build.
