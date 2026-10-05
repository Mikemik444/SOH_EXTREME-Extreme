"""Compile the actual segmented address reader/writers and frame rejection wrapper."""
from pathlib import Path
import argparse, json, subprocess
from run_native_tests import function
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--source',type=Path,required=True);p.add_argument('--baseline',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args();o=a.output.resolve();o.mkdir(parents=True,exist_ok=True)
s=a.source.read_text(encoding='utf-8');old=a.baseline.read_text(encoding='utf-8')
r=Path(__file__).resolve().parents[1]
common=r'''
#define NOMINMAX
#include <windows.h>
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <memory>
#include <stack>
#include <vector>
uint64_t checks=0;
void ck(bool ok){++checks;if(!ok){std::printf("failed %llu\n",checks);std::abort();}}
#define SPDLOG_ERROR(...) ((void)0)
constexpr size_t MAX_SEGMENT_POINTERS=16,MAX_VERTICES=64;
enum {G_MW_NUMLIGHT=2,G_MW_FOG=8,G_MW_SEGMENT=6,G_MW_SEGMENT_INTERP=14};
struct RSP{int current_num_lights=0;bool lights_changed=false;int16_t fog_mul=0,fog_offset=0;};
struct F3DVtx {};
struct F3DGfx{struct{uintptr_t w0,w1;}words;};
class Interpreter{public:
 uintptr_t mSegmentPointers[16]{}; // first member, so protected-page setup is exact
 RSP*mRsp=nullptr;int mInterpolationIndex=2,loads=0;
 void*SegAddr(uintptr_t);
 void GfxSpMovewordF3dex2(uint8_t,uint16_t,uintptr_t);
 void GfxSpMovewordF3d(uint8_t,uint16_t,uintptr_t);
 void GfxSpVertex(size_t,size_t,const F3DVtx*){++loads;}
};
std::weak_ptr<Interpreter>mInstance;
struct GfxExecStack{std::stack<F3DGfx*>cmd_stack;std::vector<const F3DGfx*>gfx_path;std::vector<int>disp_stack;
 F3DGfx*&currCmd(){return cmd_stack.top();}
 void stop(){while(!cmd_stack.empty())cmd_stack.pop();gfx_path.clear();}
}g_exec_stack;
unsigned ucode_handler_index=4;
#define C0(pos,width) ((cmd->words.w0>>(pos))&((1U<<(width))-1))
'''
def run(name,text):
    src=o/(name+'.cpp');exe=o/(name+'.exe');src.write_text(text)
    c=subprocess.run(['cl','/nologo','/std:c++20','/EHsc','/MD','/O2',str(src),'/Fo'+str(o/(name+'.obj')),'/Fe'+str(exe)],capture_output=True,text=True)
    t=subprocess.run([str(exe)],capture_output=True,text=True) if c.returncode==0 else None
    return dict(compile_exit=c.returncode,compile_output=c.stdout+c.stderr,exit_code=t.returncode if t else None,output=t.stdout+t.stderr if t else '')
before=run('baseline',common+function(old,'void* Interpreter::SegAddr(')+r'''
int main(){SetErrorMode(SEM_NOGPFAULTERRORBOX);SYSTEM_INFO si;GetSystemInfo(&si);
 auto*memory=static_cast<uint8_t*>(VirtualAlloc(nullptr,si.dwPageSize*2,MEM_RESERVE,PAGE_NOACCESS));ck(memory!=nullptr);
 ck(VirtualAlloc(memory,si.dwPageSize,MEM_COMMIT,PAGE_READWRITE)!=nullptr);
 auto*gfx=reinterpret_cast<Interpreter*>(memory+si.dwPageSize-16*sizeof(uintptr_t));
 // Slot 16, the first invalid index, touches the protected next page.
 volatile auto result=gfx->SegAddr(0x10000001);std::printf("%p\n",result);
}''')
assert before['compile_exit']==0 and before['exit_code']&0xffffffff==0xc0000005,before
code=common+(r/'Cmake/SohExtremeVertexGuard.cpp.inc').read_text()
for sig in ('void* Interpreter::SegAddr(','void Interpreter::GfxSpMovewordF3dex2(',
            'void Interpreter::GfxSpMovewordF3d(','bool gfx_vtx_handler_f3dex2('):
    code+=function(s,sig)+'\n'
code+='static void gfx_step(){gfx_vtx_handler_f3dex2(&g_exec_stack.currCmd());}\n'
code+=(r/'Cmake/SohExtremeGfxStep.cpp.inc').read_text()
code+=r'''
template<class F>bool rejected(F f){try{f();return false;}catch(const SohExtremeInvalidGfx&){return true;}}
int main(){auto owner=std::make_shared<Interpreter>();mInstance=owner;auto&g=*owner;RSP rsp;g.mRsp=&rsp;
 for(unsigned seg=0;seg<256;++seg)for(uintptr_t offset:{uintptr_t(0),uintptr_t(2),uintptr_t(0xfffffe)}){
  for(auto&base:g.mSegmentPointers)base=0x100000000;
  auto address=(uintptr_t(seg)<<24)|offset|1;void*resolved=nullptr;
  ck(rejected([&]{resolved=g.SegAddr(address);})==(seg>=16));
  if(seg<16)ck(reinterpret_cast<uintptr_t>(resolved)==0x100000000+offset);
 }
 for(auto address:{uintptr_t(0xFECD00000241FFD7),uintptr_t(0x0100000001000001),UINTPTR_MAX})
  ck(rejected([&]{g.SegAddr(address);}));
 for(unsigned seg=0;seg<16;++seg){
  g.mSegmentPointers[seg]=0;ck(rejected([&]{g.SegAddr((uintptr_t(seg)<<24)|1);}));
  g.mSegmentPointers[seg]=UINTPTR_MAX-1;ck(rejected([&]{g.SegAddr((uintptr_t(seg)<<24)|3);}));
  ck(reinterpret_cast<uintptr_t>(g.SegAddr((uintptr_t(seg)<<24)|1))==UINTPTR_MAX-1);
 }
 // Aligned native addresses and null retain their existing representation.
 for(auto address:{uintptr_t(0),uintptr_t(0x10000),reinterpret_cast<uintptr_t>(&rsp)})
  ck(reinterpret_cast<uintptr_t>(g.SegAddr(address))==address);
 for(int variant=0;variant<2;++variant)for(unsigned offset=0;offset<=UINT16_MAX;++offset){
  for(auto&base:g.mSegmentPointers)base=0x100000000;
  uintptr_t snapshot[16];std::memcpy(snapshot,g.mSegmentPointers,sizeof(snapshot));
  bool bad=rejected([&]{if(variant)g.GfxSpMovewordF3d(G_MW_SEGMENT,offset,0x1000);
                       else g.GfxSpMovewordF3dex2(G_MW_SEGMENT,offset,0x1000);});
  bool wantBad=offset%4||offset>=64;ck(bad==wantBad);
  if(wantBad)ck(std::memcmp(snapshot,g.mSegmentPointers,sizeof(snapshot))==0);
  else{snapshot[offset/4]=0x1000;ck(std::memcmp(snapshot,g.mSegmentPointers,sizeof(snapshot))==0);}
 }
 // Interpolation slots already use modulo 16, so valid writes stay available.
 for(int variant=0;variant<2;++variant)for(int seg=0;seg<16;++seg){
  g.mSegmentPointers[seg]=0;
  if(variant)g.GfxSpMovewordF3d(G_MW_SEGMENT_INTERP,32+seg,0x2000);
  else g.GfxSpMovewordF3dex2(G_MW_SEGMENT_INTERP,32+seg,0x2000);
  ck(g.mSegmentPointers[seg]==0x2000);
 }
 // The actual vertex handler resolves SegAddr before invoking the old vertex
 // buffer checks. Verify rejection unwinds to the existing .59 frame wrapper.
 F3DGfx bad{{0x01001002,0xFECD00000241FFD7}},good{{0x01001002,0x10000}};
 g_exec_stack.cmd_stack.push(&bad);g_exec_stack.gfx_path.push_back(&good);g_exec_stack.disp_stack.push_back(1);
 ck(!SohExtremeGfxStep());ck(g.loads==0&&g_exec_stack.cmd_stack.empty()&&g_exec_stack.gfx_path.empty()&&g_exec_stack.disp_stack.empty());
 g_exec_stack.cmd_stack.push(&good);ck(SohExtremeGfxStep());ck(g.loads==1);g_exec_stack.stop();
 std::printf("%llu assertions passed; invalid segment read/write blocked before access\n",checks);
}'''
after=run('fixed',code)
report=dict(passed=after['compile_exit']==0 and after['exit_code']==0,baseline=before,fixed=after,scope=__doc__,
    limitations=['Guard coverage is not proof of the original bad-command producer.','No live game playtest.'])
(o/'native.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));raise SystemExit(not report['passed'])
