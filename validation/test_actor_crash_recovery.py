"""Exercise actual callback recovery and crash-stack code with controlled Windows faults.

The truncated callback is injected, not reproduced by normal gameplay. These
tests validate containment and diagnostics, not the unidentified corrupting write.
"""
from pathlib import Path
import argparse, json, subprocess

p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
r=Path(__file__).resolve().parents[1];o=a.output.resolve();o.mkdir(parents=True,exist_ok=True)
s=(r/'src/code/z_actor.c').read_text()
def function(sig):
    start=s.index(sig);end=s.index('{',start);depth=1;i=end+1
    while depth:
        if s[i]=='{':depth+=1
        if s[i]=='}':depth-=1
        i+=1
    return s[start:i]
functions='\n'.join(function(sig) for sig in ('void Actor_GetCrashCallback(', 'static void Actor_CallWithEnemySpawnSource(', 'static void Actor_RecoverTruncatedButterflyDraw('))
code=r'''
#include <windows.h>
#include <dbghelp.h>
#include <cstdio>
#include <cstdint>
#include <string>
#include <iostream>
#include <cstdarg>
#include "soh/Enhancements/randomizer/ActorDrawRecovery.h"
using s16=int16_t;
struct Actor;struct PlayState{int sceneNum=32;};
using ActorFunc=void(*)(Actor*,PlayState*);
struct Actor {s16 id=0,params=0;ActorFunc init=nullptr,destroy=nullptr,update=nullptr,draw=nullptr;};
struct ActorDBEntry {bool valid=true;ActorFunc update=nullptr,destroy=nullptr,draw=nullptr;} db;
const int ACTOR_EN_BUTTE=1;
bool dbMissing=false;ActorDBEntry* ActorDB_Retrieve(int){return dbMissing?nullptr:&db;}
PlayState play;PlayState*gPlayState=&play;
int logs=0;void osSyncPrintf(const char*,...){++logs;}
Actor*sEnemyCallbackSource=nullptr;ActorFunc sActiveActorCallback=nullptr;
s16 sActiveCallbackActorId=-1,sActiveCallbackActorParams=0;
'''+functions+r'''
int checks=0,failures=0;
void ck(bool yes,const char*why){++checks;if(!yes){++failures;std::cout<<"FAIL "<<why<<"\n";}}
void update(Actor*,PlayState*){} void destroy(Actor*,PlayState*){} void other(Actor*,PlayState*){}
int drawn=0;void draw(Actor*a,PlayState*){
 ++drawn;s16 id,params;uintptr_t callback;Actor_GetCrashCallback(&id,&params,&callback);
 ck(id==a->id&&params==a->params&&callback==(uintptr_t)draw,"active draw snapshot");
}
void nested(Actor*a,PlayState*p){
 Actor inner{ACTOR_EN_BUTTE,22};Actor_CallWithEnemySpawnSource(draw,&inner,p);
 s16 id,params;uintptr_t callback;Actor_GetCrashCallback(&id,&params,&callback);
 ck(id==a->id&&params==a->params&&callback==(uintptr_t)nested&&sEnemyCallbackSource==a,"nested snapshot restored");
}
struct Logger{void flush(){}} logger;
struct Context{static Context*GetRawInstance(){static Context c;return &c;}Logger*GetLogger(){return &logger;}};
namespace spdlog {void shutdown(){}}
std::string trace;
struct CrashHandler{
 void PrintStack(CONTEXT*);
 void PrintRegisters(CONTEXT*){} void PrintCommon(){}
 void AppendStr(const char*s){trace+=s;}void AppendLine(const char*s){trace+=s;trace+='\n';}
} handler;
'''+(r/'Cmake/SohExtremeCrashStack.cpp.inc').read_text()+r'''
DWORD faultCode=0;uintptr_t faultPC=0;
LONG filter(EXCEPTION_POINTERS*p){faultCode=p->ExceptionRecord->ExceptionCode;
 faultPC=(uintptr_t)p->ExceptionRecord->ExceptionAddress;handler.PrintStack(p->ContextRecord);return EXCEPTION_EXECUTE_HANDLER;}
__declspec(noinline) void faultCall(ActorFunc fn,Actor*a){fn(a,&play);}
void controlledFault(ActorFunc fn,Actor*a){__try{faultCall(fn,a);}__except(filter(GetExceptionInformation())){}}
int main(){
 db={true,update,destroy,draw};
 auto truncated=(ActorFunc)(uintptr_t)(uint32_t)(uintptr_t)draw;
 ck((uintptr_t)draw>UINT32_MAX,"64-bit ASLR test address");
 Actor actor{ACTOR_EN_BUTTE,5,nullptr,destroy,update,truncated};
 controlledFault(actor.draw,&actor);
 ck(faultCode==EXCEPTION_ACCESS_VIOLATION&&faultPC==(uintptr_t)truncated,"injected truncation reproduces execute fault");
 char pc[64];snprintf(pc,sizeof(pc),"#0 PC=0x%016llX",(unsigned long long)faultPC);
 ck(trace.find(pc)!=std::string::npos,"fault log retains actual truncated PC");
 ck(trace.find("<unresolved>")!=std::string::npos,"unresolved address labeled honestly");
 Actor_RecoverTruncatedButterflyDraw(&actor);
 ck(actor.draw==draw&&logs==1,"exact truncated native draw recovered");
 Actor_CallWithEnemySpawnSource(actor.draw,&actor,&play);ck(drawn==1,"recovered function runs");
 for(int n=0;n<9;++n){
  actor={ACTOR_EN_BUTTE,5,nullptr,destroy,update,truncated};dbMissing=false;db.valid=true;
  switch(n){case 0:actor.id=3;break;case 1:actor.init=other;break;case 2:actor.draw=nullptr;break;
  case 3:actor.draw=other;break;case 4:actor.update=other;break;case 5:actor.destroy=other;break;
  case 6:dbMissing=true;break;case 7:db.valid=false;break;case 8:actor.draw=(ActorFunc)((uintptr_t)truncated+1);break;}
  auto old=actor.draw;Actor_RecoverTruncatedButterflyDraw(&actor);ck(actor.draw==old,"nonmatching draw left untouched");
 }
 dbMissing=false;db.valid=true;
 for(uintptr_t upper=1;upper<256;++upper)for(uintptr_t low:{0u,1u,0x7fffffffu,0xffffffffu}){
  uintptr_t full=(upper<<32)|low;
  ck(SohExtreme_IsTruncatedNativeDraw(low,full)==(low!=0),"exact low-half recovery bounds");
  ck(!SohExtreme_IsTruncatedNativeDraw(full,full),"intact full pointer unchanged");
  ck(!SohExtreme_IsTruncatedNativeDraw(low^1,full),"different pointer never repaired");
 }
 actor={ACTOR_EN_BUTTE,7};Actor_CallWithEnemySpawnSource(nested,&actor,&play);
 s16 id,params;uintptr_t cb;Actor_GetCrashCallback(&id,&params,&cb);
 ck(id==-1&&cb==0&&sEnemyCallbackSource==nullptr,"idle snapshot restored");
 trace.clear();CONTEXT context{};RtlCaptureContext(&context);handler.PrintStack(&context);
 ck(trace.find("#0 PC=0x")!=std::string::npos&&trace.find("RVA=0x0 ")==std::string::npos,"real module PC and RVA retained without PDB");
 ck(trace.find("#1 PC=0x")!=std::string::npos,"caller frame retained without PDB");
 std::cout<<checks<<" crash containment/diagnostic assertions, "<<failures<<" failures\n";
 std::cout<<trace;return failures?1:0;
}
'''
src=o/'crash_test.cpp';src.write_text(code);exe=o/'crash_test.exe'
c=subprocess.run(['cl','/nologo','/EHsc','/std:c++20','/I'+str(r),str(src),'/Fo'+str(o/'crash_test.obj'),'/Fe'+str(exe),'/link','dbghelp.lib'],capture_output=True,text=True)
t=subprocess.run([str(exe)],capture_output=True,text=True) if c.returncode==0 else None
report=dict(passed=c.returncode==0 and t.returncode==0,output=c.stdout+c.stderr+(t.stdout+t.stderr if t else ''),scope=__doc__)
(o/'crash.json').write_text(json.dumps(report,indent=2));print(report['output']);raise SystemExit(not report['passed'])
