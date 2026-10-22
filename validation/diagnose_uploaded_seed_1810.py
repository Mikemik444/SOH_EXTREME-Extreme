"""Inspect the unchanged seed's failed frontier using the exact replay state.

Counterfactual inventory additions exist only in private CollectionState
copies. They are diagnostic probes, never a seed edit or delivered item.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch

import replay_uploaded_seed_1810 as audit
from worlds.soh_extreme._vendor_oot_soh.Enums import Ages
from worlds.soh_extreme.EnemyRoomLogic import GRAPH


ROOT = Path(__file__).resolve().parents[1]
W = 'RR_WATER_TEMPLE_'
G = 'RR_GERUDO_TRAINING_GROUND_'


def path_to(state, target):
    result = []
    current = state.path.get(target)
    while current:
        name, current = current
        result.append(name)
    return list(reversed(result))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spoiler', type=Path, required=True)
    parser.add_argument('--exact-reproduction', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    captured = []
    original_state = audit.CollectionState

    def capture_state(multiworld):
        state = original_state(multiworld)
        captured.append(state)
        return state

    replay_report = ROOT / 'tests/uploaded_seed_1810_diagnostic_replay.json'
    command = [audit.__file__, '--spoiler', str(args.spoiler), '--exact-reproduction',
               str(args.exact_reproduction), '--report', str(replay_report)]
    with patch.object(sys, 'argv', command), patch.object(audit, 'CollectionState', capture_state):
        audit.main()
    assert len(captured) == 1
    state = captured[0]
    mw = state.multiworld
    world = mw.worlds[1]
    replay = json.loads(replay_report.read_bytes())
    assert not replay['goal_met'] and replay['checked_network_locations'] == 355
    before = audit.source_hashes()
    checks = {location.address: location for location in world.get_locations() if location.address is not None}
    focus_ids = (11211277, 11205146, 203, 9800230, 9700261, 9800537, 569, 9700475, 11000114)

    def reached(probe, spot, age=Ages.CHILD):
        return audit.ER._reachable_as_age(world, probe, spot, age)

    def region(token):
        return world.get_region(audit.ER.region_name(token))

    def route_details(edge, probe):
        old_age = probe._soh_extreme_age[1]
        probe._soh_extreme_age[1] = Ages.CHILD
        try:
            local = bool(edge.access_rule(probe))
        finally:
            probe._soh_extreme_age[1] = old_age
        row = {'edge': edge.name, 'source_region': edge.parent_region.name,
               'target_region': edge.connected_region.name,
               'source_reachable_child': reached(probe, edge.parent_region),
               'source_reachable_adult': reached(probe, edge.parent_region, Ages.ADULT),
               'local_predicate_child': local, 'edge_reachable_child': reached(probe, edge)}
        if edge.name.startswith('EXTREME Shuffled Entrance '):
            endpoint = int(edge.name.rsplit(' ', 1)[1])
            source = audit.ER.ENDPOINTS[endpoint]
            target = audit.ER.ENDPOINTS[world._er_mapping.get(endpoint, endpoint)]
            row.update(source_id=endpoint, target_id=target['id'],
                       physical_source=source['name'], arrival=target['target'])
            if source['source'] in GRAPH:
                row['native_source_conditions'] = [value['condition']
                    for value in GRAPH[source['source']]['exits'] if value['target'] == source['target']]
            if target['id'] in audit.ER.WATER_ARRIVAL_LEVELS:
                row['dry_water_level'] = audit.ER.WATER_ARRIVAL_LEVELS[target['id']]
        return row

    regions = (G + 'LOBBY', G + 'ENTRYWAY', W + 'PILLAR_2F', W + '2F_CENTRAL_LM',
               W + '3F_CENTRAL_A', W + 'LOW_EMBLEM',
               'GF_TOP_OF_LOWER_VINES', 'GF_BOTTOM_OF_LOWER_VINES',
               'GF_TOP_OF_UPPER_VINES', 'GF_BOTTOM_OF_UPPER_VINES',
               'RR_GANONS_CASTLE_FOREST_TRIAL_FINAL_ROOM')
    incoming = {token: [route_details(edge, state) for edge in region(token).entrances]
                for token in regions}
    focus = {str(address): dict(audit.location_row(checks[address]),
                               reachable=reached(state, checks[address]),
                               path=path_to(state, checks[address].parent_region))
             for address in focus_ids}

    counterfactuals = []
    for extra in ('Climb', 'Time Travel', 'Pot Soul', 'Iron Boots'):
        probe = state.copy()
        item = (audit.Item(extra, audit.ItemClassification.progression, None, 1)
                if extra == 'Time Travel' else world.create_item(extra))
        probe.collect(item, True)
        pot_now = reached(probe, checks[11211277]) or reached(probe, checks[11211277], Ages.ADULT)
        immediately = {str(address): reached(probe, checks[address]) or reached(probe, checks[address], Ages.ADULT)
                       for address in focus_ids}
        path = path_to(probe, checks[11211277].parent_region) if pot_now else []
        new_rows = []
        while True:
            available = sorted((location for location in world.get_locations() if location.item
                                and location not in probe.locations_checked and location not in probe.advancements
                                and location.can_reach(probe)), key=lambda location: (location.player, location.name))
            if not available:
                break
            for location in available:
                if location in probe.locations_checked or location in probe.advancements:
                    continue
                if location.advancement:
                    probe.advancements.add(location)
                probe.collect(location.item, True, location)
                if location.address is not None and location.item.advancement:
                    new_rows.append(audit.location_row(location))
        count = sum(location in probe.locations_checked or location in probe.advancements
                    for location in checks.values())
        counterfactuals.append({'private_added_item': extra, 'pot_soul_immediately_reachable': pot_now,
                               'immediate_focus': immediately, 'pot_soul_path': path,
                               'goal_met_after_followup_collection': mw.has_beaten_game(probe, 1),
                               'network_checks_after_followup_collection': count,
                               'first_new_progression_checks': new_rows[:20]})
    assert before == audit.source_hashes()
    report = {'status': 'diagnosed', 'seed': replay['seed'], 'goal_met': replay['goal_met'],
              'network_checks': replay['network_checks'],
              'checked_network_locations': replay['checked_network_locations'],
              'blocked_network_locations': replay['blocked_network_locations'],
              'actual_triforce_pieces_at_stop': state.count('Triforce Piece', 1),
              'required_triforce_pieces': world.triforce_pieces_required,
              'focused_checks': focus, 'incoming_edges_at_fixed_point': incoming,
              'private_counterfactuals': counterfactuals,
              'replay_report': str(replay_report), 'replay_report_sha256': audit.sha(replay_report),
              'diagnostic_script_sha256': audit.sha(__file__), 'source_sha256': before,
              'source_unchanged_during_run': True,
              'scope': 'Exact existing map, items, classifications and prices. Counterfactual additions only in private in-memory state copies; no changes to production, seed, items or live saves.'}
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'status': report['status'], 'triforce': report['actual_triforce_pieces_at_stop'],
                      'counterfactuals': [{key: value for key, value in row.items()
                                          if key in ('private_added_item', 'pot_soul_immediately_reachable',
                                                     'goal_met_after_followup_collection', 'network_checks_after_followup_collection')}
                                         for row in counterfactuals]}, indent=2))


if __name__ == '__main__':
    main()
