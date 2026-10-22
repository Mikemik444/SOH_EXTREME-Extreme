"""Compile actual warp departure, native routing and AP scene-journal functions.

Engine animation timing, scene allocation, collision, hook dispatch and network
I/O are isolated. The complete native Environment_WarpSongLeave, warp resolver,
pause/skip callbacks, AP record/completion bodies and transition-reporting methods
execute with the real entrance table and catalog, under ASan/UBSan.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def function(text, signature):
    """Retain a complete function; these selected bodies have balanced braces."""
    start = text.index(signature)
    opened = text.index('{', start)
    depth = 1
    end = opened + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end] + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dependencies', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    compiler = shutil.which('g++') or shutil.which('c++')
    if not compiler:
        raise SystemExit('A C++20 compiler is required.')
    dependencies = ('entrance_table.h', 'scene_table.h')
    for name in dependencies:
        assert (args.dependencies / name).is_file(), name
    sources = (
        'soh/Network/Archipelago/SceneTransitionChecks.h',
        'soh/Network/Archipelago/SceneTransitionData.inc',
        'soh/Network/Archipelago/ArchipelagoClient.cpp',
        'soh/Network/Archipelago/ArchipelagoClient.h',
        'soh/Network/Archipelago/ArchipelagoC.h',
        'soh/Network/Archipelago/EntranceRuntime.inc',
        'soh/Network/Archipelago/EntranceRouting.h',
        'soh/Network/Archipelago/EntranceRandomizerData.inc',
        'soh/Network/Archipelago/EntranceDestinationPolicy.h',
        'soh/Network/Archipelago/EntranceDestinationData.inc',
        'soh/Enhancements/randomizer/randomizer_entrance.c',
        'soh/Enhancements/randomizer/hook_handlers.cpp',
        'soh/Enhancements/QoL/PauseWarp.cpp',
        'soh/Enhancements/QoL/SkipWarpAnimation.cpp',
        'src/code/z_kankyo.c', 'src/code/z_play.c',
        'src/overlays/actors/ovl_player_actor/z_player.c',
        'src/overlays/actors/ovl_Demo_Kankyo/z_demo_kankyo.c',
        'archipelago/soh_extreme/SceneTransitionCatalog.json',
    )
    tests = ('tools/tests/test_warp_song_checks.py',
             'tools/tests/warp_song_checks_tests.cpp.in',
             'tools/tests/warp_song_1812_legacy_crossing.inc')
    before = {name: digest(root / name) for name in sources}
    test_before = {name: digest(root / name) for name in tests}
    read = lambda name: (root / name).read_text(encoding='utf-8-sig')
    client = read('soh/Network/Archipelago/ArchipelagoClient.cpp')
    runtime = read('soh/Network/Archipelago/EntranceRuntime.inc')
    native = read('soh/Enhancements/randomizer/randomizer_entrance.c')
    pause = read('soh/Enhancements/QoL/PauseWarp.cpp')
    skip = read('soh/Enhancements/QoL/SkipWarpAnimation.cpp')
    player = read('src/overlays/actors/ovl_player_actor/z_player.c')
    kankyo = read('src/code/z_kankyo.c')
    demo = read('src/overlays/actors/ovl_Demo_Kankyo/z_demo_kankyo.c')
    play = read('src/code/z_play.c')
    hooks = read('soh/Enhancements/randomizer/hook_handlers.cpp')
    assert 'Environment_WarpSongLeave(play);' in demo
    # Capture happens before nextEntranceIndex is committed or trigger cleared.
    assert play.count('Archipelago_CaptureSceneTransition();') == 4
    for found in re.finditer('Archipelago_CaptureSceneTransition\\(\\);', play):
        assert 'gSaveContext.entranceIndex = play->nextEntranceIndex;' in play[found.end():found.end()+150]
    rows = json.loads(read('archipelago/soh_extreme/SceneTransitionCatalog.json'))
    warp_rows = [row for row in rows if row['kind'] == 'WarpSong']
    assert len(warp_rows) == 6
    assert {row['id'] for row in warp_rows} == {row['id'] for row in rows if row['source_scene'] < 0}
    assert all(row['mode'] == 'entrance' and len(row['entrances']) == 1 for row in warp_rows)
    capture = {
        'captured_warp_client.inc': '\n'.join(function(client, signature) for signature in (
            'bool ArchipelagoClient::HasSceneTransitionChecks() const',
            'void ArchipelagoClient::ReportTransition(',
            'void ArchipelagoClient::BeginWarpSongTransition(',
            'void ArchipelagoClient::CaptureSceneTransition()',
            'void ArchipelagoClient::CompleteSceneTransition(',
            'void ArchipelagoClient::AdvanceDoorTransition()',
            'extern "C" void Archipelago_BeginWarpSongTransition(',
        )),
        'captured_warp_runtime.inc': '\n'.join(function(runtime, signature) for signature in (
            'void Record(int source)', 'int64_t Complete(int scene)',
        )),
        'captured_warp_lookup.inc': function(native, 's16 Entrance_GetOverride(s16 index)') + function(native, 's16 Entrance_OverrideNextIndex(s16 nextEntranceIndex)'),
        'captured_warp_native.inc': function(native, 'void Entrance_SetWarpSongEntrance(void)'),
        'captured_warp_environment.inc': function(kankyo, 'void Environment_WarpSongLeave(PlayState* play)'),
        'captured_warp_hook.inc': function(hooks, 'void RandomizerOnWarpSongLeaveHandler()'),
        'captured_warp_pause.inc': function(pause, 'static void PauseWarp_Execute()'),
        'captured_warp_skip.inc': function(skip, 'static void RegisterSkipWarpHooks()'),
        'captured_pause_maps.inc': '\n'.join(re.search(
            r'static const int '+name+r'\[\] = \{[\s\S]*?\};', pause).group(0)
            for name in ('ocarinaSongMap', 'entranceIndexMap')),
        'captured_player_song_map.inc': re.search(r'static (?:const )?s16 sWarpSongEntrances\[\] = \{[\s\S]*?\};', player).group(0),
        'captured_warp_truth.inc': '\n'.join(
            '{'+str(row['entrances'][0])+','+str(row['id'])+','+str(row['target_scene'])+'},'
            for row in warp_rows),
    }
    start = player.index('        gSaveContext.respawn[RESPAWN_MODE_RETURN].entranceIndex = sWarpSongEntrances[')
    capture['captured_player_warp_setup.inc'] = player[start:player.index('        this->csAction =', start)]
    start = player.index('        if (Actor_Spawn(&play->actorCtx, play, ACTOR_DEMO_KANKYO,')
    capture['captured_player_warp_actor.inc'] = player[start:player.index('        gSaveContext.seqId =', start)]
    legacy = read('tools/tests/warp_song_1812_legacy_crossing.inc')
    baseline_sha = re.search(r'Original full source SHA256: ([0-9a-f]{64})', legacy).group(1)
    with tempfile.TemporaryDirectory(prefix='soh-warp-song-') as directory:
        work = Path(directory)
        for name, text in capture.items():
            (work / name).write_text(text)
        executable = work / 'warp_song_checks'
        command = [compiler, '-x', 'c++', '-std=c++20', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                   '-Wno-missing-field-initializers', '-Wno-unused-parameter',
                   '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                   '-I', str(work), '-I', str(args.dependencies.resolve()), '-I', str(root),
                   '-I', str(root / 'soh/Network/Archipelago'),
                   str(Path(__file__).with_name('warp_song_checks_tests.cpp.in')), '-o', str(executable)]
        subprocess.run(command, check=True)
        env = dict(os.environ, ASAN_OPTIONS='detect_leaks=0', UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
        result = subprocess.run([str(executable)], text=True, capture_output=True, env=env)
        if result.returncode:
            print(result.stdout)
            print(result.stderr)
            raise SystemExit(result.returncode)
        result = json.loads(result.stdout)
    assert before == {name: digest(root / name) for name in sources}, 'Production source changed during validation'
    assert test_before == {name: digest(root / name) for name in tests}, 'Fixture changed during validation'
    report = dict(status='passed', **result, source_sha256=before, test_sha256=test_before,
                  dependency_sha256={name: digest(args.dependencies / name) for name in dependencies},
                  source_unchanged_during_tests=True,
                  baseline={'release': '1.8.12', 'source_sha256': {
                      'soh/Network/Archipelago/SceneTransitionChecks.h': baseline_sha}},
                  sanitizers=['address', 'undefined'], leak_scanner=False,
                  native_windows_build=False, in_game_playthrough=False,
                  scope='Actual native warp, pause/skip callbacks, AP routing record/completion and scene-journal functions; controlled engine/network IO.',
                  limitations=[
                      'Animation timing, scene allocation, destination collision/arrival guards and network transport are fixture I/O.',
                      'The actual production AP Record and Complete functions run with the real routing class; ArmArrival and scene-history storage are boundary shims.',
                      'A full Windows game build or controller playthrough is not claimed.',
                  ],
                  replay_command='python3 source/tools/tests/test_warp_song_checks.py --dependencies tests/entrance_184_native_dependencies --report tests/warp_song_1813_native.json')
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({key: report[key] for key in ('status', 'cases', 'assertions', 'baseline_reproductions')}))


if __name__ == '__main__':
    main()
