"""Execute real Gerudo init, update, capture and card-refresh functions.

Engine rendering, animation, message and collision I/O use minimal shims. This
does not include scene actor-list assets or establish where guards are placed.
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


def fragments():
    paths = {
        'white': ACTORS / 'ovl_En_Ge1/z_en_ge1.c',
        'white_header': ACTORS / 'ovl_En_Ge1/z_en_ge1.h',
        'purple': ACTORS / 'ovl_En_Ge2/z_en_ge2.c',
        'purple_header': ACTORS / 'ovl_En_Ge2/z_en_ge2.h',
        'hooks': SOURCE / 'soh/Enhancements/randomizer/hook_handlers.cpp',
    }
    code = {name: path.read_text() for name, path in paths.items()}
    groups = {
        'WHITE': ('white', [
            'EnGe1_CheckCarpentersFreed', 'EnGe1_Init', 'EnGe1_KickPlayer',
            'EnGe1_SpotPlayer', 'EnGe1_WatchForPlayerFrontOnly',
            'EnGe1_WatchForAndSensePlayer', 'EnGe1_UpdateRandomizerFriendliness',
            'EnGe1_Update',
        ]),
        'PURPLE': ('purple', [
            'EnGe2_ChangeAction', 'EnGe2_CheckCarpentersFreed', 'EnGe2_Init',
            'Ge2_DetectPlayerInUpdate', 'EnGe2_CaptureClose', 'EnGe2_CaptureCharge',
            'EnGe2_CaptureTurn', 'EnGe2_SetupCapturePlayer',
            'EnGe2_SetActionAfterTalk', 'EnGe2_MaintainColliderAndSetAnimState',
            'EnGe2_MoveAndBlink', 'EnGe2_UpdateFriendly', 'EnGe2_UpdateAfterTalk',
            'EnGe2_UpdateRandomizerFriendliness', 'EnGe2_Update', 'EnGe2_UpdateStunned',
        ]),
    }
    parts = {}
    for token, (key, names) in groups.items():
        parts[token] = '\n\n'.join(re.sub(r'\bthis\b', 'self', function(code[key], name)) for name in names)
    parts['WHITE_TYPES'] = re.search(r'typedef enum \{.*?\} EnGe1Type;', code['white_header'], re.S)[0]
    parts['WHITE_HAIR'] = re.search(r'typedef enum \{.*?\} EnGe1Hairstyle;', code['white'], re.S)[0]
    parts['PURPLE_TYPES'] = re.search(r'typedef enum \{.*?\} EnGe2Type;', code['purple'], re.S)[0]
    parts['PURPLE_ACTIONS'] = re.search(r'typedef enum \{[^}]*\} EnGe2Action;', code['purple'], re.S)[0]
    parts['PURPLE_ACTION_TABLE'] = re.search(r'static EnGe2ActionFunc sActionFuncs\[\] = \{.*?\};', code['purple'], re.S)[0]
    parts['STATE_FLAGS'] = '\n'.join(re.findall(r'^#define GE[12]_STATE_.*$', code['white']+'\n'+code['purple'], re.M))
    # Execute the actual hook branches that override freed-carpenter friendliness
    # and allow a card holder to request voluntary jail travel.
    hooks = code['hooks']
    start = hooks.index('        case VB_GERUDO_GUARD_SET_ACTION_AFTER_TALK:')
    end = hooks.index('        case VB_GTG_GATE_BE_OPEN:', start)
    parts['HOOK_CASES'] = hooks[start:end]
    for key in ('WHITE', 'PURPLE'):
        assert 'UpdateRandomizerFriendliness' in parts[key]
    # Preserve the separate deliberate-capture update entry point.
    assert 'UpdateRandomizerFriendliness' not in function(code['purple'], 'EnGe2_UpdateAfterTalk')
    return paths, parts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    paths, parts = fragments()
    fixture = Path(__file__).with_name('gerudo_guard_card_native_tests.cpp.in')
    cpp_text = fixture.read_text()
    for key, value in parts.items():
        cpp_text = cpp_text.replace('@'+key+'@', value)
    assert not re.search(r'@[A-Z_]+@', cpp_text)
    with tempfile.TemporaryDirectory(prefix='soh-gerudo-card-') as tmp:
        build = Path(tmp)
        cpp = build / 'guards.cpp'
        cpp.write_text(cpp_text)
        command = ['g++', '-std=c++20', '-Wall', '-Wextra', '-Werror',
                   '-Wno-unused-variable', '-Wno-unused-parameter',
                   '-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-g', '-O1',
                   str(cpp), '-o', str(build / 'guards')]
        compiled = subprocess.run(command, text=True, capture_output=True)
        if compiled.returncode:
            raise RuntimeError(compiled.stdout+compiled.stderr)
        env = dict(os.environ, ASAN_OPTIONS='detect_leaks=0:halt_on_error=1',
                   UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
        result = subprocess.run([str(build/'guards')], text=True, capture_output=True, env=env)
        print(result.stdout, end='')
        if result.returncode:
            raise RuntimeError(result.stderr or f'Guard tests failed: {result.returncode}')
        match = re.search(r'RESULT cases=(\d+) assertions=(\d+)', result.stdout)
        assert match
    paths['runner'] = Path(__file__)
    paths['fixture'] = fixture
    report = {
        'status': 'passed', 'cases': int(match[1]), 'assertions': int(match[2]),
        'sanitizers': ['AddressSanitizer', 'UndefinedBehaviorSanitizer'],
        'scope': 'Actual EnGe1/EnGe2 init, update, sensing/capture, card-refresh, friendly/stunned and voluntary-jail functions plus actual randomizer friendliness/jail hook branches. Animation, rendering, collision and message I/O are shimmed. Soul-freeze dispatch is modeled by the harness; no full native build, scene actor placement or gameplay test.',
        'output': result.stdout.splitlines(),
        'sources': {str(path.relative_to(SOURCE)): hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in paths.values()},
        'tested_function_sha256': {key: hashlib.sha256(value.encode()).hexdigest()
                                   for key, value in parts.items()},
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
