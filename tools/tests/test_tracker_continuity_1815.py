"""Compile the complete production tracker header, not a mock of its cache."""
from pathlib import Path
import subprocess,os,json,hashlib,re,argparse
R=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser();p.add_argument('--report',type=Path);a=p.parse_args()
import tempfile
with tempfile.TemporaryDirectory() as tmp:
 exe=Path(tmp)/'tracker'
 cmd=['g++','-std=c++20','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-omit-frame-pointer','-I',str(R),str(Path(__file__).with_name('tracker_continuity_1815.cpp')),'-o',str(exe)]
 subprocess.run(cmd,check=True)
 result=subprocess.run([str(exe)],check=True,text=True,capture_output=True,env=dict(os.environ,ASAN_OPTIONS='detect_leaks=0:halt_on_error=1'))
 print(result.stdout,end='')
client=(R/'soh/Network/Archipelago/ArchipelagoClient.cpp').read_text()
start=client.index('const SohExtreme::TrackerSnapshot* ArchipelagoClient::GetFinderSnapshot(')
body=client[start:client.index('\nvoid ArchipelagoClient::Enable()',start)]
assert body.index('finderMirror.Current(')<body.index('ammoRefillMask = 0')<body.index('finderMirror.Display(')
assert 'return display;' in body and 'finderRequestPacer.Due(' in body
assert 'finderRequestPacer.Sent(' in body
assert 'finderRequestPacer.Reset();' in client
report={'status':'passed','assertions':int(re.search(r'(\d+) assertions',result.stdout)[1]),'scope':'Complete production TrackerMirror.h compiled under ASan/UBSan; client call-site wiring checked structurally. No full native game build or live UI timing claimed.','output':result.stdout,'sources':{str(f.relative_to(R)):hashlib.sha256(f.read_bytes()).hexdigest() for f in [R/'soh/Network/Archipelago/TrackerMirror.h',R/'soh/Network/Archipelago/ArchipelagoClient.cpp',R/'soh/Network/Archipelago/ArchipelagoClient.h',Path(__file__),Path(__file__).with_name('tracker_continuity_1815.cpp')]}}
if a.report:a.report.write_text(json.dumps(report,indent=2)+'\n')
