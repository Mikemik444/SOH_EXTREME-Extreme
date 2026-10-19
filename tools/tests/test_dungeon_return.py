"""Compile production dungeon/previous-scene returns, save menu and respawn flow.

Engine scene/room allocation, file storage, audio and message drawing are
isolated. Real native entrance tables, resolvers, reload identity predicates,
menu helpers and game-over respawn functions are compiled with sanitizers.
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
from test_entrance_slot_bridge import between, digest, enum_containing


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dependencies', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    compiler = shutil.which('g++') or shutil.which('c++')
    if not compiler:
        raise SystemExit('A C++20 compiler is required.')
    dependencies = ('json.hpp','entrance_table.h','scene_table.h','z64.h','z64save.h')
    for name in dependencies:
        if not (args.dependencies/name).is_file():
            raise SystemExit(f'Missing verified native dependency: {name}')
    names = (
        'soh/Network/Archipelago/EntranceRuntime.inc','soh/Network/Archipelago/EntranceRouting.h',
        'soh/Network/Archipelago/ArchipelagoC.h','soh/Network/Archipelago/ArchipelagoClient.cpp',
        'soh/Network/Archipelago/EntranceRandomizerData.inc','soh/Network/Archipelago/EntranceDestinationPolicy.h',
        'soh/Network/Archipelago/EntranceDestinationData.inc','soh/Network/Archipelago/SceneTransitionChecks.h',
        'soh/Network/Archipelago/SceneTransitionData.inc',
        'soh/Enhancements/randomizer/randomizer_entrance.c','soh/Enhancements/randomizer/randomizer_entrance.h',
        'soh/Enhancements/randomizer/randomizer_grotto.c','soh/Enhancements/randomizer/randomizer_grotto.h',
        'soh/Enhancements/randomizer/randomizerTypes.h','soh/Enhancements/randomizer/hook_handlers.cpp',
        'soh/Enhancements/randomizer/randomizerEnums/RandomizerSettingKey.h',
        'soh/Enhancements/randomizer/randomizerEnums/RandomizerOptions.h',
        'soh/Enhancements/QoL/BetterSaveMenu.cpp','src/code/z_play.c','src/code/z_room.c','src/code/z_sram.c',
        'src/overlays/misc/ovl_kaleido_scope/z_kaleido_scope_PAL.c',
        'archipelago/soh_extreme/EntranceCatalog.json')
    tests = ('tools/tests/test_dungeon_return.py','tools/tests/dungeon_return_tests.cpp',
             'tools/tests/test_entrance_slot_bridge.py','tools/tests/entrance_slot_bridge_tests.cpp')
    before = {name:digest(root/name) for name in names}
    tests_before = {name:digest(root/name) for name in tests}
    read = lambda name: (root/name).read_text(encoding='utf-8-sig')
    client = read('soh/Network/Archipelago/ArchipelagoClient.cpp')
    native = read('soh/Enhancements/randomizer/randomizer_entrance.c')
    header = read('soh/Enhancements/randomizer/randomizer_entrance.h')
    grotto = read('soh/Enhancements/randomizer/randomizer_grotto.c')
    grotto_header = read('soh/Enhancements/randomizer/randomizer_grotto.h')
    types = read('soh/Enhancements/randomizer/randomizerTypes.h')
    hooks = read('soh/Enhancements/randomizer/hook_handlers.cpp')
    menu = read('soh/Enhancements/QoL/BetterSaveMenu.cpp')
    play = read('src/code/z_play.c')
    room = read('src/code/z_room.c')
    sram = read('src/code/z_sram.c')
    kaleido = read('src/overlays/misc/ovl_kaleido_scope/z_kaleido_scope_PAL.c')
    engine = (args.dependencies/'z64.h').read_text()
    save = (args.dependencies/'z64save.h').read_text()
    native_constants = '\n'.join(re.findall(r'^#define (?:ENTRANCE_TABLE_SIZE|ENTRANCE_OVERRIDES_MAX_COUNT|SHUFFLEABLE_BOSS_COUNT)\s+[^\r\n]+',header,re.M))
    native_constants += '\n'+between(header,'#define ENTRANCE_INFO_FIELD','typedef struct')
    native_constants += '\n'+'\n'.join(re.findall(r'^#define ENTRANCE_GROTTO_(?:LOAD|EXIT)_START\s+\S+',types,re.M))
    native_constants += '\n'+'\n'.join(re.findall(r'^#define (?:NOT_GROTTO|GROTTO_LOAD|GROTTO_RETURN)\s+\S+',grotto_header,re.M))
    native_constants += '\n#define NUM_GROTTOS '+str(between(grotto,'static const GrottoLoadInfo','static const GrottoReturnInfo').count('.entranceIndex ='))
    engine_constants = '\n'.join(enum_containing(engine,m) for m in ('TRANS_TYPE_WIPE,','TCA_NORMAL,','TCC_BLACK,','TCS_FAST'))
    engine_constants += '\n'+re.search(r'^#define TRANS_TYPE_CIRCLE[^\r\n]+',engine,re.M).group(0)
    engine_constants += '\n'+'\n'.join(re.findall(r'^#define ENTRANCE_INFO_(?:CONTINUE_BGM_FLAG|DISPLAY_TITLE_CARD_FLAG|END_TRANS_TYPE_(?:MASK|SHIFT)|START_TRANS_TYPE_(?:MASK|SHIFT))[^\r\n]+',engine,re.M))
    engine_constants += '\n'+enum_containing(save,'RESPAWN_MODE_DOWN,')+'\n'+enum_containing(save,'LINK_AGE_ADULT,')
    harness = read('tools/tests/entrance_slot_bridge_tests.cpp').split('#include "captured_native_savewarp.inc"',1)[0]
    harness = harness.replace('    int numRooms = 64;', '''    int numRooms = 64;
    struct { int promptChoice = 0, unk_1EC = 0; } pauseCtx;
    struct { struct { int tempSwch = 0, tempCollect = 0; } flags; } actorCtx;''')
    harness = harness.replace('    int fileNum = 0;', '    int fileNum = 0;\n    struct { int resetToSpawn = 0; } ship;')
    init = between(play,'void Play_Init(GameState*','void Play_Destroy(') if 'void Play_Destroy(' in play[play.index('void Play_Init(GameState*'):] else play[play.index('void Play_Init(GameState*'):play.index('void Play_Main(')]
    assert init.index('Actor_InitContext(') < init.index('Archipelago_EntranceRecordRoomEntry();')
    assert 'Archipelago_EntranceRecordRoomEntry();' in between(room,'void Room_FinishRoomChange(','\n}')
    assert 'Play_TriggerRespawn(play);\n                        gSaveContext.respawnFlag = -2;' in kaleido
    metadata = between(client,'void ArchipelagoClient::LoadSaveMetadata(','void ArchipelagoClient::BeginItemReplay(')
    captures = {
        'captured_engine_constants.h':engine_constants,
        'captured_native_constants.h':native_constants,
        'captured_native_structs.h':between(header,'typedef struct {','#ifdef __cplusplus')+'\n'+between(grotto_header,'typedef struct {','#ifdef __cplusplus'),
        'captured_native_init.inc':between(native,'// Overwrite the dynamic exit','s16 Entrance_PeekNextIndexOverride('),
        'captured_grotto_data.inc':between(grotto,'// Information necessary for entering each grotto','// SOH-EXTREME Shovel semantics.'),
        'captured_grotto_functions.inc':between(grotto,'void Grotto_InitExitAndLoadLists(void)','// Override the entrance index when entering into a grotto actor'),
        'captured_native_lookup.inc':between(native,'s16 Entrance_PeekNextIndexOverride(','u32 Entrance_SceneAndSpawnAre('),
        'captured_native_savewarp.inc':between(native,'void Entrance_SetSavewarpEntrance(void)','void Entrance_SetWarpSongEntrance(void)'),
        'captured_native_gameover.inc':between(native,'void Entrance_SetGameOverEntrance(void)','// Properly savewarp the player'),
        'captured_grotto_force_return.inc':between(grotto,'void Grotto_ForceGrottoReturn(void)','// Used for the DMT special voids'),
        'captured_native_respawn.inc':between(play,'void Play_SetRespawnData(','s32 Play_CamIsNotFixed('),
        'captured_return_engine.inc':harness,
        'captured_metadata_identity.inc':between(metadata,'    auto sameIdentity =','    // Return to Spawn'),
        'captured_metadata_reset.inc':between(metadata,'    const bool preserveRequestedDungeonReturn =','    {\n        std::scoped_lock lock(queueMutex);'),
        'captured_menu_messages.inc':between(menu,'static CustomMessage saveMsg =','static CustomMessage spawnAsChildMsg ='),
        'captured_menu_spawn.inc':between(menu,'static int16_t GetAgeSpawnEntrance(','bool IsSceneDungeon('),
        'captured_menu_is_dungeon.inc':between(menu,'bool IsSceneDungeon(','static void StartContinuePrompt('),
        'captured_menu_prompt.inc':between(menu,'static void StartContinuePrompt(','static void BeginSaveMenuReload('),
        'captured_menu_begin_reload.inc':between(menu,'static void BeginSaveMenuReload(','static void ChooseSaveMenuSpawn('),
        'captured_sram_dungeon_entries.inc':between(sram,'static s16 sDungeonEntrances[] =','/**'),
        'captured_sram_entrance_selection.inc':between(sram,'    switch (gSaveContext.savedSceneNum)',
                                                     '    osSyncPrintf("scene_no ='),
        'captured_load_spawn_gate.inc':between(hooks,'        // Handle randomized spawn positions after the save context','        onFlagSetHook ='),
        'captured_native_exit.inc':between(hooks,'void RandomizerOnExitGameHandler(','void RandomizerOnKaleidoscopeUpdateHandler('),
        'captured_client_scene.inc':between(client,'void ArchipelagoClient::CaptureSceneTransition()','void ArchipelagoClient::BeginDoorTransition('),
        'captured_room_entry_call.inc':'    Archipelago_EntranceRecordRoomEntry();',
        'captured_category_truth.inc':'\n'.join('{'+str(row['id'])+','+str(row['category'] in {'dungeons','bosses','dungeon_doors'}).lower()+'},' for row in json.loads(read('archipelago/soh_extreme/EntranceCatalog.json'))),
    }
    with tempfile.TemporaryDirectory(prefix='soh-dungeon-return-') as directory:
        work=Path(directory)
        for name in ('entrance.h','randomizer_entrance.h','randomizer_grotto.h'):
            stub=work/'soh/Enhancements/randomizer'/name;stub.parent.mkdir(parents=True,exist_ok=True);stub.write_text('// Engine IO supplied by the native fixture.\n')
        for name, contents in captures.items(): (work/name).write_text(contents+'\n')
        executable=work/'dungeon_return'
        command=[compiler,'-std=c++20','-O1','-g','-Wall','-Wextra','-Werror','-Wno-missing-field-initializers',
                 '-Wno-unused-variable','-Wno-narrowing','-Wno-unused-parameter','-fsanitize=address,undefined',
                 '-fno-omit-frame-pointer','-I',str(work),'-I',str(args.dependencies.resolve()),'-I',str(root),
                 str(Path(__file__).with_name('dungeon_return_tests.cpp')),'-o',str(executable)]
        subprocess.run(command,check=True)
        env=dict(os.environ,ASAN_OPTIONS='detect_leaks=0',UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
        result=subprocess.run([str(executable)],capture_output=True,text=True,env=env)
        if result.returncode:
            print(result.stdout);print(result.stderr);raise SystemExit(result.returncode)
        cases=json.loads(result.stdout)
    after={name:digest(root/name) for name in names}
    if before!=after or tests_before!={name:digest(root/name) for name in tests}:
        raise SystemExit('Source changed during validation; rerun after edits settle.')
    report={'status':'passed','cases':cases,'case_count':sum(cases.values()),'source_sha256':after,'test_sha256':tests_before,
            'dependency_sha256':{name:digest(args.dependencies/name) for name in dependencies},
            'source_unchanged_during_tests':True,'sanitizers':['address','undefined'],'leak_scanner':False,
            'engine_io_isolated':True,'native_windows_build':False,'in_game_playthrough':False,
            'coverage':['full native Entrance_Init and table construction','full native savewarp and game-over entrance functions',
                        'full native respawn setup and last-entrance functions','native grotto resolver and game-over return flags',
                        'actual BetterSaveMenu message text, continue prompt and reload begin helper','actual AP metadata preservation predicates',
                        'actual native Sram_OpenSave dungeon table and entrance selection',
                        'previous distinct physical scene and source dungeon ownership','same-scene room reloads and native room completion',
                        'explicit age spawn, absent history, reload/map/file/age invalidation','all 719 endpoint pool classifications'],
            'limitations':['Room geometry, native actor scene loading, audio, persistent file IO and UI rendering are isolated.',
                           'Saved previous-scene positions enter through the native integer ActorEntry coordinate path.',
                           'No Windows game build or controller playthrough was possible with the uploaded partial checkout.']}
    args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'status':'passed','report':str(args.report),'case_count':report['case_count'],'cases':cases},indent=2))

if __name__=='__main__': main()
