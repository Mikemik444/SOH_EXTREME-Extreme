"""Compile actual MODIFYVTX, dispatch, frame execution and guards with engine adapters.

Vertex-load/triangle shader bodies are outside this harness; their real preambles
are exercised before a sentinel. No live assets or GPU rendering are simulated.
"""
from pathlib import Path
import argparse
import json
import subprocess
from run_native_tests import function

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--source', type=Path, required=True)
p.add_argument('--baseline', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
o = a.output.resolve()
o.mkdir(parents=True, exist_ok=True)
s = a.source.read_text(encoding='utf-8')
old = a.baseline.read_text(encoding='utf-8')
r = Path(__file__).resolve().parents[1]
guard = (r / 'Cmake/SohExtremeVertexGuard.cpp.inc').read_text()
step = (r / 'Cmake/SohExtremeGfxStep.cpp.inc').read_text()
assert guard in s and step in s
common = r'''
#define NOMINMAX
#include <windows.h>
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <cstring>
#include <cstdio>
#include <memory>
#include <stack>
#include <vector>
#include <string>
#include <unordered_map>
#include <limits>
static uint64_t checks=0,logs=0;
void ck(bool ok){++checks;if(!ok){std::printf("FAILED check %llu\n",checks);std::abort();}}
template<class... T>void log_error(T...){++logs;}
#define SPDLOG_ERROR(...) log_error(__VA_ARGS__)
#define SPDLOG_CRITICAL(...) log_error(__VA_ARGS__)
#define SUPPORT_CHECK(x) ((void)0) // Release behavior of the baseline renderer
constexpr int MAX_VERTICES=64,G_MWO_POINT_ST=0x14,G_EX_ALWAYS_EXECUTE_BRANCH=1;
struct F3DVtx {};
struct RGBA {uint8_t r,g,b,a;};
struct LoadedVertex {float x,y,z,w,u,v;RGBA color;uint8_t clip_rej;};
struct RSP {LoadedVertex loaded_vertices[MAX_VERTICES+4];int extra_geometry_mode=0;};
struct F3DGfx {struct {uintptr_t w0,w1;}words;};
using Gfx=F3DGfx;
struct Mtx{};struct MtxF{};
struct GfxExecStack {
 std::stack<F3DGfx*>cmd_stack;std::vector<const F3DGfx*>gfx_path;std::vector<int>disp_stack;
 void start(F3DGfx*);void stop();F3DGfx*&currCmd();
 void branch(F3DGfx*){++branches;}
 int branches=0;
}g_exec_stack;
enum UcodeHandlers {ucode_f3d,ucode_f3db,ucode_f3dex,ucode_f3dexb,ucode_f3dex2};
static UcodeHandlers ucode_handler_index=ucode_f3dex2;
void gfx_set_ucode_handler(UcodeHandlers v){ucode_handler_index=v;}
constexpr int F3DEX2_G_LOAD_UCODE=0xdd,OTR_G_VTX_OTR_FILEPATH=0x20,OTR_G_SETTIMG_OTR_FILEPATH=0x21,
 OTR_G_DL_OTR_FILEPATH=0x22,OTR_G_PUSHCD=0x23,OTR_G_MTX_OTR_FILEPATH=0x24;
using Handlers=std::unordered_map<int8_t,std::pair<const char*,bool(*)(F3DGfx**)>>;
Handlers otrHandlers,rdpHandlers,ucodeHandlers;
std::vector<Handlers*>ucode_handlers(5,&ucodeHandlers);
struct RDP{bool viewport_or_scissor_changed;};
struct Api {
 int target=0,starts=0,resolves=0;
 template<class... T>void UpdateFramebufferParameters(T...){}
 void StartFrame(){++starts;}
 void StartDrawToFramebuffer(int v,float){target=v;}
 void ClearFramebuffer(bool,bool){}
 void ResolveMSAAColorBuffer(int,int){++resolves;}
 uintptr_t GetFramebufferTextureId(int){return 123;}
};
struct Debug {bool IsDebugging(){return false;}template<class T>bool HasBreakPoint(T&){return false;}};
struct Dimensions{int width=640,height=480;};
class Interpreter {public:
 RSP*mRsp=nullptr;RDP*mRdp=nullptr;Api*mRapi=nullptr;std::shared_ptr<Debug>mGfxDebugger=std::make_shared<Debug>();
 std::vector<int>mGetPixelDepthPending,mGetPixelDepthCached;
 const std::unordered_map<Mtx*,MtxF>*mCurMtxReplacements;
 Dimensions mGfxCurrentWindowDimensions,mCurDimensions,mNativeDimensions;
 bool mRendersToFb=false;int mFbActive=0,mGameFb=8,mGameFbMsaaResolved=9,mMsaaLevel=1;
 uintptr_t mGfxFrameBuffer=0;struct{int viewport=0,scissor=0;}mRenderingState;
 int acceptedLoads=0,acceptedTriangles=0;std::vector<int>flushTargets;
 void SpReset(){mFbActive=0;}
 bool ViewportMatchesRendererResolution(){return true;}
 void Flush(){flushTargets.push_back(mRapi->target);}
 void GfxSpModifyVertex(uint16_t,uint8_t,uint32_t);
 void GfxSpVertex(size_t,size_t,const F3DVtx*);
 void GfxSpTri1(uint8_t,uint8_t,uint8_t,bool);
 void Run(Gfx*,const std::unordered_map<Mtx*,MtxF>&);
};
std::weak_ptr<Interpreter>mInstance;
std::stack<std::string>currentDir;
namespace Ship {struct Context {
 static Context*GetRawInstance(){static Context c;return &c;}
 Context*GetResourceManager(){return this;}
 void*GetResourceRawPointer(uint64_t){return nullptr;}
};}
#define C0(pos,width) ((cmd->words.w0>>(pos))&((1U<<(width))-1))
#define C1(pos,width) ((cmd->words.w1>>(pos))&((1U<<(width))-1))
'''

def run(name, text):
    src = o / (name + '.cpp')
    src.write_text(text, encoding='utf-8')
    exe = o / (name + '.exe')
    compile_result = subprocess.run(['cl', '/nologo', '/std:c++20', '/EHsc', '/MD', '/O2', str(src),
                                     '/Fo' + str(o / (name + '.obj')), '/Fe' + str(exe)], capture_output=True, text=True)
    result = subprocess.run([str(exe)], capture_output=True, text=True) if compile_result.returncode == 0 else None
    return dict(compile_exit=compile_result.returncode, compile_output=compile_result.stdout + compile_result.stderr,
                exit_code=result.returncode if result else None, output=result.stdout + result.stderr if result else '')

modify_sig = 'void Interpreter::GfxSpModifyVertex('
protected_setup = r'''
 SetErrorMode(SEM_NOGPFAULTERRORBOX);
 // Reserve the full malformed-index range, and commit only the real vertex
 // buffer. The logged 0x4DFF write lands deterministically in an uncommitted page.
 auto* memory=static_cast<uint8_t*>(VirtualAlloc(nullptr,4*1024*1024,MEM_RESERVE,PAGE_NOACCESS));ck(memory!=nullptr);
 SYSTEM_INFO system;GetSystemInfo(&system);
 ck(VirtualAlloc(memory,system.dwPageSize,MEM_COMMIT,PAGE_READWRITE)!=nullptr);
 Interpreter gfx;gfx.mRsp=reinterpret_cast<RSP*>(memory);
'''
baseline = run('baseline', common + function(old, modify_sig) + 'int main(){' + protected_setup + r'''
 gfx.GfxSpModifyVertex(0x4DFF,G_MWO_POINT_ST,0x00100020);return 0;}
''')
assert baseline['compile_exit'] == 0 and baseline['exit_code'] & 0xffffffff == 0xc0000005, baseline

actual = guard + '\n'
for sig in ('void GfxExecStack::start(', 'void GfxExecStack::stop(', 'F3DGfx*& GfxExecStack::currCmd(',
            modify_sig, 'bool gfx_modify_vtx_handler_f3dex2(', 'bool gfx_branch_z_otr_handler_f3dex2(', 'static void gfx_step('):
    actual += function(s, sig) + '\n'
actual += step + '\n' + function(s, 'void Interpreter::Run(') + '\n'
# Compile the actual guarding preambles, with shader work replaced by sentinels.
for sig, end, suffix in [
    ('void Interpreter::GfxSpVertex(', '    for (size_t i =', '++acceptedLoads;'),
    ('void Interpreter::GfxSpTri1(', '    struct LoadedVertex* v1 =', '++acceptedTriangles;'),
]:
    body = function(s, sig)
    actual += body[:body.index(end)] + suffix + '\n}\n'

test = r'''
bool end_handler(F3DGfx**){g_exec_stack.stop();return true;}
bool framebuffer_handler(F3DGfx**){auto gfx=mInstance.lock();gfx->mFbActive=1;gfx->mRapi->target=7;return false;}
bool unrelated_handler(F3DGfx**){throw 42;}
template<class F>bool rejected(F f){try{f();return false;}catch(const SohExtremeInvalidGfx&){return true;}}
int main(){
''' + protected_setup + r'''
 ck(rejected([&]{gfx.GfxSpModifyVertex(0x4DFF,G_MWO_POINT_ST,0x00100020);}));
 VirtualFree(memory,0,MEM_RELEASE);
 RSP rsp{};RDP rdp{};Api api;
 auto owner=std::make_shared<Interpreter>();mInstance=owner;auto&g=*owner;
 g.mRsp=&rsp;g.mRdp=&rdp;g.mRapi=&api;
 F3DVtx vertex;
 for(size_t start=0;start<=128;++start)for(size_t count=0;count<=128;++count){
  int before=g.acceptedLoads;
  bool bad=rejected([&]{g.GfxSpVertex(count,start,&vertex);});
  bool expected=start>64||count>64-std::min(start,size_t(64));
  ck(bad==expected);ck(g.acceptedLoads==before+!bad);
 }
 for(auto start:{size_t(0),size_t(63),size_t(64),SIZE_MAX,SIZE_MAX-1})
  for(auto count:{size_t(0),size_t(1),SIZE_MAX,SIZE_MAX-1})
   ck(rejected([&]{g.GfxSpVertex(count,start,&vertex);})==(start>64||count>64-std::min(start,size_t(64))));
 ck(rejected([&]{g.GfxSpVertex(1,0,nullptr);}));
 ck(!rejected([&]{g.GfxSpVertex(0,64,nullptr);}));
 for(uint32_t idx=0;idx<=UINT16_MAX;++idx){
  auto snapshot=rsp;
  bool bad=rejected([&]{g.GfxSpModifyVertex(static_cast<uint16_t>(idx),G_MWO_POINT_ST,0xfffe0003);});
  ck(bad==(idx>=64));
  if(bad)ck(std::memcmp(&snapshot,&rsp,sizeof(rsp))==0);
  else ck(rsp.loaded_vertices[idx].u==-2&&rsp.loaded_vertices[idx].v==3);
 }
 for(int where=0;where<=255;++where)
  ck(rejected([&]{g.GfxSpModifyVertex(0,where,0);})==(where!=G_MWO_POINT_ST));
 // Every encoded triangle index in every position, with and without rectangle
 // scratch vertices. All checks precede any vertex dereference.
 for(int rect=0;rect<=1;++rect)for(int pos=0;pos<3;++pos)for(int idx=0;idx<256;++idx){
  int before=g.acceptedTriangles;
  bool bad=rejected([&]{g.GfxSpTri1(pos==0?idx:0,pos==1?idx:1,pos==2?idx:2,rect);});
  ck(bad==(idx>=(rect?68:64)));ck(g.acceptedTriangles==before+!bad);
 }
 for(uint32_t idx=0;idx<4096;++idx){
  F3DGfx commands[2]={{{idx,0}},{{0,0}}};auto*cmd=commands;
  bool bad=rejected([&]{gfx_branch_z_otr_handler_f3dex2(&cmd);});
  ck(bad==(idx>=64));ck(cmd==commands+(bad?0:1));
 }
 // Actual dispatch and actual Run: reject unknown opcode before the following
 // malformed write; separately reject malformed MODIFYVTX with known opcode.
 ucodeHandlers[static_cast<int8_t>(0x02)]={"modify",gfx_modify_vtx_handler_f3dex2};
 ucodeHandlers[static_cast<int8_t>(0xdf)]={"end",end_handler};
 ucodeHandlers[static_cast<int8_t>(0x30)]={"framebuffer",framebuffer_handler};
 ucodeHandlers[static_cast<int8_t>(0x31)]={"unrelated exception",unrelated_handler};
 const uintptr_t modify=0x02000000|(G_MWO_POINT_ST<<16);
 F3DGfx invalid[]={{{0x04000000,0}},{{modify|(0x4DFF<<1),0x00100020}},{{0xdf000000,0}}};
 F3DGfx malformed[]={{{modify|(0x4DFF<<1),0x00100020}},{{0xdf000000,0}}};
 F3DGfx valid[]={{{modify|(63<<1),0xfffe0003}},{{0xdf000000,0}}};
 F3DGfx bad_ucode[]={{{0xddffffff,0}},{{0xdf000000,0}}};
 std::unordered_map<Mtx*,MtxF>matrices;
 for(auto commands:{invalid,malformed,bad_ucode}){
  auto snapshot=rsp;currentDir.push("test");g_exec_stack.disp_stack.push_back(1);
  g.Run(commands,matrices);
  ck(std::memcmp(&snapshot,&rsp,sizeof(rsp))==0);
  ck(g_exec_stack.cmd_stack.empty()&&g_exec_stack.gfx_path.empty()&&g_exec_stack.disp_stack.empty());
  ck(currentDir.empty()&&ucode_handler_index==ucode_f3dex2);
  g.Run(valid,matrices);ck(rsp.loaded_vertices[63].u==-2&&rsp.loaded_vertices[63].v==3);
 }
 F3DGfx offscreen[]={{{0x30000000,0}},{{0x04000000,0}},{{0xdf000000,0}}};
 for(bool toFb:{false,true}){
  g.mRendersToFb=toFb;g.flushTargets.clear();g.Run(offscreen,matrices);
  ck(g.mFbActive==0&&g.flushTargets.size()==2&&g.flushTargets[0]==7);
  ck(g.flushTargets[1]==(toFb?g.mGameFb:0)&&api.target==0);
  g.Run(valid,matrices);ck(g_exec_stack.cmd_stack.empty());
 }
 // Invalid commands inside a called list clear all pending caller state.
 g_exec_stack.start(valid);g_exec_stack.cmd_stack.push(malformed);
 g_exec_stack.gfx_path.push_back(valid);g_exec_stack.disp_stack.push_back(1);
 ck(!SohExtremeGfxStep());ck(g_exec_stack.cmd_stack.empty()&&g_exec_stack.gfx_path.empty()&&g_exec_stack.disp_stack.empty());
 // Malformed frames do not build queues or emit an unbounded log per frame.
 auto beforeLogs=logs;
 for(int i=0;i<10000;++i){g.flushTargets.clear();g.Run(malformed,matrices);ck(g_exec_stack.cmd_stack.empty());}
 ck(logs-beforeLogs<32);
 g.Run(valid,matrices);ck(rsp.loaded_vertices[63].v==3);
 F3DGfx unrelated[]={{{0x31000000,0}}};
 bool propagated=false;try{g.Run(unrelated,matrices);}catch(int value){propagated=value==42;}
 ck(propagated);g.Run(valid,matrices);
 std::printf("%llu assertions passed; protected-page fault blocked; valid next frames preserved\n",checks);
}
'''
fixed = run('fixed', common + actual + test)
report = dict(passed=fixed['compile_exit'] == 0 and fixed['exit_code'] == 0, baseline=baseline, fixed=fixed,
              scope=__doc__, limitations=['Does not identify the original malformed-command producer.', 'No live game/GPU playtest.'])
(o / 'native.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
raise SystemExit(not report['passed'])
