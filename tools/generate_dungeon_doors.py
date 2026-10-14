"""Generate the reviewed physical-door catalog, independent of game archives."""
from pathlib import Path
import json
from dungeon_door_bindings import PREFIX, SIDES, ROUTES, CONDITIONS, OMIT, SCENE_PORTAL_DOORS

ROOT=Path(__file__).resolve().parents[1]

def generate():
    graph=json.loads((ROOT/'archipelago/soh_extreme/EnemyRoomGraph.json').read_text())
    records=json.loads((ROOT/'tools/dungeon_door_records.json').read_text())
    assert {(r['scene'],r['index']) for r in records}=={(s,i) for s,ds in SIDES.items() for i in ds}
    out=[]
    for r in records:
        scene,index=r['scene'],r['index']
        if (scene,index) in SCENE_PORTAL_DOORS:continue
        prefix='RR_'+PREFIX[scene]+'_'
        a,b=SIDES[scene][index]
        for side,(source,target) in enumerate(((a,b),(b,a))):
            key=(scene,index,side)
            if key in OMIT:continue
            # The engine makes the reverse side of a boss shutter unopenable.
            if r['actor']==46 and (r['params']>>6)&15==5 and side==0:continue
            source,target=ROUTES.get(key,(source,target))
            source,target=prefix+source,prefix+target
            assert source in graph and target in graph,key
            edges=[e for e in graph[source]['exits'] if e['target']==target]
            condition,note=CONDITIONS.get(key,(None,None))
            if condition is None:
                assert len(edges)==1 and edges[0]['condition'].strip(';')!='false',(key,source,target)
            room_from,room_to=(r['room_a'],r['room_b']) if side==0 else (r['room_b'],r['room_a'])
            label=graph[source]['name']+' -> '+graph[target]['name']
            endpoint = (f'room {room_from} side {side+1} to side {2-side}' if room_from==room_to
                        else f'room {room_from} to {room_to}')
            row=dict(id=11200000+scene*1024+index*2+side,
                name=f'Dungeon Door: {label} (door {index+1}, {endpoint})',
                index=f'DOOR_{scene}_{index}_{side}',kind='DungeonDoor',mode='door',
                source=source,target=target,source_scene=scene,target_scene=scene,
                door=index,side=side,room_from=room_from,room_to=room_to,
                actor=r['actor'],params=r['params'],position=r['pos'],rotation=r['rot'],
                entrances=[],grotto=-1,content=-1)
            if condition is not None:row.update(condition=condition,reason=note)
            if r['actor']==46 and (r['params']>>6)&15==5:
                dungeon='GANONS_CASTLE' if scene==10 else PREFIX[scene]
                row['extra_condition']=f'HasItem(RG_{dungeon}_BOSS_KEY)'
            out.append(row)
    (ROOT/'archipelago/soh_extreme/DungeonDoorCatalog.json').write_text(json.dumps(out,indent=2)+'\n')
    print('Exported',len(out),'directed room doors')
    return out

if __name__=='__main__':generate()
