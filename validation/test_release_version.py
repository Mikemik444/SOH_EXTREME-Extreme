"""Verify release/protocol agreement and preserve existing save/archive compatibility.

Run in a Visual Studio x64 developer shell after configuring the game with CMake.
"""
from pathlib import Path
import argparse, ast, json, re, subprocess

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--output',type=Path,required=True)
p.add_argument('--cmake',default='cmake')
a=p.parse_args();r=Path(__file__).resolve().parents[1]
out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
release=re.search(r'#define SOH_EXTREME_VERSION "([0-9.]+)"',(r/'soh/SohExtremeVersion.h').read_text())[1]
for name in ['archipelago/archipelago.json','archipelago/soh_extreme/archipelago.json']:
    assert json.loads((r/name).read_text())['world_version']==release

# Exercise the actual Python serializer. Its region-label dependency is unrelated
# to serialization and is not needed for these supplied rows.
tree=ast.parse((r/'archipelago/soh_extreme/TrackerMirror.py').read_text())
tree.body=[node for node in tree.body if not (isinstance(node,ast.ImportFrom) and node.module=='NpcSpeech')]
ns={};exec(compile(tree,'TrackerMirror.py','exec'),ns)
assert ns['VERSION']==release
payload=ns['encode_snapshot'](nonce='1'*32,request=1,revision=1,slot=1,
    received=3,active={100,101,102},checked={102},rows=[
        {'id':100,'state':1,'name':'Reachable check','region':'Kokiri Forest'},
        {'id':101,'state':2,'name':'Glitched check','region':'Lake Hylia'}],producer='release-test')
(out/'snapshot.b64').write_text(payload)

stubs=out/'stubs/libultraship';stubs.mkdir(parents=True,exist_ok=True)
(stubs/'libultra.h').write_text('typedef unsigned short u16;\n')
cpp=r'''#include <cassert>
#include <fstream>
#include <iostream>
#include <iterator>
#include "soh/Network/Archipelago/TrackerMirror.h"
#include "src/boot/build.c"
int main(int argc,char**argv) {
    assert(argc==2);
    assert(std::string(gBuildVersion)=="SOH-EXTREME " SOH_EXTREME_VERSION);
    // Rebranding must not invalidate the existing 9.2.3 assets or save format.
    assert(gBuildVersionMajor==9 && gBuildVersionMinor==2 && gBuildVersionPatch==3);
    assert(gGitBranch[0] && gGitCommitHash[0]);
    std::ifstream input(argv[1]);std::string payload((std::istreambuf_iterator<char>(input)),{});
    auto snapshot=SohExtreme::DecodeTrackerSnapshot(payload);
    assert(snapshot.version==SOH_EXTREME_VERSION);
    SohExtreme::TrackerMirrorState mirror;mirror.Reset(std::string(32,'1'));mirror.NextRequest();
    std::string error;assert(mirror.Accept(snapshot,1,10,error));
    auto current=mirror.Current(1,3,{100,101,102},{102},11,error);
    assert(current && current->rows.size()==2 && current->rows[0].state==1 && current->rows[1].state==2);
    snapshot.version="0.11.63";snapshot.revision++;
    assert(!mirror.Accept(snapshot,1,12,error));
    assert(error=="Tracker version mismatch; use " SOH_EXTREME_VERSION " on both sides.");
    std::cout<<gBuildVersion<<": Python snapshot accepted; old version rejected; save/asset format preserved\n";
}
'''
source=out/'release.cpp';source.write_text(cpp)
exe=out/'release.exe'
build=subprocess.run(['cl','/nologo','/std:c++20','/EHsc','/MT','/O2','/I'+str(r),'/I'+str(out/'stubs'),
    str(source),'/Fo'+str(out/'release.obj'),'/Fe'+str(exe)],capture_output=True,text=True)
(out/'compile.log').write_text(build.stdout+build.stderr)
assert build.returncode==0,build.stdout+build.stderr
run=subprocess.run([str(exe),str(out/'snapshot.b64')],capture_output=True,text=True)
assert run.returncode==0,run.stdout+run.stderr

# Source archives inside another checkout must not display that parent's commit.
archive=out/'source-archive';archive.mkdir(exist_ok=True)
script=out/'metadata.cmake'
script.write_text(f'''set(CMAKE_CURRENT_SOURCE_DIR "{archive.as_posix()}")
include("{(r/'Cmake/SohExtremeBuildInfo.cmake').as_posix()}")
if(NOT CMAKE_PROJECT_GIT_BRANCH STREQUAL "Source archive" OR NOT CMAKE_PROJECT_GIT_COMMIT_HASH STREQUAL "Not recorded")
    message(FATAL_ERROR "Source archive inherited unrelated Git metadata")
endif()
''')
meta=subprocess.run([a.cmake,'-P',str(script)],capture_output=True,text=True)
assert meta.returncode==0,meta.stdout+meta.stderr
(out/'release-version.json').write_text(json.dumps({'passed':True,'version':release,
    'native_protocol':run.stdout.strip(),'archive_format':'9.2.3',
    'source_archive_fallback_verified':True},indent=2))
print(run.stdout.strip());print('PASS manifest agreement and source-archive metadata fallback')
