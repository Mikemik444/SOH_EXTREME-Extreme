"""Compile all seven native EnHoll forms and their room-boundary hook wiring.

The real actor predicates, action functions, preload swaps and observation hooks
run unchanged except C's `this` identifier is renamed for C++. Room allocation,
player transforms and Archipelago history storage use explicit engine I/O shims;
the companion dungeon-return fixture exercises the real history implementation.
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


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    paths = {
        'actor': ACTORS / 'ovl_En_Holl/z_en_holl.c',
        'header': ACTORS / 'ovl_En_Holl/z_en_holl.h',
        'api': SOURCE / 'soh/Network/Archipelago/ArchipelagoC.h',
        'runner': Path(__file__),
        'extractor': Path(__file__).with_name('test_soul_object_blockers.py'),
        'fixture': Path(__file__).with_name('hallway_boundary_native_tests.cpp.in'),
    }
    before = {str(path.relative_to(SOURCE)): digest(path) for path in paths.values()}
    actor, header, api = (paths[key].read_text() for key in ('actor', 'header', 'api'))
    actions = [
        'EnHoll_HorizontalVisibleNarrow', 'EnHoll_VerticalDownBgCoverLarge',
        'EnHoll_VerticalInvisible', 'EnHoll_HorizontalBgCoverSwitchFlag',
        'EnHoll_HorizontalInvisible', 'EnHoll_VerticalBgCover', 'EnHoll_WaitRoomLoaded',
    ]
    names = [
        'EnHoll_SetupAction', 'EnHoll_IsKokiriLayer8', 'EnHoll_ChooseAction',
        'EnHoll_SwapRooms', 'EnHoll_ShouldTrackRoomBoundary',
        'EnHoll_ObserveRoomBoundary', 'EnHoll_SelectRoomBoundary',
        'EnHoll_RequestNewRoom', *actions, 'EnHoll_Update',
    ]
    functions = {name: function(actor, name) for name in names}
    parts = {
        'CONSTANTS': '\n'.join(re.findall(r'^#define ENHOLL_[^\n]+', actor+'\n'+header, re.M)),
        'TYPES': re.search(r'typedef enum EnHollType \{.*?\} EnHollType;', header, re.S)[0],
        'API': '\n'.join(re.findall(r'^void Archipelago_Entrance(?:Observe|Select)RoomBoundary\([^\n]+', api, re.M)),
        'DECLARATIONS': '\n'.join('void '+name+'(EnHoll*, PlayState*);' for name in actions),
        'ACTION_TABLE': re.search(r'static EnHollActionFunc sActionFuncs\[\] = \{.*?\};', actor, re.S)[0],
        'TRIGGERS': re.search(r'static f32 sHorizontalVisibleNarrowTriggerDists\[2\]\[4\] = \{.*?\};', actor, re.S)[0],
        'FUNCTIONS': '\n\n'.join(functions.values()),
    }
    assert len(parts['API'].splitlines()) == 2
    assert '#include "soh/Network/Archipelago/ArchipelagoC.h"' in actor
    assert actor.count('Room_RequestNewRoom(') == 1, 'Every native hallway request must use the observer wrapper.'
    text = paths['fixture'].read_text()
    for key, value in parts.items():
        text = text.replace('@'+key+'@', re.sub(r'\bthis\b', 'self', value))
    assert not re.search(r'@[A-Z_]+@', text)
    with tempfile.TemporaryDirectory(prefix='soh-hallway-boundary-') as tmp:
        build = Path(tmp)
        cpp = build / 'hallways.cpp'
        cpp.write_text(text)
        command = ['g++', '-std=c++20', '-Wall', '-Wextra', '-Werror',
                   '-Wno-unused-variable', '-Wno-unused-parameter',
                   '-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-g', '-O1',
                   str(cpp), '-o', str(build / 'hallways')]
        compiled = subprocess.run(command, text=True, capture_output=True)
        if compiled.returncode:
            raise RuntimeError(compiled.stdout+compiled.stderr)
        env = dict(os.environ, ASAN_OPTIONS='detect_leaks=0:halt_on_error=1',
                   UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
        result = subprocess.run([str(build/'hallways')], text=True, capture_output=True, env=env)
        print(result.stdout, end='')
        if result.returncode:
            raise RuntimeError(result.stderr or f'Hallway tests failed: {result.returncode}')
        match = re.search(r'RESULT cases=(\d+) assertions=(\d+)', result.stdout)
        assert match
    after = {str(path.relative_to(SOURCE)): digest(path) for path in paths.values()}
    if before != after:
        raise RuntimeError('Source changed during validation; rerun after edits settle.')
    report = {
        'status': 'passed', 'cases': int(match[1]), 'assertions': int(match[2]),
        'sanitizers': ['AddressSanitizer', 'UndefinedBehaviorSanitizer'],
        'source_unchanged_during_tests': True,
        'scope': 'Actual EnHoll Update, all seven hallway types, room swaps, wait/finish actions, source-side observation and pre-request/final-commit selection helpers. Actor coordinate transforms, room loader, switch lookup and AP hook storage are shimmed. The companion entrance_return_death_1810_native.json validates actual history storage. No native game build, scene geometry or controller playthrough.',
        'output': result.stdout.splitlines(),
        'sources': after,
        'tested_function_sha256': {name: hashlib.sha256(value.encode()).hexdigest()
                                   for name, value in functions.items()},
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
