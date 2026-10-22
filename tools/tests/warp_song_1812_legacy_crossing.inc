// Retained 1.8.12 journal for exact baseline regression.
// Original full source SHA256: b68dbe6fc478ca7cd9938c1d6ec3a453c8296e844b78f550faac41ccab21a496

#include <cstdint>
#include <cmath>

namespace LegacyCrossing {

enum class CrossingKind { Entrance, GrottoLoad, GrottoExit, Door };
struct Crossing {
    int64_t location;
    CrossingKind kind;
    int source, target, entrance, content, door, fromRoom, toRoom, side;
    float x, z;
};

inline constexpr Crossing kCrossings[] = {
#include "SceneTransitionData.inc"
};

// Age/time variants share a physical portal identity, not separate checks.
inline int CrossingScene(int scene) {
    switch (scene) {
        case 28: case 29: return 27; // Market entrance
        case 31: return 30;          // Back alley
        case 33: case 34: return 32; // Market
        case 36: case 37: return 35; // Temple of Time courtyard
        case 70: return 69;          // Castle guards
        case 95: return 100;         // The two ages of castle grounds
        case 101: return 44;         // Kakariko bazaar resource alias
        default: return scene;
    }
}

inline const Crossing* FindSceneCrossing(int source, int entrance, int respawn,
                                         int content, int returnScene) {
    source=CrossingScene(source);
    // RespawnData stores the grotto byte as s8. Most valid grotto contents
    // have the high bit set, while the catalog records the unsigned value.
    content &= 0xFF;
    for (const auto& entry:kCrossings) {
        if (entry.kind==CrossingKind::Door) continue;
        if (entry.source>=0 && CrossingScene(entry.source)!=source) continue;
        if (entry.kind==CrossingKind::GrottoExit) {
            if (respawn==2 && entry.content==content &&
                CrossingScene(entry.target)==CrossingScene(returnScene)) return &entry;
        // FLOOR_EFFECT_2 is an ordinary scene portal. The engine uses -2
        // to preserve its respawn position, including all three ranch buildings.
        // Death/void/save returns (-1/1) must still never award a crossing.
        } else if ((respawn==0 || respawn==-2) && entry.entrance==entrance &&
                   (entry.kind!=CrossingKind::GrottoLoad || entry.content==content)) {
            return &entry;
        }
    }
    return nullptr;
}

inline const Crossing* FindDoorCrossing(int scene, int door, int from, int to, float x, float z, int side = -1) {
    for (const auto& entry:kCrossings) {
        if (entry.kind==CrossingKind::Door && entry.source==scene && entry.door==door &&
            entry.fromRoom==from && entry.toRoom==to &&
            (from!=to || entry.side==side) &&
            std::fabs(entry.x-x)<1.0f && std::fabs(entry.z-z)<1.0f) return &entry;
    }
    return nullptr;
}

// A request/open animation is not a crossing. Commit after Link passes through
// the door plane into the destination room; keep no actor pointers across loads.
class CrossingJournal {
  public:
    void Reset() { scene=nullptr; door=nullptr; }
    void BeginScene(const Crossing* crossing) { scene=crossing; door=nullptr; }
    int64_t Arrive(int destination) {
        const auto* crossing=scene;
        Reset();
        return crossing && CrossingScene(crossing->target)==CrossingScene(destination)
                   ? crossing->location : 0;
    }
    void BeginDoor(const Crossing* crossing, float playerX, float playerZ, float sinYaw, float cosYaw) {
        door=crossing;
        nx=sinYaw; nz=cosYaw;
        const float offset=door ? (playerX-door->x)*nx+(playerZ-door->z)*nz : 0;
        // Shutters accept an open action even within one unit of the plane.
        // Remember its side, not a minimum opening distance; the directed
        // portal resolves the side if Link starts exactly on the plane.
        startSide=!door ? 0.0f : offset>0.0f ? 1.0f : offset<0.0f ? -1.0f :
                  door->side==1 ? 1.0f : -1.0f;
    }
    int64_t AdvanceDoor(int currentScene, int room, float x, float z, bool alive) {
        if (!door) return 0;
        if (!alive || currentScene!=door->source || (room!=door->fromRoom && room!=door->toRoom)) {
            door=nullptr; return 0;
        }
        const float now=(x-door->x)*nx+(z-door->z)*nz;
        if (room==door->toRoom && std::fabs(now)>4.0f && now*startSide<0.0f) {
            const int64_t result=door->location;
            door=nullptr;
            return result;
        }
        return 0;
    }
  private:
    const Crossing* scene=nullptr;
    const Crossing* door=nullptr;
    float nx=0, nz=0, startSide=0;
};
} // namespace SohExtreme
