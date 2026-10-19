"""Exercise actual NPC soul hooks and native actor/talk/collision bodies.

This is a production-fragment test with minimal engine I/O shims. It is not
a full native build or gameplay test. C's local variable ``this`` is renamed
to ``self`` mechanically so those unchanged bodies can share the C++ fixture.
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

from test_soul_object_blockers import SOURCE, RANDO, ACTORS, FIXTURES, function


def body(text, marker):
    start=text.index(marker)+len(marker)
    clean=re.sub(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"',lambda m:' '*len(m[0]),text,flags=re.S)
    depth=1
    for end in range(start,len(text)):
        depth+=(clean[end]=='{')-(clean[end]=='}')
        if depth==0:return text[start:end]
    raise AssertionError('Unclosed hook '+marker)


def fragments():
    paths={'souls':RANDO/'MegaSouls.cpp','header':RANDO/'SoulActorAccess.h',
           'actor':SOURCE/'src/code/z_actor.c','collision':SOURCE/'src/code/z_collision_check.c',
           'kokiri':ACTORS/'ovl_En_Ko/z_en_ko.c','mido':ACTORS/'ovl_En_Md/z_en_md.c',
           'background':SOURCE/'src/code/z_bgcheck.c'}
    code={name:path.read_text() for name,path in paths.items()}
    out={}
    groups={
        'POLICY':('souls',['MegaHas','MegaSoul_CanUseRock','MegaSoul_CanUseCrate','IsMegaAnimalActor',
                  'IsMegaCrateActor','IsMegaRockActor','IsMegaScrubActor','IsMegaSignActor','IsMegaNpcSoulActor',
                  'MegaSoul_IsPathBlockingNpcPlacement','MegaSoul_IsPathBlockingNpc','MegaSoul_IsNpcSoulLocked',
                  'MegaSoul_CanInteractWithActor','MegaSoul_ShouldDisableActorCollision','MegaSoul_ShouldHideActor','UpdateNpcSoulState']),
        'NATIVE_TALK':('actor',['Actor_SetFocus','Actor_ProcessTalkRequest','Actor_OfferTalkExchange',
                       'Actor_OfferTalkExchangeEquiCylinder','Actor_OfferTalk','Actor_GetScreenPos','Npc_UpdateTalking',
                       'Actor_OfferGetItem','Actor_OfferGetItemNearby','Actor_OfferCarry','GiveItemEntryFromActor',
                       'Attention_ShouldReleaseLockOn']),
        'NATIVE_DRAW':('actor',['Actor_Draw']),
        'NATIVE_COLLISION':('collision',['CollisionCheck_GetMassType','CollisionCheck_SetOCvsOC','Collider_UpdateCylinder',
                          'CollisionCheck_SetAT','CollisionCheck_SetAC','CollisionCheck_SetOC',
                          'CollisionCheck_SetAT_SAC','CollisionCheck_SetAC_SAC','CollisionCheck_SetOC_SAC']),
        'KOKIRI':('kokiri',['func_80A995CC','EnKo_Update']),
        'MIDO':('mido',['EnMd_UpdateTalking','EnMd_BlockPath','EnMd_ListenToOcarina','EnMd_Update']),
        'NATIVE_DYNA':('background',['DynaPoly_IsBgIdBgActor','DynaPoly_GetActor','BgCheck_RaycastFloorDyna',
                        'BgCheck_SphVsDynaWall','BgCheck_CheckDynaCeiling','BgCheck_CheckLineAgainstDyna',
                        'BgCheck_SphVsFirstDynaPoly']),
    }
    for token,(source,names) in groups.items():
        out[token]='\n\n'.join(re.sub(r'\bthis\b','self',function(code[source],name)) for name in names)
    out['INIT_HOOK']=body(code['souls'],'COND_HOOK(OnActorInit, shouldRegister, [](void* actorRef) {')
    out['UPDATE_HOOK']=body(code['souls'],'COND_HOOK(ShouldActorUpdate, shouldRegister, [](void* actorRef, bool* should) {')
    out['SPEAK_HOOK']=body(code['souls'],'COND_VB_SHOULD(VB_SPEAK, shouldRegister, {')
    out['KOKIRI_MASS']=re.search(r'static CollisionCheckInfoInit2 sColChkInfoInit = \{[^}]*,\s*(MASS_\w+)\s*\}',code['kokiri'])[1]
    out['MIDO_MASS']=re.search(r'static CollisionCheckInfoInit2 sColChkInfoInit = \{[^}]*,\s*(MASS_\w+)\s*\}',code['mido'])[1]
    out['NPC_STATE_STORAGE']=re.search(r'static std::unordered_map<Actor\*, uint32_t> gNpcSoulInteractionFlags;',code['souls'])[0]
    # Verify the real hook repeats suppression after moving NPC updates, before
    # the engine's attention search. The state body itself is executed below.
    assert 'UpdateNpcSoulState(actor);' in body(code['souls'],'COND_HOOK(OnActorUpdate, shouldRegister, [handleEnemyDeath](void* actorRef) {')
    assert 'MegaSoul_CanInteractWithActor(actor)' in function(code['actor'],'Attention_FindActorInCategory')
    delayed=function(code['kokiri'],'func_80A99048')
    assert 'ENKO_TYPE == ENKO_TYPE_CHILD_3' in delayed and 'this->collider.dim.height += 200;' in delayed
    assert 'VB_OPEN_KOKIRI_FOREST' in delayed and 'this->actionFunc = func_80A995CC;' in delayed
    mido_init=function(code['mido'],'EnMd_Init')
    assert 'play->sceneNum == SCENE_LOST_WOODS' in mido_init
    assert '!Flags_GetEventChkInf(EVENTCHKINF_PLAYED_SARIAS_SONG_FOR_MIDO_AS_ADULT)' in mido_init
    assert 'this->actionFunc = EnMd_BlockPath;' in mido_init
    # Symbolic IDs are shim constants; equality/placement logic comes entirely
    # from the production policy, with independently enumerated test cases.
    ids=set(re.findall(r'\bACTOR_(?!FLAG_|CAT_)[A-Z0-9_]+\b','\n'.join(out.values())))
    ids.update(['ACTOR_EN_RU1','ACTOR_EN_GOROIWA','ACTOR_BG_JYA_GOROIWA','ACTOR_BG_JYA_BOMBIWA'])
    out['ACTOR_IDS']='enum { '+', '.join(sorted(ids))+' };'
    return paths,out


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path);args=parser.parse_args()
    paths,parts=fragments()
    template=(FIXTURES/'npc_fixture.cpp.in').read_text()
    for key,value in parts.items():template=template.replace('@'+key+'@',value)
    assert not re.search(r'@[A-Z_]+@',template)
    with tempfile.TemporaryDirectory(prefix='soh-soul-npc-') as tmp:
        build=Path(tmp);source=build/'npc.cpp';source.write_text(template)
        command=['g++','-std=c++20','-Wall','-Wextra','-Werror','-Wno-unused-variable','-Wno-unused-parameter',
                 '-fsanitize=address,undefined','-fno-omit-frame-pointer','-g','-O1','-I',str(SOURCE),
                 str(source),'-lm','-o',str(build/'npc')]
        compiled=subprocess.run(command,text=True,capture_output=True)
        if compiled.returncode:raise RuntimeError(compiled.stdout+compiled.stderr)
        env=dict(os.environ,ASAN_OPTIONS='detect_leaks=0:halt_on_error=1',UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
        result=subprocess.run([str(build/'npc')],text=True,capture_output=True,env=env)
        print(result.stdout,end='')
        if result.returncode:raise RuntimeError(result.stderr or f'NPC test failed: {result.returncode}')
        match=re.search(r'RESULT cases=(\d+) assertions=(\d+)',result.stdout);assert match
    report={'status':'passed','cases':int(match[1]),'assertions':int(match[2]),
            'sanitizers':['AddressSanitizer','UndefinedBehaviorSanitizer'],
            'scope':'Actual soul policy/hooks, draw/talk/get-item/targeting, Kokiri exit boy update/movement, adult Lost Woods Mido update/blocking/talk/ocarina functions, all six collider registration functions, OC separation, and five dynamic collision query loops. Engine I/O and geometric narrow-phase helpers are shimmed; no full native build, ROM collision simulation, or gameplay test.',
            'output':result.stdout.splitlines(),
            'sources':{str(path.relative_to(SOURCE)):hashlib.sha256(path.read_bytes()).hexdigest() for path in paths.values()}}
    for path in [Path(__file__), Path(__file__).with_name('test_soul_object_blockers.py'), FIXTURES/'npc_fixture.cpp.in']:
        report['sources'][str(path.relative_to(SOURCE))]=hashlib.sha256(path.read_bytes()).hexdigest()
    if args.report:args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
