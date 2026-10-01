"""Compile changed native lobby route and real tracker grouping implementation."""
from pathlib import Path
import argparse,json,re,subprocess
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
r=Path(__file__).resolve().parents[1];o=a.output.resolve();o.mkdir(parents=True,exist_ok=True)
s=(r/'soh/Enhancements/randomizer/location_access/dungeons/dodongos_cavern.cpp').read_text()
expr=re.search(r'ENTRANCE\(RR_DODONGOS_CAVERN_LOBBY_SWITCH,\s*(.*?)\),',s)[1]
graph=json.loads((r/'archipelago/soh_extreme/EnemyRoomGraph.json').read_text())
assert next(e['condition'] for e in graph['RR_DODONGOS_CAVERN_LOBBY']['exits'] if e['target']=='RR_DODONGOS_CAVERN_LOBBY_SWITCH')==expr
code=r'''
#include <cassert>
#include <iostream>
#include <set>
#include "soh/Network/Archipelago/TrackerRegions.h"
struct Logic{bool IsAdult=false,groundJump=false,grab=false;
 bool CanGroundJump(bool){return groundJump;}bool HasItem(int){return grab;}} value;
Logic*logic=&value;
constexpr int RG_POWER_BRACELET=1;
bool switchShortcut(){return '''+expr+r''';}
int n=0;
#define CK(x) do{++n;if(!(x)){std::cerr<<"failed "<<__LINE__<<": "<<#x<<"\n";return 1;}}while(0)
using namespace SohExtreme;
int main(){
 for(int bits=0;bits<8;++bits){value={bool(bits&1),bool(bits&2),bool(bits&4)};
  CK(switchShortcut()==bool(bits&3));
 }
 TrackerSnapshot s;s.rows={{9700000,1,"EXTREME Mkt Wonder Day 1","Market"},
 {9800486,1,"Enemy Defeat: Market Ruins Room 0 Redead/Gibdo 1","Market"},
 {10000092,1,"NPC Speech: Dancing Couple","Market"},
 {10000109,2,"NPC Speech: Bazaar Shopkeeper","Market"},
 {9700010,1,"EXTREME Kak Watchtower Butterfly Fairy","Kak Watchtower"}};
 auto area=[](int64_t id){return id==9700000||id==9800486?4:5;};
 int resolverCalls=0;
 auto resolve=[&](int64_t id){++resolverCalls;return area(id);};
 for(int current:{-1,4,5})for(bool first:{false,true})for(bool only:{false,true})for(bool normal:{false,true}){
  resolverCalls=0;
  auto groups=GroupTrackerRows(s,current,first,only,resolve,[&](const TrackerRow&r){return !normal||r.state==1;});
  CK(resolverCalls==s.rows.size());std::set<int64_t>seen;bool passedCurrent=false;
  for(const auto&g:groups){
   if(!g.currentArea)passedCurrent=true;
   else if(first)CK(!passedCurrent);
   int ordinary=0,glitched=0;
   for(const auto*row:g.rows){CK(seen.insert(row->id).second);CK(g.currentArea==(area(row->id)==current));
    if(only)CK(g.currentArea);if(normal)CK(row->state==1);
    if(row->state==1)++ordinary;else++glitched;
    if(current==5&&(row->id==9700000||row->id==9800486))CK(!g.currentArea);
   }
   CK(g.normal==ordinary&&g.glitched==glitched);
   if(g.region=="Market")CK(g.sharedRegion);
  }
  for(const auto&row:s.rows)CK(seen.count(row.id)==(!only||area(row.id)==current)&&(!normal||row.state==1)||(!seen.count(row.id)&&normal&&row.state!=1));
 }
 CK(s.rows.size()==5&&s.rows[0].region=="Market"); // input is immutable
 // Lots of mixed-region rows preserve identities and exact status under filtering.
 for(int i=0;i<1000;++i)s.rows.push_back({i,uint8_t(i%2+1),"row"+std::to_string(i),"Mixed"});
 auto groups=GroupTrackerRows(s,2,true,false,[](int64_t id){return int(id%4);},[](const auto&){return true;});
 std::set<int64_t>seen;
 for(const auto&g:groups)for(const auto*row:g.rows){CK(seen.insert(row->id).second);CK(g.currentArea==(row->id%4==2));}
 CK(seen.size()==s.rows.size());
 std::cout<<n<<" native lobby/area assertions passed\n";
}
'''
src=o/'dc_area.cpp';src.write_text(code);exe=o/'dc_area.exe'
c=subprocess.run(['cl','/nologo','/EHsc','/std:c++20','/Zc:preprocessor','/I'+str(r),str(src),'/Fo'+str(o/'dc_area.obj'),'/Fe'+str(exe)],capture_output=True,text=True)
t=subprocess.run([str(exe)],capture_output=True,text=True) if c.returncode==0 else None
report=dict(passed=c.returncode==0 and t.returncode==0,output=c.stdout+c.stderr+(t.stdout+t.stderr if t else ''),scope=__doc__)
(o/'native.json').write_text(json.dumps(report,indent=2));print(report['output']);raise SystemExit(not report['passed'])
