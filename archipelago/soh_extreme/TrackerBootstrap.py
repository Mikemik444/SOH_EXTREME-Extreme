"""Build the SOH tracker from its connected slot, without reading player YAMLs.

Universal Tracker's ordinary bootstrap scans its Players directory even for a
world that supports slot-data regeneration.  This adapter changes that bootstrap
for one SOH context.  Region creation, rules, inventory evaluation and reporting
remain Universal Tracker's own implementations.

Keep this module independent of Archipelago/UT imports until installation: the
APWorld is also imported by generation and by the native worker's protocol tests.
"""
from __future__ import annotations

from argparse import Namespace
from collections.abc import Mapping
from copy import deepcopy
import importlib
import traceback


GAME = "SOH-EXTREME"


def _resolved_arguments(world_type, slot_data, slot_name, seed_name):
    """Make the option namespace consumed by the real UT ``TMain``.

    All options come from the server.  Old snapshots that published their options
    at the top level remain supported; a missing modern option cannot silently
    inherit a local YAML or a newly changed default.
    """
    from Options import NumericOption

    if not isinstance(slot_data, Mapping) or not slot_data:
        raise ValueError("The connected server did not provide a SOH-EXTREME slot snapshot.")
    snapshot = deepcopy(dict(slot_data))
    resolved = snapshot.get("extreme_all_options", snapshot)
    if not isinstance(resolved, Mapping):
        raise ValueError("The connected seed's extreme_all_options must be an option dictionary.")

    option_types = world_type.options_dataclass.type_hints
    if "extreme_all_options" in snapshot:
        unknown = sorted(set(resolved) - set(option_types))
        if unknown:
            raise ValueError(
                "The connected seed uses options this SOH-EXTREME APWorld does not support: "
                + ", ".join(unknown)
                + ". Install the APWorld version used by the room."
            )

    args = Namespace(multi=1, game={1: GAME}, name={1: slot_name}, race=False,
                     outputname=seed_name or slot_name, player_ids={1})
    missing = []
    raw_options = {}
    for name, option_type in option_types.items():
        if name in resolved:
            value = resolved[name]
        elif name in snapshot:
            value = snapshot[name]
        elif name == "song_note_songs":
            # Before per-song selection existed, note shuffle always selected
            # every song.  This is a defined legacy migration, not a local default.
            value = ["all"]
        else:
            missing.append(name)
            continue
        if (issubclass(option_type, NumericOption) and isinstance(value, str)
                and value.strip().lower().startswith("random")):
            raise ValueError(
                f"The connected seed has an unresolved random value for {name!r}. "
                "Tracker needs the resolved server option and cannot roll it again."
            )
        try:
            option = option_type.from_any(deepcopy(value))
        except Exception as exc:
            raise ValueError(
                f"Could not restore the connected seed's option {name!r}: {exc}"
            ) from exc
        setattr(args, name, {1: option})
        raw_options[name] = deepcopy(value)
        # A few legacy stock helpers read the duplicated top-level options.
        snapshot.setdefault(name, deepcopy(value))
    if missing:
        raise ValueError(
            "The connected seed is missing resolved options needed by this APWorld: "
            + ", ".join(missing)
            + ". Use a matching SOH-EXTREME APWorld or regenerate the room with a complete slot snapshot."
        )
    snapshot["extreme_all_options"] = raw_options

    for name in ("required_trials", "shop_prices", "shop_vanilla_items", "extreme_active_locations"):
        if name not in snapshot:
            raise ValueError(
                f"The connected seed is missing its saved {name!r}. "
                "Tracker cannot reconstruct that seed state safely from defaults."
            )
    for name in ("shop_prices", "shop_vanilla_items"):
        if not isinstance(snapshot[name], Mapping):
            raise ValueError(f"The connected seed's {name!r} must be a dictionary.")
    active = snapshot["extreme_active_locations"]
    if not isinstance(active, (list, tuple, set)) or any(type(location) is not int for location in active):
        raise ValueError("The connected seed's active locations must be numeric location IDs.")
    if not isinstance(snapshot["required_trials"], (list, tuple)):
        raise ValueError("The connected seed's required trials must be a saved list.")

    # This seed is only the deterministic bootstrap RNG.  Actual entrances,
    # trials, shop inventory/prices and resolved options are restored above.
    seed = snapshot.get("archipelago_seed", 0)
    if type(seed) is not int:
        raise ValueError("The connected seed's archipelago_seed must be an integer.")
    return args, seed, snapshot


def install_slot_data_core(context):
    """Install a context-local UT Core adapter and preserve its callbacks.

    The original class, global UT settings, process arguments and other tracker
    contexts are untouched.  Installing an unsupported UT version fails clearly
    instead of falling back to local YAML generation.
    """
    original = context.tracker_core
    if getattr(original, "_soh_slot_data_bootstrap", False):
        return original
    if not callable(getattr(original, "TMain", None)):
        raise RuntimeError(
            "SOH-EXTREME requires a Universal Tracker version with TrackerCore.TMain. "
            "Update tracker.apworld before starting the tracker."
        )
    upstream = importlib.import_module(type(original).__module__)
    package = importlib.import_module(upstream.__package__)
    log_line = upstream.TrackerLogLine
    log_group = upstream.TrackerLogLineGroup
    deferred_mode = package.DeferredEntranceMode

    class SlotDataTrackerCore(type(original)):
        _soh_slot_data_bootstrap = True

        def _set_host_settings(self):
            # Never access player_files_path: its UserFolderPath validation can
            # open a picker or fail before UT gets to its temporary slot YAML.
            settings = package.TrackerWorld.settings

            def setting(name, default):
                try:
                    return settings[name]
                except (KeyError, AttributeError):
                    return default

            location_names = bool(setting("include_location_name", True))
            region_names = bool(setting("include_region_name", False))
            report = "Both" if location_names and region_names else "Location" if location_names else "Region"
            sorting = str(setting("sorting_method", "apworld")) if location_names else "region"
            try:
                deferred = deferred_mode(setting("enforce_deferred_entrances", "default"))
            except (ValueError, TypeError):
                deferred = deferred_mode.default
            priorities = dict(setting("sorting_priorities", {}) or {})
            if not priorities:
                priorities = dict(default=0, hinted=1, excluded=2, excluded_glitched=3,
                                  hinted_glitched=4, glitched=5, unconnected=6)
            normalized_priorities = {}
            for name, value in priorities.items():
                try:
                    normalized_priorities[name] = max(0, int(value))
                except (ValueError, TypeError):
                    # A malformed display preference must not prevent a valid
                    # connected seed from loading.
                    continue
            priorities = normalized_priorities
            priorities["error"] = -1
            highest = max(priorities.values())
            priorities.setdefault("other", highest + 1)
            priorities["ut_status"] = highest + 2
            for category in log_group:
                priorities.setdefault(category.value, priorities["other"])
            return (None, report, bool(setting("hide_excluded_locations", False)),
                    bool(setting("use_split_map_icons", True)), deferred,
                    bool(setting("display_glitched_logic", True)), priorities, sorting)

        def disconnect(self):
            super().disconnect()
            self.launch_multiworld = None
            self.locations_available = []
            self.glitched_locations = []
            self.gen_error = ""
            self._soh_waiting_for_slot = False

        def updateTracker(self):
            if self.get_current_world() is None:
                # Preserve the waiting message or the specific slot-data error;
                # base UT otherwise replaces either with a missing-YAML message.
                return package.CurrentTrackerState.init_empty_state()
            return super().updateTracker()

        def initalize_tracker_core(self, connected_cls, raw_slot_data):
            if not isinstance(raw_slot_data, Mapping) or not raw_slot_data:
                # The upstream interpreter calls dict(slot_data) before the
                # generator, so handle an absent/malformed snapshot here too.
                self.run_generator({})
                return
            return super().initalize_tracker_core(connected_cls, raw_slot_data)

        def run_generator(self, slot_data=None, override_yaml_path=None, super_override_yaml_path=None):
            # The path parameters are retained for UT's existing call contract.
            # Only the connected server's snapshot is a source of seed data.
            self.multiworld = None
            self.launch_multiworld = None
            self.player_folder_override = None
            self.locations_available = []
            self.glitched_locations = []
            self.location_alias_map = {}
            self.tracker_disabled = False
            self.gen_error = ""
            try:
                (_, self.output_format, self.hide_excluded, self.use_split, deferred,
                 self.enable_glitched_logic, self.sorting_priorities,
                 self.sorting_method) = self._set_host_settings()
                if self.enforce_deferred_connections is None:
                    self.enforce_deferred_connections = deferred

                if slot_data is None:
                    passthrough = self.re_gen_passthrough or {}
                    slot_data = passthrough.get(GAME)
                if slot_data is None:
                    self.player_id = None
                    self.set_page(log_line(
                        "Connect to your SOH-EXTREME slot to load its saved options and logic. No player YAML is needed.",
                        "", log_group.UT_STATUS))
                    if not getattr(self, "_soh_waiting_for_slot", False):
                        self.logger.info("SOH-EXTREME tracker is waiting for server slot data; player YAMLs are not used.")
                    self._soh_waiting_for_slot = True
                    return
                self._soh_waiting_for_slot = False
                if self.game != GAME or not self.slot_name:
                    raise ValueError("Connect to a named SOH-EXTREME slot before rebuilding tracker logic.")
                from worlds.AutoWorld import AutoWorldRegister
                world_type = AutoWorldRegister.world_types[GAME]
                args, seed, snapshot = _resolved_arguments(
                    world_type, slot_data, self.slot_name, getattr(context, "seed_name", None))
                self.re_gen_passthrough = {GAME: snapshot}
                self.player_id = 1
                multiworld = self.TMain(args, seed)

                actual = {location.address for location in multiworld.get_locations(1)
                          if isinstance(location.address, int)}
                expected = set(snapshot["extreme_active_locations"])
                if actual != expected:
                    missing = sorted(expected - actual)
                    extra = sorted(actual - expected)
                    raise ValueError(
                        "The connected seed's location manifest does not match the regenerated graph "
                        f"({len(missing)} missing, {len(extra)} unexpected). "
                        "Use the SOH-EXTREME APWorld matching this room."
                    )
                # Same cleanup as UT's ordinary generator: AP delivers numeric
                # starting items through ReceivedItems; native events stay local.
                multiworld.precollected_items = {
                    player: [item for item in items if item.code is None]
                    for player, items in multiworld.precollected_items.items()
                }
                self.multiworld = multiworld
                self.logger.info("SOH-EXTREME tracker loaded %d checks from server slot data without player YAMLs.",
                                 len(expected))
            except Exception as exc:
                self.multiworld = None
                self.player_id = None
                self.tracker_disabled = True
                self.gen_error = traceback.format_exc()
                message = getattr(exc, "message", None) or str(exc) or type(exc).__name__
                self.logger.error("SOH-EXTREME tracker could not rebuild the connected seed: %s", self.gen_error)
                # Report the real slot/version error; do not inherit UT's generic
                # advice to install a YAML after slot-only generation fails.
                self.set_page(log_line("SOH-EXTREME tracker could not load this seed: " + message,
                                       "", log_group.UT_ERROR))

    core = object.__new__(SlotDataTrackerCore)
    core.__dict__.update(original.__dict__)
    # Upstream exposes process-wide caches.  This context always builds from its
    # current snapshot and must never reuse another connection's mutable world.
    core.cached_multiworlds = []
    core.cached_slot_data = []
    # These defaults also make errors during settings loading displayable before
    # the first successful generator call; base UT initializes them in GMain.
    core.sorting_priorities = {category.value: 0 for category in log_group}
    core.sorting_priorities["error"] = -1
    core.sorting_method = "apworld"
    core.output_format = "Location"
    core.hide_excluded = False
    core.use_split = True
    context.tracker_core = core
    return core
