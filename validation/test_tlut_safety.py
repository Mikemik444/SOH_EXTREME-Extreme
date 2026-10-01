"""Exercise the production TLUT copy with real Windows protected memory pages."""
from pathlib import Path
import argparse,json,subprocess
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--previous-function',type=Path);a=p.parse_args()
r=Path(__file__).resolve().parent.parent;o=a.output.resolve();o.mkdir(parents=True,exist_ok=True)
fixed=(r/'Cmake/SohExtremeTlut.cpp.inc').read_text()
common=r'''
#define NOMINMAX
#include <windows.h>
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <cstring>
#include <cstdio>
#define SUPPORT_CHECK(x) assert(x)
#define SPDLOG_ERROR(...) ((void)0)
constexpr int G_IM_SIZ_16b=2;
struct RDP {const uint8_t*palettes[2]={};const uint8_t*palette_dram_addr[2]={};uint8_t palette_staging[2][256]={};
 struct {const uint8_t*addr=nullptr;int siz=G_IM_SIZ_16b;}texture_to_load;
 struct {uint16_t tmem=256;}texture_tile[8];};
class Interpreter {public:RDP*mRdp;void GfxDpLoadTlut(uint8_t,uint32_t);};
'''
setup=r'''
 SYSTEM_INFO system;GetSystemInfo(&system);const size_t page=system.dwPageSize;
 auto*memory=static_cast<uint8_t*>(VirtualAlloc(nullptr,page*2,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));assert(memory);
 for(size_t i=0;i<page*2;++i)memory[i]=static_cast<uint8_t>(i);
 DWORD previous;assert(VirtualProtect(memory+page,page,PAGE_NOACCESS,&previous));
 RDP r;Interpreter interpreter{&r};r.texture_to_load.addr=memory+page-256;
'''
def run(name,source):
 src=o/(name+'.cpp');src.write_text(source);exe=o/(name+'.exe')
 c=subprocess.run(['cl','/nologo','/std:c++20','/EHsc','/MD',str(src),'/Fo'+str(o/(name+'.obj')),'/Fe'+str(exe)],capture_output=True,text=True)
 t=subprocess.run([str(exe)],capture_output=True,text=True) if c.returncode==0 else None
 return dict(compile_exit=c.returncode,compile_output=c.stdout+c.stderr,exit_code=t.returncode if t else None,output=t.stdout+t.stderr if t else '')
before=None
if a.previous_function:
 before=run('previous',common+a.previous_function.read_text()+'int main(){SetErrorMode(SEM_NOGPFAULTERRORBOX);'+setup+'interpreter.GfxDpLoadTlut(0,255);}\n')
 assert before['compile_exit']==0 and before['exit_code'] & 0xffffffff == 0xc0000005,before
code=common+fixed+'int main(){int count=0;auto ck=[&](bool v){assert(v);++count;};'+setup+r'''
 std::memset(r.palette_staging,0xaa,sizeof(r.palette_staging));
 interpreter.GfxDpLoadTlut(0,255); // first 256 readable, second 256 inaccessible
 ck(r.palettes[0]==nullptr&&r.palettes[1]==nullptr);
 for(auto&half:r.palette_staging)for(auto b:half)ck(b==0xaa);
 r.texture_to_load.addr=memory+page-16;interpreter.GfxDpLoadTlut(0,15); // short CI4 crosses a protected page
 ck(r.palettes[0]==nullptr);ck(r.palette_staging[0][0]==0xaa);
 r.texture_to_load.addr=nullptr;interpreter.GfxDpLoadTlut(0,255);ck(r.palettes[0]==nullptr);
 r.texture_to_load.addr=memory;interpreter.GfxDpLoadTlut(8,255);interpreter.GfxDpLoadTlut(0,UINT32_MAX);
 ck(r.palettes[0]==nullptr);
 r.texture_tile[0].tmem=512;interpreter.GfxDpLoadTlut(0,255);ck(r.palettes[0]==nullptr);
 r.texture_tile[0].tmem=65535;interpreter.GfxDpLoadTlut(0,0);ck(r.palettes[1]==nullptr);
 // All valid palette offsets and lengths; crossing halves preserves every byte.
 for(int tmem=256;tmem<512;++tmem)for(int entries=1;entries<=256;++entries){
  r=RDP{};r.texture_to_load.addr=memory;r.texture_tile[0].tmem=tmem;
  std::memset(r.palette_staging,0xaa,sizeof(r.palette_staging));interpreter.GfxDpLoadTlut(0,entries-1);
  unsigned start=(tmem-256)*2,size=std::min(unsigned(entries*2),512-start);
  for(unsigned i=0;i<512;++i)assert(r.palette_staging[i/256][i%256]==(i>=start&&i<start+size?memory[i-start]:0xaa));
  ck(r.palettes[start/256]==r.palette_staging[start/256]);
 }
 r=RDP{};r.texture_to_load.addr=memory;interpreter.GfxDpLoadTlut(0,255);
 ck(r.palette_dram_addr[0]==memory&&r.palette_dram_addr[1]==memory+256);
 ck(r.palettes[0]==r.palette_staging[0]&&r.palettes[1]==r.palette_staging[1]);
 auto saved=r;VirtualFree(memory,0,MEM_RELEASE);
 ck(std::memcmp(r.palette_staging,saved.palette_staging,512)==0);
 std::printf("%d assertions passed; inaccessible second half rejected without partial publication\n",count);
}
'''
after=run('fixed',code);report=dict(passed=after['compile_exit']==0 and after['exit_code']==0,before=before,after=after,scope=__doc__)
(o/'tlut.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2));raise SystemExit(not report['passed'])
