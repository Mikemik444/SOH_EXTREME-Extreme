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
           'mido':ACTORS/'ovl_En_Md/z_en_md.c'}
    code={name:path.read_text() for name,path in paths.items()}
    out={}
    groups={
        'POLICY':('souls',['MegaHas','MegaSoul_CanUseRock','MegaSoul_CanUseCrate','IsMegaAnimalActor',
                  'IsMegaCrateActor','IsMegaRockActor','IsMegaScrubActor','IsMegaSignActor','IsMegaNpcSoulActor',
                  'MegaSoul_IsPathBlockingNpcPlacement','MegaSoul_IsPathBlockingNpc','UpdateHiddenNpcFocus',
                  'MegaSoul_ShouldHideActor']),
        'NATIVE_TALK':('actor',['Actor_SetFocus','Actor_ProcessTalkRequest','Actor_OfferTalkExchange',
                       'Actor_OfferTalkExchangeEquiCylinder','Actor_OfferTalk','Actor_GetScreenPos','Npc_UpdateTalking']),
        'NATIVE_DRAW':('actor',['Actor_Draw']),
        'NATIVE_COLLISION':('collision',['CollisionCheck_GetMassType','CollisionCheck_SetOCvsOC','Collider_UpdateCylinder']),
        'MIDO':('mido',['EnMd_UpdateTalking','EnMd_BlockPath','EnMd_Update']),
    }
    for token,(source,names) in groups.items():
        out[token]='\n\n'.join(re.sub(r'\bthis\b','self',function(code[source],name)) for name in names)
    out['INIT_HOOK']=body(code['souls'],'COND_HOOK(OnActorInit, shouldRegister, [](void* actorRef) {')
    out['UPDATE_HOOK']=body(code['souls'],'COND_HOOK(ShouldActorUpdate, shouldRegister, [](void* actorRef, bool* should) {')
    out['SPEAK_HOOK']=body(code['souls'],'COND_VB_SHOULD(VB_SPEAK, shouldRegister, {')
    out['MIDO_MASS']=re.search(r'static CollisionCheckInfoInit2 sColChkInfoInit = \{[^}]*,\s*(MASS_\w+)\s*\}',code['mido'])[1]
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
            'scope':'Actual soul policy/hooks, native draw, talk offering/screen focus, Mido update/blocking, cylinder update and OC separation bodies with engine I/O shims; not a full native build or gameplay test.',
            'output':result.stdout.splitlines(),
            'sources':{str(path.relative_to(SOURCE)):hashlib.sha256(path.read_bytes()).hexdigest() for path in paths.values()}}
    if args.report:args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
