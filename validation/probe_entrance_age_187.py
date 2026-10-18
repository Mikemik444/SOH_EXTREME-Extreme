"""Read-only safety probes on the complete real source-world rule graph."""
from hashlib import sha256
import json
from pathlib import Path
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
from worlds.soh_extreme import SohExtremeWorld
from worlds.soh_extreme import EntranceRandomizer as ER
from worlds.soh_extreme._vendor_oot_soh.Enums import Ages


ROOT = Path('/workspace/scratch/8fddab5b8169')
SOURCE = ROOT / 'source'
YAML = ROOT / 'upload/SOH-EXTREME(20261017-230302).yaml'
FILES = ['archipelago/soh_extreme/EntranceRandomizer.py',
         'archipelago/soh_extreme/EntranceSafety.py',
         'archipelago/soh_extreme/EntranceDestinationPolicy.json',
         'archipelago/soh_extreme/EntranceCatalog.json',
         'archipelago/soh_extreme/__init__.py',
         'archipelago/soh_extreme/_vendor_oot_soh/RegionAgeAccess.py',
         'archipelago/soh_extreme/_vendor_oot_soh/Regions.py',
         'archipelago/soh_extreme/_vendor_oot_soh/location_access/overworld/castle_grounds.py']


def hashes():
    return {name: sha256((SOURCE / name).read_bytes()).hexdigest() for name in FILES}


def main():
    started = time.monotonic()
    before = hashes()
    random.seed(187)
    rolled = roll_settings(yaml.safe_load(YAML.read_text()))
    options = {key: getattr(rolled, key).value for key in SohExtremeWorld.options_dataclass.type_hints}
    options = {key: dict(value) if isinstance(value, dict) else value for key, value in options.items()}
    for key in ER.ENTRANCE_OPTIONS:
        options[key] = set() if key == 'mixed_entrance_pools' else 0
    options.update(starting_age='child', shuffle_child_spawn=1, shuffle_adult_spawn=1,
                   mixed_entrance_pools={'all'})
    multiworld = setup_multiworld(SohExtremeWorld, steps=(), seed=187, options=options)
    world = multiworld.worlds[1]
    for step in ('generate_early', 'create_regions', 'create_items', 'set_rules'):
        call_all(multiworld, step)
        print(f'{step}: {time.monotonic() - started:.2f}s', flush=True)

    def physical_edge(endpoint):
        row = ER.ENDPOINTS[endpoint]
        source = world.get_region(ER.region_name(row['source']))
        target = ER.region_name(row['target'])
        matches = [edge for edge in source.exits if edge.connected_region.name == target]
        assert len(matches) == 1, (endpoint, len(matches))
        return matches[0]

    spawn_edges = {endpoint: physical_edge(endpoint) for endpoint in (187, 642)}
    identity_edges = {endpoint: physical_edge(endpoint) for endpoint in (832, 1000, 2060)}
    originals = {endpoint: edge.connected_region for endpoint, edge in spawn_edges.items()}
    identities = {endpoint: edge.access_rule for endpoint, edge in identity_edges.items()}
    outcomes = []
    for name, replacements, expected in (
            ('vanilla_spawn_identity_returns', {}, True),
            ('adult_spawn_hc_fairy_while_interiors_disabled', {642: 1400}, False),
            ('child_spawn_ogc_fairy_while_interiors_disabled', {187: 1218}, False),
            ('adult_spawn_hc_storms_while_grottos_disabled', {642: 1804}, False),
            ('correct_age_fairy_arrivals', {187: 1400, 642: 1218}, True),
            ('safe_identity_after_rejected_candidate', {}, True)):
        for endpoint, edge in spawn_edges.items():
            edge.connected_region.entrances.remove(edge)
            target = (world.get_region(ER.region_name(ER.ENDPOINTS[replacements[endpoint]]['target']))
                      if endpoint in replacements else originals[endpoint])
            edge.connect(target)
        state = multiworld.get_all_state(False, perform_sweep=False)
        state.sweep_for_advancements()
        actual = ER._age_routes_are_safe(world, replacements, spawn_edges, state)
        assert actual == expected, (name, actual, expected)
        masks = {}
        for endpoint, edge in identity_edges.items():
            assert edge.access_rule is identities[endpoint]
            masks[str(endpoint)] = {
                'child': ER._reachable_as_age(world, state, edge, Ages.CHILD),
                'adult': ER._reachable_as_age(world, state, edge, Ages.ADULT),
            }
        outcomes.append({'case': name, 'mapping': replacements, 'safe': actual,
                         'restricted_physical_sources_reachable': masks})
        print(name, actual, flush=True)
    after = hashes()
    assert before == after, 'Production source changed during this probe'
    report = {
        'passed': True, 'runtime': 'Archipelago 0.6.7',
        'scope': 'Complete source world setup and actual rules; no randomized entrance generation, fill, or native launch.',
        'cases': outcomes, 'case_count': len(outcomes),
        'yaml_sha256': sha256(YAML.read_bytes()).hexdigest(),
        'source_hashes': after, 'source_unchanged_during_probe': True,
        'elapsed_seconds': round(time.monotonic() - started, 3),
    }
    (ROOT / 'tests/entrance_destination_187_full_graph_probe.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'passed': True, 'case_count': len(outcomes),
                      'elapsed_seconds': report['elapsed_seconds']}), flush=True)


if __name__ == '__main__':
    main()
