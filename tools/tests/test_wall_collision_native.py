"""Execute native mud-wall collision registration and break behavior.

The preserved old production draw/object-wait/update functions reproduce the
no-draw failure. Current actor functions, AC reset/registration and damage-mask
checks run from production source. Engine object loading, contact geometry,
graphics, audio, dynamic collision allocation and matrix operations are shimmed.
Requires Python 3 and g++ with C++20, AddressSanitizer and UBSan; no ROM assets or
external test dependency bundle is needed.
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
        'wall': ACTORS / 'ovl_Bg_Breakwall/z_bg_breakwall.c',
        'wall_header': ACTORS / 'ovl_Bg_Breakwall/z_bg_breakwall.h',
        'collision': SOURCE / 'src/code/z_collision_check.c',
        'actor_engine': SOURCE / 'src/code/z_actor.c',
        'souls': SOURCE / 'soh/Enhancements/randomizer/MegaSouls.cpp',
        'blue_fire': SOURCE / 'soh/Enhancements/Items/BlueFireArrows.cpp',
        'bomb': ACTORS / 'ovl_En_Bom/z_en_bom.c',
        'bombflower': ACTORS / 'ovl_En_Bombf/z_en_bombf.c',
        'bombchu': ACTORS / 'ovl_En_Bom_Chu/z_en_bom_chu.c',
        'player': ACTORS / 'ovl_player_actor/z_player.c',
        'legacy': Path(__file__).with_name('bg_breakwall_legacy_functions.inc'),
        'runner': Path(__file__),
        'extractor': Path(__file__).with_name('test_soul_object_blockers.py'),
        'fixture': Path(__file__).with_name('wall_collision_native_tests.cpp.in'),
    }
    before = {str(path.relative_to(SOURCE)): digest(path) for path in paths.values()}
    code = {key: path.read_text() for key, path in paths.items()}
    groups = {
        'WALL': ('wall', ['BgBreakwall_SetupAction', 'BgBreakwall_Init',
                         'BgBreakwall_Destroy', 'BgBreakwall_WaitForObject',
                         'BgBreakwall_Wait', 'BgBreakwall_LavaCoverMove',
                         'BgBreakwall_UpdateCollider', 'BgBreakwall_Update', 'BgBreakwall_Draw']),
        'COLLISION': ('collision', ['Collider_ResetACBase', 'Collider_ResetACInfo',
                                  'Collider_ResetQuadAC', 'CollisionCheck_SetAC',
                                  'CollisionCheck_NoSharedFlags', 'Collider_SetQuadMidpoints',
                                  'Collider_SetQuadVertices']),
        'SOULS': ('souls', ['MegaHas', 'MegaSoul_CanUseRock', 'MegaSoul_CanUseCrate',
                           'IsMegaAnimalActor', 'IsMegaCrateActor', 'IsMegaRockActor',
                           'IsMegaScrubActor', 'IsMegaNpcSoulActor',
                           'MegaSoul_IsNpcSoulLocked', 'MegaSoul_CanInteractWithActor']),
        'BLUE_FIRE': ('blue_fire', ['UpdateBlueFireCollidersBgBreakwall']),
        'BOMBCHU': ('bombchu', ['EnBomChu_Explode']),
    }
    functions = {name: function(code[key], name)
                 for key, names in groups.values() for name in names}
    parts = {token: '\n\n'.join(functions[name] for name in names)
             for token, (_, names) in groups.items()}
    parts['WALL_TYPES'] = re.search(r'typedef enum \{.*?\} BombableWallType;', code['wall_header'], re.S)[0]
    parts['INFO_STRUCT'] = re.search(r'typedef struct \{.*?\} BombableWallInfo;', code['wall'], re.S)[0]
    parts['DATA'] = '\n\n'.join(re.search(pattern, code['wall'], re.S)[0] for pattern in [
        r'static ColliderQuadInit sQuadInit = \{.*?\n\};',
        r'static BombableWallInfo sBombableWallInfo\[\] = \{.*?\n\};',
        r'static InitChainEntry sInitChain\[\] = \{.*?\n\};',
        r'static Vec3f sColQuadList\[\]\[4\] = \{.*?\n\};',
    ])
    parts['ACTOR_DEFAULT_FLAGS'] = re.search(r'^#define FLAGS ([^\n]+)', code['wall'], re.M)[1]
    parts['MELEE_FLAGS'] = re.search(r'static u32 D_80854488\[\]\[2\] = \{.*?\n\};', code['player'], re.S)[0]
    for token, key in [('BOMB_MASK', 'bomb'), ('BOMBFLOWER_MASK', 'bombflower')]:
        init = re.search(r'static ColliderJntSphElementInit sJntSphElementsInit\[1\] = \{.*?\n\};', code[key], re.S)[0]
        parts[token] = re.search(r'ELEMTYPE_UNK0,\s*\{ (0x[0-9A-Fa-f]+),', init)[1]
    actor_update = function(code['actor_engine'], 'Actor_UpdateAll')
    parts['UPDATE_PREDICATE'] = re.search(r'if \(\((DECR\(actor->freezeTimer\).*?)\) \{', actor_update, re.S)[1]
    actor_draw = function(code['actor_engine'], 'Actor_Draw')
    start = actor_draw.index('    if (actor->flags & ACTOR_FLAG_IGNORE_QUAKE)')
    end = actor_draw.index('    Actor_SetObjectDependency(play, actor);', start)
    parts['DRAW_TRANSFORM'] = actor_draw[start:end]
    parts['LEGACY'] = code['legacy']
    symbols = set(re.findall(r'\b(?:ACTOR_|RAND_INF_|RSK_)[A-Z0-9_]+\b', parts['SOULS']))
    symbols.update({'ACTOR_BG_BREAKWALL', 'ACTOR_BG_BOMBWALL', 'ACTOR_EN_BOM'})
    parts['SYMBOLS'] = 'enum { '+', '.join(sorted(symbols))+' };'
    assert 'CollisionCheck_SetAC' not in functions['BgBreakwall_Draw']
    assert 'BgBreakwall_UpdateCollider' in functions['BgBreakwall_Update']
    assert 'BgBreakwall_UpdateCollider' not in parts['LEGACY']
    text = code['fixture']
    for key, value in parts.items():
        text = text.replace('@'+key+'@', re.sub(r'\bthis\b', 'self', value))
    assert not re.search(r'@[A-Z_]+@', text)
    with tempfile.TemporaryDirectory(prefix='soh-wall-collision-') as tmp:
        build = Path(tmp); cpp = build/'walls.cpp'; cpp.write_text(text)
        command = ['g++', '-std=c++20', '-Wall', '-Wextra', '-Werror',
                   '-Wno-unused-variable', '-Wno-unused-parameter',
                   '-Wno-missing-field-initializers',
                   '-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-g', '-O1',
                   str(cpp), '-o', str(build/'walls')]
        compiled = subprocess.run(command, text=True, capture_output=True)
        if compiled.returncode:
            raise RuntimeError(compiled.stdout+compiled.stderr)
        env = dict(os.environ, ASAN_OPTIONS='detect_leaks=0:halt_on_error=1',
                   UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
        result = subprocess.run([str(build/'walls')], text=True, capture_output=True, env=env)
        print(result.stdout, end='')
        if result.returncode:
            raise RuntimeError(result.stderr or f'Wall tests failed: {result.returncode}')
        match = re.search(r'RESULT cases=(\d+) assertions=(\d+)', result.stdout); assert match
    after = {str(path.relative_to(SOURCE)): digest(path) for path in paths.values()}
    if before != after:
        raise RuntimeError('Source changed during validation; rerun after edits settle.')
    report = {
        'status': 'passed', 'cases': int(match[1]), 'assertions': int(match[2]),
        'sanitizers': ['AddressSanitizer', 'UndefinedBehaviorSanitizer'],
        'source_unchanged_during_tests': True,
        'scope': 'Actual BgBreakwall init, object-wait, update, quad transform, draw, break/switch and lava functions; actual AC reset/registration, damage-mask predicate, Soul actor classification/interaction gates, Blue Fire extension and Bombchu explosion handoff. Preserved old production draw/object-wait/update functions reproduce the former no-draw failure only. Actual engine update-culling predicate and actor draw transform are extracted. Engine contact geometry, object/room assets, matrix math, graphics/audio/effects and dynamic collision allocation are shimmed. No complete native game build or controller playthrough.',
        'baseline_source_sha256': re.search(r'Original z_bg_breakwall.c SHA256: ([0-9a-f]{64})', code['legacy'])[1],
        'original_attack_mask': '0x00000048',
        'accepted_native_attacks': ['explosives: 0x00000008', 'ordinary Hammer swing: 0x00000040'],
        'excluded_native_hammer_jumpslash': '0x40000000',
        'replay_command': 'python source/tools/tests/test_wall_collision_native.py --report tests/wall_collision_1810_native.json',
        'external_dependencies': ['Python 3', 'g++ with C++20, AddressSanitizer and UndefinedBehaviorSanitizer'],
        'output': result.stdout.splitlines(), 'sources': after,
        'tested_function_sha256': {name: hashlib.sha256(value.encode()).hexdigest()
                                   for name, value in functions.items()},
        'extracted_predicate_sha256': {key: hashlib.sha256(parts[key].encode()).hexdigest()
                                      for key in ('UPDATE_PREDICATE', 'DRAW_TRANSFORM', 'LEGACY')},
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
