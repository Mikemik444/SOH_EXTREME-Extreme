"""Generate and replay 18 seeds with the real AP fill, balancing and final guard."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse, json, os, subprocess, sys, time

p = argparse.ArgumentParser()
p.add_argument('--ap-root', type=Path, required=True)
p.add_argument('--yaml', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
a.output.mkdir(parents=True, exist_ok=True)
cases = [(f'{phase}-{i}', 290980 + j*3+i, 1, {'frozen_starting_time':phase})
         for j, phase in enumerate(('dawn','day','dusk','night')) for i in range(3)]
cases += [('two-soh-day',291000,2,{'frozen_starting_time':'day'}),
          ('two-soh-night',291001,2,{'frozen_starting_time':'night'}),
          ('ganon-day',291002,1,{'triforce_hunt':False,'frozen_starting_time':'day'}),
          ('ganon-night',291003,1,{'triforce_hunt':False,'frozen_starting_time':'night'}),
          ('adult-start',291004,1,{'closed_forest':'off','starting_age':'adult','frozen_starting_time':'night'}),
          ('individual-notes',291005,1,{'song_note_shuffle':'individual_notes','frozen_starting_time':'night'})]

def run(case):
    name, seed, players, overrides = case
    report = a.output / (name+'.json')
    command = [sys.executable, str(Path(__file__).with_name('run_case.py')),
        '--ap-root',str(a.ap_root),'--yaml',str(a.yaml),'--seed',str(seed),
        '--players',str(players),'--overrides',json.dumps(overrides),'--report',str(report)]
    start = time.monotonic()
    with (a.output/(name+'.log')).open('w',encoding='utf-8') as log:
        result = subprocess.run(command,stdout=log,stderr=subprocess.STDOUT)
    details = json.loads(report.read_text()) if report.exists() else {}
    passed = result.returncode == 0 and details.get('passed',False)
    row = dict(name=name,seed=seed,players=players,overrides=overrides,passed=passed,
        seconds=round(time.monotonic()-start,2),report=report.name,
        final_validation=details.get('final_validation'),network_checks=details.get('network_locations'),
        error=details.get('error'))
    print(json.dumps(row),flush=True)
    return row

with ThreadPoolExecutor(max_workers=2) as executor:
    rows = [f.result() for f in as_completed([executor.submit(run,case) for case in cases])]
result=dict(passed=all(r['passed'] for r in rows), cases=sorted(rows,key=lambda r:r['seed']),
    scope=__doc__,total_seeds=len(rows),worlds=sum(r['players'] for r in rows))
(a.output/'summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
raise SystemExit(not result['passed'])
