"""Exercise the production BPS reader and compare conversion to a normal reference ROM.

Use an x64 Visual Studio developer shell. ROMs remain private and unmodified.
An optional harness built with TEST_TORCH also checks extraction asset parity.
"""
from pathlib import Path
import argparse
import binascii
import hashlib
import json
import struct
import subprocess
import zipfile

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--mq', type=Path, required=True)
p.add_argument('--normal', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
p.add_argument('--torch-harness', type=Path)
a=p.parse_args()
r=Path(__file__).resolve().parents[1]
out=a.output.resolve(); out.mkdir(parents=True,exist_ok=True)
exe=out/'normal_oot.exe'
build=subprocess.run(['cl','/nologo','/std:c++20','/EHsc','/MT','/O2','/I',str(r),
    str(Path(__file__).with_suffix('.cpp')),'/Fo'+str(out/'normal_oot.obj'),'/Fe'+str(exe)], capture_output=True,text=True)
(out/'compile.log').write_text(build.stdout+build.stderr,encoding='utf-8')
assert build.returncode==0, build.stdout+build.stderr
cases=[]
def run(name,command,source,other,expected=None,success=True):
    target=out/(name+'.bin')
    proc=subprocess.run([str(exe),command,str(source),str(other),str(target)],capture_output=True,text=True)
    assert proc.returncode==(0 if success else 1),(name,proc.returncode,proc.stdout,proc.stderr)
    if success and expected is not None: assert target.read_bytes()==expected,name
    cases.append({'name':name,'passed':True,'message':proc.stderr.strip()})
    return target
def num(n):
    b=bytearray()
    while True:
        v=n&127; n >>= 7
        if n==0: return b+bytes([v|128])
        b.append(v); n-=1
def patch(source,target,commands,ss=None,ts=None,meta=b''):
    b=b'BPS1'+num(len(source) if ss is None else ss)+num(len(target) if ts is None else ts)+num(len(meta))+meta+commands
    b+=struct.pack('<II',binascii.crc32(source),binascii.crc32(target))
    return b+struct.pack('<I',binascii.crc32(b))
def fixture(name,source,target,commands,success=True,**kw):
    src=out/(name+'.src'); src.write_bytes(source)
    pat=out/(name+'.bps'); pat.write_bytes(patch(source,target,commands,**kw))
    return src,pat,run(name,'apply',src,pat,target,success)
# Four commands, backward source offsets, and overlapping/backward TargetCopy.
source=b'abcdefghij'
fixture('all-commands',source,b'abXYefgabcXYefgabc',
    num(4)+num(5)+b'XY'+num(10)+num(8)+num(10)+num(15)+num(31)+num(4),meta=b'fixture')
fixture('overlap',b'',b'zzzzzzzz',num(1)+b'z'+num(27)+num(0))
fixture('target-backward',b'',b'abababab',num(5)+b'ab'+num(7)+num(0)+num(15)+num(5))
fixture('empty',b'',b'',b'')
fixture('source-read-oob',b'a',b'abc',num(8),False)
fixture('source-copy-oob',b'a',b'b',num(2)+num(4),False)
fixture('source-copy-before',b'a',b'b',num(2)+num(3),False)
fixture('target-unwritten',b'a',b'a',num(3)+num(0),False)
fixture('target-copy-before',b'a',b'a',num(3)+num(3),False)
fixture('literal-truncated',b'',b'ab',num(5)+b'a',False)
fixture('output-overrun',b'aa',b'a',num(4),False)
fixture('output-short',b'ab',b'ab',num(0),False)
fixture('output-crc',b'a',b'b',num(0),False)
fixture('wrong-source-size',b'a',b'a',num(0),False,ss=2)
fixture('too-large-output',b'a',b'a',num(0),False,ts=65*1024*1024)
fixture('command-overflow',b'a',b'a',b'\x7f'*12+b'\x80',False)
fixture('offset-overflow',b'a',b'a',num(2)+b'\x7f'*12+b'\x80',False)
fixture('unterminated-command',b'a',b'a',b'\x00',False)
src,pat,_=fixture('valid',b'a',b'a',num(0))
bad=bytearray(pat.read_bytes());bad[-1]^=1;pat.write_bytes(bad)
run('bad-patch-crc','apply',src,pat,success=False)
pat.write_bytes(b'BPS1')
run('short-header','apply',src,pat,success=False)
pat.write_bytes(patch(b'b',b'a',num(1)+b'a'))
run('wrong-source-crc','apply',src,pat,success=False)

mq=a.mq.read_bytes(); normal=a.normal.read_bytes()
initial={str(a.mq):hashlib.sha256(mq).hexdigest(),str(a.normal):hashlib.sha256(normal).hexdigest()}
assert hashlib.sha1(mq).hexdigest()=='f46239439f59a2a594ef83cf68ef65043b1bffe2'
assert hashlib.sha1(normal).hexdigest()=='ad69c91157f6705e8ab06c79fe08aad47bb57ba7'
assets=r/'assets/yml'
converted=run('pal-mq-normal','convert',a.mq,assets,normal)
run('normal-unchanged','normalize',a.normal,assets,normal)
for width,name in [(2,'v64'),(4,'n64')]:
    swapped=bytearray(len(mq))
    for i in range(width): swapped[i::width]=mq[width-1-i::width]
    path=out/('mq.'+name); path.write_bytes(swapped)
    run(name+'-conversion','convert',path,assets,normal)
    path.unlink()
run('missing-patch','convert',a.mq,out/'missing-assets',success=False)
run('wrong-revision','convert',a.normal,assets,success=False)
bad=bytearray(mq);bad[1234]^=1
path=out/'corrupt.z64';path.write_bytes(bad)
run('corrupt-source','convert',path,assets,success=False)
path.unlink()
path=out/'bad-order.z64';path.write_bytes(b'abcd')
run('bad-byte-order','normalize',path,assets,success=False)
path.write_bytes(b'a')
run('bad-rom-size','normalize',path,assets,success=False)
assert all(hashlib.sha256(Path(path).read_bytes()).hexdigest()==sha for path,sha in initial.items())

# Compile the real extraction entry point with only the UI/Torch services adapted.
# This verifies conversion handoff and temporary-file lifetime independently of
# Torch's filesystem-metadata requirements; it does not simulate extracted assets.
extract_source=(r/'soh/Extractor/Extract.cpp').read_text(encoding='utf-8')
def function(signature):
    start=extract_source.index(signature); body=extract_source.index('{',start); depth=1; end=body+1
    while depth:
        depth += (extract_source[end]=='{')-(extract_source[end]=='}');end+=1
    return extract_source[start:end]
fixture=out/'handoff-install';(fixture/'assets/normal-oot').mkdir(parents=True,exist_ok=True)
(fixture/'assets/normal-oot/pal-mq-to-ntsc10.bps').write_bytes((assets/'normal-oot/pal-mq-to-ntsc10.bps').read_bytes())
cpp=r'''#include "soh/Extractor/NormalOot.h"
#include <atomic>
#include <cstdio>
#include <memory>
#include <stdexcept>
#include <iostream>
#define SPDLOG_ERROR(...) ((void)0)
#define SPDLOG_INFO(...) ((void)0)
constexpr int gBuildVersionMajor=9, gBuildVersionMinor=2, gBuildVersionPatch=3;
namespace ShipUtils { size_t Random(size_t lo,size_t hi) { static size_t x=17; x=x*1664525+1013904223;return lo+x%(hi-lo+1); } }
static std::vector<uint8_t> expected;
static std::filesystem::path torchRom;
static int torchMode=0, torchCalls=0;
static void require(bool v,const char* m) {if(!v) throw std::runtime_error(m);}
namespace SohTorch {
size_t CountAssetFiles(const std::string& path) {require(path.ends_with("/ntsc_1-0"),"wrong extraction recipe");return 1;}
std::string Extract(const std::string& rom,const std::string&,const std::string& dest,const std::string&,std::atomic<size_t>*) {
    ++torchCalls;torchRom=rom;std::vector<uint8_t> contents;std::string error;
    require(SohRom::ReadFile(rom,contents,64*1024*1024,error),"missing Torch input");
    require(contents==expected,"Torch did not receive the normal ROM");
    if(torchMode==1)return "";
    if(torchMode==2)throw std::runtime_error("controlled extractor exception");
    if(torchMode==3)return "oot-mq.o2r";
    std::ofstream(dest+"/oot.o2r") << "test service output";
    return "oot.o2r";
}}
class Extractor {
public:
    std::unique_ptr<unsigned char[]> mRomData;
    std::string mCurrentRomPath,mLastError;size_t mCurRomSize=0;bool mq=false;
    bool IsMasterQuest()const{return mq;}
    const char* GetOutputArchiveName()const{return "oot.o2r";}
    const char* GetTorchVersionDir()const{return "ntsc_1-0";}
    std::string Mkdtemp();
    bool CallTorch(std::string,std::string,std::atomic<size_t>*,std::atomic<size_t>*);
};
''' + function('std::string Extractor::Mkdtemp()')+'\n'+function('bool Extractor::CallTorch(')+r'''
int main(int argc,char**argv) {
    if(argc!=5)return 2;
    try {
        std::vector<uint8_t> mq;std::string error;
        require(SohRom::ReadFile(argv[1],mq,64*1024*1024,error),"MQ read");
        require(SohRom::ReadFile(argv[2],expected,64*1024*1024,error),"normal read");
        Extractor ex;ex.mq=true;ex.mCurrentRomPath=argv[1];ex.mCurRomSize=mq.size();
        ex.mRomData=std::make_unique<unsigned char[]>(mq.size());std::memcpy(ex.mRomData.get(),mq.data(),mq.size());
        std::filesystem::create_directories(argv[4]);std::atomic<size_t> count=0,total=0;
        require(ex.CallTorch(argv[3],argv[4],&count,&total),"MQ handoff");
        require(torchCalls==1 && torchRom!=argv[1],"MQ source was not isolated");
        require(!std::filesystem::exists(torchRom.parent_path()),"temporary ROM was retained");
        require(std::filesystem::exists(std::filesystem::path(argv[4])/"oot.o2r"),"normal output not installed");
        for(torchMode=1;torchMode<=3;++torchMode) {
            bool threw=false;
            try {require(!ex.CallTorch(argv[3],argv[4],&count,&total),"unexpected successful failure");}
            catch(const std::runtime_error&){if(torchMode!=2)throw;threw=true;}
            require(threw==(torchMode==2),"exception contract");
            require(!std::filesystem::exists(torchRom.parent_path()),"failure leaked temporary ROM");
            if(torchMode!=2)require(!ex.mLastError.empty(),"failure lacked error");
        }
        const int calls=torchCalls;
        require(!ex.CallTorch(std::string(argv[3])+"/missing",argv[4],&count,&total),"missing patch accepted");
        require(torchCalls==calls,"Torch called after failed conversion");
        torchMode=0;ex.mq=false;ex.mCurrentRomPath=argv[2];
        require(ex.CallTorch(argv[3],argv[4],&count,&total),"normal handoff");
        require(torchRom==argv[2] && std::filesystem::exists(torchRom),"normal input modified");
        std::cout<<"PASS production CallTorch: normal/MQ handoff, missing patch, failure/exception cleanup, wrong archive rejection\n";
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
'''
driver=out/'extraction_handoff.cpp';driver.write_text(cpp,encoding='utf-8')
handoff=out/'extraction_handoff.exe'
build=subprocess.run(['cl','/nologo','/std:c++20','/EHsc','/MT','/O2','/I',str(r),str(driver),
                     '/Fo'+str(out/'extraction_handoff.obj'),'/Fe'+str(handoff)],capture_output=True,text=True)
assert build.returncode==0,build.stdout+build.stderr
proc=subprocess.run([str(handoff),str(a.mq.resolve()),str(a.normal.resolve()),str(fixture),str(out/'handoff-output')],capture_output=True,text=True)
(out/'handoff.log').write_text(build.stdout+build.stderr+proc.stdout+proc.stderr,encoding='utf-8')
assert proc.returncode==0,proc.stdout+proc.stderr

report={'passed':True,'cases':cases,'source_sha256':initial,'converted_sha1':hashlib.sha1(converted.read_bytes()).hexdigest(),
    'originals_unchanged':True,'patch_sha256':hashlib.sha256((assets/'normal-oot/pal-mq-to-ntsc10.bps').read_bytes()).hexdigest(),
    'production_handoff':{'passed':True,'output':proc.stdout,'scope':'Actual CallTorch and Mkdtemp with controlled Torch service; no asset extraction'}}
if a.torch_harness:
    for name,rom in [('normal',a.normal),('converted',converted)]:
        dest=out/('torch-'+name)
        proc=subprocess.run([str(a.torch_harness.resolve()),'extract',str(rom.resolve()),str(assets),str(dest)],capture_output=True,text=True)
        (out/('torch-'+name+'.log')).write_text(proc.stdout+proc.stderr,encoding='utf-8')
        assert proc.returncode==0,(name,proc.stdout[-2000:],proc.stderr[-2000:])
    with zipfile.ZipFile(out/'torch-normal/oot.o2r') as x,zipfile.ZipFile(out/'torch-converted/oot.o2r') as y:
        assert x.testzip() is None and y.testzip() is None
        assert set(x.namelist())==set(y.namelist())
        assert all(x.read(n)==y.read(n) for n in x.namelist())
        report['torch']={'passed':True,'identical_entries':len(x.namelist()),'archive':'oot.o2r'}
(out/'normal-oot.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(f'PASS {len(cases)} native cases; real conversion byte-for-byte matches the normal ROM. '+str(report.get('torch','')))
