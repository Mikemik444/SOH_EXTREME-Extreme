"""Read-only actual-age, event-only nonmusic topology assessment.

The original retained seed-1 graph and original global item objects are used.
Previously reserved diagnostic rewards are never swept as network locations.
All-item states below are structural diagnostics, not playable inventory claims.
"""
import hashlib
import json
import time
from collections import Counter


def diagnose_nonmusic_component(world, multiworld):
    started = time.monotonic()
    output = ROOT / 'tests/spawn_183_frontier_nonmusic_component_child.json'
    assert not output.exists()
    original_assignments = [(id(loc), id(loc.item), loc.locked)
                            for loc in world.get_locations()]
    original_pool_ids = [id(item) for item in multiworld.itempool]
    original_rng = (world.random.getstate(), multiworld.random.getstate())
    original_graph = [(id(edge), id(edge.connected_region))
                      for region in world.get_regions() for edge in region.exits]
    event_locations = [loc for loc in world.get_locations()
                       if loc.address is None and loc.advancement
                       and loc.item.player == world.player]
    network_locations = [loc for loc in world.get_locations() if loc.address is not None]
    overworld_rows = [row for row in ER.CATALOG if row['category'] == 'overworld']
    overworld_tokens = sorted({row[key] for row in overworld_rows for key in ('source', 'target')})
    own_pool = [item for item in multiworld.itempool if item.player == world.player]
    song_names = {name for name, _ in world.SONG_NOTE_LAYOUT}
    instrument_names = sorted({item.name for item in own_pool
                              if 'ocarina' in item.name.lower() and 'button' not in item.name.lower()})

    def is_music(item):
        return ('ocarina' in item.name.lower() or item.name in song_names
                or world._song_for_note(item.name)[0] is not None)

    component_report = {
        'status': 'running', 'seed_of_original_retained_graph': 1,
        'starting_age': world.options.starting_age.current_key,
        'scope': ('Original retained graph, actual starting age, configured '
                  'precollected items, original pool object hypotheses, and '
                  'reachable event locations only. Existing diagnostic network '
                  'placements are not swept. Structural diagnostics do not '
                  'prove these hypothetical inventories can be obtained.'),
        'entrance_source_sha256': hashlib.sha256((ROOT / 'source/archipelago/soh_extreme/EntranceRandomizer.py').read_bytes()).hexdigest(),
        'child_spawn': {'id': world._er_mapping[187], 'endpoint': ER.ENDPOINTS[world._er_mapping[187]]},
        'original_global_item_count': len(multiworld.itempool),
        'precollected_names': dict(Counter(item.name for item in multiworld.precollected_items[world.player])),
        'instrument_names_excluded_in_primary_test': instrument_names,
        'authored_overworld_endpoint_count': len(overworld_rows),
        'authored_overworld_unique_region_count': len(overworld_tokens),
        'states': {},
    }

    def reachable(state, spot):
        return ER._reachable_at_starting_age(world, state, spot)

    def event_only_closure(state):
        # Explicit actual-age event closure avoids both diagnostic network
        # placements and implicit switching to the alternate starting age.
        pending = [loc for loc in event_locations if loc not in state.advancements]
        while pending:
            sphere = [loc for loc in pending if reachable(state, loc)]
            if not sphere:
                break
            for loc in sphere:
                state.advancements.add(loc)
                state.collect(loc.item, True, loc)
            pending = [loc for loc in pending if loc not in state.advancements]
        assert all(loc.address is None for loc in state.advancements)
        assert all(loc.address is None for loc in state.locations_checked)

    def evaluate(label, allowed):
        began = time.monotonic()
        state = CollectionState(multiworld)
        initial_names = dict(state.prog_items[world.player])
        assert not state.locations_checked and not state.advancements
        for item in allowed:
            state.collect(item, True)
        event_only_closure(state)
        regions = [region for region in world.get_regions() if reachable(state, region)]
        checks = [loc for loc in network_locations if reachable(state, loc)]
        overworld = [{
            'token': token, 'region': ER.region_name(token),
            'reachable': reachable(state, world.get_region(ER.region_name(token))),
        } for token in overworld_tokens]
        hf = world.get_region(ER.region_name('HYRULE_FIELD'))
        result = {
            'hypothetical_original_pool_objects_collected': len(allowed),
            'initial_constructor_progression': initial_names,
            'excluded_pool_item_counts': dict(Counter(item.name for item in own_pool
                if not any(item is other for other in allowed))),
            'reachable_region_count': len(regions),
            'reachable_region_names': [region.name for region in regions],
            'reachable_network_check_count': len(checks),
            'reachable_network_check_names': [loc.name for loc in checks],
            'reachable_event_names': sorted(loc.name for loc in state.advancements),
            'overworld_regions': overworld,
            'reachable_overworld_region_count': sum(entry['reachable'] for entry in overworld),
            'hyrule_field_reachable': reachable(state, hf),
            'addressed_network_rewards_swept': 0,
            'positive_progression_counts': dict(sorted((name, count) for name, count
                                                      in state.prog_items[world.player].items() if count)),
            'seconds': round(time.monotonic() - began, 3),
        }
        component_report['states'][label] = result
        component_report['elapsed_seconds'] = round(time.monotonic() - started, 3)
        output.write_text(json.dumps(component_report, indent=2) + '\n')
        print('NONMUSIC_COMPONENT ' + json.dumps({
            'state': label, 'pool_objects': len(allowed),
            'reachable_regions': len(regions), 'reachable_network_checks': len(checks),
            'reachable_overworld_regions': result['reachable_overworld_region_count'],
            'hyrule_field_reachable': result['hyrule_field_reachable'],
            'seconds': result['seconds'],
        }), flush=True)
        return state

    actual = evaluate('actual_start_event_only', [])
    no_instrument = evaluate('all_original_pool_except_ocarina_instruments',
                             [item for item in own_pool if item.name not in instrument_names])
    no_music = evaluate('all_original_pool_except_all_music_items',
                        [item for item in own_pool if not is_music(item)])
    all_items = evaluate('all_original_pool_control', own_pool)
    assert [(id(loc), id(loc.item), loc.locked) for loc in world.get_locations()] == original_assignments
    assert [id(item) for item in multiworld.itempool] == original_pool_ids
    assert (world.random.getstate(), multiworld.random.getstate()) == original_rng
    assert [(id(edge), id(edge.connected_region)) for region in world.get_regions()
            for edge in region.exits] == original_graph
    component_report['status'] = 'passed'
    component_report['world_pool_assignments_graph_and_rng_unchanged'] = True
    component_report['elapsed_seconds'] = round(time.monotonic() - started, 3)
    output.write_text(json.dumps(component_report, indent=2) + '\n')
    print('NONMUSIC_COMPONENT_DONE elapsed=' + str(component_report['elapsed_seconds']), flush=True)
    return {'nonmusic_component_report': component_report,
            'nonmusic_actual_start_state': actual,
            'nonmusic_without_instrument_state': no_instrument,
            'nonmusic_without_music_state': no_music,
            'nonmusic_all_items_state': all_items}


globals().update(diagnose_nonmusic_component(world, multiworld))
