"""Run actual-start regressions against AP and bind the results to checked sources."""
from pathlib import Path
import hashlib
import importlib.util
import io
import json
import os
import platform
import sys
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'source'
TEST_PATHS = [SOURCE / 'tools/tests' / name for name in (
    'test_entrance_start.py', 'test_overworld_entrances.py', 'test_spawn_placement.py',
)]
REPORT_PATH = ROOT / 'tests/entrance_184_spawn_placement_validation.json'
LOG_PATH = ROOT / 'tests/entrance_184_spawn_placement_regressions.log'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_hashes():
    paths = [path for path in (SOURCE / 'archipelago/soh_extreme').rglob('*')
             if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc']
    return {path.relative_to(SOURCE).as_posix(): digest(path)
            for path in sorted(paths + TEST_PATHS)}


hashes_before = source_hashes()
suite = unittest.TestSuite()
for path in TEST_PATHS:
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(module))

from worlds.soh_extreme import EntranceRandomizer as ER
from worlds.soh_extreme import SohExtremeWorld
import Utils

assert Path(ER.__file__).resolve() == SOURCE / 'archipelago/soh_extreme/EntranceRandomizer.py'
log = io.StringIO()
started = time.monotonic()
result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
elapsed = time.monotonic() - started
LOG_PATH.write_text(log.getvalue())
print(log.getvalue(), end='')
hashes_after = source_hashes()
unchanged = hashes_before == hashes_after
passed = result.wasSuccessful() and unchanged
report = {
    'status': 'passed' if passed else 'failed',
    'command': [sys.executable, str(Path(__file__).resolve())],
    'environment': {'PYTHONPATH': os.environ.get('PYTHONPATH', '')},
    'working_directory': str(Path.cwd()),
    'python_version': platform.python_version(),
    'archipelago_version': Utils.__version__,
    'world_version': SohExtremeWorld.world_version.as_simple_string(),
    'tests_run': result.testsRun,
    'failures': len(result.failures),
    'errors': len(result.errors),
    'skipped': len(result.skipped),
    'elapsed_seconds': round(elapsed, 3),
    'source_sha256': hashes_before,
    'source_unchanged_during_run': unchanged,
    'test_files': [path.relative_to(SOURCE).as_posix() for path in TEST_PATHS],
    'runner_sha256': digest(Path(__file__)),
    'log': LOG_PATH.name,
    'log_sha256': digest(LOG_PATH),
    'entrance_mapping_revision': ER.REVISION,
    'scope': [
        'Actual AP 0.6.7 CollectionState and SoH age-aware regions, locations, items, and source rules.',
        'Child and adult selected shuffled starts require Hyrule Field with actual configured inventory.',
        'Free returns and several free checks cannot substitute for an unplaced three-item escape bundle.',
        'Configured items and reachable local prefill are used without pool mutation or new grants.',
        'Configured Ocarina is allowed by the actual-start guard; the separate structural probe excludes it.',
        'Other-age reachability, inaccessible prefill, and cached rewards from a rejected topology cannot certify the selected start.',
        'Every mapped age spawn rejects Water Temple scene and room arrivals without actual Swim, including other-age-only shuffle.',
        'Dry other-age destinations, a configured first Progressive Scale, and shuffle_swim off remain accepted without new grants.',
        'No selected-spawn mapping and other-age-only dry spawn shuffle retain their prior initial hub and free-check rules.',
        'Actual connect pipeline places selected-age spawns before swaps and preserves actual hub access on every accepted start probe.',
        'Bounded fallback restores identity topology before retrying; exhausted alternatives fail instead of keeping default spawns.',
        'Enabled mixed pools, reverse coupling, overworld source gates, and saved-map replay remain covered.',
    ],
    'limitations': [
        'This suite validates graph generation and AP state behavior; it does not fill a seed or prove final item placement.',
        'Native runtime and actual game execution are outside this report.',
    ],
}
if not unchanged:
    report['source_sha256_after'] = hashes_after
REPORT_PATH.write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({key: report[key] for key in (
    'status', 'world_version', 'tests_run', 'failures', 'errors',
    'elapsed_seconds', 'source_unchanged_during_run',
)}))
raise SystemExit(0 if passed else 1)
