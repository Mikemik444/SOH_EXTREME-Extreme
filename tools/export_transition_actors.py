"""Read scene commands from a user's local O2R; export only door/exit metadata.

No ROM or archive is distributed. Format follows SOH's SceneCommand importers.
"""
from pathlib import Path
import argparse, json, re, struct, zipfile

def scene_commands(data):
    offset=64
    def read(fmt):
        nonlocal offset
        result=struct.unpack_from('<'+fmt,data,offset);offset+=struct.calcsize('<'+fmt)
        return result[0] if len(result)==1 else result
    def string():
        size=read('I');return read(str(size)+'s').rstrip(b'\0').decode()
    result={}
    for _ in range(read('I')):
        cmd=read('I')
        if cmd in (0,1,14):
            result[cmd]=[read('BBBBhhhhhH' if cmd==14 else 'HhhhhhhH') for _ in range(read('I'))]
        elif cmd==4: result[cmd]=[(string(),read('II')) for _ in range(read('I'))]
        elif cmd in (3,23):result[cmd]=string()
        elif cmd in (13,24):result[cmd]=[string() for _ in range(read('I'))]
        elif cmd in (6,11,19):result[cmd]=[read('BB' if cmd==6 else 'H') for _ in range(read('I'))]
        elif cmd in (12,15): result[cmd]=[read('BhhhBBBBh' if cmd==12 else '18Bhh') for _ in range(read('I'))]
        elif cmd==20:pass
        elif cmd in (2,8,25):result[cmd]=read('bI')
        elif cmd in (5,17):result[cmd]=read('4B')
        elif cmd in (16,21):result[cmd]=read('3B')
        elif cmd==18:result[cmd]=read('2B')
        elif cmd==22:result[cmd]=read('B')
        elif cmd==7:result[cmd]=read('BH')
        elif cmd==10:
            _,typ=read('BB')
            assert typ in (0,2),typ
            for _ in range(read('B')):
                read('B')
                if typ==2:read('4h')
                string();string()
        else:raise ValueError(f'Unknown scene command {cmd} at {offset-4}')
    assert offset==len(data),(offset,len(data))
    return result

def collision_exits(data):
    offset=76
    def read(fmt):
        nonlocal offset
        result=struct.unpack_from('<'+fmt,data,offset);offset+=struct.calcsize('<'+fmt)
        return result[0] if len(result)==1 else result
    vertices=[read('3h') for _ in range(read('I'))]
    polys=[read('8H') for _ in range(read('I'))]
    surfaces=[read('2I') for _ in range(read('I'))]
    result={}
    for poly in polys:
        exit=surfaces[poly[0]][1]>>8&31
        if exit:result.setdefault(exit,[]).append([vertices[i&0x1fff] for i in poly[1:4]])
    return result

def export(archive,root):
    table=(root/'include/tables/scene_table.h').read_text()
    scenes=re.findall(r'/\* (0x[0-9A-Fa-f]+) \*/ DEFINE_SCENE\((\w+),[^,]+, (SCENE_\w+)',table)
    output=[]
    with zipfile.ZipFile(archive) as z:
        for sid,resource,token in scenes:
            paths=[p for p in z.namelist() if p.endswith('/'+resource) and p.startswith(('scenes/nonmq/','scenes/shared/'))]
            for p in paths:
                data=scene_commands(z.read(p))
                row=dict(scene=int(sid,16),token=token,resource=p,doors=data.get(14,[]),exits=data.get(19,[]),
                         entrances=data.get(6,[]),spawns=data.get(0,[]),alternates=data.get(24,[]))
                if 3 in data:row['exit_polys']=collision_exits(z.read(data[3]))
                if int(sid,16)<=13:
                    row['room_actors']={str(i):scene_commands(z.read(name)).get(1,[]) for i,(name,_) in enumerate(data.get(4,[]))}
                output.append(row)
    return output

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('archive',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    rows=export(a.archive,Path(__file__).resolve().parents[1]);a.output.write_text(json.dumps(rows,indent=2))
    print(len(rows),'scenes;',sum(len(r['doors']) for r in rows),'transition actors')
