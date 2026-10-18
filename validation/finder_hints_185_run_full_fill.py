"""Record the exact production source used by a complete AP 0.6.7 fill."""
from pathlib import Path
import hashlib
import json
import runpy
import sys

root = Path(__file__).resolve().parents[1]
source = root / 'source'
paths = [path for path in (source / 'archipelago/soh_extreme').rglob('*')
         if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc']
before = {path.relative_to(source).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
          for path in paths}
report_path = Path(sys.argv[sys.argv.index('--report') + 1])
script = source / 'tools/tests/validate_user_full_fill.py'
sys.argv[0] = str(script)
runpy.run_path(str(script), run_name='__main__')
after = {path.relative_to(source).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
         for path in paths}
assert after == before, 'Production source changed during full-fill validation'
data = json.loads(report_path.read_text())
assert data['validation']['passed']
assert data['validation']['players']['1']['goal_met']
assert data['validation']['players']['1']['checked'] == data['validation']['players']['1']['network_checks']
assert data['world_version'] == '1.8.5'
assert data['initial_network_checks'] > 0
assert data['initial_physical_checks'] > 0
assert data['initial_hyrule_field_reachable']
assert data['saved_mixed_entrance_pools'] == ['all']
assert data['native_overworld_flag'] == 1
assert set(data['enabled_entrance_categories']) == set(data['expanded_mixed_categories'])
assert data['changed_overworld_endpoints'] > 0
data['yaml_sha256'] = hashlib.sha256(Path(data['yaml']).read_bytes()).hexdigest()
data.update(status='passed', source_sha256=before, source_unchanged_during_run=True)
report_path.write_text(json.dumps(data, indent=2) + '\n')
print(json.dumps({'status': data['status'], 'age': data['age'], 'seed': data['seed'],
                  'report': str(report_path), 'elapsed_seconds': data['elapsed_seconds']}), flush=True)
