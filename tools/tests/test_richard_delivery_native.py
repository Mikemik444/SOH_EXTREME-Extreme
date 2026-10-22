"""Exercise native Richard pickup, local scene transfer and lady delivery.

Actual production functions and narrowly delimited source branches are compiled
with engine I/O shims. Scene object-bank availability is a test input; room asset
lists and collision geometry are not supplied by the uploaded source.
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

from test_soul_object_blockers import SOURCE, ACTORS, function
from test_soul_npc_blockers import body


def fragments():
    paths = {
        'dog': ACTORS / 'ovl_En_Dog/z_en_dog.c',
        'dog_header': ACTORS / 'ovl_En_Dog/z_en_dog.h',
        'lady': ACTORS / 'ovl_En_Hy/z_en_hy.c',
        'player': ACTORS / 'ovl_player_actor/z_player.c',
        'hooks': SOURCE / 'soh/Enhancements/randomizer/hook_handlers.cpp',
        'souls': SOURCE / 'soh/Enhancements/randomizer/MegaSouls.cpp',
        'catalog': SOURCE / 'archipelago/soh_extreme/EntranceCatalog.json',
        'scene_checks': SOURCE / 'archipelago/soh_extreme/SceneTransitionCatalog.json',
    }
    code = {key: path.read_text() for key, path in paths.items()}
    parts = {}
    parts['DOG'] = '\n\n'.join(function(code['dog'], name) for name in
                                ['EnDog_CanFollow', 'EnDog_Init', 'EnDog_FollowPlayer'])
    spawn_marker = '        if (gSaveContext.dogParams < 0) {'
    parts['TRANSFER'] = spawn_marker+body(function(code['player'], 'Player_Update'), spawn_marker)+'}'
    init_marker = '            if (gSaveContext.dogParams != 0) {'
    parts['ARM_TRANSFER'] = init_marker+body(code['player'], init_marker)+'}'
    text_fn = function(code['lady'], 'EnHy_GetTextId')
    parts['LADY_TEXT'] = text_fn[text_fn.index('        case ENHY_TYPE_AOB:'):text_fn.index('        case ENHY_TYPE_COB:')]
    parts['LADY_SPAWN'] = function(code['lady'], 'EnHy_ShouldSpawn')
    talk_fn = function(code['lady'], 'EnHy_UpdateTalkState')
    # The earlier cases play recognition audio. Delivery happens in the final
    # textbox-closing switch, after the player finishes the conversation.
    start = talk_fn.rindex('                case 0x709E:')
    parts['LADY_TALK'] = talk_fn[start:talk_fn.index('\n            }', start)]
    hook_start = code['hooks'].index('        case VB_GIVE_ITEM_FROM_LOST_DOG: {')
    parts['REWARD_HOOK'] = code['hooks'][hook_start:code['hooks'].index('        case VB_GIVE_ITEM_FROM_BOMBCHU_BOWLING:', hook_start)]
    parts['ANIMAL_POLICY'] = '\n\n'.join(function(code['souls'], name) for name in
                                          ['AnimalSoulInfForActor', 'HasRequiredAnimalSoul'])
    init_hook = body(code['souls'], 'COND_HOOK(ShouldActorInit, shouldRegister, [](void* actorRef, bool* result) {')
    gate_start = init_hook.index('        if (RAND_GET_OPTION(RSK_SHUFFLE_ANIMAL_SOUL) && IsMegaAnimalActor(actor->id) &&')
    gate_marker = init_hook[gate_start:init_hook.index('{', gate_start)+1]
    parts['ANIMAL_INIT_GATE'] = gate_marker+body(init_hook, gate_marker)+'}'
    parts['DOG_ENUMS'] = re.search(r'typedef enum \{[^}]*\} EnDogAnimation;', code['dog'], re.S)[0]
    parts['DOG_BEHAVIOR'] = re.search(r'typedef enum \{[^}]*\} DogBehavior;', code['dog'], re.S)[0]
    symbols = set(re.findall(r'\b(?:SCENE_|ENHY_TYPE_|ACTOR_|RAND_INF_)[A-Z0-9_]+\b', '\n'.join(parts.values())))
    parts['SYMBOLS'] = 'enum { '+', '.join(sorted(symbols))+' };'
    for key in parts:
        parts[key] = re.sub(r'\bthis\b', 'self', parts[key])
    endpoints = json.loads(code['catalog'])
    assert not any(e['id'] in {908, 920} or e['source'] == 'MARKET_DOG_LADY_HOUSE' or
                   e['target'] == 'MARKET_DOG_LADY_HOUSE' for e in endpoints)
    return paths, parts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    paths, parts = fragments()
    fixture = Path(__file__).with_name('richard_delivery_native_tests.cpp.in')
    cpp_text = fixture.read_text()
    for key, value in parts.items():
        cpp_text = cpp_text.replace('@'+key+'@', value)
    assert not re.search(r'@[A-Z_]+@', cpp_text)
    with tempfile.TemporaryDirectory(prefix='soh-richard-') as tmp:
        build = Path(tmp); cpp = build/'richard.cpp'; cpp.write_text(cpp_text)
        command = ['g++', '-std=c++20', '-Wall', '-Wextra', '-Werror',
                   '-Wno-unused-variable', '-Wno-unused-parameter', '-Wno-unused-function',
                   '-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-g', '-O1',
                   str(cpp), '-o', str(build/'richard')]
        compiled = subprocess.run(command, text=True, capture_output=True)
        if compiled.returncode:
            raise RuntimeError(compiled.stdout+compiled.stderr)
        env = dict(os.environ, ASAN_OPTIONS='detect_leaks=0:halt_on_error=1',
                   UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
        result = subprocess.run([str(build/'richard')], text=True, capture_output=True, env=env)
        print(result.stdout, end='')
        if result.returncode:
            raise RuntimeError(result.stderr or f'Richard test failed: {result.returncode}')
        match = re.search(r'RESULT cases=(\d+) assertions=(\d+)', result.stdout); assert match
    paths['runner'] = Path(__file__); paths['fixture'] = fixture
    report = {
        'status': 'passed', 'cases': int(match[1]), 'assertions': int(match[2]),
        'sanitizers': ['AddressSanitizer', 'UndefinedBehaviorSanitizer'],
        'scope': 'Actual dog Init/CanFollow/FollowPlayer, player scene-transfer marker/spawn branch, dog-lady spawn and Richard dialogue/reward branches, animal Soul policy/init gate, and randomizer reward hook. Engine I/O and object-bank availability are shimmed; common NPC/language dispatch is outside this fixture and is covered by the separate NPC/AP suites. No complete native build, scene asset list, route geometry or gameplay test.',
        'output': result.stdout.splitlines(),
        'sources': {str(path.relative_to(SOURCE)): hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in paths.values()},
        'tested_function_sha256': {key: hashlib.sha256(value.encode()).hexdigest() for key, value in parts.items()},
        'protected_house_entrances_absent_from_shuffle_catalog': [908, 920],
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
