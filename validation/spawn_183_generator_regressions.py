"""Run current generator regression suites and retain their exact source hashes."""
from pathlib import Path
import hashlib
import importlib.util
import io
import json
import time
import unittest

root = Path(__file__).resolve().parents[1]
source = root / 'source'
test_paths = [source / 'tools/tests' / name for name in
              ('test_entrance_start.py', 'test_overworld_entrances.py', 'test_spawn_placement.py')]
source_paths = [path for path in (source / 'archipelago/soh_extreme').rglob('*')
                if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc']
checked = source_paths + test_paths
hashes = {path.relative_to(source).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
          for path in checked}
suite = unittest.TestSuite()
for path in test_paths:
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(module))

log = io.StringIO()
started = time.monotonic()
result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
elapsed = time.monotonic() - started
log_path = root / 'tests/spawn_183_generator_regressions.log'
log_path.write_text(log.getvalue())
print(log.getvalue(), end='')
assert hashes == {path.relative_to(source).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                  for path in checked}, 'Checked source changed while tests ran'

from worlds.soh_extreme import EntranceRandomizer as ER
from worlds.soh_extreme import SohExtremeWorld
import Utils

report = {
    'status': 'passed' if result.wasSuccessful() else 'failed',
    'archipelago_version': Utils.__version__,
    'world_version': SohExtremeWorld.world_version.as_simple_string(),
    'tests_run': result.testsRun, 'failures': len(result.failures),
    'errors': len(result.errors), 'skipped': len(result.skipped),
    'elapsed_seconds': round(elapsed, 3),
    'source_sha256': hashes,
    'source_unchanged_during_run': True,
    'test_files': [path.relative_to(source).as_posix() for path in test_paths],
    'log': log_path.name,
    'entrance_mapping_revision': ER.REVISION,
    'scope': 'Official AP 0.6.7 rules and state; finite destination search, live graph order/fallback, '
             'coupling, enabled pools, safe starts, unchanged saved-map replay, and physical starting connectivity without Ocarina.',
}
(root / 'tests/spawn_183_generator_validation.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({key: report[key] for key in
                  ('status', 'world_version', 'tests_run', 'failures', 'errors', 'elapsed_seconds')}))
raise SystemExit(0 if result.wasSuccessful() else 1)
