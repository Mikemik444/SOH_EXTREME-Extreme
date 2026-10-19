"""Compile production object action/collision/draw paths with minimal engine shims.

The uploaded source lacks the root native build and runtime assets. These tests
exercise actual production functions (not a full native game build). --ap also
checks the installed Archipelago world's real Spirit doorway and vendor rules.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

SOURCE=Path(__file__).resolve().parents[2]
FIXTURES=Path(__file__).with_name('soul_object_validation')
ACTORS=SOURCE/'src/overlays/actors'
RANDO=SOURCE/'soh/Enhancements/randomizer'


def function(text,name):
    match=re.search(r'(?m)^(?:static )?(?:extern "C" )?[\w:*]+(?:\s+[\w:*]+)?\s+'+re.escape(name)+r'\([^;]*?\)\s*\{',text)
    if not match: raise AssertionError('Missing source function '+name)
    start=text.index('{',match.start())
    # Keep offsets while ignoring braces inside comments and string literals.
    clean=re.sub(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'',lambda m:' '*len(m[0]),text,flags=re.S)
    depth=0
    for end in range(start,len(text)):
        depth += (clean[end]=='{')-(clean[end]=='}')
        if depth==0:return text[match.start():end+1]
    raise AssertionError('Unclosed source function '+name)


def fragments():
    paths={name:ACTORS/f'ovl_{folder}'/f'z_{file}.c' for name,folder,file in [
        ('small','Obj_Kibako','obj_kibako'),('large','Obj_Kibako2','obj_kibako2'),
        ('rock','En_Ishi','en_ishi'),('brown','Obj_Bombiwa','obj_bombiwa'),
        ('bronze','Obj_Hamishi','obj_hamishi'),('ceiling','Bg_Jya_Bombchuiwa','bg_jya_bombchuiwa')]}
    paths.update(collision=SOURCE/'src/code/z_collision_check.c',background=SOURCE/'src/code/z_bgcheck.c',
                 souls=RANDO/'MegaSouls.cpp',header=RANDO/'SoulActorAccess.h',
                 rocks=RANDO/'ShuffleRocks.cpp',crates=RANDO/'ShuffleCrates.cpp')
    code={name:path.read_text() for name,path in paths.items()}
    native={token:function(code[source],name) for token,source,name in [
        ('MASS_TYPES','collision','CollisionCheck_GetMassType'),('OC_COLLISION','collision','CollisionCheck_SetOCvsOC'),
        ('UPDATE_SPHERES','collision','Collider_UpdateSpheres'),('SMALL_CRATE_IDLE','small','ObjKibako_Idle'),
        ('LARGE_CRATE_IDLE','large','ObjKibako2_Idle'),('ROCK_SOUL_HELPER','rock','EnIshi_HasRockSoul'),
        ('ROCK_WAIT','rock','EnIshi_Wait'),('BOMB_BOULDER_UPDATE','brown','ObjBombiwa_Update'),
        ('BRONZE_BOULDER_UPDATE','bronze','ObjHamishi_Update'),('CEILING_WAIT','ceiling','BgJyaBombchuiwa_WaitForExplosion'),
        ('CEILING_COLLIDER','ceiling','BgJyaBombchuiwa_UpdateCollider'),('CEILING_UPDATE','ceiling','BgJyaBombchuiwa_Update')]}
    for token,source in [('EN_ISHI_MASS','rock'),('BOMBIWA_MASS','brown'),('HAMISHI_MASS','bronze')]:
        native[token]=re.search(r'static CollisionCheckInfoInit sColChkInfoInit = \{[^}]*,\s*(MASS_\w+)\s*\}',code[source])[1]
    recovery=code['rocks'].split('COND_VB_SHOULD(VB_BOULDER_BREAK_FLAG, shouldRegisterBoulder, {',1)[1].split('\n    });',1)[0]
    draw={
        'ROCK_MISSING':function(code['rocks'],'RockSoulMissing'),
        'CRATE_MISSING':function(code['crates'],'CrateSoulMissing'),
        'ROCK_DRAWS':'\n\n'.join(function(code['rocks'],name+'_RandomizerDraw') for name in ('EnIshi','ObjBombiwa','ObjHamishi')),
        'CRATE_DRAWS':'\n\n'.join(function(code['crates'],name+'_RandomizerDraw') for name in ('ObjKibako','ObjKibako2')),
        'RECOVERY_HOOK':recovery,
    }
    # Rendering no longer owns the hidden ceiling boulder's physics.
    assert 'Collider_UpdateSpheres' not in function(code['ceiling'],'BgJyaBombchuiwa_Draw')
    assert 'BgJyaBombchuiwa_UpdateCollider' in native['CEILING_UPDATE']
    assert 'SoulTint' not in code['rocks'] and 'SoulTint' not in code['crates']
    return paths,native,draw


def check_ap():
    import ModuleUpdate
    ModuleUpdate.update_ran=True
    import settings
    settings.no_gui=True;settings.skip_autosave=True
    from BaseClasses import CollectionState
    from test.general import setup_multiworld
    from worlds.soh_extreme import SohExtremeWorld
    from worlds.soh_extreme import EntranceRandomizer as ER
    from worlds.soh_extreme.EnemyRoomLogic import GRAPH,NativeEnemyRegions
    from worlds.soh_extreme._vendor_oot_soh.Enums import Ages,Items,Regions
    mw=setup_multiworld(SohExtremeWorld,steps=('generate_early','create_regions','create_items'),seed=1,
                        options={'shuffle_rock_boulder_soul':1,'sunlight_arrows':1,'shuffle_dungeon_doors':1})
    world=mw.worlds[1]
    # Entrance routing later replaces stock edges with the physical native
    # graph. Preserve the actual vendor callback before that preparation.
    vendor=next(edge for edge in world.get_region(str(Regions.SPIRIT_TEMPLE_CHILD_CLIMB)).exits
                if edge.connected_region and edge.connected_region.name==str(Regions.SPIRIT_TEMPLE_CENTRAL_CHAMBER)).access_rule
    world.set_rules()
    rr='RR_SPIRIT_TEMPLE_SUN_ON_FLOOR_2F'
    target='RR_SPIRIT_TEMPLE_STATUE_ROOM_CHILD'
    expression=next(row['condition'] for row in GRAPH[rr]['exits'] if row['target']==target)
    native_source=(RANDO/'location_access/dungeons/spirit_temple.cpp').read_text()
    assert expression in native_source
    native=world._extreme_room_compiler.expr(expression,rr).resolve(world)
    physical=ER._source_rule(world,next(row for row in ER.CATALOG if row['source']==rr and row['target']==target))
    def state_for(items):
        state=CollectionState(mw)
        for item in items:state.collect(world.create_item(str(item)),True)
        state._soh_extreme_age[1]=Ages.ADULT
        return state
    soul='Rock / Boulder Soul'
    light=(Items.LIGHT_ARROW,Items.PROGRESSIVE_BOW,Items.PROGRESSIVE_MAGIC_METER)
    cases=[]
    for items,expected in [((),False),((soul,),False),((Items.PROGRESSIVE_BOMB_BAG,),False),
                           ((Items.PROGRESSIVE_BOMB_BAG,soul),True),(light,True)]:
        observed={name:bool(rule(state_for(items))) for name,rule in [('native',native),('physical_door',physical),('vendor',vendor)]}
        assert all(value==expected for value in observed.values()),(items,expected,observed)
        cases.append({'inventory':list(map(str,items)),'expected':expected,'routes':observed})
    world.options.sunlight_arrows.value=0
    no_sun=world._extreme_room_compiler.expr(expression,rr).resolve(world)
    assert not no_sun(state_for(light))
    world.options.shuffle_rock_boulder_soul.value=0
    free_soul=world._extreme_room_compiler.expr(expression,rr).resolve(world)
    assert free_soul(state_for((Items.PROGRESSIVE_BOMB_BAG,)))
    print('PASS actual AP native, physical doorway, and vendor Spirit routes require the soul only for breaking')
    return {'status':'passed','cases':cases,'sunlight_disabled_without_soul':False,'soul_disabled_with_explosives':True,
            'scope':'Real AP rule compilation and local predicates; no new full-world fill or gameplay test.'}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path);parser.add_argument('--ap',action='store_true')
    args=parser.parse_args()
    paths,native,draw=fragments()
    outputs=[];counts={'cases':0,'assertions':0}
    with tempfile.TemporaryDirectory(prefix='soh-soul-object-') as tmp:
        build=Path(tmp)
        for name,language,parts in [('native','c',native),('draw','cpp',draw)]:
            template=(FIXTURES/(name+'_fixture.'+language+'.in')).read_text()
            for token,text in parts.items():template=template.replace('@'+token+'@',text)
            assert not re.search(r'@[A-Z_]+@',template)
            file=build/(name+'.'+language);file.write_text(template)
            command=['gcc' if language=='c' else 'g++','-std=c11' if language=='c' else '-std=c++20',
                     '-Wall','-Wextra','-Werror','-Wno-unused-variable','-Wno-unused-parameter',
                     '-fsanitize=address,undefined','-fno-omit-frame-pointer','-g','-O1',str(file),'-lm','-o',str(build/name)]
            compiled=subprocess.run(command,text=True,capture_output=True)
            if compiled.returncode:raise RuntimeError(compiled.stdout+compiled.stderr)
            env=dict(os.environ,ASAN_OPTIONS='detect_leaks=0:halt_on_error=1',UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
            result=subprocess.run([str(build/name)],text=True,capture_output=True,env=env)
            print(result.stdout,end='')
            if result.returncode:raise RuntimeError(result.stderr or f'{name} failed: {result.returncode}')
            match=re.search(r'RESULT cases=(\d+) assertions=(\d+)',result.stdout);assert match
            for key,value in zip(counts,match.groups()):counts[key]+=int(value)
            outputs+=result.stdout.splitlines()
    report={'status':'passed','native':counts,'sanitizers':['AddressSanitizer','UndefinedBehaviorSanitizer'],
            'scope':'Actual source action functions, OC separation, collider transform, randomized draw and recovery hook bodies with engine shims; not a full native build or gameplay test.',
            'output':outputs}
    if args.ap:report['ap']=check_ap()
    for name in ('EnemyRoomGraph.json','EnemyRoomLogic.py','_vendor_oot_soh/location_access/dungeons/spirit_temple.py'):
        paths[name]=SOURCE/'archipelago/soh_extreme'/name
    paths['spirit']=RANDO/'location_access/dungeons/spirit_temple.cpp'
    for key,path in [('runner',Path(__file__)),('native_fixture',FIXTURES/'native_fixture.c.in'),
                     ('draw_fixture',FIXTURES/'draw_fixture.cpp.in')]:
        paths[key]=path
    report['sources']={str(path.relative_to(SOURCE)):hashlib.sha256(path.read_bytes()).hexdigest() for path in paths.values()}
    if args.report:args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
