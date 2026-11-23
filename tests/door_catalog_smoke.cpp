#include "SceneTransitionChecks.h"
#include <cassert>
#include <cstdio>
int main() {
    int count = 0;
    for (const auto& c : SohExtreme::kCrossings) {
        if (c.kind != SohExtreme::CrossingKind::Door) continue;
        ++count;
        const auto* found = SohExtreme::FindDoorCrossing(c.source, c.door, c.fromRoom, c.toRoom, c.x, c.z, c.side);
        assert(found && found->location == c.location);
    }
    assert(count == 421);
    // A false room change does not satisfy the crossing journal without
    // moving across the authored physical plane.
    SohExtreme::CrossingJournal journal;
    const auto* c = SohExtreme::FindDoorCrossing(0,0,0,1,-455,455,0);
    assert(c);
    journal.BeginDoor(c,-445,455,1.0f,0.0f);
    assert(journal.AdvanceDoor(0,1,-445,455,true)==0);
    assert(journal.AdvanceDoor(0,1,-470,455,true)==c->location);
    std::puts("PASS: 421 door crossings resolve, and crossing journal requires actual travel");
}
