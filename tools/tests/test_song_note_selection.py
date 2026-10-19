"""Exercise selectable song notes with the actual AP options, pools and rules.

Run with the supported Archipelago runtime on PYTHONPATH. Prefill tests execute
the official restrictive fill; only hint creation is isolated when testing slot
serialization before a complete item fill. No game client is simulated here.
"""
from collections import Counter
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch
import argparse
import io
import json
import time
import unittest

import ModuleUpdate
ModuleUpdate.update_ran = True
import settings
settings.no_gui = True
settings.skip_autosave = True
import Utils
from BaseClasses import CollectionState, PlandoOptions
from Options import OptionError
from test.general import setup_multiworld
from worlds.AutoWorld import call_all
from worlds import soh_extreme
from worlds.soh_extreme import SohExtremeWorld
from worlds.soh_extreme.Options import SongNoteSongs
from worlds.soh_extreme.SongNotes import SONG_NOTE_KEYS, SONG_NOTE_LAYOUT, song_note_mask
from worlds.soh_extreme._vendor_oot_soh import SongShuffle
from worlds.soh_extreme._vendor_oot_soh.Enums import Items, Regions
from worlds.soh_extreme._vendor_oot_soh.LogicHelpers import can_play_song, ocarina_buttons_required


SOURCE = Path(__file__).resolve().parents[2]
SELECTED = {"Zelda's Lullaby", "Bolero of Fire"}
ALL_SONGS = {song for song, _ in SONG_NOTE_LAYOUT}
CONFIGURATIONS = []


def build_world(label, *, rules=False, prefill=False, **overrides):
    options = {
        'song_note_shuffle': 'individual_notes',
        'song_note_songs': ['zeldas_lullaby', 'bolero_of_fire'],
        'shuffle_songs': 'anywhere',
        'shuffle_ocarinas': 1,
        'shuffle_ocarina_buttons': 1,
        'skip_child_zelda': 0,
    } | overrides
    if options.get('song_note_songs') is None:
        del options['song_note_songs']
    multiworld = setup_multiworld(SohExtremeWorld, steps=(), seed=189, options=options)
    world = multiworld.worlds[1]
    call_all(multiworld, 'generate_early')
    # Use Main's public precollection path and timing, including both AP common
    # options. From-pool removal itself remains Main's later responsibility.
    for field in ('start_inventory', 'start_inventory_from_pool'):
        for name, count in getattr(world.options, field).value.items():
            for _ in range(count):
                multiworld.push_precollected(world.create_item(name))
    for step in ('create_regions', 'create_items'):
        call_all(multiworld, step)
    if rules or prefill:
        call_all(multiworld, 'set_rules')
    if prefill:
        for step in ('connect_entrances', 'generate_basic', 'pre_fill'):
            call_all(multiworld, step)
    CONFIGURATIONS.append({'name': label, 'options': options, 'through_prefill': prefill})
    return world


def pool(world):
    return Counter(item.name for item in world.multiworld.itempool if item.player == world.player)


def blank_state(world):
    originals = world.multiworld.precollected_items[1]
    world.multiworld.precollected_items[1] = []
    try:
        return CollectionState(world.multiworld)
    finally:
        world.multiworld.precollected_items[1] = originals


def collect(world, state, name, count=1):
    for _ in range(count):
        state.collect(world.create_item(str(name)), True)


class SongSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.partial = build_world('two songs', rules=True)

    def test_keys_and_full_names_normalize_without_renumbering(self):
        for index, (key, (song, length)) in enumerate(zip(SONG_NOTE_KEYS, SONG_NOTE_LAYOUT)):
            with self.subTest(song=song):
                self.assertEqual(SongNoteSongs.from_any([song.upper()]).value, {key})
                self.assertEqual(SohExtremeWorld.item_name_to_id['Progressive ' + song], 9500300 + index)
                self.assertEqual(len(SohExtremeWorld.SONG_NOTE_GROUPS[song]), length)
        self.assertEqual(sum(count for _, count in SONG_NOTE_LAYOUT), 74)
        self.assertEqual(SongNoteSongs.from_any('Zelda’s Lullaby, BOLERO OF FIRE').value,
                         {'zeldas_lullaby', 'bolero_of_fire'})
        self.assertEqual(SongNoteSongs.from_any(['all', 'song_of_time']).value, {'all'})
        self.assertEqual(SongNoteSongs.from_any([]).value, set())
        for invalid in (['not_a_song'], [123]):
            with self.subTest(invalid=invalid), self.assertRaises(OptionError):
                SongNoteSongs.from_any(invalid)
        # Keep the standard AP OptionSet random parser operational.
        random_choice = SongNoteSongs.from_any('random-range-2-2')
        random_choice.verify(SohExtremeWorld, 'Song selection test', PlandoOptions(0))
        self.assertEqual(len(random_choice.value), 2)

    def test_subset_pool_contains_only_selected_progressive_songs(self):
        counts = pool(self.partial)
        self.assertEqual(counts["Progressive Zelda's Lullaby"], 6)
        self.assertEqual(counts['Progressive Bolero of Fire'], 8)
        for song in ALL_SONGS:
            with self.subTest(song=song):
                self.assertEqual(counts[song], int(song not in SELECTED))
                if song not in SELECTED:
                    self.assertEqual(counts['Progressive ' + song], 0)
        self.assertEqual(song_note_mask(self.partial.options), 0x81)
        self.assertFalse(any(name.startswith('Song Note ') for name in counts))

    def test_all_default_preserves_existing_74_copy_pool(self):
        world = build_world('legacy default all', song_note_songs=None)
        counts = pool(world)
        self.assertEqual(world.options.song_note_songs.value, {'all'})
        for song, required in SONG_NOTE_LAYOUT:
            self.assertEqual(counts['Progressive ' + song], required)
            self.assertEqual(counts[song], 0)
        self.assertEqual(song_note_mask(world.options), 0xFFF)

    def test_empty_selection_and_mode_off_keep_whole_songs(self):
        for label, options in (
            ('empty selection', {'song_note_songs': []}),
            ('mode off', {'song_note_shuffle': 'off'}),
        ):
            with self.subTest(configuration=label):
                world = build_world(label, **options)
                counts = pool(world)
                self.assertEqual(world._song_note_groups(), {})
                self.assertEqual(song_note_mask(world.options), 0)
                for song in ALL_SONGS:
                    self.assertEqual(counts[song], 1)
                    self.assertEqual(counts['Progressive ' + song], 0)

    def test_each_song_can_be_selected_independently(self):
        options = self.partial.options
        original = options.song_note_songs
        try:
            for index, (song, count) in enumerate(SONG_NOTE_LAYOUT):
                with self.subTest(song=song):
                    options.song_note_songs = SongNoteSongs.from_any([song])
                    self.assertEqual(song_note_mask(options), 1 << index)
                    self.assertEqual(self.partial._song_note_groups(),
                                     {song: ('Progressive ' + song,) * count})
        finally:
            options.song_note_songs = original

    def test_unselected_songs_keep_vanilla_locations(self):
        world = build_world('partial with vanilla songs', shuffle_songs='off', prefill=True)
        for location_name, song in SongShuffle.song_vanilla_locations.items():
            with self.subTest(song=str(song)):
                location = world.get_location(location_name)
                if str(song) in SELECTED:
                    self.assertIsNone(location.item)
                    self.assertIsNotNone(location.address)
                else:
                    self.assertEqual(location.item.name, str(song))
        self.assertEqual(len(world.multiworld.itempool), len(world.multiworld.get_unfilled_locations()))

    def test_unselected_songs_keep_song_and_dungeon_reward_prefill(self):
        for mode in ('song_locations', 'dungeon_rewards'):
            with self.subTest(mode=mode):
                world = build_world('partial with ' + mode, shuffle_songs=mode, prefill=True)
                song_locations = set(SongShuffle.song_vanilla_locations) if mode == 'song_locations' else set(
                    SongShuffle.dungeon_reward_song_locations)
                complete = [loc for loc in world.get_locations() if loc.item and loc.item.name in ALL_SONGS]
                self.assertEqual({loc.item.name for loc in complete}, ALL_SONGS - SELECTED)
                self.assertTrue(all(loc.name in song_locations for loc in complete))
                self.assertFalse(any(str(item) in ALL_SONGS for item in world.pre_fill_pool))
                self.assertEqual(len(world.multiworld.itempool), len(world.multiworld.get_unfilled_locations()))
                self.assertEqual(sum(pool(world)['Progressive ' + song] for song in SELECTED), 14)

    def test_plentiful_removes_all_selected_whole_song_copies(self):
        world = build_world('plentiful subset', item_pool='plentiful')
        counts = pool(world)
        for song, required in SONG_NOTE_LAYOUT:
            if song in SELECTED:
                self.assertEqual(counts[song], 0)
                self.assertEqual(counts['Progressive ' + song], required)
            else:
                self.assertGreaterEqual(counts[song], 1)

    def test_stock_starting_song_toggles_expand_only_selected_songs(self):
        world = build_world('starting song toggles', start_with_zeldas_lullaby=1, start_with_eponas_song=1)
        starting = Counter(item.name for item in world.multiworld.precollected_items[1])
        self.assertEqual(starting["Progressive Zelda's Lullaby"], 6)
        self.assertEqual(starting["Zelda's Lullaby"], 0)
        self.assertEqual(starting["Epona's Song"], 1)
        self.assertEqual(starting["Progressive Epona's Song"], 0)
        self.assertEqual(pool(world)["Progressive Zelda's Lullaby"], 0)

    def test_common_starting_inventory_expands_selected_songs_only(self):
        world = build_world('common starting inventory', start_inventory={
            "Zelda's Lullaby": 1, 'Bolero of Fire': 1, "Epona's Song": 1})
        self.assertEqual(world.options.start_inventory.value, {
            "Progressive Zelda's Lullaby": 6, 'Progressive Bolero of Fire': 8, "Epona's Song": 1})
        counts = pool(world)
        for song in SELECTED:
            self.assertEqual(counts['Progressive ' + song], 0)
            self.assertEqual(counts[song], 0)
        # Every selected note is precollected, so replacing selected whole songs
        # must still run when there are zero extra note copies to place.
        self.assertEqual(sum(item.name in SELECTED for item in world.multiworld.itempool), 0)

    def test_from_pool_starting_requests_keep_main_removal_units(self):
        world = build_world('from pool starting inventory', start_inventory_from_pool={
            "Zelda's Lullaby": 1, "Epona's Song": 1})
        self.assertEqual(world.options.start_inventory_from_pool.value,
                         {"Progressive Zelda's Lullaby": 6, "Epona's Song": 1})
        self.assertEqual(pool(world)["Progressive Zelda's Lullaby"], 6)
        self.assertEqual(pool(world)["Epona's Song"], 1)

    def test_selected_completion_and_removal_invalidate_actual_song_rules(self):
        world = self.partial
        for song, needed in ((Items.ZELDAS_LULLABY, 6), (Items.BOLERO_OF_FIRE, 8)):
            with self.subTest(song=str(song)):
                rule = can_play_song(song, (Regions.ROOT, world)).resolve(world)
                state = blank_state(world)
                collect(world, state, Items.PROGRESSIVE_OCARINA)
                for button in ocarina_buttons_required[song]:
                    collect(world, state, button)
                self.assertFalse(rule(state))
                # A stale/manual full-song receipt cannot bypass selected notes.
                collect(world, state, song)
                self.assertFalse(rule(state))
                collect(world, state, 'Progressive ' + str(song), needed - 1)
                self.assertFalse(rule(state))
                collect(world, state, 'Progressive ' + str(song))
                self.assertTrue(rule(state))
                state.remove(world.create_item('Progressive ' + str(song)))
                self.assertFalse(rule(state))

    def test_unselected_song_requires_ocarina_and_buttons_but_no_notes(self):
        world = self.partial
        song = Items.EPONAS_SONG
        rule = can_play_song(song, (Regions.ROOT, world)).resolve(world)
        state = blank_state(world)
        collect(world, state, song)
        self.assertFalse(rule(state))
        collect(world, state, Items.PROGRESSIVE_OCARINA)
        self.assertFalse(rule(state))
        buttons = ocarina_buttons_required[song]
        for button in buttons[:-1]:
            collect(world, state, button)
        self.assertFalse(rule(state))
        collect(world, state, buttons[-1])
        self.assertTrue(rule(state))
        self.assertEqual(state.count('Progressive ' + str(song), 1), 0)

    def test_selected_complete_notes_still_require_ocarina_and_buttons(self):
        world = self.partial
        song = Items.ZELDAS_LULLABY
        rule = can_play_song(song, (Regions.ROOT, world)).resolve(world)
        state = blank_state(world)
        collect(world, state, 'Progressive ' + str(song), 6)
        self.assertFalse(rule(state))
        collect(world, state, Items.PROGRESSIVE_OCARINA)
        self.assertFalse(rule(state))
        for button in ocarina_buttons_required[song]:
            collect(world, state, button)
        self.assertTrue(rule(state))

    def test_mixed_legacy_starting_notes_use_order_independent_progressive_receipts(self):
        for field in ('start_inventory', 'start_inventory_from_pool'):
            for reverse in (False, True):
                entries = [("Progressive Zelda's Lullaby", 5), ('Song Note 01', 1)]
                if reverse:
                    entries.reverse()
                with self.subTest(field=field, reverse=reverse):
                    world = build_world('legacy note normalization ' + field + str(reverse),
                                        **{field: dict(entries)})
                    self.assertEqual(getattr(world.options, field).value,
                                     {"Progressive Zelda's Lullaby": 6})
                    starting = Counter(item.name for item in world.multiworld.precollected_items[1])
                    self.assertEqual(starting["Progressive Zelda's Lullaby"], 6)
                    self.assertEqual(starting['Song Note 01'], 0)
                    self.assertEqual(pool(world)["Progressive Zelda's Lullaby"],
                                     6 if field == 'start_inventory_from_pool' else 0)

    def test_duplicate_legacy_starting_flags_count_once_across_options(self):
        world = build_world('duplicate legacy requests',
                            start_inventory={"Progressive Zelda's Lullaby": 4, 'Song Note 01': 3},
                            start_inventory_from_pool={'Song Note 01': 1, 'Song Note 02': 2})
        self.assertEqual(world.options.start_inventory.value, {"Progressive Zelda's Lullaby": 5})
        self.assertEqual(world.options.start_inventory_from_pool.value, {"Progressive Zelda's Lullaby": 1})
        self.assertEqual(pool(world)["Progressive Zelda's Lullaby"], 1)

    def test_legacy_tracker_starting_receipt_names_are_not_rewritten(self):
        for revision in (0, 1):
            with self.subTest(revision=revision):
                multiworld = setup_multiworld(SohExtremeWorld, steps=(), options={
                    'song_note_shuffle': 1, 'song_note_songs': ['zeldas_lullaby'],
                    'start_inventory': {"Progressive Zelda's Lullaby": 5, 'Song Note 01': 1}})
                world = multiworld.worlds[1]
                world.using_ut = True
                world.passthrough = {'song_note_catalog_revision': revision}
                world._expand_starting_song_requests()
                self.assertEqual(world.options.start_inventory.value,
                                 {"Progressive Zelda's Lullaby": 5, 'Song Note 01': 1})

    def test_new_selected_song_plando_rejects_legacy_overlap_and_full_song_bypass(self):
        world = self.partial
        location = next(loc for loc in world.multiworld.get_unfilled_locations() if loc.address is not None)
        try:
            with patch('worlds.soh_extreme.FrontierFill.validate_filled_world'):
                for item in ('Song Note 01', "Zelda's Lullaby"):
                    with self.subTest(item=item):
                        location.item = world.create_item(item)
                        with self.assertRaisesRegex(OptionError, 'legacy numbered notes'):
                            world.post_fill()
                # Whole-song plando remains supported for an unselected song.
                location.item = world.create_item("Epona's Song")
                world.post_fill()
        finally:
            location.item = None

    def test_slot_snapshot_and_legacy_tracker_restore_preserve_selection(self):
        # This world is intentionally unfilled: hints have separate full-fill
        # validation, while all actual option/slot serialization runs here.
        with patch.object(soh_extreme, 'CreateInGameHints', return_value={}), patch.object(
                soh_extreme, 'CreateNonlocalHints', return_value=[]):
            slot = self.partial.fill_slot_data()
        self.assertEqual(slot['song_note_songs'], ['bolero_of_fire', 'zeldas_lullaby'])
        self.assertEqual(slot['extreme_all_options']['song_note_songs'], slot['song_note_songs'])
        self.assertEqual(slot['extreme_soh_cvars']['SongNoteSongMask'], 0x81)
        self.assertEqual(slot['extreme_soh_cvars']['SongNoteShuffle'], 1)
        self.assertEqual(slot['progressive_song_requirements'], {
            "Progressive Zelda's Lullaby": 6, 'Progressive Bolero of Fire': 8})
        for legacy, revision in ((False, 1), (True, 1), (True, 0)):
            with self.subTest(legacy=legacy, revision=revision):
                saved = dict(slot)
                saved['extreme_all_options'] = dict(slot['extreme_all_options'])
                saved['song_note_catalog_revision'] = revision
                if legacy:
                    saved.pop('song_note_songs')
                    saved['extreme_all_options'].pop('song_note_songs')
                multiworld = setup_multiworld(SohExtremeWorld, steps=(), options={
                    'song_note_shuffle': 0, 'song_note_songs': ['song_of_time']})
                world = multiworld.worlds[1]
                multiworld.re_gen_passthrough = {world.game: saved}
                world._apply_universal_tracker_slot_data()
                self.assertEqual(set(world._song_note_groups()), ALL_SONGS if legacy else SELECTED)
                self.assertEqual(song_note_mask(world.options), 0xFFF if legacy else 0x81)
                if revision == 0:
                    self.assertEqual(world._song_note_groups()["Zelda's Lullaby"][0], 'Song Note 01')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    source_files = sorted(p for p in (SOURCE / 'archipelago/soh_extreme').rglob('*')
                          if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc')
    source_files.append(Path(__file__))
    hashes = lambda: {p.relative_to(SOURCE).as_posix(): sha256(p.read_bytes()).hexdigest() for p in source_files}
    before = hashes()
    start = time.monotonic()
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(SongSelectionTests))
    unchanged = before == hashes()
    report = {
        'passed': result.wasSuccessful() and unchanged, 'test_cases': result.testsRun,
        'archipelago_version': Utils.__version__, 'source_sha256': before,
        'source_unchanged_during_tests': unchanged, 'configurations': CONFIGURATIONS,
        'output': stream.getvalue(), 'elapsed_seconds': round(time.monotonic() - start, 3),
        'scope': __doc__,
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + '\n')
    print(stream.getvalue())
    print(json.dumps({name: report[name] for name in
                      ('passed', 'test_cases', 'source_unchanged_during_tests', 'elapsed_seconds')}))
    raise SystemExit(0 if report['passed'] else 1)


if __name__ == '__main__':
    main()
