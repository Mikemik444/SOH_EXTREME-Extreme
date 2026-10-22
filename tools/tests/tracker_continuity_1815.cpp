#include "soh/Network/Archipelago/TrackerMirror.h"
#include <cassert>
#include <iostream>
#include <chrono>
using namespace SohExtreme;
static size_t assertions=0;
#define CHECK(x) do { ++assertions; if(!(x)) { std::cerr << "FAILED " << __LINE__ << ": " #x << '\n'; return 1; } } while(false)
int main() {
    TrackerMirrorState state; std::string status,error;
    const std::string nonce(32,'a');
    std::set<int64_t> active{1,2,3},checked{};
    state.Reset(nonce);
    CHECK(!state.Display(1,0,active,checked,1,status));
    TrackerSnapshot a; a.nonce=nonce; a.slot=1; a.producer="worker";a.version="1.8.15";
    a.request=state.NextRequest(); a.revision=1; a.received=0;a.active=active;
    a.liveShields=0; a.liveTime=0; a.liveClock=0x6000; a.liveAmmo=7; a.liveAmmoOwned=7;
    a.liveAmmoState=19; a.ammoRefills=7;
    a.rows={{1,1,"first [Child]","Test region"},{2,1,"second [Any age]","Test region"}};
    CHECK(state.Accept(a,1,1,error));
    auto current=[&](uint64_t received=0,uint32_t shields=0,uint32_t phase=0,uint32_t clock=0x6000,
                     uint32_t flags=0,uint32_t ammo=7,uint64_t ammoState=19,double now=1.1) {
      return state.Current(1,received,active,checked,now,status,shields,phase,clock,flags,ammo,ammoState);
    };
    auto display=[&](uint64_t received=0,uint32_t shields=0,uint32_t phase=0,uint32_t clock=0x6000,
                     uint32_t flags=0,uint32_t ammo=7,uint64_t ammoState=19,double now=1.1) {
      return state.Display(1,received,active,checked,now,status,shields,phase,clock,flags,ammo,ammoState);
    };
    CHECK(current() && current()->ammoRefills==7);
    CHECK(display() && display()->rows.size()==2 && display()->ammoRefills==0);
    CHECK(!current(1)); CHECK(display(1) && display(1)->rows.size()==2);
    CHECK(status.find("previous results")!=std::string::npos);
    CHECK(!current(0,1)); CHECK(display(0,1)->rows.size()==2);
    CHECK(!current(0,0,1)); CHECK(display(0,0,1)->rows.size()==2);
    CHECK(!current(0,0,0,0xE001)); CHECK(display(0,0,0,0xE001)->rows.size()==2);
    CHECK(!current(0,0,0,0x6000,1)); CHECK(display(0,0,0,0x6000,1)->rows.size()==2);
    CHECK(!current(0,0,0,0x6000,0,3)); CHECK(display(0,0,0,0x6000,0,3)->rows.size()==2);
    CHECK(!current(0,0,0,0x6000,0,7,20)); CHECK(display(0,0,0,0x6000,0,7,20)->rows.size()==2);
    CHECK(!current(0,0,0,0x6000,0,7,19,12)); CHECK(display(0,0,0,0x6000,0,7,19,12)->rows.size()==2);
    checked.insert(1);
    CHECK(!current());
    auto view=display(1); CHECK(view && view->rows.size()==1 && view->rows.front().id==2 && view->checked.count(1));
    const auto* rows=view->rows.data();
    for(int i=0;i<1000;++i) { CHECK(display(1)->rows.data()==rows); CHECK(!current(1)); }
    a.received=1; a.checked=checked; a.revision=2;a.request=state.NextRequest();
    a.rows={{2,1,"second [Any age]","Test region"},{3,1,"newly unlocked [Adult]","New region"}};
    CHECK(state.Accept(a,1,2,error));
    CHECK(current(1,0,0,0x6000,0,7,19,2.1));
    view=display(1,0,0,0x6000,0,7,19,2.1);
    CHECK(view->rows.size()==2 && view->rows.back().id==3 && view->received==1);
    CHECK(view->ammoRefills==0);
    CHECK(!state.Accept(a,1,2.2,error)); // duplicate publication
    auto invalid=a;invalid.nonce=std::string(32,'b');invalid.revision++;
    CHECK(!state.Accept(invalid,1,2.2,error));
    CHECK(!state.Display(2,1,active,checked,2.2,status));
    auto wrongManifest=active;wrongManifest.insert(4);
    CHECK(!state.Display(1,1,wrongManifest,checked,2.2,status));
    state.Reset(std::string(32,'c'));
    CHECK(!state.Display(1,1,active,checked,2.3,status));
    CHECK(!state.Accept(a,1,2.4,error));
    TrackerRequestPacer pacer;
    CHECK(pacer.Due(1,42,3));pacer.Sent(1,42);
    CHECK(!pacer.Due(1.05,43,3)); CHECK(pacer.Due(1.151,43,3));pacer.Sent(1.151,43);
    CHECK(!pacer.Due(1.4,43,3));CHECK(pacer.Due(3,43,3));
    CHECK(pacer.Due(1.5,43,0)); // explicit refresh keeps cached rows
    int requests=0;pacer.Reset();
    for(int frame=0;frame<600;++frame) {
      double t=10+frame/60.; if(pacer.Due(t,static_cast<uint64_t>(frame),1000)) {pacer.Sent(t,frame);++requests;}
    }
    CHECK(requests<=67 && requests>=60);
    pacer.Reset();CHECK(pacer.Due(0,0,100));
    std::cout << "PASS: " << assertions << " assertions; same-session display retained, strict gameplay unchanged, atomic replies, check masking, resets and request coalescing.\n";
}
