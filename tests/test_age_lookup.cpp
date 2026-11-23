#include <cassert>
#include <iostream>
#include "RoomTransitionLabels.h"
int main() {
    using namespace SohExtreme;
    constexpr int64_t granny=11'000'845LL;
    constexpr int64_t kakGrave=11'000'228LL;
    constexpr int64_t graveKak=11'000'405LL;
    for (const auto id : {granny,kakGrave,graveKak}) {
        assert(SharedSceneTransitionLocationId(id)==id);
        for (const auto offset : {20'000'000LL,40'000'000LL}) {
            const auto aged=id+offset;
            assert(SharedSceneTransitionLocationId(aged)==id);
            assert(FindCheckDescription(aged)!=nullptr);
            assert(FindCheckDescription(aged)==FindCheckDescription(id));
            assert(EntranceEndpointByCheck(aged)!=nullptr);
            assert(EntranceEndpointByCheck(aged)==EntranceEndpointByCheck(id));
        }
    }
    // Distinct server IDs are never conflated by the native report path.
    assert(granny+20'000'000LL!=granny+40'000'000LL);
    assert(SharedSceneTransitionLocationId(12'345'678LL)==12'345'678LL);
    std::cout<<"header age ID / physical source lookups passed\n";
}
