"""Exercise both real Mido passage rules across Soul, speech, song and trick modes.

Run in the official AP runtime with this source world installed. The supplied
YAML is read only; isolated options keep the physical Lost Woods edges in place.
This checks access rules, not collision geometry or a full item fill.
"""
from pathlib import Path
import argparse
import hashlib
import inspect
import json
import random
import time

from validate_npc_path_blockers import (
    SOURCE_FILES, SohExtremeWorld, Utils, call_all, roll_settings,
    setup_multiworld, verify_mido_routes, yaml,
)
from worlds.soh_extreme import EntranceRandomizer as ER
from worlds.soh_extreme._vendor_oot_soh.Enums import Tricks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('yaml_path', type=Path)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    started = time.monotonic()
    source = Path(__file__).resolve().parents[2]
    loaded = Path(inspect.getfile(SohExtremeWorld))
    assert loaded.read_bytes() == (source / 'archipelago/soh_extreme/__init__.py').read_bytes()
    files = (*SOURCE_FILES, 'archipelago/soh_extreme/SongNotes.py',
             'archipelago/soh_extreme/_vendor_oot_soh/SongShuffle.py',
             'archipelago/soh_extreme/Options.py')
    hashes = {name: hashlib.sha256((source / name).read_bytes()).hexdigest() for name in files}
    random.seed(189)
    rolled = roll_settings(yaml.safe_load(args.yaml_path.read_text(encoding='utf-8-sig')))
    options = {name: getattr(rolled, name).value for name in SohExtremeWorld.options_dataclass.type_hints}
    options = {name: dict(value) if isinstance(value, dict) else value for name, value in options.items()}
    for key in ER.ENTRANCE_OPTIONS:
        options[key] = set() if key == 'mixed_entrance_pools' else 0
    options.update(starting_age='adult', enable_all_tricks=0, tricks_in_logic=set())
    checks = []
    worlds = []
    configurations = [
        dict(shuffle_npc_soul=1, shuffle_speak=0, song_note_shuffle=0),
        dict(shuffle_npc_soul=1, shuffle_speak=1, song_note_shuffle=0),
        dict(shuffle_npc_soul=1, shuffle_speak=2, song_note_shuffle=1,
             song_note_songs={'sarias_song'}),
        dict(shuffle_npc_soul=0, shuffle_speak=2, song_note_shuffle=0),
        dict(shuffle_npc_soul=1, shuffle_speak=2, song_note_shuffle=1,
             song_note_songs={'all'}, tricks_in_logic={str(Tricks.LW_MIDO_BACKFLIP)}),
    ]
    for values in configurations:
        mw = setup_multiworld(SohExtremeWorld, steps=(), seed=189, options=dict(options, **values))
        world = mw.worlds[1]
        for stage in ('generate_early', 'create_regions', 'create_items', 'set_rules'):
            call_all(mw, stage)
        full = mw.get_all_state(False)
        configuration = {key: sorted(value) if isinstance(value, (set, frozenset)) else value
                         for key, value in values.items()}
        verify_mido_routes(world, full, checks, configuration)
        worlds.append(configuration)
        print(json.dumps(dict(configuration, status='passed', total_cases=len(checks))), flush=True)
    assert hashes == {name: hashlib.sha256((source / name).read_bytes()).hexdigest() for name in files}, \
        'Production rules changed during the regression.'
    report = dict(status='passed', cases=len(checks), worlds=worlds, checks=checks,
                  runtime_version=Utils.__version__, source_sha256=hashes,
                  yaml_sha256=hashlib.sha256(args.yaml_path.read_bytes()).hexdigest(),
                  loaded_world_source=str(loaded),
                  probe_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  shared_probe_sha256=hashlib.sha256(Path(__file__).with_name(
                      'validate_npc_path_blockers.py').read_bytes()).hexdigest(),
                  elapsed_seconds=round(time.monotonic() - started, 3),
                  scope='Actual AP source worlds through set_rules. Both Mido passage directions, '
                        'both ages, all speech modes, Soul disabled control, selected/all progressive '
                        'song modes, instrument requirement, and enabled forward backflip. '
                        'No full fill, native collision simulation or gameplay.')
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({key: report[key] for key in ('status', 'cases', 'runtime_version', 'elapsed_seconds')}),
          flush=True)


if __name__ == '__main__':
    main()
