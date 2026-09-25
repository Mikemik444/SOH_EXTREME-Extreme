"""Check the packaged AP catalogue against full native source and preserved save slots."""
from pathlib import Path
import argparse,ast,re,json,zipfile,hashlib
p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path,required=True);p.add_argument('--apworld',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
checks=[]
def check(name,actual,expected=True):
 checks.append(dict(name=name,passed=actual==expected,actual=actual,expected=expected));print('PASS' if actual==expected else 'FAIL',name)
def placements(text):
 return [tuple(int(x.strip().removesuffix('LL'),0) for x in m.group(1).split(',')) for m in re.finditer(r'\{([^}]+)\}',text)]
with zipfile.ZipFile(a.apworld) as z:
 check('ZIP CRC',z.testzip() is None)
 manifest=json.loads(z.read('archipelago.json'));check('version',manifest['world_version'],'0.11.17')
 check('both manifests agree',json.loads(z.read('soh_extreme/archipelago.json')),manifest)
 tree=ast.parse(z.read('soh_extreme/EnemyDropLocations.py'))
 rows=[tuple(ast.literal_eval(v) for v in n.args) for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='EnemyDropLocationData']
 errors=[];parsed=0
 for name in z.namelist():
  if not name.endswith('.py'):continue
  tree=ast.parse(z.read(name),filename=name);parsed+=1
  for n in ast.walk(tree):
   imports=[v.name for v in n.names] if isinstance(n,ast.Import) else [n.module or ''] if isinstance(n,ast.ImportFrom) and n.level==0 else []
   if any(v=='worlds.oot_soh' or v.startswith('worlds.oot_soh.') for v in imports):errors.append(name)
 check('all packaged Python sources parse',parsed>0)
 check('no external stock world imports',errors,[])
 check('no test adapters or cache bundled',any('offline_bootstrap' in n or '__pycache__' in n for n in z.namelist()),False)
 native=placements((a.source_root/'soh/Enhancements/randomizer/EnemyDefeatPlacements.inc').read_text())
 ids={r[1] for r in rows};native_by_id={r[6]:r for r in native}
 check('753 active enemy checks',len(rows),753);check('unique names',len({r[0] for r in rows}),753);check('unique AP IDs',len(ids),753)
 check('786 append-only receipt slots',len(native),786)
 legacy=json.loads(Path(__file__).with_name('legacy_receipt_slots.json').read_text())
 check('all original 570 receipt identities unchanged',[list(r) for r in native[:570]],legacy)
 # Keep the successful equality check compact in the output report.
 checks[-1]['actual']=checks[-1]['expected']='570 full placement tuples' if checks[-1]['passed'] else 'mismatch'
 check('native IDs retain append-only sequence',[r[6] for r in native],list(range(9800000,9800786)))
 checks[-1]['actual']=checks[-1]['expected']='9800000..9800785' if checks[-1]['passed'] else 'mismatch'
 inactive={r[6] for r in native if r[4]==0x54 and r[5]==0}|{9800549,9800554}|set(range(9800765,9800786))
 check('only noncombat and offspring reserved slots inactive',set(native_by_id)-ids,inactive)
 checks[-1]['actual']=sorted(checks[-1]['actual']);checks[-1]['expected']=sorted(checks[-1]['expected'])
 check('195 previously expanded IDs remain active',len([x for x in ids if x>=9800570]),195)
 check('AP and native identities agree',all(tuple(r[2:8])==native_by_id[r[1]][:6] for r in rows))
 finder=[]
 for line in (a.source_root/'soh/Network/Archipelago/ArchipelagoEnemyFinderMap.inc').read_text().splitlines():
  if not line.strip().startswith('{'):continue
  # Names have no commas. Preserve all twelve native fields.
  f=[s.strip() for s in line.strip().strip('{}, ').split(',')]
  assert len(f)==12
  finder.append(f)
 byfinder={int(f[0].removesuffix('LL')):f for f in finder}
 check('finder IDs match AP',set(byfinder),ids);checks[-1]['actual']=checks[-1]['expected']='753 IDs' if checks[-1]['passed'] else 'mismatch'
 check('finder scene/room/grotto/actor and spawn mask match AP',all(tuple(map(int,byfinder[r[1]][3:7]))==(r[2],r[3],r[4],r[6]) and int(byfinder[r[1]][9])==r[11] for r in rows))
 forest=[r for r in rows if r[2]==3]
 check('40 Forest enemies have room regions',len(forest),40)
 check('Forest no entryway fallback',all(not r[10].endswith('ENTRYWAY') for r in forest))
 # AP and native use different names for several of the same physical rooms.
 forest_names={
  'FIRST_ROOM':{'TREES'}, 'SOUTH_CORRIDOR':{'OVERGROWN_HALLWAY_LOWER'},
  'EAST_CORRIDOR':{'BLUE_DOORMAT_HALLWAY'}, 'NORTH_CORRIDOR':{'NORTH_HALLWAY'},
  'WEST_CORRIDOR':{'RED_DOORMAT_HALLWAY'}, 'NE_OUTDOORS_LOWER':{'NE_COURTYARD_LOWER'},
  'NE_OUTDOORS_UPPER':{'NE_COURTYARD_UPPER'}, 'NW_OUTDOORS_LOWER':{'NW_COURTYARD_LOWER'},
  'NW_OUTDOORS_UPPER':{'NW_COURTYARD_UPPER'}, 'BLOCK_PUSH_ROOM':{'BLOCK_PUSH_ROOM_TOP','BLOCK_PUSH_FLOOR'},
  'BOSS_REGION':{'BASEMENT'}, 'NW_CORRIDOR_TWISTED':{'NW_HALLWAY_TWISTED'},
  'NE_CORRIDOR_STRAIGHTENED':{'NE_HALLWAY_STRAIGHTENED'}}
 check('Forest AP/native physical-room crosswalk agrees',all(byfinder[r[1]][2].removeprefix('RR_FOREST_TEMPLE_') in forest_names.get(r[10].removeprefix('FOREST_TEMPLE_'),{r[10].removeprefix('FOREST_TEMPLE_')}) for r in forest))
 check('upper block-room enemies retain extra access gate',all(r[12]=='forest_block_top' for r in forest if byfinder[r[1]][2]=='RR_FOREST_TEMPLE_BLOCK_PUSH_ROOM_TOP'))
 check('Bow arena has three distinct IDs',all(byfinder[i][2]=='RR_FOREST_TEMPLE_UPPER_STALFOS' for i in (9800720,9800721,9800722)))
 for name in ['Poe Soul','Leever Soul','Stalchild Soul','Big Octo Soul']:
  text=z.read('soh_extreme/__init__.py').decode();check('existing soul retained: '+name,name in text and any(r[8]==name for r in rows))
 actor=(a.source_root/'src/code/z_actor.c').read_text();mega=(a.source_root/'soh/Enhancements/randomizer/MegaSouls.cpp').read_text()
 check('identity captured before actor initialization',actor.index('MegaSoul_CaptureEnemyDefeatIdentityFrom(actor, sourcePlacement, spawnSource)')<actor.index('Actor_Init(actor, play)'))
 for tag in ['EnemyDefeatIdentity','EnemyDefeatDropIdentity','EnemySourceIdentity']:
  check('destroy clears '+tag,'Remove<'+tag+'>(actor)' in mega)
 check('real OptionValue is explicitly read','.Get() != 0, HasRequiredEnemySoul(actor)' in mega)
 coarse=[{'id':r[1],'name':r[0],'region':r[10]} for r in rows if r[10].endswith('ENTRYWAY')]
 result={'passed':all(x['passed'] for x in checks),'active_enemy_checks':len(rows),'previously_added_enemy_checks_retained':195,'native_receipt_slots':len(native),'python_files_parsed':parsed,'legacy_coarse_entryway_check_count':len(coarse),'legacy_coarse_entryway_checks':coarse,'apworld_sha256':hashlib.sha256(a.apworld.read_bytes()).hexdigest(),'checks':checks}
 a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(result,indent=2));raise SystemExit(not result['passed'])
