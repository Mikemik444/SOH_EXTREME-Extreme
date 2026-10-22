// Retained pre-observation registration/init bodies. These are executable
// baseline evidence, not an alternate implementation of the new policy.
namespace Legacy {

// Original soh/Enhancements/randomizer/ShufflePots.cpp SHA256: 7d43dc3a47acf8755a86aad8bf70a6daea40f48383454c66a4b30e6434b7a937

void RegisterShufflePots() {
    bool shouldRegister = IS_RANDO && RAND_GET_OPTION(RSK_SHUFFLE_POTS);

    COND_ID_HOOK(OnActorInit, ACTOR_OBJ_TSUBO, shouldRegister, [](void* actorRef) {
        Actor* actor = static_cast<Actor*>(actorRef);
        ObjTsubo* potActor = static_cast<ObjTsubo*>(actorRef);

        auto potIdentity = IdentifyPot(gPlayState->sceneNum, (s16)actor->world.pos.x, (s16)actor->world.pos.z);
        ObjectExtension::GetInstance().Set<CheckIdentity>(actor, std::move(potIdentity));
    });

    // Draw custom model for pot to indicate it holding a randomized item.
    COND_VB_SHOULD(VB_POT_SETUP_DRAW, shouldRegister, {
        ObjTsubo* potActor = va_arg(args, ObjTsubo*);
        if (ObjTsubo_RandomizerHoldsItem(potActor, gPlayState)) {
            potActor->actor.draw = (ActorFunc)ObjTsubo_RandomizerDraw;
            *should = false;
        }
    });

    // Do not spawn vanilla item from pot, instead spawn the ranomized item.
    COND_VB_SHOULD(VB_POT_DROP_ITEM, shouldRegister, {
        ObjTsubo* potActor = va_arg(args, ObjTsubo*);
        if (ObjTsubo_RandomizerHoldsItem(potActor, gPlayState)) {
            ObjTsubo_RandomizerSpawnCollectible(potActor, gPlayState);
            *should = false;
        }
    });

    // Unlock early Ganon's Boss Key doors to allow access to the pots there when pots are shuffled in dungeon
    COND_VB_SHOULD(VB_LOCK_BOSS_DOOR, shouldRegister, {
        DoorShutter* doorActor = va_arg(args, DoorShutter*);
        auto shufflePotSetting = RAND_GET_OPTION(RSK_SHUFFLE_POTS);
        if (gPlayState->sceneNum == SCENE_GANONS_TOWER && doorActor->dyna.actor.world.pos.y == 800 &&
            (shufflePotSetting.Is(RO_SHUFFLE_POTS_DUNGEONS) || shufflePotSetting.Is(RO_SHUFFLE_POTS_ALL))) {
            *should = false;
        }
    });
}

// Original soh/Enhancements/randomizer/ShuffleCrates.cpp SHA256: 6e6c06da4c997978cb7977ac691ec7c389201882290c4f89fbe4a3da6a024889

void ObjKibako2_RandomizerInit(void* actorRef) {
    Actor* actor = static_cast<Actor*>(actorRef);
    auto logicSetting = RAND_GET_OPTION(RSK_LOGIC_RULES);

    // don't shuffle the no logic crates when not in no logic
    if (actor->id != ACTOR_OBJ_KIBAKO2 || (logicSetting.IsNot(RO_LOGIC_NO_LOGIC) &&
                                           ((gPlayState->sceneNum == SCENE_GERUDOS_FORTRESS &&
                                             (s16)actor->world.pos.x == -4051 && (s16)actor->world.pos.z == -3429) ||
                                            (gPlayState->sceneNum == SCENE_GERUDOS_FORTRESS &&
                                             (s16)actor->world.pos.x == -4571 && (s16)actor->world.pos.z == -3429) ||
                                            (gPlayState->sceneNum == SCENE_GERUDOS_FORTRESS &&
                                             (s16)actor->world.pos.x == 3443 && (s16)actor->world.pos.z == -4876) ||
                                            (gPlayState->sceneNum == SCENE_GERUDO_VALLEY &&
                                             (s16)actor->world.pos.x == -764 && (s16)actor->world.pos.z == 148) ||
                                            (gPlayState->sceneNum == SCENE_GERUDO_VALLEY &&
                                             (s16)actor->world.pos.x == -860 && (s16)actor->world.pos.z == -125) ||
                                            (gPlayState->sceneNum == SCENE_GERUDO_VALLEY &&
                                             (s16)actor->world.pos.x == -860 && (s16)actor->world.pos.z == -150) ||
                                            (gPlayState->sceneNum == SCENE_GERUDO_VALLEY &&
                                             (s16)actor->world.pos.x == -860 && (s16)actor->world.pos.z == -90))))
        return;

    ObjKibako2* crateActor = static_cast<ObjKibako2*>(actorRef);

    auto crateIdentity = IdentifyCrate(gPlayState->sceneNum, (s16)actor->world.pos.x, (s16)actor->world.pos.z);
    ObjectExtension::GetInstance().Set<CheckIdentity>(actor, std::move(crateIdentity));
}

void ObjKibako_RandomizerInit(void* actorRef) {
    Actor* actor = static_cast<Actor*>(actorRef);

    if (actor->id != ACTOR_OBJ_KIBAKO)
        return;

    ObjKibako* smallCrateActor = static_cast<ObjKibako*>(actorRef);

    auto crateIdentity = IdentifySmallCrate(gPlayState->sceneNum, (s16)actor->home.pos.x, (s16)actor->home.pos.z);
    ObjectExtension::GetInstance().Set<CheckIdentity>(actor, std::move(crateIdentity));
}

void RegisterShuffleCrates() {
    bool shouldRegister = IS_RANDO && RAND_GET_OPTION(RSK_SHUFFLE_CRATES);

    COND_ID_HOOK(OnActorInit, ACTOR_OBJ_KIBAKO2, shouldRegister, ObjKibako2_RandomizerInit);

    COND_VB_SHOULD(VB_CRATE_SETUP_DRAW, shouldRegister, {
        ObjKibako2* crateActor = va_arg(args, ObjKibako2*);
        if (ObjKibako2_RandomizerHoldsItem(crateActor, gPlayState)) {
            crateActor->dyna.actor.draw = (ActorFunc)ObjKibako2_RandomizerDraw;
            *should = false;
        }
    });

    COND_VB_SHOULD(VB_CRATE_DROP_ITEM, shouldRegister, {
        ObjKibako2* crateActor = va_arg(args, ObjKibako2*);
        if (ObjKibako2_RandomizerHoldsItem(crateActor, gPlayState)) {
            ObjKibako2_RandomizerSpawnCollectible(crateActor, gPlayState);
            *should = false;
        } else {
            *should = true;
        }
    });

    COND_ID_HOOK(OnActorInit, ACTOR_OBJ_KIBAKO, shouldRegister, ObjKibako_RandomizerInit);

    COND_VB_SHOULD(VB_SMALL_CRATE_SETUP_DRAW, shouldRegister, {
        ObjKibako* smallCrateActor = va_arg(args, ObjKibako*);
        if (ObjKibako_RandomizerHoldsItem(smallCrateActor, gPlayState)) {
            smallCrateActor->actor.draw = (ActorFunc)ObjKibako_RandomizerDraw;
            *should = false;
        }
    });

    COND_VB_SHOULD(VB_SMALL_CRATE_DROP_ITEM, shouldRegister, {
        ObjKibako* smallCrateActor = va_arg(args, ObjKibako*);
        if (ObjKibako_RandomizerHoldsItem(smallCrateActor, gPlayState)) {
            ObjKibako_RandomizerSpawnCollectible(smallCrateActor, gPlayState);
            *should = false;
        } else {
            *should = true;
        }
    });

    // Prevent the randomized items from the "decoy" crates from immediately despawning
    COND_VB_SHOULD(VB_ITEM00_KILL, shouldRegister, {
        if (RAND_GET_OPTION(RSK_LOGIC_RULES).Is(RO_LOGIC_NO_LOGIC) && gPlayState->sceneNum == SCENE_GERUDOS_FORTRESS) {
            EnItem00* item00 = va_arg(args, EnItem00*);

            if (item00->actor.world.pos.x < -3500.0f) {
                *should &= item00->actor.world.pos.y < -10000.0f;
            }
        }
    });
}

} // namespace Legacy
// Unchanged ObjTsubo_RandomizerHoldsItem SHA256: c95a03ae52e99240fb4c61f11b53399cfac9be2376635e41d28d405e229f5d9e
// Unchanged ObjTsubo_RandomizerSpawnCollectible SHA256: 2d8c923080f7d551558e9c67b0c5ab902e1f7e3cd2aad5ef725e40eeeaca079d
// Unchanged ObjKibako2_RandomizerHoldsItem SHA256: 85107302d09cf643c53c9c492c3e3ae92729f44104ec2987f805a671374ba688
// Unchanged ObjKibako_RandomizerHoldsItem SHA256: d1bdc8958cbe30fc08db1358aacb37ffe506c0c3c1c339495cba068ae3c47e5c
// Unchanged ObjKibako2_RandomizerSpawnCollectible SHA256: d88fdd7ab1d5026468fac66ad421fb8bbe705bd16158e4c1bfdbef2dd58436c8
// Unchanged ObjKibako_RandomizerSpawnCollectible SHA256: 5dd1e2a87d3db7005d0aa93ca4878effb7aabadbaac202d03cf090fb2efc34aa
