// Included inside CheckTracker after the scene/door display catalogues.
// Display only: never call transition, discovery, or check-reporting APIs here.
struct RoomDebugWorldLabel {
    SohExtreme::ExitPoint position;
    std::string text;
    bool operator==(const RoomDebugWorldLabel& other) const {
        return position.x == other.position.x && position.y == other.position.y &&
               position.z == other.position.z && text == other.text;
    }
};
static constexpr const char* roomDebugWorldTag = "soh_extreme_scene_debug";
static const CollisionHeader* roomDebugCollision = nullptr;
static std::vector<SohExtreme::ExitAnchor> roomDebugExitAnchors;
static std::vector<RoomDebugWorldLabel> roomDebugWorldLabels;

static void ResetRoomDebugWorldLabels() {
    NameTag_RemoveAllByTag(roomDebugWorldTag);
    roomDebugCollision = nullptr;
    roomDebugExitAnchors.clear();
    roomDebugWorldLabels.clear();
}

static int RoomDebugResolveExit(int entrance) {
    if (entrance == ENTR_RETURN_GROTTO) {
        const int grotto = Grotto_CurrentGrotto();
        if (grotto >= 0 && grotto < NUM_GROTTOS) return 0x800 + grotto;
        return gSaveContext.respawn[RESPAWN_MODE_RETURN].entranceIndex;
    }
    const int dynamic = SohExtreme::SceneDynamicExitIndex(entrance, gPlayState->curSpawn);
    if (dynamic >= 0) {
        // The adult castle fairy uses a separate index only in randomizer.
        return !IS_RANDO && dynamic == 2 ? ENTR_CASTLE_GROUNDS_GREAT_FAIRY_EXIT : dynamicExitList[dynamic];
    }
    return entrance;
}

static int RoomDebugOverriddenEntrance(int entrance) {
    if (!IS_RANDO || entrance < 0) return entrance;
    if ((gPlayState->sceneNum == SCENE_CASTLE_COURTYARD_GUARDS_DAY ||
         gPlayState->sceneNum == SCENE_CASTLE_COURTYARD_GUARDS_NIGHT) &&
        entrance == ENTR_CASTLE_GROUNDS_RAINBOW_BRIDGE_EXIT) return entrance;
    if (entrance < ENTR_MAX) return Entrance_GetOverride(entrance);
    // Grotto identities live outside the normal entrance table. Read the
    // configured override directly; the traversal API also changes respawns.
    const auto* overrides = Randomizer_GetEntranceOverrides();
    if (overrides) for (int i = 0; i < ENTRANCE_OVERRIDES_MAX_COUNT; ++i) {
        if (overrides[i].index == entrance) return overrides[i].override;
    }
    return entrance;
}

static std::string RoomDebugSceneExitText(int entrance, const std::string& prefix) {
    const int destination = RoomDebugOverriddenEntrance(RoomDebugResolveExit(entrance));
    int scene = -1;
    std::string name;
    const auto* data = EntranceTracker::GetEntranceData(destination);
    if (data) name = data->destination;
    for (const auto& row : roomDebugSceneTransitions) {
        if (row.entrance != destination) continue;
        scene = row.target;
        if (name.empty()) {
            name = row.name;
            const auto separator = name.find(" -> ");
            if (separator != std::string::npos) name.erase(0, separator + 4);
        }
        break;
    }
    if (scene < 0 && destination >= 0 && destination < ENTR_MAX) scene = gEntranceTable[destination].scene;
    if (name.empty() && scene >= 0) name = SohUtils::GetSceneName(scene);
    char id[32];
    std::snprintf(id, sizeof(id), "0x%04X", destination);
    if (name.empty()) name = std::string("Entrance ") + id;
    return prefix + " -> " + name + (scene >= 0 ? "\nScene: " + SohUtils::GetSceneName(scene) : "") +
           " (" + id + ")";
}

static void CacheRoomDebugExitAnchors() {
    const auto* header = gPlayState->colCtx.colHeader;
    if (header == roomDebugCollision) return;
    roomDebugCollision = header;
    roomDebugExitAnchors.clear();
    if (!header || !header->polyList || !header->vtxList || !header->surfaceTypeList) return;
    std::vector<SohExtreme::ExitTriangle> triangles;
    for (int i = 0; i < header->numPolygons; ++i) {
        auto* poly = &header->polyList[i];
        const int exit = SurfaceType_GetSceneExitIndex(&gPlayState->colCtx, poly, BGCHECK_SCENE);
        if (exit <= 0 || exit > 31) continue;
        SohExtreme::ExitTriangle triangle{ exit, {} };
        bool valid = true;
        for (int v = 0; v < 3; ++v) {
            const int index = COLPOLY_VTX_INDEX(poly->vtxData[v]);
            if (index >= header->numVertices) { valid = false; break; }
            const auto& p = header->vtxList[index];
            triangle.points[v] = { static_cast<float>(p.x), static_cast<float>(p.y), static_cast<float>(p.z) };
        }
        if (valid) triangles.push_back(triangle);
    }
    roomDebugExitAnchors = SohExtreme::SceneExitAnchors(triangles);
}

static int RoomDebugGrottoEntrance(const Actor* actor) {
    for (const auto& crossing : SohExtreme::kCrossings) {
        if (crossing.kind == SohExtreme::CrossingKind::GrottoLoad &&
            SohExtreme::CrossingScene(crossing.source) == SohExtreme::CrossingScene(gPlayState->sceneNum) &&
            crossing.content == (actor->params & 0xFF)) return static_cast<int>(crossing.location - 11000000);
    }
    // Also support physical grottos outside the AP catalogue.
    static constexpr int entrances[] = {
        ENTR_FAIRYS_FOUNTAIN_0, ENTR_GROTTOS_0, ENTR_GROTTOS_1, ENTR_GROTTOS_2, ENTR_GROTTOS_3,
        ENTR_GROTTOS_4, ENTR_GROTTOS_5, ENTR_GROTTOS_6, ENTR_GROTTOS_7, ENTR_GROTTOS_8,
        ENTR_GROTTOS_9, ENTR_GROTTOS_10, ENTR_GROTTOS_11, ENTR_GROTTOS_12, ENTR_GROTTOS_13
    };
    int index = ((actor->params >> 12) & 7) - 1;
    if (index < 0) index = actor->home.rot.z + 1;
    return index >= 0 && index < static_cast<int>(std::size(entrances)) ? entrances[index] : -1;
}

static std::string RoomDebugPassageText(const Actor* actor, int index) {
    const auto& door = gPlayState->transiActorCtx.list[index];
    const int type = (actor->params >> 6) & 7;
    const int room = gPlayState->roomCtx.curRoom.num;
    if (type == 1) {
        if (door.sides[0].room != room && door.sides[0].room != door.sides[1].room) return {};
        return "One-way drop -> Room " + std::to_string(door.sides[1].room);
    }
    if (type == 2 || type == 5) {
        const int side = GET_PLAYER(gPlayState)->actor.world.pos.y > actor->world.pos.y ? 0 : 1;
        return "Vertical passage " + std::to_string(index + 1) + " -> Room " +
               std::to_string(door.sides[1 - side].room);
    }
    std::string text = RoomDebugDestination(index);
    text.replace(0, 4, "Passage");
    return text;
}

static void UpdateRoomDebugWorldLabels() {
    if (!CVarGetInteger(CVAR_TRACKER_CHECK("RoomDebugDestinationLabels"), 0) ||
        !gPlayState || !GameInteractor::IsSaveLoaded(true)) {
        if (roomDebugCollision || !roomDebugWorldLabels.empty()) ResetRoomDebugWorldLabels();
        return;
    }
    CacheRoomDebugExitAnchors();
    std::vector<RoomDebugWorldLabel> next;
    if (gPlayState->setupExitList) for (const auto& anchor : roomDebugExitAnchors) {
        next.push_back({ anchor.position, RoomDebugSceneExitText(gPlayState->setupExitList[anchor.exit - 1],
                                                                "Scene exit " + std::to_string(anchor.exit)) });
    }
    for (const auto& list : gPlayState->actorCtx.actorLists) for (Actor* actor = list.head; actor; actor = actor->next) {
        std::string text;
        if (actor->id == ACTOR_EN_HOLL) {
            const int index = static_cast<uint16_t>(actor->params) >> 10;
            if (index >= gPlayState->transiActorCtx.numActors) continue;
            text = RoomDebugPassageText(actor, index);
        } else if (actor->id == ACTOR_DOOR_ANA) {
            const int entrance = RoomDebugGrottoEntrance(actor);
            if (entrance >= 0) text = RoomDebugSceneExitText(entrance, "Grotto");
        } else if (actor->id == ACTOR_DOOR_WARP1 || actor->id == ACTOR_EN_OWL) {
            const bool owl = actor->id == ACTOR_EN_OWL;
            // Arrival effects and decorative crystals do not transport Link.
            if (!owl && actor->params != -1 && actor->params != 0 && actor->params != 1) continue;
            for (const auto& row : roomDebugSceneTransitions) {
                if (row.source != gPlayState->sceneNum || std::string(row.kind) != (owl ? "OwlDrop" : "BlueWarp")) continue;
                text = RoomDebugSceneExitText(row.entrance, owl ? "Owl flight" : "Blue warp");
                break;
            }
        }
        if (!text.empty()) next.push_back({ { actor->world.pos.x, actor->world.pos.y, actor->world.pos.z }, text });
    }
    if (next == roomDebugWorldLabels) return;
    NameTag_RemoveAllByTag(roomDebugWorldTag);
    roomDebugWorldLabels = std::move(next);
    for (const auto& label : roomDebugWorldLabels) {
        NameTagOptions options = { roomDebugWorldTag, 55, { 140, 235, 255, 255 }, true };
        NameTag_RegisterAtWorldPosition(label.position.x, label.position.y, label.position.z, label.text.c_str(), options);
    }
}
