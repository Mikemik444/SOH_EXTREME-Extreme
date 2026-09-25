"""Static coverage/consistency checks. Callback presence is NOT runtime proof."""
from pathlib import Path
import argparse,json,re,ast,collections,hashlib
p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path,required=True);p.add_argument('--ap-source',type=Path,required=True);p.add_argument('--report',type=Path,required=True);p.add_argument('--baseline-root',type=Path);a=p.parse_args()
root=a.source_root.resolve();v=Path(__file__).parent;checks=[]
def check(name,condition):checks.append({'name':name,'passed':bool(condition)});print('PASS' if condition else 'FAIL',name)
text=(a.ap_source/'EnemyDropLocations.py').read_text();tree=ast.parse(text)
rows=[tuple(ast.literal_eval(v) for v in n.args) for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='EnemyDropLocationData']
metadata={r['id']:r for r in json.loads((v/'fixtures/actor_categories.json').read_text())};matrix=[]
for id,entries in sorted(collections.defaultdict(list,((id,[r for r in rows if r[6]==id]) for id in set(r[6] for r in rows))).items()):
 m=metadata[id];src=(root/m['source']).read_text();lines=[i for i,s in enumerate(src.splitlines(),1) if 'GameInteractor_ExecuteOnEnemyDefeat(' in s and not s.strip().startswith('//')]
 check('terminal defeat hook present in '+m['name'],bool(lines));matrix.append({**m,'active_checks':len(entries),'defeat_callback_lines':lines,'status':'static callback coverage; not a whole-game execution'})
ids={r[1] for r in rows};check('no offspring addresses in active AP catalogue',not ids.intersection(range(9800765,9800786)))
check('scene-placed Gohma larvae retained',all(i in ids for i in (9800019,9800020,9800021)))
check('all three Bow-room Stalfos retained',all(i in ids for i in (9800720,9800721,9800722)))
check('all four actual sisters retained',all(i in ids for i in range(9800566,9800570)))
engine=(root/'src/code/z_actor.c').read_text();mega=(root/'soh/Enhancements/randomizer/MegaSouls.cpp').read_text()
check('all direct actor lifecycle callbacks pass through origin wrapper',not re.search(r'actor->(?:init|update|draw|destroy)\(actor,\s*play\)',engine))
check('all init/update/spawn/kill/destroy notifications pass through origin wrapper',not re.search(r'GameInteractor_ExecuteOnActor(?:Init|Update|Spawn|Kill|Destroy)\(actor\)',engine))
check('capture refuses fallback address lookup','FindEnemyDefeatPlacement(' not in mega)
check('rejected index explicitly clears identity','identity->placementIndex = index;' in mega and 'if (enemyCreated || index < 0' in mega)
peahat=(root/'src/overlays/actors/ovl_En_Peehat/z_en_peehat.c').read_text()
check('Peahat births do not request AP lanes','MegaSoul_SpawnEnemyChild(' not in peahat and peahat.count('Actor_SpawnAsChild(')>=2)
fm=(root/'src/overlays/actors/ovl_En_Floormas/z_en_floormas.c').read_text()
check('Floormaster has only the final group callback',fm.count('GameInteractor_ExecuteOnEnemyDefeat(')==1 and 'GameInteractor_ExecuteOnEnemyDefeat(defeated);' in fm)
check('Floormaster final pickup uses last fragment position','defeated->world.pos = this->actor.world.pos;' in fm)
check('actor-compatible C bridge contains new API',all(n in (root/'soh/Enhancements/randomizer/EnemyDropBridge.h').read_text() for n in ('MegaSoul_CaptureEnemyDefeatIdentityFrom','MegaSoul_IsEnemySpawnSource','MegaSoul_ResetEnemyDefeatLife')))
check('native receipt table matches 0.11.12 fixture hash',hashlib.sha256((root/'soh/Enhancements/randomizer/EnemyDefeatPlacements.inc').read_bytes()).hexdigest()==(v/'fixtures/receipt_slots_0.11.12.sha256').read_text().strip())
if a.baseline_root:
 relative='soh/Enhancements/randomizer/EnemyDefeatPlacements.inc'
 check('all 786 existing receipt slots byte-for-byte preserved',(root/relative).read_bytes()==(a.baseline_root/relative).read_bytes())
for slotpath in sorted((a.report.parent).glob('seed-*.json.slot1.json')):
 slot=json.loads(slotpath.read_text());active={int(i) for i in slot['extreme_active_locations']};names=slot['extreme_location_name_to_id']
 check(slotpath.name+' omits offspring from active locations',not active.intersection(range(9800765,9800786)))
 check(slotpath.name+' omits offspring from names',not set(names.values()).intersection(range(9800765,9800786)))
 check(slotpath.name+' exports explicit origin policy',slot.get('enemy_spawn_policy')=='placed_and_non_enemy_scripted_encounters')
 if slot['shuffle_enemy_drops']:check(slotpath.name+' contains all 753 enemy checks',ids.issubset(active))
 else:check(slotpath.name+' honors enemy shuffle disabled',not ids.intersection(active))
result={'passed':all(c['passed'] for c in checks),'checks':checks,'actor_types':matrix,'scope':'Static source and slot-data audit. No animation/collision/object-bank execution is implied.'}
a.report.write_text(json.dumps(result,indent=2));raise SystemExit(not result['passed'])
