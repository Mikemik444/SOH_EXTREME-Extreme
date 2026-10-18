"""Tie the final release to completed generation and regression evidence."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'source'
TESTS = ROOT / 'tests'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(name):
    return json.loads((TESTS / name).read_text(encoding='utf-8-sig'))


def main():
    generator = read('spawn_183_generator_validation.json')
    assert generator['status'] == 'passed' and generator['world_version'] == '1.8.3'
    assert generator['source_unchanged_during_run']
    assert generator['failures'] == generator['errors'] == generator['skipped'] == 0
    hashes = dict(generator['source_sha256'])
    for relative, expected in hashes.items():
        assert digest(SOURCE / relative) == expected, relative

    fills = []
    for age in ('child', 'adult'):
        result = read(f'spawn_183_full_fill_{age}.json')
        assert result['status'] == 'passed' and result['world_version'] == '1.8.3'
        assert result['age'] == age and result['seed'] == 1
        assert result['source_unchanged_during_run']
        assert all(hashes.get(path) == expected for path, expected in result['source_sha256'].items())
        assert result['validation']['passed']
        player = result['validation']['players']['1']
        assert player['goal_met'] and player['full_accessibility']
        assert player['checked'] == player['network_checks'] == 4036
        assert result['overworld_endpoints'] == 52
        assert result['native_overworld_flag'] == 1
        assert result['saved_mixed_entrance_pools'] == ['all']
        assert set(result['expanded_mixed_categories']) == set(result['enabled_entrance_categories'])
        assert result['initial_network_checks'] > 1
        fills.append(dict(age=age, seed=1, checked=4036, goal_met=True,
                          elapsed_seconds=result['elapsed_seconds'],
                          child_spawn=result['child_spawn'], adult_spawn=result['adult_spawn']))

    # The release restores ordinary AP item filling exactly; the rejected
    # experimental placement prefix is not part of this archive.
    assert digest(SOURCE / 'archipelago/soh_extreme/FrontierFill.py') == (
        'bee9dd5e923412bc7138d7e03a3f1f05a37b136b158c389b11b9e951ebf8ca30')
    helper = 'tools/tests/validate_user_full_fill.py'
    hashes[helper] = digest(SOURCE / helper)

    evidence = []
    for name, expected_status in (
        ('spawn_183_baseline_reproduction.json', 'reproduced'),
        ('spawn_183_generator_validation.json', 'passed'),
        ('spawn_183_frontier_physical_guard_regression_child.json', 'passed'),
        ('spawn_183_full_fill_child.json', 'passed'),
        ('spawn_183_full_fill_adult.json', 'passed'),
    ):
        data = read(name)
        assert data['status'] == expected_status
        entry = dict(path=name, status='passed', sha256=digest(TESTS / name))
        if expected_status != 'passed':
            entry['expected_report_status'] = expected_status
        evidence.append(entry)

    supporting_names = [
        'spawn_183_reproduce.py', 'spawn_183_generator_regressions.py',
        'spawn_183_run_full_fill.py', 'spawn_183_release_evidence.py',
        'spawn_183_full_fill_child.log', 'spawn_183_full_fill_adult.log',
        'spawn_183_frontier_nonmusic_component_child.json',
        'spawn_183_frontier_nonmusic_component_probe.py',
    ]
    # The nonmusic component diagnosis is explicitly historical: it identifies
    # the earlier rejected map, while the completed fills validate this source.
    report = dict(
        status='passed', world_version='1.8.3', archipelago_version='0.6.7',
        entrance_mapping_revision=1, source_sha256=hashes, evidence=evidence,
        supporting_files=[dict(path=name, sha256=digest(TESTS / name)) for name in supporting_names],
        generator_tests=generator['tests_run'], complete_fill_runs=fills,
        unchanged_yaml_sha256=digest(ROOT / 'delivery/SOH-EXTREME-1.8.3-spawn-placement/SOH-EXTREME.yaml'),
        scope='Official AP generation through final accessibility checks with normal restrictive fill; '
              'no native Windows build or gameplay run.',
    )
    destination = TESTS / 'spawn_183_release_validation.json'
    destination.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({key: report[key] for key in ('status', 'world_version', 'generator_tests', 'complete_fill_runs')},
                     indent=2))


if __name__ == '__main__':
    main()
