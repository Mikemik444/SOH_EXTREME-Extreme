"""Bind the exact seed's failed frontier to its saved map and authored rules.

Read-only JSON/source analysis: this does not construct an AP world, generate a
seed, modify an inventory, or change production sources.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative):
    return json.loads((ROOT / relative).read_bytes())


def sha(relative):
    return hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()


def main():
    inputs = {
        'exact': 'tests/uploaded_seed_189_exact_metadata.json',
        'baseline': 'tests/uploaded_seed_189_baseline_replay.json',
        'corrected': 'tests/uploaded_seed_1810_corrected_replay.json',
        'diagnostic': 'tests/uploaded_seed_1810_blocker_diagnostic.json',
        'catalog': 'source/archipelago/soh_extreme/EntranceCatalog.json',
        'old_graph': 'tests/uploaded_seed_189_baseline/source/archipelago/soh_extreme/EnemyRoomGraph.json',
        'current_graph': 'source/archipelago/soh_extreme/EnemyRoomGraph.json',
    }
    data = {name: read(path) for name, path in inputs.items()}
    exact, old, new, diagnostic = (data[name] for name in ('exact', 'baseline', 'corrected', 'diagnostic'))
    catalog = {row['id']: row for row in data['catalog']}
    mapping = {int(source): target for source, target in exact['mapping'].items()}
    assert exact['status'] == 'exactly_reproduced'
    assert old['goal_met'] and old['checked_network_locations'] == 4036
    assert old['sphere_sizes_match_original']
    assert not new['goal_met'] and new['checked_network_locations'] == 355
    assert new['blocked_network_locations'] == 3681 and len(new['spheres']) == 10
    assert new['source_unchanged_during_run']
    assert diagnostic['source_sha256'] == new['source_sha256']
    assert diagnostic['actual_triforce_pieces_at_stop'] == 3
    assert diagnostic['required_triforce_pieces'] == 20
    for key in ('all_network_placements_restored_exactly',
                'all_network_item_classifications_restored_exactly',
                'all_shop_prices_restored_exactly',
                'saved_map_restored_through_production_connect'):
        assert new[key]

    def mapped(source, expected):
        assert mapping[source] == expected
        return {'physical_source_id': source, 'saved_target_id': expected,
                'physical_source_name': catalog[source]['name'],
                'source_region': catalog[source]['source'],
                'actual_arrival_region': catalog[expected]['target'],
                'physical_source_check_id': catalog[source]['check_id']}

    def edge(graph, source, target):
        rows = [row for row in data[graph][source]['exits'] if row['target'] == target]
        assert len(rows) == 1
        return rows[0]

    water = 'RR_WATER_TEMPLE_'
    former_local_path = [(water + '2F_CENTRAL_LM', water + 'MAIN'),
                         (water + 'MAIN', water + '3F_CENTRAL_H'),
                         (water + '3F_CENTRAL_H', water + 'OUTSIDE_WATERFALL'),
                         (water + 'OUTSIDE_WATERFALL', water + 'WATERFALL')]
    native_rule_comparison = [
        {'source': source, 'target': target,
         'baseline': edge('old_graph', source, target),
         'corrected': edge('current_graph', source, target)}
        for source, target in former_local_path
    ]
    event_spheres = {
        event: {'baseline': old['first_item_spheres'].get(event),
                'corrected': new['first_item_spheres'].get(event)}
        for event in ('EXTREME Native Event: LOGIC_WATER_COULD_MIDDLE',
                      'EXTREME Native Event: LOGIC_WATER_COULD_HIGH_FROM_MID',
                      'EXTREME Native Event: LOGIC_WATER_HIGH',
                      'EXTREME Native Event: LOGIC_WATER_LOW',
                      'EXTREME Native Event: LOGIC_WATER_MIDDLE')
    }
    assert event_spheres['EXTREME Native Event: LOGIC_WATER_COULD_MIDDLE']['baseline'] == 2
    assert event_spheres['EXTREME Native Event: LOGIC_WATER_COULD_HIGH_FROM_MID']['baseline'] == 10
    assert all(row['corrected'] is None for row in event_spheres.values())
    for item, sphere in [('Open Chest', 8), ('Progressive Scale', 9)]:
        assert old['first_item_spheres'][item] == new['first_item_spheres'][item] == sphere
    assert old['first_item_spheres']['Pot Soul'] == 11
    assert 'Pot Soul' not in new['first_item_spheres']
    assert not diagnostic['focused_checks']['11211277']['reachable']
    assert diagnostic['focused_checks']['11205146']['reachable']

    proof_sources = [
        'source/archipelago/soh_extreme/EntranceRandomizer.py',
        'source/archipelago/soh_extreme/EnemyRoomLogic.py',
        'source/archipelago/soh_extreme/_vendor_oot_soh/LogicHelpers.py',
        'source/soh/Enhancements/randomizer/location_access/dungeons/water_temple.cpp',
        'source/soh/Enhancements/randomizer/logic.cpp',
        'source/soh/Network/Archipelago/EntranceRandomizerData.inc',
        'source/src/overlays/actors/ovl_Bg_Mizu_Water/z_bg_mizu_water.h',
        'upload/AP_90569625277056890789_Spoiler(1).txt',
    ]
    report = {
        'status': 'existing_seed_fails_corrected_rules',
        'seed': exact['seed'], 'official_output_name': exact['official_output_name'],
        'goal_met': False, 'network_checks': 4036, 'checked_network_locations': 355,
        'blocked_network_locations': 3681, 'triforce_pieces': 3, 'required_triforce_pieces': 20,
        'collection_spheres_before_stall': 10,
        'baseline_parity': '4036 placements, classifications and prices restored; all 36 original progression sphere sizes matched under isolated 1.8.9.',
        'smallest_concrete_lost_approach': {
            'early_water_ingresses': [mapped(1158, 8862), mapped(1246, 8863)],
            'landing_height': 460, 'high_water_height': 765,
            'current_arrival_requirement': 'Actual LOW or MIDDLE control proof, or usable Iron Boots (owned boots, adult, Swim).',
            'current_failed_state': 'Child only; no usable Iron Boots; no actual LOW, MIDDLE or HIGH control event.',
            'baseline_event_spheres': event_spheres,
            'former_local_water_path': native_rule_comparison,
            'following_exact_mapped_legs': [mapped(8849, 2056), mapped(401, 8965),
                                            mapped(9001, 9611), mapped(9613, 9871)],
            'lost_progression': {'check_id': 11211277, 'item': 'Pot Soul',
                                 'baseline_sphere': 11, 'spoiler_line': 4783},
            'why_lost': 'The source check is dry and retains its physical traversal predicate. Its GTG Lobby parent has no reachable approach in the corrected fixed point. The old Water path supplied an invalid ingress and assumed water-control access across shuffled doors.',
            'paired_reverse_is_not_an_alternative': mapped(9870, 9612),
            'reverse_explanation': 'Forest Trial Final Room only has the mapped arrival from the same inaccessible GTG Lobby source 9613 in this saved map; returning from it cannot establish the initial approach.',
        },
        'preserved_valid_opening': {
            'open_chest_arrival': mapped(1099, 8859),
            'open_chest_check': 11205146, 'open_chest_sphere': 8, 'open_chest_spoiler_line': 4772,
            'scale_check': 203, 'scale_sphere': 9, 'scale_spoiler_line': 4776,
            'source_credit_example': {'id': 11001246, 'item': 'Strength Upgrade', 'sphere': 2,
                                      'explanation': 'The dry Hyrule Field source crossing still awards its item even though the mapped flooded destination is not a usable onward route.'},
        },
        'inventory_probe_limitation': 'Separate private copied-state probes adding Climb, Time Travel, Pot Soul or Iron Boots individually all still failed the goal. They are diagnostic only; no item was sent or seed edited.',
        'scope': 'Exact existing placements and saved mapping under actual AP predicates. This proves failure of the corrected generation/Finder logic model, not an exhaustive in-game search over unintended tricks. No new generation, source edit or repair is performed.',
        'input_sha256': {path: sha(path) for path in inputs.values()},
        'proof_source_sha256': {path: sha(path) for path in proof_sources},
        'script_sha256': sha(Path(__file__).relative_to(ROOT)),
    }
    path = ROOT / 'tests/uploaded_seed_1810_frontier_explanation.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'status': report['status'], 'goal_met': False,
                      'checked': 355, 'total': 4036, 'triforce': '3/20',
                      'report': str(path)}, indent=2))


if __name__ == '__main__':
    main()
