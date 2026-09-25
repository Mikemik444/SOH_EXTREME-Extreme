#include <cassert>
#include <fstream>
#include <iostream>
#include <set>
#include <string>
#include "soh/Network/Archipelago/TrackerRegions.h"
#include "soh/Network/Archipelago/TrackerWorkerConfig.h"
using namespace SohExtreme;
int main(int argc, char** argv) {
    assert(argc == 2);
    std::ifstream file(argv[1]);
    std::string payload((std::istreambuf_iterator<char>(file)), {});
    auto snapshot = DecodeTrackerSnapshot(payload);
    std::string status;
    TrackerMirrorState mirror; mirror.Reset(snapshot.nonce); mirror.NextRequest();
    assert(mirror.Accept(snapshot, 1, 1.0, status));
    assert(mirror.Current(1, snapshot.received, snapshot.active, snapshot.checked, 1.0, status));
    assert(!mirror.Current(1, snapshot.received + 1, snapshot.active, snapshot.checked, 1.0, status));
    assert(!mirror.Current(1, snapshot.received, snapshot.active, snapshot.checked, 12.0, status));
    auto other = snapshot; other.nonce = std::string(32, 'b'); other.revision++;
    assert(!mirror.Accept(other, 1, 2.0, status));
    other=snapshot; other.version="0.11.19"; other.revision++;
    assert(!mirror.Accept(other, 1, 2.0, status));
    auto area = [](int64_t id) { return id % 3 == 0 ? 5 : (id % 3 == 1 ? 4 : -1); };
    auto all = [](const TrackerRow&) { return true; };
    auto checkSet = [&](const auto& groups, bool onlyCurrent) {
        std::set<int64_t> ids;
        bool leftCurrent = false;
        for (const auto& group : groups) {
            if (!group.currentArea) leftCurrent = true;
            else assert(!leftCurrent);
            size_t normal=0, glitched=0;
            for (const auto* row : group.rows) {
                assert(ids.insert(row->id).second);
                assert(snapshot.active.count(row->id));
                assert(!snapshot.checked.count(row->id));
                if (onlyCurrent) assert(area(row->id)==5);
                if(row->state==1)normal++;else glitched++;
            }
            assert(normal == group.normal && glitched == group.glitched);
        }
        return ids;
    };
    auto grouped = GroupTrackerRows(snapshot,5,true,false,area,all);
    auto ids = checkSet(grouped,false);
    assert(ids.size() == snapshot.rows.size());
    for(const auto& row:snapshot.rows) assert(ids.count(row.id));
    auto only = GroupTrackerRows(snapshot,5,true,true,area,all);
    auto onlyIds=checkSet(only,true);
    for(const auto& row:snapshot.rows) assert(bool(onlyIds.count(row.id)) == (area(row.id)==5));
    auto alpha = GroupTrackerRows(snapshot,5,false,false,area,all);
    for(size_t i=1;i<alpha.size();++i)assert(alpha[i-1].region < alpha[i].region);
    auto none = GroupTrackerRows(snapshot,-1,true,true,area,all);
    assert(none.empty());
    auto filtered = GroupTrackerRows(snapshot,5,true,false,area,[](const TrackerRow& row){return row.state==1;});
    for(const auto& group:filtered)for(const auto* row:group.rows)assert(row->state==1);
    // The snapshot remains byte/row-order immutable after every presentation filter.
    assert(DecodeTrackerSnapshot(payload).rows.size() == snapshot.rows.size());
    const auto config=MakeTrackerWorkerBootstrap("127.0.0.1:38281","Mike \"quoted\" \\ tester","Secret & % ! \\ \"",1,std::string(32,'a'));
    std::cout<<config<<"\n";
    std::cout<<"Validated "<<ids.size()<<" exact row identities in "<<grouped.size()<<" region groups.\n";
    std::cout<<"Current-area ordering, filtering, snapshot guards, and startup JSON passed.\n";
}
