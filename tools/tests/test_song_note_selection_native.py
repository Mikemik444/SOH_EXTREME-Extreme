"""Execute native per-song tracker, slot defaulting, and unchanged note receipts.

Actual production function bodies are compiled with CVar/ImGui/save I/O shims.
This does not compile the complete client or exercise a running game.
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

from test_soul_object_blockers import SOURCE, function
from test_soul_npc_blockers import body


def fragments():
    paths={
        'tracker':SOURCE/'soh/Enhancements/randomizer/randomizer_item_tracker.cpp',
        'client':SOURCE/'soh/Network/Archipelago/ArchipelagoClient.cpp',
        'inf':SOURCE/'soh/Enhancements/randomizer/randomizerEnums/RandomizerInf.h',
        'get':SOURCE/'soh/Enhancements/randomizer/randomizerEnums/RandomizerGet.h',
        'prefix':SOURCE/'soh/cvar_prefixes.h',
    }
    code={key:path.read_text() for key,path in paths.items()}
    functions={
        'TRACKER': '\n\n'.join(function(code['tracker'],name) for name in
                    ['SongNoteTrackingMask','SongNoteTrackingActive','DrawSongNoteProgress']),
        'LEGACY_DEFAULTS':function(code['client'],'ApplyLegacySongNoteMask'),
        'RECEIPTS':'\n\n'.join(function(code['client'],name) for name in
                    ['SetQuestSong','HasNote','GetApSongIndex','ApplyApSongNote','ArchipelagoClient::RefreshSongNotes']),
    }
    array=re.search(r'struct SongNotes \{[^;]+;[^}]+\};\s*static constexpr SongNotes kApSongNotes\[\] = \{.*?\n\s*\};',
                    code['client'],re.S)[0]
    functions['SONG_TABLE']=array
    functions['QUEST_ENUM']='enum { '+', '.join(dict.fromkeys(re.findall(r'QUEST_SONG_\w+',array)))+' };'
    functions['ITEM_CONSTANTS']='\n'.join(re.findall(r'constexpr int64_t AP_(?:FIRST|LAST)_(?:SONG_NOTE|PROGRESSIVE_SONG) = \d+;',code['client']))
    apply=function(code['client'],'ArchipelagoClient::ApplySlotSettings')
    assert apply.index('ApplyLegacySongNoteMask(slotSettings);') < apply.index('settingsSnapshot = slotSettings;')
    marker='for (const auto& [key, value] : settingsSnapshot) {'
    # The actual existing custom-CVar loop applies the new key too. Test it so
    # legacy/default selections cannot leak from a previously loaded file.
    functions['CVAR_WRITER']=marker+body(apply,marker)+'}'
    assert 'CVAR_RANDOMIZER_SETTING("")' in functions['CVAR_WRITER']
    # The ordinary song icon renderer remains independent from this AP mask.
    normal_song=function(code['tracker'],'DrawSong')
    assert 'SongNoteTrackingMask' not in normal_song and 'SongNoteSongMask' not in normal_song
    return paths,functions,normal_song


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path);args=parser.parse_args()
    paths,parts,normal_song=fragments()
    fixture=Path(__file__).with_name('song_note_selection_native_tests.cpp.in')
    template=fixture.read_text()
    for key,value in parts.items():template=template.replace('@'+key+'@',value)
    assert not re.search(r'@[A-Z_]+@',template)
    with tempfile.TemporaryDirectory(prefix='soh-song-selection-') as tmp:
        build=Path(tmp);cpp=build/'song.cpp';cpp.write_text(template)
        cmd=['g++','-std=c++20','-Wall','-Wextra','-Werror','-Wno-unused-parameter',
             '-fsanitize=address,undefined','-fno-omit-frame-pointer','-g','-O1','-I',str(SOURCE),str(cpp),'-o',str(build/'song')]
        compiled=subprocess.run(cmd,text=True,capture_output=True)
        if compiled.returncode:raise RuntimeError(compiled.stdout+compiled.stderr)
        env=dict(os.environ,ASAN_OPTIONS='detect_leaks=0:halt_on_error=1',UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
        result=subprocess.run([str(build/'song')],text=True,capture_output=True,env=env)
        print(result.stdout,end='')
        if result.returncode:raise RuntimeError(result.stderr or f'Native song tests failed: {result.returncode}')
        match=re.search(r'RESULT cases=(\d+) assertions=(\d+)',result.stdout);assert match
    paths['runner']=Path(__file__);paths['fixture']=fixture
    report={'status':'passed','cases':int(match[1]),'assertions':int(match[2]),
            'sanitizers':['AddressSanitizer','UndefinedBehaviorSanitizer'],
            'scope':'Actual native tracker selection/render bodies, slot default helper, custom CVar apply loop, and unchanged progressive/legacy note receipt/completion functions; ImGui, CVar, and save/notification I/O are shimmed. Not a complete native build or gameplay test.',
            'output':result.stdout.splitlines(),
            'sources':{str(path.relative_to(SOURCE)):hashlib.sha256(path.read_bytes()).hexdigest() for path in paths.values()},
            'tested_function_sha256':{key:hashlib.sha256(value.encode()).hexdigest() for key,value in parts.items()},
            'normal_song_icon_renderer_sha256':hashlib.sha256(normal_song.encode()).hexdigest()}
    if args.report:args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
