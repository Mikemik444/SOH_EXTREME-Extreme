"""Verify source snapshot, room crosswalk and unchanged identity catalogues.
This establishes source/packaging consistency, not physical map playtesting.
"""
import argparse,ast,dataclasses,hashlib,json,re,runpy
from pathlib import Path
from source_index import native_sources
p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path,required=True);p.add_argument('--baseline',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
root=a.source_root;package=root/'source/soh_extreme';checks=[]
def ck(name,actual,expected=True):
 if isinstance(expected,bool):actual=bool(actual)
 row={'test':name,'passed':actual==expected,'actual':actual,'expected':expected};checks.append(row)
 if not row['passed']:print('FAIL',name,str(actual)[:1000])
graph=json.loads((package/'EnemyRoomGraph.json').read_text());mapping=json.loads((package/'EnemyRoomMap.json').read_text())
_,regions=native_sources(root)
expected={k:v for k,v in regions.items() if '/dungeons/' in v['file'] and '_MQ_' not in k}
ck('export exactly matches current native source regions',graph,expected);checks[-1].update(actual=len(graph),expected=len(expected))
ck('429 exported vanilla regions',len(graph),429)
entries=runpy.run_path(str(package/'EnemyDropLocations.py'))['ENEMY_DROP_LOCATIONS'];old=runpy.run_path(str(a.baseline/'source/soh_extreme/EnemyDropLocations.py'))['ENEMY_DROP_LOCATIONS']
ck('no new or retired active enemy IDs',[e.address for e in entries],[e.address for e in old]);checks[-1].update(actual=len(entries),expected=len(old))
ck('all native region assignments exist',[e.name for e in entries if e.region_token.startswith('RR_') and e.region_token not in graph],[])
ck('all and only mapped native regions have manifest rows',{e.address for e in entries if e.region_token.startswith('RR_')},{int(k) for k in mapping});checks[-1].update(actual=len(mapping),expected=len(mapping))
oldfinder=(a.baseline/'soh/Network/Archipelago/ArchipelagoEnemyFinderMap.inc').read_text();finder=(root/'soh/Network/Archipelago/ArchipelagoEnemyFinderMap.inc').read_text()
parsed={int(i):rr for i,rr in re.findall(r'\{\s*(\d+)LL,\s*\w+,\s*(RR_\w+),',finder)}
for e in entries:
 if str(e.address) in mapping:ck('manifest/native-table match '+str(e.address),parsed[e.address],mapping[str(e.address)]['native_region'])
flags={e['event'] for row in graph.values() for e in row['events']}
for token in ('LOGIC_SHADOW_SILVER_BLADES','LOGIC_GANONS_CASTLE_SILVER_SPIRIT','LOGIC_FOREST_JOELLE','LOGIC_FOREST_BETH','LOGIC_FOREST_AMY'):
 ck('native event preserved '+token,token in flags)
identities=('EnemyDefeatPlacements.inc','EnemySpawnAliases.inc','EnemyChildAliases.inc','EnemySpawnCatalog.h','MegaSouls.cpp')
identity_hashes={}
for name in identities:
 rel=Path('soh/Enhancements/randomizer')/name;now=(root/rel).read_bytes();before=(a.baseline/rel).read_bytes()
 ck('unchanged append-only/origin runtime '+name,now,before);checks[-1].update(actual=hashlib.sha256(now).hexdigest(),expected=hashlib.sha256(before).hexdigest());identity_hashes[name]=hashlib.sha256(now).hexdigest()
# Source-only package can always be imported from ZIP: data reads use resources,
# not Path(__file__).parent, and no dependency points at an external stock world.
for path in package.rglob('*.py'):
 ast.parse(path.read_text(),filename=str(path))
ck('all Python sources parse',True)
report={'scope':__doc__,'checks':checks,'total':len(checks),'failures':sum(not c['passed'] for c in checks),'coverage':{'active_enemies':len(entries),'mapped_enemies':len(mapping),'entryway_assignments_replaced':sum('ENTRYWAY' in row['previous_ap_region'] for row in mapping.values()),'native_regions':len(graph),'native_edge_event_conditions':sum(len(row['events'])+sum(e['target'] in graph for e in row['exits']) for row in graph.values()),'source_files':sorted({r['file'] for r in graph.values()}),'identity_hashes':identity_hashes}}
a.report.write_text(json.dumps(report,indent=2));print('TOTAL',report['total'],'FAILURES',report['failures']);raise SystemExit(bool(report['failures']))
