"""Focused real-AP interaction parity for invisible NPC path blockers.

Builds normal source worlds through set_rules. These are age-specific interaction
checks with otherwise complete inventory, not a full fill or native gameplay run.
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
import yaml
from Generate import roll_settings
from test.general import setup_multiworld
from worlds.AutoWorld import call_all
from worlds.soh_extreme import SohExtremeWorld, NpcSpeech
from worlds.soh_extreme._vendor_oot_soh.Enums import Ages, Items


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('yaml_path', type=Path, help='SOH-EXTREME player YAML used for base settings.')
    parser.add_argument('--report', type=Path, help='Write detailed JSON evidence to this path.')
    parser.add_argument('--source-root', type=Path, default=Path(__file__).resolve().parents[2],
                        help='Repository root containing soh/ and archipelago/ (default: this source tree).')
    parser.add_argument('--seed', type=int, default=186)
    args = parser.parse_args()
    source_root = args.source_root.resolve()
    loaded_world = Path(inspect.getfile(SohExtremeWorld))
    expected_world = source_root / 'archipelago/soh_extreme/__init__.py'
    if not loaded_world.is_file() or loaded_world.read_bytes() != expected_world.read_bytes():
        parser.error('Install this source tree as the loose worlds/soh_extreme world before running the probe.')
    started = time.monotonic()
    random.seed(args.seed)
    rolled = roll_settings(yaml.safe_load(args.yaml_path.read_text(encoding='utf-8-sig')))
    options = {name: getattr(rolled, name).value for name in SohExtremeWorld.options_dataclass.type_hints}
    options = {name: dict(value) if isinstance(value, dict) else value for name, value in options.items()}
    options.update(starting_age='child', closed_forest='on', kakariko_gate='closed', zoras_fountain='closed', shuffle_npc_soul=1, shuffle_speak=2, npc_speech_sanity=1, shuffle_adult_trade_items=1)
    checks = []
    worlds = []
    for skip in (0, 1):
        mw = setup_multiworld(SohExtremeWorld, steps=(), seed=args.seed, options=dict(options, skip_child_zelda=skip))
        world = mw.worlds[1]
        for stage in ('generate_early', 'create_regions', 'create_items', 'set_rules'):
            call_all(mw, stage)
        full = mw.get_all_state(False)

        def state_for(age, missing=()):
            s = full.copy()
            for name in missing:
                while s.has(name, 1):
                    s.remove(world.create_item(name))
            s._soh_extreme_age[1] = Ages[age.upper()]
            return s

        def verify(name, age, missing, expected):
            location = world.get_location(name)
            state = state_for(age, missing)
            actual = bool(location.access_rule(state))
            checks.append(dict(skip_child_zelda=skip, check=name, age=age, missing=list(missing), expected=expected, actual=actual))
            if actual != expected:
                print('FAILED', checks[-1], flush=True)
        byid = {entry['id']: entry for entry in NpcSpeech.active_entries(world)}
        for location_id in NpcSpeech.PATH_BLOCKER_CONVERSATIONS:
            entry = byid[location_id]
            route = next((r for r in entry['routes'] if not (skip and 'before_child_zelda' in r['gates'])))
            age = route['age'] if route['age'] != 'either' else 'child'
            verify(entry['name'], age, ('NPC Soul',), True)
            verify(entry['name'], age, ('NPC Soul', 'Speak ' + entry['language']), False)
        verify('NPC Speech: King Zora', 'adult', ('NPC Soul',), True)
        verify('NPC Speech: King Zora', 'adult', ('NPC Soul', 'Speak Zora'), False)
        verify('NPC Speech: King Zora', 'adult', ('NPC Soul', 'Climb'), False)
        verify('NPC Speech: Talon', 'child', ('NPC Soul',), not bool(skip))
        verify('NPC Speech: Talon', 'adult', ('NPC Soul',), False)
        verify('NPC Speech: Talon', 'child', ('NPC Soul', 'Speak Hylian'), False)
        for name, age in (('NPC Speech: Gerudo Valley Cucco Keeper', 'child'), ('NPC Speech: Gerudo Archery Host', 'adult'), ('NPC Speech: Gerudo Fortress Ground Resident', 'adult')):
            verify(name, age, ('NPC Soul',), False)
        for name, age, language in (('Mido', 'child', 'Kokiri'), ('Mido From Outside Deku Tree', 'child', 'Kokiri'), ("ZD Deliver Ruto's Letter", 'child', 'Zora'), ('Kak Gate', 'child', 'Hylian'), ('Kak Gate Guard', 'child', 'Hylian'), ('GF Gate', 'adult', 'Gerudo'), ('GF Gate Outside', 'adult', 'Gerudo'), ('GTG Gate', 'adult', 'Gerudo'), ('ZD King Zora Thawed', 'adult', 'Zora'), ('ZD Trade Prescription', 'adult', 'Zora')):
            verify(name, age, ('NPC Soul',), True)
            verify(name, age, ('NPC Soul', 'Speak ' + language), False)
        verify('Mido', 'child', ('NPC Soul', str(Items.KOKIRI_SWORD)), False)
        verify('Mido', 'child', ('NPC Soul', str(Items.BUY_DEKU_SHIELD)), False)
        verify('Mido', 'adult', ('NPC Soul',), False)
        verify('Kak Gate', 'child', ('NPC Soul', str(Items.ZELDAS_LETTER)), False)
        verify('Kak Gate', 'adult', ('NPC Soul',), False)
        verify('GTG Gate', 'adult', ('NPC Soul', str(Items.GERUDO_MEMBERSHIP_CARD)), False)
        verify('GTG Gate', 'adult', ('NPC Soul', str(Items.PROGRESSIVE_WALLET)), False)
        verify('ZD Trade Prescription', 'adult', ('NPC Soul', str(Items.PRESCRIPTION)), False)
        verify('ZD Diving Minigame', 'child', ('NPC Soul',), False)
        if not skip:
            verify('HC Malon Egg', 'child', ('NPC Soul',), False)
        for source, target in (('Hyrule Castle Grounds', 'HC Past Gate'), ('HC Moat', 'HC Drain Ledge')):
            region = world.get_region(source)
            edge = next((e for e in region.exits if e.connected_region and e.connected_region.name == target))
            actual = bool(edge.access_rule(state_for('child', ('NPC Soul',))))
            checks.append(dict(skip_child_zelda=skip, entrance=edge.name, missing=['NPC Soul'], expected=True, actual=actual))
            assert actual, checks[-1]
        worlds.append({'skip_child_zelda': skip, 'location_count': len(world.get_locations())})
    files = ['archipelago/soh_extreme/NpcSpeech.py', 'archipelago/soh_extreme/NpcSpeechCatalog.json', 'archipelago/soh_extreme/NativeLogic.py', 'archipelago/soh_extreme/NativeLogicAlternatives.py', 'archipelago/soh_extreme/NativeAbilityAudit.py', 'archipelago/soh_extreme/__init__.py', 'archipelago/soh_extreme/_vendor_oot_soh/LogicHelpers.py', *['archipelago/soh_extreme/_vendor_oot_soh/location_access/overworld/' + name + '.py' for name in ('castle_grounds', 'gerudo_fortress', 'kakariko', 'zoras_domain')], 'soh/Enhancements/randomizer/logic.h', 'soh/Enhancements/randomizer/logic.cpp', 'soh/Enhancements/randomizer/location_access.cpp', 'soh/Enhancements/randomizer/randomizer_check_tracker.cpp', *['soh/Enhancements/randomizer/location_access/overworld/' + name + '.cpp' for name in ('castle_grounds', 'gerudo_fortress', 'kakariko', 'kokiri_forest', 'zoras_domain')], 'soh/Network/Archipelago/NpcSpeechScenes.inc', 'soh/Network/Archipelago/NpcSpeechAreas.inc']
    assert all((row['actual'] == row['expected'] for row in checks)), [row for row in checks if row['actual'] != row['expected']]
    report = {'status': 'passed', 'checks': checks, 'cases': len(checks), 'worlds': worlds, 'elapsed_seconds': round(time.monotonic() - started, 3), 'scope': 'Actual AP 0.6.7 source worlds through set_rules; isolated age-specific interaction gates with complete inventory minus the named items. No full item fill, native build or gameplay.', 'source_sha256': {name: hashlib.sha256((source_root / name).read_bytes()).hexdigest() for name in files}}
    report['yaml'] = str(args.yaml_path.resolve())
    report['yaml_sha256'] = hashlib.sha256(args.yaml_path.read_bytes()).hexdigest()
    report['seed'] = args.seed
    report['probe_source'] = str(Path(__file__).resolve())
    report['probe_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    report['loaded_world_source'] = inspect.getfile(SohExtremeWorld)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'status': report['status'], 'cases': report['cases'], 'elapsed_seconds': report['elapsed_seconds']}, indent=2), flush=True)


if __name__ == "__main__":
    main()
