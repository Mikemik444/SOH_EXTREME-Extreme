"""Validate NPC Soul interaction rules in actual SOH-EXTREME AP worlds.

All invisible NPC conversations, rewards and exchanges must be unavailable,
including the Kokiri exit boy and adult Lost Woods Mido whose collision is retained. Physical gates and
age/language prerequisites remain independent requirements. This is a focused
rule regression, not a full item fill or native gameplay test.
"""
from pathlib import Path
import argparse
import inspect
import hashlib
import json
import random
import time

import ModuleUpdate
ModuleUpdate.update_ran = True
import settings
settings.no_gui = True
settings.skip_autosave = True
import Utils
import yaml
from Generate import roll_settings
from test.general import setup_multiworld
from worlds.AutoWorld import call_all
from worlds.soh_extreme import SohExtremeWorld, NpcSpeech
from worlds.soh_extreme._vendor_oot_soh.Enums import Ages, Items, Regions, Tricks


INTERACTIONS = (
    ('Mido', 'child', 'Kokiri'),
    ('Mido From Outside Deku Tree', 'child', 'Kokiri'),
    ("ZD Deliver Ruto's Letter", 'child', 'Zora'),
    ('Kak Gate', 'child', 'Hylian'),
    ('Kak Gate Guard', 'child', 'Hylian'),
    ('Kak Adult Talon', 'adult', 'Hylian'),
    ('GF Gate', 'adult', 'Gerudo'),
    ('GF Gate Outside', 'adult', 'Gerudo'),
    ('GTG Gate', 'adult', 'Gerudo'),
    ('ZD King Zora Thawed', 'adult', 'Zora'),
    ('ZD Trade Prescription', 'adult', 'Zora'),
    ('LLR Talon Race', 'adult', 'Hylian'),
    ('LLR Time Trial', 'adult', 'Hylian'),
)

# Native actions audited against the real actors. A physical gate remains a
# gate even when its operator is hidden. The song trigger in the windmill is a
# background actor, and is deliberately not reclassified as an NPC interaction.
SOURCE_FILES = (
    'archipelago/soh_extreme/__init__.py',
    'archipelago/soh_extreme/NpcSpeech.py',
    'archipelago/soh_extreme/NpcSpeechCatalog.json',
    'archipelago/soh_extreme/NativeLogic.py',
    'archipelago/soh_extreme/NativeLogicAlternatives.py',
    'archipelago/soh_extreme/NativeAbilityAudit.py',
    'archipelago/soh_extreme/_vendor_oot_soh/LogicHelpers.py',
    *('archipelago/soh_extreme/_vendor_oot_soh/location_access/overworld/' + name + '.py'
      for name in ('castle_grounds', 'gerudo_fortress', 'kakariko', 'kokiri_forest',
                   'lost_woods', 'zoras_domain', 'lon_lon_ranch')),
    'soh/Enhancements/randomizer/logic.h',
    'soh/Enhancements/randomizer/logic.cpp',
    'soh/Enhancements/randomizer/location_access.cpp',
    'soh/Enhancements/randomizer/randomizer_check_tracker.cpp',
    *('soh/Enhancements/randomizer/location_access/overworld/' + name + '.cpp'
      for name in ('castle_grounds', 'gerudo_fortress', 'kakariko', 'kokiri_forest',
                   'lost_woods', 'zoras_domain', 'lon_lon_ranch')),
    'src/overlays/actors/ovl_En_Md/z_en_md.c',
    'src/overlays/actors/ovl_En_Ta/z_en_ta.c',
    'src/overlays/actors/ovl_Bg_Relay_Objects/z_bg_relay_objects.c',
    'soh/Network/Archipelago/NpcSpeechScenes.inc',
    'soh/Network/Archipelago/NpcSpeechAreas.inc',
)


def verify_mido_routes(world, full, checks, configuration):
    """Test the actual two directed edges, without unrelated meadow approaches."""
    soul = bool(world.options.shuffle_npc_soul.value)
    speech = world.options.shuffle_speak.value
    trick = (bool(world.options.enable_all_tricks.value)
             or str(Tricks.LW_MIDO_BACKFLIP) in world.options.tricks_in_logic.value)
    language = ('Speak' if speech == 1 else 'Speak Kokiri',)
    song = str(Items.SARIAS_SONG)
    missing_song = (f'Progressive {song}', *world.SONG_NOTE_GROUPS[song], song)
    missing_instrument = (str(Items.PROGRESSIVE_OCARINA),)
    missing_all = ('NPC Soul', *language, *missing_song, *missing_instrument)
    for source, target, forward in ((Regions.LOST_WOODS, Regions.LW_BEYOND_MIDO, True),
                                    (Regions.LW_BEYOND_MIDO, Regions.LOST_WOODS, False)):
        matches = [edge for edge in world.get_region(str(source)).exits
                   if edge.connected_region and edge.connected_region.name == str(target)]
        assert len(matches) == 1, (source, target, len(matches))
        edge = matches[0]
        bypass = forward and trick
        cases = [
            ('adult', (), True),
            ('adult', ('NPC Soul',), not soul or bypass),
            ('adult', language, not speech or bypass),
            ('adult', missing_song, bypass),
            ('adult', missing_instrument, bypass),
            ('adult', missing_all, bypass),
            ('child', missing_all, True),
        ]
        for age, missing, expected in cases:
            state = full.copy()
            for name in (str(Items.GLITCHED), *missing):
                while state.has(name, world.player):
                    state.remove(world.create_item(name))
            state._soh_extreme_age[world.player] = Ages[age.upper()]
            actual = bool(edge.access_rule(state))
            row = dict(configuration, entrance=edge.name, age=age, missing=list(missing),
                       expected=bool(expected), actual=actual)
            checks.append(row)
            assert actual == bool(expected), row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('yaml_path', type=Path)
    parser.add_argument('--report', type=Path)
    parser.add_argument('--source-root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--seed', type=int, default=189)
    args = parser.parse_args()
    source_root = args.source_root.resolve()
    loaded_world = Path(inspect.getfile(SohExtremeWorld))
    expected_world = source_root / 'archipelago/soh_extreme/__init__.py'
    if not loaded_world.is_file() or loaded_world.read_bytes() != expected_world.read_bytes():
        parser.error('Load this source tree as worlds/soh_extreme before running this regression.')
    source_hashes = {name: hashlib.sha256((source_root / name).read_bytes()).hexdigest()
                     for name in SOURCE_FILES}
    started = time.monotonic()
    random.seed(args.seed)
    rolled = roll_settings(yaml.safe_load(args.yaml_path.read_text(encoding='utf-8-sig')))
    options = {name: getattr(rolled, name).value for name in SohExtremeWorld.options_dataclass.type_hints}
    options = {name: dict(value) if isinstance(value, dict) else value for name, value in options.items()}
    options.update(starting_age='child', closed_forest='on', kakariko_gate='closed',
                   zoras_fountain='closed', shuffle_npc_soul=1, npc_speech_sanity=1,
                   shuffle_adult_trade_items=1, skip_epona_race=0,
                   enable_all_tricks=0, tricks_in_logic=set())
    checks = []
    worlds = []

    # All three speech modes are tested with NPC Soul enabled. Disabling either
    # feature must make only that capability innate, not the other feature.
    configurations = [(1, speech, skip) for speech in (0, 1, 2) for skip in (0, 1)]
    configurations.append((0, 2, 0))
    for soul_mode, speech_mode, skip in configurations:
        mw = setup_multiworld(SohExtremeWorld, steps=(), seed=args.seed,
                              options=dict(options, shuffle_npc_soul=soul_mode,
                                           shuffle_speak=speech_mode, skip_child_zelda=skip))
        world = mw.worlds[1]
        for stage in ('generate_early', 'create_regions', 'create_items', 'set_rules'):
            call_all(mw, stage)
        full = mw.get_all_state(False)
        configuration = dict(shuffle_npc_soul=soul_mode, shuffle_speak=speech_mode,
                             skip_child_zelda=skip)

        def state_for(age, missing=()):
            state = full.copy()
            for name in missing:
                while state.has(name, 1):
                    state.remove(world.create_item(name))
            state._soh_extreme_age[1] = Ages[age.upper()]
            return state

        def verify(name, age, missing, expected):
            location = world.get_location(name)
            actual = bool(location.access_rule(state_for(age, missing)))
            row = dict(configuration, check=name, age=age, missing=list(missing),
                       expected=expected, actual=actual)
            checks.append(row)
            assert actual == expected, row

        def language_item(language):
            return 'Speak' if speech_mode == 1 else 'Speak ' + language

        verify_mido_routes(world, full, checks, configuration)

        # Test every active first-conversation identity at both ages. The denied
        # case does not depend on finding the NPC's normal age or time of day.
        baseline_available = 0
        for entry in NpcSpeech.active_entries(world):
            if entry['name'] not in world._npc_conversations:
                continue
            for age in ('child', 'adult'):
                location = world.get_location(entry['name'])
                baseline = bool(location.access_rule(state_for(age)))
                baseline_available += baseline
                verify(entry['name'], age, ('NPC Soul',), False if soul_mode else baseline)
                if baseline:
                    verify(entry['name'], age, (), True)
                    if speech_mode:
                        removed = (tuple('Speak ' + lang for lang in NpcSpeech.LANGUAGES)
                                   if entry['language'] == 'Any' and speech_mode == 2 else
                                   (language_item(entry['language']),))
                        verify(entry['name'], age, removed, False)
        assert baseline_available, configuration

        # Explicit formerly exempt placements, including the exit boy who is
        # still allowed to have blocking collision while hidden.
        for name, age, language in (
            ('NPC Speech: Kokiri Forest Exit Boy', 'child', 'Kokiri'),
            ('NPC Speech: Mido', 'child', 'Kokiri'),
            ('NPC Speech: King Zora', 'adult', 'Zora'),
            ('NPC Speech: Talon', 'adult', 'Hylian'),
        ):
            verify(name, age, ('NPC Soul',), not bool(soul_mode))
            if speech_mode:
                verify(name, age, (language_item(language),), False)

        for name, age, language in INTERACTIONS:
            verify(name, age, (), True)
            verify(name, age, ('NPC Soul',), not bool(soul_mode))
            if speech_mode:
                verify(name, age, (language_item(language),), False)

        # Restoring NPC Soul must not erase the other physical prerequisites.
        for name, age, missing in (
            ('Mido', 'child', (str(Items.KOKIRI_SWORD),)),
            ('Mido', 'child', (str(Items.BUY_DEKU_SHIELD),)),
            ('Kak Gate', 'child', (str(Items.ZELDAS_LETTER),)),
            ('GTG Gate', 'adult', (str(Items.GERUDO_MEMBERSHIP_CARD),)),
            ('GTG Gate', 'adult', (str(Items.PROGRESSIVE_WALLET),)),
            ('ZD Trade Prescription', 'adult', (str(Items.PRESCRIPTION),)),
            ('Kak Adult Talon', 'adult', (str(Items.POCKET_EGG),)),
        ):
            verify(name, age, missing, False)
        verify('Mido', 'adult', (), False)
        verify('Kak Gate', 'adult', (), False)
        verify('ZD Diving Minigame', 'child', ('NPC Soul',), not bool(soul_mode))
        if not skip:
            verify('HC Malon Egg', 'child', ('NPC Soul',), not bool(soul_mode))

        for source, target in (('Hyrule Castle Grounds', 'HC Past Gate'),
                               ('HC Moat', 'HC Drain Ledge')):
            region = world.get_region(source)
            edge = next(e for e in region.exits if e.connected_region and e.connected_region.name == target)
            # Isolate the normal paid gate / Talon-and-crates approaches from
            # legitimate alternate traversal (vine route is a separate edge).
            missing = ('NPC Soul', str(Items.HOVER_BOOTS))
            actual = bool(edge.access_rule(state_for('child', missing)))
            expected = not bool(soul_mode) or (source == 'HC Moat' and bool(skip))
            row = dict(configuration, entrance=edge.name, age='child', missing=list(missing),
                       expected=expected, actual=actual)
            checks.append(row)
            assert actual == expected, row

        # NPC absence must not invent a sword/shield demonstration or a delivered
        # letter. Generation uses the normal, monotonic routes, even though an
        # intangible Kokiri Mido/King Zora can be passed before Soul arrives.
        for name in ('Mido', 'Mido From Outside Deku Tree', "ZD Deliver Ruto's Letter"):
            if soul_mode:
                verify(name, 'child', ('NPC Soul',), False)
        # Draining the well is handled by the background song trigger, not EnFu.
        verify('Kak Windmill Phonogram Man', 'child', ('NPC Soul',), True)
        worlds.append(dict(configuration, location_count=len(world.get_locations()),
                           first_talk_age_routes_available=baseline_available))
        print(json.dumps(dict(configuration, status='passed', total_cases=len(checks))), flush=True)

    # The explicit skip-race option must continue to grant its intended bypass
    # without requiring an invisible host to conduct a race.
    mw = setup_multiworld(SohExtremeWorld, steps=(), seed=args.seed,
                          options=dict(options, shuffle_speak=2, skip_child_zelda=0, skip_epona_race=1))
    world = mw.worlds[1]
    for stage in ('generate_early', 'create_regions', 'create_items', 'set_rules'):
        call_all(mw, stage)
    full = mw.get_all_state(False)
    configuration = dict(shuffle_npc_soul=1, shuffle_speak=2, skip_child_zelda=0, skip_epona_race=1)
    verify('LLR Talon Race', 'adult', ('NPC Soul', 'Speak Hylian'), True)
    verify('LLR Time Trial', 'adult', ('NPC Soul', 'Speak Hylian'), False)
    worlds.append(dict(configuration, location_count=len(world.get_locations())))

    final_hashes = {name: hashlib.sha256((source_root / name).read_bytes()).hexdigest()
                    for name in SOURCE_FILES}
    assert final_hashes == source_hashes, 'Rule sources changed while regression was running.'
    report = dict(status='passed', checks=checks, cases=len(checks), worlds=worlds,
                  elapsed_seconds=round(time.monotonic() - started, 3),
                  runtime_version=Utils.__version__,
                  scope='Actual AP source worlds through set_rules; age-specific first-talk, '
                        'reward, exchange and gate checks across all speech modes. '
                        'No full item fill, native build or gameplay.',
                  source_sha256=source_hashes,
                  conservative_routes='No negative-item access rules or permanent flag grants. '
                        'Temporary passage through an intangible NPC is not assumed for generation '
                        'or tracker logic because receiving NPC Soul can restore that blocker.',
                  yaml=str(args.yaml_path.resolve()),
                  yaml_sha256=hashlib.sha256(args.yaml_path.read_bytes()).hexdigest(),
                  seed=args.seed, probe_source=str(Path(__file__).resolve()),
                  probe_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  loaded_world_source=inspect.getfile(SohExtremeWorld))
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: report[key] for key in ('status', 'cases', 'runtime_version', 'elapsed_seconds')},
                     indent=2), flush=True)


if __name__ == '__main__':
    main()
