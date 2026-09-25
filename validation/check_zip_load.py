"""Verify that the installed .apworld (not loose sources) registers version 0.11.19."""
import argparse,sys,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--ap-root',type=Path,required=True);p.add_argument('--report',type=Path,required=True);p.add_argument('--offline-adapters',action='store_true');a=p.parse_args()
sys.path.insert(0,str(a.ap_root.resolve()))
if a.offline_adapters:import offline_bootstrap
import worlds
import worlds.soh_extreme as package
from worlds.AutoWorld import AutoWorldRegister
w=AutoWorldRegister.world_types['SOH-EXTREME']
r={'failed_world_loads':worlds.failed_world_loads,'loaded_from':package.__file__,'world_version':w.world_version.as_simple_string(),'external_stock_world_registered':'Ship of Harkinian' in AutoWorldRegister.world_types}
r['passed']=not r['failed_world_loads'] and '.apworld' in r['loaded_from'] and r['world_version']=='0.11.19' and not r['external_stock_world_registered']
a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(r,indent=2));print(json.dumps(r,indent=2))
raise SystemExit(0 if r['passed'] else 1)
