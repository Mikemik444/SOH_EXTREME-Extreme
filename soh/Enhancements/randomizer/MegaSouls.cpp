#include "soh/Enhancements/game-interactor/GameInteractor.h"
#include "soh/Enhancements/randomizer/SeedContext.h"
#include "soh/Enhancements/randomizer/static_data.h"
#include "soh/Enhancements/randomizer/location.h"
#include "soh/Network/Archipelago/ArchipelagoC.h"
#include "soh/ShipInit.hpp"
#include "soh/SaveManager.h"
#include "soh/ObjectExtension/ActorListIndex.h"
#include "soh/ObjectExtension/ObjectExtension.h"
#include "soh/Enhancements/randomizer/randomizer_entrance_tracker.h"

#include <algorithm>
#include <array>
#include <cstdint>
#include <cstdio>
#include <unordered_map>
#include <vector>
#include <mutex>
#include "soh/Enhancements/randomizer/EnemyDropPolicy.h"
#include "soh/Enhancements/randomizer/EnemyDropBridge.h"
#include "soh/Enhancements/randomizer/EnemySpawnCatalog.h"
#include "soh/Enhancements/randomizer/FishingSoulAccess.h"

extern "C" bool Archipelago_IsCurrentSaveActive(void);

extern "C" {
#include "z64.h"
#include "macros.h"
#include "functions.h"
#include "variables.h"
#include "overlays/actors/ovl_En_Wood02/z_en_wood02.h"
#include "overlays/actors/ovl_Fishing/z_fishing.h"
extern PlayState* gPlayState;
}

// Mega Randomizer category-soul runtime enforcement.
// Enemy Soul "Gone Until Found" deliberately lets the actor initialize so
// scene scripts and puzzle setup still run.  After init, the locked enemy is
// hidden and frozen until its Soul is obtained.
static bool MegaHas(RandomizerInf inf) {
    return Flags_GetRandomizerInf(inf);
}

extern "C" bool MegaSoul_IsFishingOwnerPresent(void) {
    return !IS_RANDO || !RAND_GET_OPTION(RSK_SHUFFLE_NPC_SOUL) || MegaHas(RAND_INF_NPC_SOUL);
}

extern "C" bool MegaSoul_ArePondFishPresent(void) {
    if (!IS_RANDO) return true;
    const int mode = RAND_GET_OPTION(RSK_SHUFFLE_ANIMAL_SOUL).Get();
    if (mode == 0) return true;
    return MegaHas(mode == 1 ? RAND_INF_ANIMAL_SOUL : RAND_INF_ANIMAL_SOUL_FISH);
}

extern "C" bool MegaSoul_CanTalkToFishingOwner(void) {
    return MegaSoul_IsFishingOwnerPresent() &&
           (!IS_RANDO || !RAND_GET_OPTION(RSK_SHUFFLE_SPEAK) || MegaHas(RAND_INF_CAN_SPEAK_HYLIAN));
}

extern "C" bool MegaSoul_CanUseCrate(void) {
    return !IS_RANDO || !RAND_GET_OPTION(RSK_SHUFFLE_CRATE_SOUL) || MegaHas(RAND_INF_CRATE_SOUL);
}

static bool IsMegaAnimalActor(s16 id) {
    switch (id) {
        case ACTOR_EN_COW:
        case ACTOR_EN_NIW:
        case ACTOR_EN_DOG:
        case ACTOR_EN_FISH:
        case ACTOR_EN_INSECT:
        case ACTOR_EN_BUTTE:
        case ACTOR_EN_FR:
        case ACTOR_EN_HORSE:
        case ACTOR_EN_HORSE_NORMAL:
            return true;
        default:
            return false;
    }
}

static bool IsMegaPotActor(s16 id) {
    switch (id) {
        case ACTOR_OBJ_TSUBO:
        case ACTOR_EN_TUBO_TRAP:
        case ACTOR_EN_WALL_TUBO:
            return true;
        default:
            return false;
    }
}

static bool IsMegaCrateActor(s16 id) {
    return id == ACTOR_OBJ_KIBAKO || id == ACTOR_OBJ_KIBAKO2;
}

static bool IsMegaRockActor(s16 id) {
    return id == ACTOR_EN_ISHI || id == ACTOR_OBJ_BOMBIWA || id == ACTOR_OBJ_HAMISHI;
}

static bool IsMegaGrassActor(s16 id) {
    return id == ACTOR_EN_KUSA;
}

static bool IsMegaScrubActor(s16 id) {
    // ACTOR_EN_DNS is the business/sanity Deku Scrub used by the randomized
    // scrub checks. ACTOR_EN_SHOPNUTS is its above-ground sales form.
    return id == ACTOR_EN_DNS || id == ACTOR_EN_SHOPNUTS;
}

static bool IsMegaBushActor(const Actor* actor) {
    if (actor == nullptr || actor->id != ACTOR_EN_WOOD02) {
        return false;
    }
    const s16 type = actor->params & 0xFF;
    return type >= WOOD_BUSH_GREEN_SMALL && type <= WOOD_BUSH_BLACK_LARGE_SPAWNED;
}

static bool IsMegaTreeActor(const Actor* actor) {
    if (actor == nullptr || actor->id != ACTOR_EN_WOOD02) {
        return false;
    }
    const s16 type = actor->params & 0xFF;
    return type >= WOOD_TREE_CONICAL_LARGE && type <= WOOD_TREE_KAKARIKO_ADULT;
}

static bool IsMegaBeehiveActor(s16 id) {
    return id == ACTOR_OBJ_COMB;
}

static bool IsMegaSignActor(s16 id) {
    return id == ACTOR_EN_KANBAN;
}

// En_Sw is shared by ordinary Skulltulas/Skullwalltulas and Gold Skulltulas.
// Only the nonzero high type bits are Gold Skulltulas; ordinary Skulltulas are
// normal Enemy Drop checks and must not be filtered out with the GS system.
static bool IsGoldSkulltulaActor(const Actor* actor) {
    if (actor == nullptr) {
        return false;
    }
    if (actor->id == ACTOR_EN_SI) {
        return true;
    }
    return actor->id == ACTOR_EN_SW && (((actor->params & 0xE000) >> 13) != 0);
}

static bool IsOrdinarySkulltulaActor(const Actor* actor) {
    if (actor == nullptr) {
        return false;
    }

    // En_St is the normal/big/invisible Skulltula actor. En_Sw type 0 is the
    // wall-crawling Skullwalltula; nonzero En_Sw type bits are Gold Skulltulas.
    // Both ordinary families belong to Skulltula Soul and to Enemy Defeat sanity.
    return actor->id == ACTOR_EN_ST ||
           (actor->id == ACTOR_EN_SW && !IsGoldSkulltulaActor(actor));
}

static bool IsMegaNpcSoulActor(const Actor* actor) {
    if (actor == nullptr) {
        return false;
    }

    // Fishing_Init changes only the owner to params=EN_FISH_OWNER. Fish keep
    // params 100..116 (and aquarium=200); they must never inherit NPC Soul.
    if (actor->id == ACTOR_FISHING) {
        return actor->params < EN_FISH_PARAM;
    }

    // Animals, business scrubs and Gold Skulltulas have their own Soul systems.
    if (IsMegaAnimalActor(actor->id) || IsMegaScrubActor(actor->id) ||
        actor->id == ACTOR_EN_SW || actor->id == ACTOR_EN_SI) {
        return false;
    }

    if (actor->category == ACTORCAT_NPC) {
        return true;
    }

    // Some talk/merchant/story actors are not categorized as ACTORCAT_NPC.
    // Mirror the broader native location-side NPC list so "NPC Soul" really
    // means every NPC disappears, not merely actors in one category.
    switch (actor->id) {
        case ACTOR_BG_ZG:
        case ACTOR_DEMO_DU:
        case ACTOR_DEMO_EC:
        case ACTOR_DEMO_EXT:
        case ACTOR_DEMO_GO:
        case ACTOR_DEMO_IK:
        case ACTOR_DEMO_IM:
        case ACTOR_DEMO_SA:
        case ACTOR_EN_ANI:
        case ACTOR_EN_BOM_BOWL_MAN:
        case ACTOR_EN_CS:
        case ACTOR_EN_DAIKU:
        case ACTOR_EN_DAIKU_KAKARIKO:
        case ACTOR_EN_DIVING_GAME:
        case ACTOR_EN_DNT_JIJI:
        case ACTOR_EN_DS:
        case ACTOR_EN_DU:
        case ACTOR_EN_FU:
        case ACTOR_EN_GB:
        case ACTOR_EN_GE1:
        case ACTOR_EN_GE2:
        case ACTOR_EN_GE3:
        case ACTOR_EN_GM:
        case ACTOR_EN_GO:
        case ACTOR_EN_GO2:
        case ACTOR_EN_GUEST:
        case ACTOR_EN_HEISHI1:
        case ACTOR_EN_HEISHI2:
        case ACTOR_EN_HEISHI3:
        case ACTOR_EN_HEISHI4:
        case ACTOR_EN_HS:
        case ACTOR_EN_HS2:
        case ACTOR_EN_HY:
        case ACTOR_EN_IN:
        case ACTOR_EN_JS:
        case ACTOR_EN_JSJUTAN:
        case ACTOR_EN_KAKASI:
        case ACTOR_EN_KAKASI3:
        case ACTOR_EN_KO:
        case ACTOR_EN_KZ:
        case ACTOR_EN_MA1:
        case ACTOR_EN_MA2:
        case ACTOR_EN_MA3:
        case ACTOR_EN_MD:
        case ACTOR_EN_MK:
        case ACTOR_EN_MM:
        case ACTOR_EN_MM2:
        case ACTOR_EN_MS:
        case ACTOR_EN_MU:
        case ACTOR_EN_NB:
        case ACTOR_EN_NIW_GIRL:
        case ACTOR_EN_NIW_LADY:
        case ACTOR_EN_OE2:
        case ACTOR_EN_OSSAN:
        case ACTOR_EN_OWL:
        case ACTOR_EN_PO_RELAY:
        case ACTOR_EN_RL:
        case ACTOR_EN_RU1:
        case ACTOR_EN_RU2:
        case ACTOR_EN_SA:
        case ACTOR_EN_SSH:
        case ACTOR_EN_STH:
        case ACTOR_EN_SYATEKI_MAN:
        case ACTOR_EN_TA:
        case ACTOR_EN_TAKARA_MAN:
        case ACTOR_EN_TG:
        case ACTOR_EN_TK:
        case ACTOR_EN_TORYO:
        case ACTOR_EN_TR:
        case ACTOR_EN_XC:
        case ACTOR_EN_ZL1:
        case ACTOR_EN_ZL2:
        case ACTOR_EN_ZL3:
        case ACTOR_EN_ZL4:
        case ACTOR_EN_ZO:
        case ACTOR_FISHING:
        case ACTOR_ITEM_INBOX:
        case ACTOR_OBJ_DEKUJR:
            return true;
        default:
            return false;
    }
}

static int GetEnemySoulMode() {
    // 0 = Off, 1 = All Enemies as 1, 2 = Individual Enemies.
    return RAND_GET_OPTION(RSK_SHUFFLE_ENEMY_SOUL).Get();
}

static int GetEnemySoulBehavior() {
    // 0 = Gone Until Found, 1 = Invincible Until Found.
    return RAND_GET_OPTION(RSK_ENEMY_SOUL_BEHAVIOR).Get();
}

static RandomizerInf EnemySoulInfForActorId(int16_t actorId) {
    // Do not treat the generic Enemy Soul as a wildcard here. Mode 1 checks
    // RAND_INF_ENEMY_SOUL explicitly in HasRequiredEnemySoul(); mode 2 must only
    // honor the exact species flag. This also repairs saves where an older AP
    // client accidentally set the generic flag after receiving one individual Soul.
    switch (actorId) {
        case ACTOR_EN_TEST: return RAND_INF_ENEMY_SOUL_STALFOS;
        case ACTOR_EN_OKUTA: return RAND_INF_ENEMY_SOUL_OCTOROK;
        case ACTOR_EN_WALLMAS: return RAND_INF_ENEMY_SOUL_WALLMASTER;
        case ACTOR_EN_DODONGO: return RAND_INF_ENEMY_SOUL_DODONGO;
        case ACTOR_EN_FIREFLY: return RAND_INF_ENEMY_SOUL_KEESE;
        case ACTOR_EN_TITE: return RAND_INF_ENEMY_SOUL_TEKTITE;
        case ACTOR_EN_PEEHAT: return RAND_INF_ENEMY_SOUL_PEAHAT;
        case ACTOR_EN_ZF: return RAND_INF_ENEMY_SOUL_LIZALFOS_DINOLFOS;
        case ACTOR_EN_GOMA: return RAND_INF_ENEMY_SOUL_GOHMA_LARVA;
        case ACTOR_EN_BUBBLE: return RAND_INF_ENEMY_SOUL_SHABOM;
        case ACTOR_EN_DODOJR: return RAND_INF_ENEMY_SOUL_BABY_DODONGO;
        case ACTOR_EN_BILI:
        case ACTOR_EN_VALI: return RAND_INF_ENEMY_SOUL_BIRI_BARI;
        case ACTOR_EN_TP: return RAND_INF_ENEMY_SOUL_TAILPASARAN;
        case ACTOR_EN_BW: return RAND_INF_ENEMY_SOUL_TORCH_SLUG;
        case ACTOR_EN_MB: return RAND_INF_ENEMY_SOUL_MOBLIN;
        case ACTOR_EN_AM: return RAND_INF_ENEMY_SOUL_ARMOS;
        case ACTOR_EN_DEKUBABA:
        case ACTOR_EN_KAREBABA: return RAND_INF_ENEMY_SOUL_DEKU_BABA;
        case ACTOR_EN_DEKUNUTS:
        case ACTOR_EN_HINTNUTS: return RAND_INF_ENEMY_SOUL_DEKU_SCRUB;
        case ACTOR_EN_BB: return RAND_INF_ENEMY_SOUL_BUBBLE;
        case ACTOR_EN_VM: return RAND_INF_ENEMY_SOUL_BEAMOS;
        case ACTOR_EN_FLOORMAS: return RAND_INF_ENEMY_SOUL_FLOORMASTER;
        case ACTOR_EN_RD: return RAND_INF_ENEMY_SOUL_REDEAD_GIBDO;
        case ACTOR_EN_FD: return RAND_INF_ENEMY_SOUL_FLARE_DANCER;
        case ACTOR_EN_DH: return RAND_INF_ENEMY_SOUL_DEAD_HAND;
        case ACTOR_EN_SB: return RAND_INF_ENEMY_SOUL_SHELL_BLADE;
        case ACTOR_EN_RR: return RAND_INF_ENEMY_SOUL_LIKE_LIKE;
        case ACTOR_EN_NY: return RAND_INF_ENEMY_SOUL_SPIKE;
        case ACTOR_EN_ANUBICE: return RAND_INF_ENEMY_SOUL_ANUBIS;
        case ACTOR_EN_IK: return RAND_INF_ENEMY_SOUL_IRON_KNUCKLE;
        case ACTOR_EN_SKJ: return RAND_INF_ENEMY_SOUL_SKULL_KID;
        case ACTOR_EN_TUBO_TRAP: return RAND_INF_ENEMY_SOUL_FLYING_POT;
        case ACTOR_EN_FZ: return RAND_INF_ENEMY_SOUL_FREEZARD;
        case ACTOR_EN_EIYER:
        case ACTOR_EN_WEIYER: return RAND_INF_ENEMY_SOUL_STINGER;
        case ACTOR_EN_WF: return RAND_INF_ENEMY_SOUL_WOLFOS;
        case ACTOR_EN_CROW: return RAND_INF_ENEMY_SOUL_GUAY;
        case ACTOR_EN_BA: return RAND_INF_ENEMY_SOUL_JABU_TENTACLE;
        case ACTOR_EN_TORCH2: return RAND_INF_ENEMY_SOUL_DARK_LINK;
        case ACTOR_DOOR_KILLER: return RAND_INF_ENEMY_SOUL_DOOR_TRAP;
        case ACTOR_EN_YUKABYUN: return RAND_INF_ENEMY_SOUL_FLYING_FLOOR_TILE;
        case ACTOR_EN_GELDB: return RAND_INF_ENEMY_SOUL_GERUDO_THIEF;
        case ACTOR_EN_PO_SISTERS: return RAND_INF_ENEMY_SOUL_POE_SISTER;
        case ACTOR_EN_POH:
        case ACTOR_EN_PO_FIELD: return RAND_INF_ENEMY_SOUL_POE;
        case ACTOR_EN_REEBA: return RAND_INF_ENEMY_SOUL_LEEVER;
        case ACTOR_EN_SKB: return RAND_INF_ENEMY_SOUL_STALCHILD;
        case ACTOR_EN_BIGOKUTA: return RAND_INF_ENEMY_SOUL_BIG_OCTO;
        case ACTOR_EN_DHA: return RAND_INF_ENEMY_SOUL_DEAD_HAND;
        default: return RAND_INF_MAX;
    }
}

static bool IsStructuralArmosStatue(const Actor* actor) {
    // En_Am params 0 is ARMOS_STATUE: a pushable structural puzzle statue.
    // It is not an enemy and must never be hidden or gated by Armos Soul.
    return actor != nullptr && actor->id == ACTOR_EN_AM && actor->params == 0;
}

static RandomizerInf EnemySoulInfForActor(const Actor* actor) {
    if (actor == nullptr || IsStructuralArmosStatue(actor)) {
        return RAND_INF_MAX;
    }
    return EnemySoulInfForActorId(actor->id);
}

extern "C" bool MegaSoul_HasEnemyDefeatSoul(int16_t actorId) {
    // Ordinary Skulltulas use the dedicated Skulltula Soul, matching the runtime
    // spawn/damage gate and the AP per-placement rule.
    if (actorId == ACTOR_EN_ST || actorId == ACTOR_EN_SW) {
        return !RAND_GET_OPTION(RSK_SHUFFLE_SKULLTULA_SOUL) || MegaHas(RAND_INF_SKULLTULA_SOUL);
    }

    const int mode = GetEnemySoulMode();
    if (mode == 0) return true;
    if (mode == 1) return MegaHas(RAND_INF_ENEMY_SOUL);
    const RandomizerInf inf = EnemySoulInfForActorId(actorId);
    return inf == RAND_INF_MAX || MegaHas(inf);
}

static RandomizerCheck EnemyDropCheckForActor(const Actor* actor) {
    if (actor == nullptr || IsStructuralArmosStatue(actor)) {
        return RC_UNKNOWN_CHECK;
    }

    // Keep this taxonomy identical to the individual Enemy Soul mapping. Bosses,
    // Business Scrubs, Gold Skulltulas and flying pots are intentionally not
    // ordinary Enemy Drop checks.
    switch (actor->id) {
        case ACTOR_EN_TEST: return RC_ENEMY_DROP_STALFOS;
        case ACTOR_EN_OKUTA: return RC_ENEMY_DROP_OCTOROK;
        case ACTOR_EN_WALLMAS: return RC_ENEMY_DROP_WALLMASTER;
        case ACTOR_EN_DODONGO: return RC_ENEMY_DROP_DODONGO;
        case ACTOR_EN_FIREFLY: return RC_ENEMY_DROP_KEESE;
        case ACTOR_EN_TITE: return RC_ENEMY_DROP_TEKTITE;
        case ACTOR_EN_PEEHAT: return RC_ENEMY_DROP_PEAHAT;
        case ACTOR_EN_ZF: return RC_ENEMY_DROP_LIZALFOS_DINOLFOS;
        case ACTOR_EN_GOMA: return RC_ENEMY_DROP_GOHMA_LARVA;
        case ACTOR_EN_BUBBLE: return RC_ENEMY_DROP_SHABOM;
        case ACTOR_EN_DODOJR: return RC_ENEMY_DROP_BABY_DODONGO;
        case ACTOR_EN_BILI: return RC_ENEMY_DROP_BIRI_BARI;
        case ACTOR_EN_VALI: return RC_ENEMY_DROP_BIRI_BARI;
        case ACTOR_EN_TP: return RC_ENEMY_DROP_TAILPASARAN;
        case ACTOR_EN_BW: return RC_ENEMY_DROP_TORCH_SLUG;
        case ACTOR_EN_MB: return RC_ENEMY_DROP_MOBLIN;
        case ACTOR_EN_AM: return RC_ENEMY_DROP_ARMOS;
        case ACTOR_EN_DEKUBABA: return RC_ENEMY_DROP_DEKU_BABA;
        case ACTOR_EN_KAREBABA: return RC_ENEMY_DROP_DEKU_BABA;
        case ACTOR_EN_DEKUNUTS: return RC_ENEMY_DROP_DEKU_SCRUB;
        case ACTOR_EN_HINTNUTS: return RC_ENEMY_DROP_DEKU_SCRUB;
        case ACTOR_EN_BB: return RC_ENEMY_DROP_BUBBLE;
        case ACTOR_EN_VM: return RC_ENEMY_DROP_BEAMOS;
        case ACTOR_EN_FLOORMAS: return RC_ENEMY_DROP_FLOORMASTER;
        case ACTOR_EN_RD: return RC_ENEMY_DROP_REDEAD_GIBDO;
        case ACTOR_EN_FD: return RC_ENEMY_DROP_FLARE_DANCER;
        case ACTOR_EN_DH: return RC_ENEMY_DROP_DEAD_HAND;
        case ACTOR_EN_SB: return RC_ENEMY_DROP_SHELL_BLADE;
        case ACTOR_EN_RR: return RC_ENEMY_DROP_LIKE_LIKE;
        case ACTOR_EN_NY: return RC_ENEMY_DROP_SPIKE;
        case ACTOR_EN_ANUBICE: return RC_ENEMY_DROP_ANUBIS;
        case ACTOR_EN_IK: return RC_ENEMY_DROP_IRON_KNUCKLE;
        case ACTOR_EN_SKJ: return RC_ENEMY_DROP_SKULL_KID;
        case ACTOR_EN_FZ: return RC_ENEMY_DROP_FREEZARD;
        case ACTOR_EN_EIYER: return RC_ENEMY_DROP_STINGER;
        case ACTOR_EN_WEIYER: return RC_ENEMY_DROP_STINGER;
        case ACTOR_EN_WF: return RC_ENEMY_DROP_WOLFOS;
        case ACTOR_EN_CROW: return RC_ENEMY_DROP_GUAY;
        case ACTOR_EN_BA: return RC_ENEMY_DROP_JABU_JABU_TENTACLE;
        case ACTOR_EN_TORCH2: return RC_ENEMY_DROP_DARK_LINK;
        default: return RC_UNKNOWN_CHECK;
    }
}

static RandomizerInf AnimalSoulInfForActor(const Actor* actor) {
    if (actor == nullptr) return RAND_INF_MAX;
    // Same rule as enemies: generic Animal Soul is only valid in mode 1.
    switch (actor->id) {
        case ACTOR_EN_COW: return RAND_INF_ANIMAL_SOUL_COW;
        case ACTOR_EN_NIW: return RAND_INF_ANIMAL_SOUL_CUCCO;
        case ACTOR_EN_DOG: return RAND_INF_ANIMAL_SOUL_DOG;
        case ACTOR_EN_FISH: return RAND_INF_ANIMAL_SOUL_FISH;
        case ACTOR_EN_INSECT: return RAND_INF_ANIMAL_SOUL_BUG;
        case ACTOR_EN_BUTTE: return RAND_INF_ANIMAL_SOUL_BUTTERFLY;
        case ACTOR_EN_FR: return RAND_INF_ANIMAL_SOUL_FROG;
        case ACTOR_EN_HORSE:
        case ACTOR_EN_HORSE_NORMAL: return RAND_INF_ANIMAL_SOUL_HORSE;
        default: return RAND_INF_MAX;
    }
}

static bool HasRequiredEnemySoul(const Actor* actor) {
    if (actor == nullptr) {
        return true;
    }

    // En_Sw ordinary Skulltulas use the dedicated Skulltula Soul rather than
    // silently bypassing Soul gating in individual-enemy mode.
    if (IsOrdinarySkulltulaActor(actor)) {
        return !RAND_GET_OPTION(RSK_SHUFFLE_SKULLTULA_SOUL) || MegaHas(RAND_INF_SKULLTULA_SOUL);
    }

    const int mode = GetEnemySoulMode();
    if (mode == 0) return true;
    if (mode == 1) return MegaHas(RAND_INF_ENEMY_SOUL);
    const RandomizerInf inf = EnemySoulInfForActor(actor);
    // Unknown/special enemy actors remain usable until an explicit Soul mapping
    // exists; every finite Enemy Defeat placement in the current table is audited
    // against the explicit mappings/category systems.
    return inf == RAND_INF_MAX || MegaHas(inf);
}

static bool HasRequiredAnimalSoul(const Actor* actor) {
    const int mode = RAND_GET_OPTION(RSK_SHUFFLE_ANIMAL_SOUL).Get();
    if (mode == 0) return true;
    if (mode == 1) return MegaHas(RAND_INF_ANIMAL_SOUL);
    const RandomizerInf inf = AnimalSoulInfForActor(actor);
    return inf == RAND_INF_MAX || MegaHas(inf);
}

static bool IsMegaEnemySoulActor(const Actor* actor) {
    if (actor == nullptr || IsStructuralArmosStatue(actor)) {
        return false;
    }

    if (IsMegaScrubActor(actor->id) || IsGoldSkulltulaActor(actor) || (IsMegaPotActor(actor->id) && actor->id != ACTOR_EN_TUBO_TRAP)) {
        return false;
    }

    // Most enemies are ACTORCAT_ENEMY. A few hostile actors, such as Door_Killer,
    // use another actor category; an explicit Enemy Soul mapping still makes
    // them full members of the Enemy Soul/Enemy Defeat system.
    return IsOrdinarySkulltulaActor(actor) || actor->category == ACTORCAT_ENEMY ||
           EnemySoulInfForActorId(actor->id) != RAND_INF_MAX;
}

static bool IsSkulltulaSoulLocked(const Actor* actor) {
    if (actor == nullptr || !RAND_GET_OPTION(RSK_SHUFFLE_SKULLTULA_SOUL)) {
        return false;
    }

    // Skulltula Soul owns every Skulltula-family actor, including Gold
    // Skulltulas.  Keep this separate from Enemy Soul so Gold Skulltulas do
    // not accidentally bypass the runtime lock merely because they are not
    // Enemy Drop locations.
    return (actor->id == ACTOR_EN_ST || actor->id == ACTOR_EN_SW || actor->id == ACTOR_EN_SI) &&
           !MegaHas(RAND_INF_SKULLTULA_SOUL);
}

static bool IsMegaEnemySoulLocked(const Actor* actor) {
    return (GetEnemySoulMode() != 0 &&
            IsMegaEnemySoulActor(actor) &&
            !HasRequiredEnemySoul(actor)) ||
           IsSkulltulaSoulLocked(actor);
}

static bool IsMegaEnemySoulGone(const Actor* actor) {
    return GetEnemySoulBehavior() == 0 && IsMegaEnemySoulLocked(actor);
}

static bool IsMegaEnemySoulInvincible(const Actor* actor) {
    return GetEnemySoulBehavior() == 1 && IsMegaEnemySoulLocked(actor);
}

struct GoneEnemyRuntimeState {
    ActorFunc draw = nullptr;
    bool attentionEnabled = false;
};

static std::unordered_map<Actor*, GoneEnemyRuntimeState> gGoneEnemyRuntimeStates;

static void HideGoneEnemy(Actor* actor) {
    if (actor == nullptr || !IsMegaEnemySoulGone(actor)) {
        return;
    }

    auto [it, inserted] = gGoneEnemyRuntimeStates.try_emplace(actor);
    if (inserted) {
        it->second.draw = actor->draw;
        it->second.attentionEnabled = (actor->flags & ACTOR_FLAG_ATTENTION_ENABLED) != 0;
    }

    // Keep the initialized actor alive for scene/puzzle bookkeeping, but make
    // it completely absent from gameplay while its Soul is missing.
    actor->draw = nullptr;
    actor->flags &= ~ACTOR_FLAG_ATTENTION_ENABLED;
    actor->isTargeted = false;
    actor->sfx = 0;

    // Incoming damage is also hard-blocked by MegaSoul_CanDamageEnemy(), but
    // clear any queued hit here so a hit from a previous frame cannot leak
    // through while the actor is transitioning into the hidden state.
    actor->colChkInfo.damage = 0;
    if (actor->colChkInfo.health == 0) {
        actor->colChkInfo.health = 1;
    }
}

static void RestoreGoneEnemy(Actor* actor) {
    if (actor == nullptr) {
        return;
    }

    auto it = gGoneEnemyRuntimeStates.find(actor);
    if (it == gGoneEnemyRuntimeStates.end()) {
        return;
    }

    actor->draw = it->second.draw;
    if (it->second.attentionEnabled) {
        actor->flags |= ACTOR_FLAG_ATTENTION_ENABLED;
    }

    gGoneEnemyRuntimeStates.erase(it);
}

extern "C" bool MegaSoul_CanDamageEnemy(Actor* actor) {
    // Both locked behaviors reject damage from Link.  "Invincible" continues
    // running AI/collision; "Gone" is additionally hidden/frozen below.
    return !IsMegaEnemySoulLocked(actor);
}

static bool IsMegaHiddenGrottoActor(const Actor* actor) {
    // Door_Ana params 0x100/0x200 mark grottos that begin hidden and must
    // normally be revealed by Song of Storms or bombs/hammer. Open holes have neither bit.
    return actor != nullptr && actor->id == ACTOR_DOOR_ANA && (actor->params & 0x0300) != 0;
}

// Includes reserved inactive noncombat and retired offspring slots. Preserve
// ordering/capacity: old saves store receipts by this legacy array index.
// Capacity is derived from the append-only placement table below.

struct EnemyDefeatPlacement {
    int16_t scene;
    int8_t room;
    int8_t grottoId;
    int16_t actorListIndex;
    int16_t actorId;
    uint16_t params;
    int64_t locationId;
};

static constexpr EnemyDefeatPlacement kEnemyDefeatPlacements[] = {
#include "soh/Enhancements/randomizer/EnemyDefeatPlacements.inc"
};
static constexpr size_t kEnemyPlacementCount = sizeof(kEnemyDefeatPlacements) / sizeof(kEnemyDefeatPlacements[0]);
static constexpr size_t AP_ENEMY_DEFEAT_COUNT = kEnemyPlacementCount;
static_assert(kEnemyPlacementCount >= 570, "Do not remove legacy receipt slots");

static std::array<uint8_t, AP_ENEMY_DEFEAT_COUNT> gEnemyDefeatCompleted{};
static std::mutex gEnemyDefeatSaveMutex;
static int gEnemyDefeatSaveSection = -1;
static std::array<Actor*, AP_ENEMY_DEFEAT_COUNT> gLiveEnemyPickups{};
static std::array<Actor*, AP_ENEMY_DEFEAT_COUNT> gLiveEnemyPlacements{};
static void PersistEnemyDefeatJournal() {
    if (gEnemyDefeatSaveSection >= 0 && Archipelago_IsCurrentSaveActive() && gSaveContext.fileNum < 3)
        SaveManager::Instance->SaveSection(gSaveContext.fileNum, gEnemyDefeatSaveSection, true);
}
// 0 = not defeated; 1 = collected/outbox; 2 = defeated, physical pickup still owed.
// Version-2 saves contain only 0/1 and retain their original 570 receipt indices.
static void MarkEnemyDefeatEarned(size_t index) {
    bool changed = false;
    {
        std::lock_guard<std::mutex> lock(gEnemyDefeatSaveMutex);
        if (index < gEnemyDefeatCompleted.size() && gEnemyDefeatCompleted[index] == 0) {
            gEnemyDefeatCompleted[index] = 2;
            changed = true;
        }
    }
    if (changed) PersistEnemyDefeatJournal();
}

static bool EnemyDefeatWasCollected(size_t index) {
    std::lock_guard<std::mutex> lock(gEnemyDefeatSaveMutex);
    return index < gEnemyDefeatCompleted.size() && gEnemyDefeatCompleted[index] == 1;
}
static void MarkEnemyDefeatCollected(size_t index) {
    std::lock_guard<std::mutex> lock(gEnemyDefeatSaveMutex);
    if (index < gEnemyDefeatCompleted.size()) gEnemyDefeatCompleted[index] = 1;
}

// Persist the exact finite spawn identity on the actor itself.  This is deliberately
// captured before actor initialization, before params can be masked or enemies change
// rooms, transform, or spawn replacement/child actors.  Using ObjectExtension also
// means Actor* reuse can never inherit an old enemy's placement identity.
struct EnemyDefeatIdentity : SohExtreme::EnemyLifeDropState {
    int32_t placementIndex = -1;
    int16_t scene = -1;
    int8_t room = -1;
    int8_t grottoId = -1;
    int16_t actorListIndex = -1;
    int16_t actorId = -1;
    uint16_t params = 0;
    Vec3f spawnPos{};
    int64_t locationId = -1;
    // One physical AP pickup / normal drop per actor life, regardless of which
    // damage source reaches the death state first.
};

static ObjectExtension::Register<EnemyDefeatIdentity> gEnemyDefeatIdentityRegister;
struct EnemySourceIdentity {
    SohExtreme::EnemySpawnKey key;
    bool enemyCreated = false;
    bool hostileAtSpawn = false;
};
static ObjectExtension::Register<EnemySourceIdentity> gEnemySourceIdentityRegister;
extern "C" bool MegaSoul_IsEnemySpawnSource(const Actor* source) {
    if (source == nullptr) return false;
    const auto* origin = ObjectExtension::GetInstance().Get<EnemySourceIdentity>(source);
    // Follow immutable provenance, NOT parent pointers (Floormasters have a
    // circular parent/child ring). An enemy-created helper cannot spawn checks.
    // Likewise a monster remains a hostile source after init changes its params
    // or a death/transform animation changes its current actor category.
    return (origin != nullptr && (origin->enemyCreated || origin->hostileAtSpawn)) ||
           source->category == ACTORCAT_BOSS || IsMegaEnemySoulActor(source);
}

static bool IsPoeSisterIntroActor(const Actor* actor) {
    if (actor == nullptr || actor->id != ACTOR_EN_PO_SISTERS) return false;
    const auto* source = ObjectExtension::GetInstance().Get<EnemySourceIdentity>(actor);
    const uint16_t params = source != nullptr ? source->key.params : static_cast<uint16_t>(actor->params);
    return (params & 0x1000) != 0;
}

static SohExtreme::EnemySpawnKey EnemySpawnKeyFor(const Actor* actor) {
    const int16_t scene = gPlayState != nullptr ? static_cast<int16_t>(gPlayState->sceneNum) : -1;
    return { scene, actor->room,
        scene == SCENE_GROTTOS ? static_cast<int16_t>(EntranceTracker::GetCurrentGrottoId()) : static_cast<int16_t>(-1),
        GetActorListIndex(actor), actor->id, static_cast<uint16_t>(actor->params),
        static_cast<int32_t>(actor->home.pos.x), static_cast<int32_t>(actor->home.pos.y),
        static_cast<int32_t>(actor->home.pos.z) };
}


struct EnemyDefeatDropIdentity {
    int32_t placementIndex = -1;
    int64_t locationId = -1;
};

static ObjectExtension::Register<EnemyDefeatDropIdentity> gEnemyDefeatDropIdentityRegister;

extern void EnItem00_DrawRandomizedItem(EnItem00* enItem00, PlayState* play);

static bool EnemyDefeatLocationStillPending(int32_t placementIndex, int64_t locationId) {
    if (SohExtreme::IsEnemyOffspringPlacement(placementIndex)) return false;
    if (placementIndex < 0 || placementIndex >= static_cast<int32_t>(kEnemyPlacementCount) ||
        locationId < 0) {
        return false;
    }

    // A synthetic AP location is never a local-randomizer reward.  Keep the
    // local receipt as an outbox for reconnect replay, not as an alternate seed.
    return SohExtreme::EnemyCheckPending(Archipelago_IsCurrentSaveActive(),
        Archipelago_IsLocationActive(locationId), Archipelago_IsLocationReported(locationId),
        EnemyDefeatWasCollected(static_cast<size_t>(placementIndex)));
}

static EnItem00* SpawnEnemyDefeatPickup(Actor* enemy, int32_t placementIndex, int64_t locationId) {
    if (enemy == nullptr || gPlayState == nullptr ||
        !EnemyDefeatLocationStillPending(placementIndex, locationId)) {
        return nullptr;
    }

    if (gLiveEnemyPickups[placementIndex] != nullptr)
        return reinterpret_cast<EnItem00*>(gLiveEnemyPickups[placementIndex]);
    Vec3f pos = enemy->world.pos;
    EnItem00* item00 =
        reinterpret_cast<EnItem00*>(Item_DropCollectible2(gPlayState, &pos, ITEM00_SOH_DUMMY));
    if (item00 == nullptr) {
        return nullptr;
    }

    EnemyDefeatDropIdentity dropIdentity;
    dropIdentity.placementIndex = placementIndex;
    dropIdentity.locationId = locationId;
    ObjectExtension::GetInstance().Set<EnemyDefeatDropIdentity>(&item00->actor, std::move(dropIdentity));

    // Use the official coloured Archipelago pickup model. The pickup itself
    // only reports the location; the server still sends the actual placed item.
    item00->randoInf = RAND_INF_MAX;
    item00->randoCheck = RC_UNKNOWN_CHECK;
    item00->itemEntry = *Rando::StaticData::RetrieveItem(RG_AP_REMOTE_IMPORTANT).GetGIEntry();
    item00->actor.draw = reinterpret_cast<ActorFunc>(EnItem00_DrawRandomizedItem);
    item00->actor.velocity.y = 8.0f;
    item00->actor.speedXZ = 2.0f;
    item00->actor.world.rot.y = static_cast<int16_t>(Rand_CenteredFloat(65536.0f));
    gLiveEnemyPickups[placementIndex] = &item00->actor;
    return item00;
}

extern "C" bool MegaSoul_IsEnemyDefeatPickup(const Actor* itemActor) {
    return itemActor != nullptr &&
        ObjectExtension::GetInstance().Get<EnemyDefeatDropIdentity>(itemActor) != nullptr;
}

extern "C" bool MegaSoul_TryCollectEnemyDefeatPickup(Actor* itemActor) {
    if (itemActor == nullptr) return false;
    const auto* identity = ObjectExtension::GetInstance().Get<EnemyDefeatDropIdentity>(itemActor);
    if (identity == nullptr || identity->placementIndex < 0 ||
        static_cast<size_t>(identity->placementIndex) >= kEnemyPlacementCount) return false;
    const int32_t index = identity->placementIndex;
    const int64_t locationId = identity->locationId;
    if (SohExtreme::IsEnemyOffspringPlacement(index)) return false;
    if (!Archipelago_IsCurrentSaveActive() || !Archipelago_IsLocationActive(locationId)) return false;
    if (!Archipelago_IsLocationReported(locationId)) Archipelago_ReportLocation(locationId);
    // SendLocation rejects disconnected/not-ready sessions. Do NOT consume the
    // physical actor in that case. Reported means accepted by the local client;
    // the saved outbox below resends after reconnect until the server knows it.
    if (!SohExtreme::CanConsumeEnemyPickup(Archipelago_IsCurrentSaveActive(),
            Archipelago_IsLocationActive(locationId), Archipelago_IsLocationReported(locationId))) return false;
    MarkEnemyDefeatCollected(static_cast<size_t>(index));
    gLiveEnemyPickups[index] = nullptr;
    PersistEnemyDefeatJournal();
    ObjectExtension::GetInstance().Remove<EnemyDefeatDropIdentity>(itemActor);
    return true;
}

extern "C" bool MegaSoul_IsEnemyDefeatLocationPending(const Actor* actor) {
    if (actor == nullptr) return false;
    const auto* identity = ObjectExtension::GetInstance().Get<EnemyDefeatIdentity>(actor);
    return identity != nullptr && EnemyDefeatLocationStillPending(identity->placementIndex, identity->locationId);
}

extern "C" bool MegaSoul_HandlesEnemyLoot(const Actor* actor) {
    return actor != nullptr && IS_RANDO && IsMegaEnemySoulActor(actor) &&
        (RAND_GET_OPTION(RSK_SHUFFLE_ENEMY_DROPS).Get() != 0 || MegaSoul_IsEnemyDefeatLocationPending(actor));
}

extern "C" int MegaSoul_ConsumeNormalEnemyDrop(Actor* actor) {
    if (actor == nullptr || !IS_RANDO) return 0;
    const bool eligible = IsMegaEnemySoulActor(actor) && !IsMegaScrubActor(actor->id) &&
        !IsGoldSkulltulaActor(actor) && (!IsMegaPotActor(actor->id) || actor->id == ACTOR_EN_TUBO_TRAP) && !IsStructuralArmosStatue(actor);
    if (!eligible) return 0;
    auto* identity = ObjectExtension::GetInstance().Get<EnemyDefeatIdentity>(actor);
    if (identity == nullptr) return 0; // not initialized by the supported engine path
    return SohExtreme::ConsumeNormalEnemyDrop(*identity, eligible,
        RAND_GET_OPTION(RSK_SHUFFLE_ENEMY_DROPS).Get() != 0, HasRequiredEnemySoul(actor),
        MegaSoul_IsEnemyDefeatLocationPending(actor));
}

static void ReplayCollectedEnemyChecks() {
    if (!Archipelago_IsCurrentSaveActive()) return;
    for (size_t i = 0; i < kEnemyPlacementCount; ++i) {
        const int64_t id = kEnemyDefeatPlacements[i].locationId;
        if (!SohExtreme::IsEnemyOffspringPlacement(static_cast<int32_t>(i)) &&
            EnemyDefeatWasCollected(i) && Archipelago_IsLocationActive(id) &&
            !Archipelago_IsLocationReported(id)) Archipelago_ReportLocation(id);
    }
}

static void RecoverEarnedEnemyPickups() {
    if (gPlayState == nullptr || !Archipelago_IsCurrentSaveActive()) return;
    Player* player = GET_PLAYER(gPlayState);
    if (player == nullptr || Player_InCsMode(gPlayState) ||
        !(player->actor.bgCheckFlags & BGCHECKFLAG_GROUND) || player->actor.yDistToWater > 0.0f) return;
    for (size_t i = 0; i < kEnemyPlacementCount; ++i) {
        bool earned;
        {
            std::lock_guard<std::mutex> lock(gEnemyDefeatSaveMutex);
            earned = gEnemyDefeatCompleted[i] == 2;
        }
        if (!earned || gLiveEnemyPickups[i] != nullptr ||
            kEnemyDefeatPlacements[i].scene != gPlayState->sceneNum) continue;
        if (kEnemyDefeatPlacements[i].grottoId >= 0 &&
            kEnemyDefeatPlacements[i].grottoId != EntranceTracker::GetCurrentGrottoId()) continue;
        if (EnemyDefeatLocationStillPending(static_cast<int32_t>(i), kEnemyDefeatPlacements[i].locationId)) {
            // The original enemy may have permanently cleared a room/switch or the
            // pickup may have fallen into a pit. Respawn only its earned pickup,
            // beside a grounded Link; do not reset dungeon flags or award it remotely.
            SpawnEnemyDefeatPickup(&player->actor, static_cast<int32_t>(i), kEnemyDefeatPlacements[i].locationId);
            break; // bounded one recovery attempt per second
        }
    }
}

static void LoadEnemyDefeatData() {
    std::array<uint8_t, AP_ENEMY_DEFEAT_COUNT> loaded{};
    SaveManager::Instance->LoadArray("completed", AP_ENEMY_DEFEAT_COUNT, [&loaded](size_t i) {
        SaveManager::Instance->LoadData("", loaded[i]);
    });
    std::lock_guard<std::mutex> lock(gEnemyDefeatSaveMutex);
    gEnemyDefeatCompleted = loaded;
    gLiveEnemyPickups.fill(nullptr);
    gLiveEnemyPlacements.fill(nullptr);
}

static void SaveEnemyDefeatData(SaveContext*, int, bool) {
    std::array<uint8_t, AP_ENEMY_DEFEAT_COUNT> snapshot{};
    {
        std::lock_guard<std::mutex> lock(gEnemyDefeatSaveMutex);
        snapshot = gEnemyDefeatCompleted;
    }
    SaveManager::Instance->SaveArray("completed", AP_ENEMY_DEFEAT_COUNT, [&snapshot](size_t i) {
        SaveManager::Instance->SaveData("", snapshot[i]);
    });
}

static void InitEnemyDefeatData(bool) {
    std::lock_guard<std::mutex> lock(gEnemyDefeatSaveMutex);
    gEnemyDefeatCompleted.fill(0);
    gLiveEnemyPickups.fill(nullptr);
    gLiveEnemyPlacements.fill(nullptr);
}

static void RegisterEnemyDefeatSaveData() {
    SaveManager::Instance->AddInitFunction(InitEnemyDefeatData);
    SaveManager::Instance->AddLoadFunction("sohExtremeEnemyDefeats", 2, LoadEnemyDefeatData);
    SaveManager::Instance->AddLoadFunction("sohExtremeEnemyDefeats", 3, LoadEnemyDefeatData);
    gEnemyDefeatSaveSection = SaveManager::Instance->AddSaveFunction("sohExtremeEnemyDefeats", 3, SaveEnemyDefeatData, true, -1);
}

static void AttachEnemyDefeatIdentity(Actor* actor) {
    if (actor == nullptr || !IS_RANDO || !IsMegaEnemySoulActor(actor) || IsStructuralArmosStatue(actor)) return;
    if (ObjectExtension::GetInstance().Get<EnemyDefeatIdentity>(actor) != nullptr) return;
    // An unmapped spawn is deliberately unmapped. Do not re-run a looser
    // index/param/nearest-position lookup and accidentally claim another enemy.
    const int32_t index = -1;
    EnemyDefeatIdentity identity;
    identity.placementIndex = index;
    identity.scene = gPlayState != nullptr ? static_cast<int16_t>(gPlayState->sceneNum) : -1;
    identity.room = actor->room;
    identity.grottoId = identity.scene == SCENE_GROTTOS ? static_cast<int8_t>(EntranceTracker::GetCurrentGrottoId()) : -1;
    identity.actorListIndex = GetActorListIndex(actor);
    identity.actorId = actor->id;
    identity.params = static_cast<uint16_t>(actor->params);
    identity.spawnPos = actor->home.pos;
    identity.locationId = index >= 0 ? kEnemyDefeatPlacements[index].locationId : -1;
    ObjectExtension::GetInstance().Set<EnemyDefeatIdentity>(actor, std::move(identity));
}

extern "C" void MegaSoul_CaptureEnemyDefeatIdentity(Actor* actor) {
    AttachEnemyDefeatIdentity(actor);
}

extern "C" int32_t MegaSoul_FindEnemyDefeatSpawn(int16_t scene, int8_t room, int16_t actorIndex,
                                                 int16_t actorId, uint16_t params,
                                                 float x, float y, float z) {
    if (!IS_RANDO || !Archipelago_IsCurrentSaveActive() || actorIndex < 0) return -1;
    const int16_t grotto = scene == SCENE_GROTTOS ? static_cast<int16_t>(EntranceTracker::GetCurrentGrottoId()) : -1;
    const SohExtreme::EnemySpawnKey key{scene, room, grotto, actorIndex, actorId, params,
        static_cast<int32_t>(x), static_cast<int32_t>(y), static_cast<int32_t>(z)};
    const int32_t exact = SohExtreme::FindExactEnemySpawn(key);
    if (exact >= 0) return exact;
    if (scene == SCENE_FOREST_TEMPLE && actorId == ACTOR_EN_PO_SISTERS && !(params & 0x1C00))
        return 566 + ((params >> 8) & 3); // existing, append-only legacy IDs
    // Grotto templates have a distinct saved identity for each physical grotto.
    if (grotto >= 0 && actorIndex >= 0) {
        for (size_t i = 0; i < kEnemyPlacementCount; ++i) {
            const auto& e = kEnemyDefeatPlacements[i];
            if (e.scene == scene && e.room == room && e.grottoId == grotto &&
                e.actorListIndex == actorIndex && e.actorId == actorId && e.params == params)
                return static_cast<int32_t>(i);
        }
    }
    return -1;
}
extern "C" bool MegaSoul_IsEnemyDefeatPlacementPending(int32_t index) {
    return index >= 0 && static_cast<size_t>(index) < kEnemyPlacementCount &&
        EnemyDefeatLocationStillPending(index, kEnemyDefeatPlacements[index].locationId);
}
extern "C" int32_t MegaSoul_FindEnemyDefeatChild(const Actor* source, int16_t actorId,
                                                uint16_t params, int16_t slot) {
    if (source == nullptr || !IS_RANDO || !Archipelago_IsCurrentSaveActive() ||
        MegaSoul_IsEnemySpawnSource(source)) return -1;
    const auto* identity = ObjectExtension::GetInstance().Get<EnemySourceIdentity>(source);
    if (identity == nullptr) return -1;
    // Paintings/cubes are puzzle controllers, not enemies. Their authored
    // children can be the last remaining painting, so use the original scene
    // and immutable child params rather than the painting's current position.
    if (identity->key.scene == SCENE_FOREST_TEMPLE && source->id == ACTOR_BG_PO_EVENT &&
        actorId == ACTOR_EN_PO_SISTERS && (params & 0x1C00) == 0) {
        const int sister = (params >> 8) & 3;
        const int32_t index = 566 + sister;
        if (sister > 0 && gLiveEnemyPlacements[index] == nullptr) return index;
        return -1;
    }
    return SohExtreme::FindExactEnemyChild(identity->key, actorId, params, slot,
        [](int32_t index) {
            return index < 0 || static_cast<size_t>(index) >= kEnemyPlacementCount ||
                gLiveEnemyPlacements[index] != nullptr;
        });
}
extern "C" void MegaSoul_CaptureEnemyDefeatIdentityFrom(Actor* actor, int32_t index, const Actor* source) {
    if (actor == nullptr || !IS_RANDO) return;
    const bool enemyCreated = MegaSoul_IsEnemySpawnSource(source);
    ObjectExtension::GetInstance().Set<EnemySourceIdentity>(
        actor, EnemySourceIdentity{EnemySpawnKeyFor(actor), enemyCreated,
            actor->category == ACTORCAT_BOSS || IsMegaEnemySoulActor(actor)});
    AttachEnemyDefeatIdentity(actor);
    auto* identity = ObjectExtension::GetInstance().Get<EnemyDefeatIdentity>(actor);
    if (identity == nullptr) return;
    if (enemyCreated || index < 0 || static_cast<size_t>(index) >= kEnemyPlacementCount ||
        SohExtreme::IsEnemyOffspringPlacement(index) || kEnemyDefeatPlacements[index].actorId != actor->id) {
        index = -1;
    }
    const int32_t old = identity->placementIndex;
    if (old >= 0 && static_cast<size_t>(old) < kEnemyPlacementCount && gLiveEnemyPlacements[old] == actor)
        gLiveEnemyPlacements[old] = nullptr;
    identity->placementIndex = index;
    identity->locationId = index >= 0 ? kEnemyDefeatPlacements[index].locationId : -1;
    if (index >= 0) gLiveEnemyPlacements[index] = actor;
}

extern "C" void MegaSoul_CaptureEnemyDefeatIdentityAt(Actor* actor, int32_t index) {
    MegaSoul_CaptureEnemyDefeatIdentityFrom(actor, index, nullptr);
}

extern "C" void MegaSoul_ResetEnemyDefeatLife(Actor* actor) {
    if (actor == nullptr || !IS_RANDO) return;
    auto* identity = ObjectExtension::GetInstance().Get<EnemyDefeatIdentity>(actor);
    if (identity != nullptr) {
        // Preserve placement, saved collection, and immutable provenance.
        // Only a confirmed new life resets the normal-loot/death debounce.
        static_cast<SohExtreme::EnemyLifeDropState&>(*identity) = {};
    }
}

extern "C" int32_t MegaSoul_GetEnemyDefeatPlacement(const Actor* actor) {
    if (actor == nullptr) return -1;
    const auto* identity = ObjectExtension::GetInstance().Get<EnemyDefeatIdentity>(actor);
    return identity != nullptr ? identity->placementIndex : -1;
}

extern "C" void MegaSoul_BeginEnemyDefeatLife(Actor* actor, int32_t index) {
    if (actor == nullptr || !IS_RANDO || !Archipelago_IsCurrentSaveActive() || index < 0 ||
        static_cast<size_t>(index) >= kEnemyPlacementCount || kEnemyDefeatPlacements[index].actorId != actor->id ||
        SohExtreme::IsEnemyOffspringPlacement(index)) return;
    const auto* origin = ObjectExtension::GetInstance().Get<EnemySourceIdentity>(actor);
    if (origin != nullptr && origin->enemyCreated) return;
    auto* identity = ObjectExtension::GetInstance().Get<EnemyDefeatIdentity>(actor);
    if (identity == nullptr) return;
    const int32_t old = identity->placementIndex;
    if (old >= 0 && static_cast<size_t>(old) < kEnemyPlacementCount && gLiveEnemyPlacements[old] == actor)
        gLiveEnemyPlacements[old] = nullptr;
    // A pooled Field Poe represents whichever authored spawn point activated it.
    // Bind that saved spawn ID, never the moving apparition/death position.
    static_cast<SohExtreme::EnemyLifeDropState&>(*identity) = {};
    identity->placementIndex = index;
    const auto& placement = kEnemyDefeatPlacements[index];
    identity->locationId = placement.locationId;
    identity->scene = placement.scene;
    identity->room = placement.room;
    identity->grottoId = placement.grottoId;
    identity->actorListIndex = placement.actorListIndex;
    identity->actorId = placement.actorId;
    identity->params = placement.params;
    for (const auto& alias : SohExtreme::kEnemySpawnAliases) {
        if (alias.placement == index) {
            identity->spawnPos = { static_cast<float>(alias.key.x), static_cast<float>(alias.key.y),
                                   static_cast<float>(alias.key.z) };
            break;
        }
    }
    gLiveEnemyPlacements[index] = actor;
}

extern "C" bool MegaSoul_HasPendingEnemyInRoom(int16_t scene, int8_t room, int16_t actorId) {
    if (!IS_RANDO || !Archipelago_IsCurrentSaveActive()) return false;
    for (size_t i = 0; i < kEnemyPlacementCount; ++i) {
        const auto& entry = kEnemyDefeatPlacements[i];
        if (entry.scene == scene && entry.room == room && entry.actorId == actorId &&
            MegaSoul_IsEnemyDefeatPlacementPending(static_cast<int32_t>(i))) return true;
    }
    return false;
}

// Kept for source compatibility; Actor_Spawn uses the position-aware resolver above.
extern "C" bool MegaSoul_IsEnemyDefeatSpawnPending(int16_t scene, int8_t room, int16_t actorIndex,
                                                  int16_t actorId, uint16_t params) {
    if (actorIndex < 0) return false;
    if (scene == SCENE_FOREST_TEMPLE && actorId == ACTOR_EN_PO_SISTERS && !(params & 0x1C00))
        return MegaSoul_IsEnemyDefeatPlacementPending(566 + ((params >> 8) & 3));
    const int8_t grotto = scene == SCENE_GROTTOS ? static_cast<int8_t>(EntranceTracker::GetCurrentGrottoId()) : -1;
    for (size_t i = 0; i < kEnemyPlacementCount; ++i) {
        const auto& e = kEnemyDefeatPlacements[i];
        if (e.scene == scene && e.room == room && e.grottoId == grotto && e.actorListIndex == actorIndex &&
            e.actorId == actorId && e.params == params) return MegaSoul_IsEnemyDefeatPlacementPending(static_cast<int32_t>(i));
    }
    return false;
}

static void RegisterMegaSouls() {
    bool shouldRegister = IS_RANDO;

    // Replay saved receipts after scene entry and periodically after reconnect.
    // Actor identity is captured by Actor_Spawn before initialization.
    COND_HOOK(OnSceneSpawnActors, shouldRegister, []() { ReplayCollectedEnemyChecks(); });
    COND_HOOK(OnPlayerUpdate, shouldRegister, []() {
        if (gPlayState != nullptr && gPlayState->gameplayFrames % 60 == 0) {
            ReplayCollectedEnemyChecks();
            RecoverEarnedEnemyPickups();
        }
    });

    COND_VB_SHOULD(VB_PLAYER_CAN_ROLL, shouldRegister, {
        if (RAND_GET_OPTION(RSK_SHUFFLE_ROLL) && !MegaHas(RAND_INF_HAS_ROLL)) {
            *should = false;
        }
    });

    // Runtime fallback for talk requests. Most sign/NPC actors are hidden by
    // ShouldActorInit below, but this also protects actors created dynamically.
    COND_VB_SHOULD(VB_SPEAK, shouldRegister, {
        Player* player = GET_PLAYER(gPlayState);
        Actor* talkActor = player != nullptr ? player->talkActor : nullptr;
        if (talkActor == nullptr) {
            return;
        }
        if (RAND_GET_OPTION(RSK_SHUFFLE_SIGN_SOUL) && !MegaHas(RAND_INF_SIGN_SOUL) &&
            IsMegaSignActor(talkActor->id)) {
            *should = false;
            return;
        }
        if (RAND_GET_OPTION(RSK_SHUFFLE_NPC_SOUL) && !MegaHas(RAND_INF_NPC_SOUL) &&
            IsMegaNpcSoulActor(talkActor)) {
            *should = false;
        }
    });

    COND_VB_SHOULD(VB_TREE_DROP_ITEM, shouldRegister, {
        if (RAND_GET_OPTION(RSK_SHUFFLE_TREE_SOUL) && !MegaHas(RAND_INF_TREE_SOUL)) {
            *should = false;
        }
    });

    // Bushes share En_Wood02 with trees. They must still initialize so their
    // collider exists, but without Grass Soul they must not yield their check.
    COND_VB_SHOULD(VB_BUSH_DROP_ITEM, shouldRegister, {
        if (RAND_GET_OPTION(RSK_SHUFFLE_GRASS_SOUL) && !MegaHas(RAND_INF_GRASS_SOUL)) {
            *should = false;
        }
    });

    // Enemy Soul runtime behavior:
    //
    // Gone Until Found:
    //   * actor DID initialize
    //   * invisible
    //   * AI/update frozen
    //   * no per-frame AT/AC/OC collider registration
    //   * cannot damage Link
    //   * cannot receive damage
    //
    // Invincible Until Found:
    //   * visible
    //   * normal AI/collision
    //   * cannot receive damage
    //
    // Because ShouldActorUpdate runs every frame even for a frozen actor, the
    // same initialized actor is restored immediately when its Soul arrives.
    COND_HOOK(ShouldActorUpdate, shouldRegister, [](void* actorRef, bool* should) {
        Actor* actor = static_cast<Actor*>(actorRef);

        // NPC Soul is existential. We still allow init so scene scripts can
        // register safely, but while the Soul is missing the NPC is completely
        // inert in addition to being invisible.
        if (actor->id != ACTOR_FISHING &&
            RAND_GET_OPTION(RSK_SHUFFLE_NPC_SOUL) && !MegaHas(RAND_INF_NPC_SOUL) &&
            IsMegaNpcSoulActor(actor)) {
            *should = false;
            return;
        }

        if (IsMegaEnemySoulGone(actor)) {
            HideGoneEnemy(actor);
            // The four lobby-introduction actors are cutscene controllers, not
            // combat encounters. Keep them invisible, but let their timer/camera/
            // switch sequence finish; freezing them can trap Link in the intro.
            if (IsPoeSisterIntroActor(actor)) return;

            // Enemy colliders are normally registered from the actor's update
            // routine. Skipping update therefore removes AT/AC/OC interaction
            // for the frame in addition to freezing all AI/movement.
            *should = false;
            return;
        }

        // The Soul may have been received while the actor was already loaded.
        // Restore its original draw/targeting state before allowing updates.
        RestoreGoneEnemy(actor);

        if (IsMegaEnemySoulInvincible(actor)) {
            actor->colChkInfo.damage = 0;
            if (actor->colChkInfo.health == 0) {
                actor->colChkInfo.health = 1;
            }

            // Persistent near-black grayscale taint while the required Soul is
            // missing. Write the filter fields directly so this does not replay
            // the Light Arrow hit sound every frame.
            actor->colorFilterParams = static_cast<int16_t>(0x8000 | 2);
            actor->colorFilterTimer = 2;
        }
    });

    // Barren-world actor gating. Object/NPC category Souls remain existential;
    // Enemy Soul is intentionally handled above as visible-but-immortal.
    COND_HOOK(ShouldActorInit, shouldRegister, [](void* actorRef, bool* result) {
        Actor* actor = static_cast<Actor*>(actorRef);
        if (actor == nullptr) {
            return;
        }

        // Poe Sisters erase their color/sister bits during init. Capture their
        // exact AP identity while those spawn params are still intact.
        if (actor->id == ACTOR_EN_PO_SISTERS) {
            AttachEnemyDefeatIdentity(actor);
        }

        // Enemy Souls are intentionally NOT rejected here.
        // "Gone Until Found" must run the actor's init routine, then the
        // OnActorInit/ShouldActorUpdate hooks hide and freeze it. This preserves
        // actor-created switches, child actors, room bookkeeping and other
        // puzzle setup while keeping the enemy absent from gameplay.

        // Scrubs use existential Soul behavior: without Scrub Soul they do not
        // exist in the scene at all. Unlike crates and rocks/boulders there is
        // no black-tainted locked model for scrubs.
        if (RAND_GET_OPTION(RSK_SHUFFLE_BUSINESS_SCRUB_SOUL) &&
            !MegaHas(RAND_INF_BUSINESS_SCRUB_SOUL) && IsMegaScrubActor(actor->id)) {
            *result = false;
            return;
        }

        // Obj_Mure owns arrays of spawned fish/bug/butterfly/grass children.  Rejecting an
        // individual child from ShouldActorInit leaves Obj_Mure holding a pointer to an actor
        // whose initialization was cancelled; its group behaviour later dereferences that
        // stale pointer (the 0.7.8 Zora's River crash).  Gate the group parent instead.
        if (actor->id == ACTOR_OBJ_MURE) {
            const s16 mureType = actor->params & 0x1F;
            if (RAND_GET_OPTION(RSK_SHUFFLE_ANIMAL_SOUL) && (mureType == 2 || mureType == 3 || mureType == 4)) {
                RandomizerInf groupSoul = RAND_INF_MAX;
                if (RAND_GET_OPTION(RSK_SHUFFLE_ANIMAL_SOUL).Is(1)) {
                    groupSoul = RAND_INF_ANIMAL_SOUL;
                } else {
                    groupSoul = (mureType == 2) ? RAND_INF_ANIMAL_SOUL_FISH :
                                (mureType == 3) ? RAND_INF_ANIMAL_SOUL_BUG :
                                                  RAND_INF_ANIMAL_SOUL_BUTTERFLY;
                }
                if (!MegaHas(RAND_INF_ANIMAL_SOUL) && !MegaHas(groupSoul)) {
                    *result = false;
                    return;
                }
            }
            if (RAND_GET_OPTION(RSK_SHUFFLE_GRASS_SOUL) && !MegaHas(RAND_INF_GRASS_SOUL) && mureType == 0) {
                *result = false;
                return;
            }
        }

        if (RAND_GET_OPTION(RSK_SHUFFLE_ANIMAL_SOUL) && IsMegaAnimalActor(actor->id) &&
            !HasRequiredAnimalSoul(actor)) {
            *result = false;
            return;
        }

        if (RAND_GET_OPTION(RSK_SHUFFLE_POT_SOUL) && !MegaHas(RAND_INF_POT_SOUL) && IsMegaPotActor(actor->id)) {
            *result = false;
            return;
        }

        // Crates intentionally remain in the scene without Crate Soul, matching
        // Rock/Boulder Soul semantics. Obj_Kibako/Obj_Kibako2 already call
        // MegaSoul_CanUseCrate(), so they stay solid but cannot be lifted or
        // broken until the soul is owned. ShuffleCrates.cpp dark-taints them.
        // Soul semantics are existential: without Grass/Bush Soul, both grass
        // and bush actors are absent from the scene.
        if (RAND_GET_OPTION(RSK_SHUFFLE_GRASS_SOUL) && !MegaHas(RAND_INF_GRASS_SOUL) &&
            (IsMegaGrassActor(actor->id) || IsMegaBushActor(actor))) {
            *result = false;
            return;
        }

        // Rock/Boulder Soul is different from the existential actor Souls:
        // rocks must remain in the scene so they continue to cover/block checks
        // and grotto holes. Their actor update functions reject lifting/breaking
        // until the Soul is obtained.

        if (RAND_GET_OPTION(RSK_SHUFFLE_TREE_SOUL) && !MegaHas(RAND_INF_TREE_SOUL) && IsMegaTreeActor(actor)) {
            *result = false;
            return;
        }

        if (RAND_GET_OPTION(RSK_SHUFFLE_BEEHIVE_SOUL) && !MegaHas(RAND_INF_BEEHIVE_SOUL) &&
            IsMegaBeehiveActor(actor->id)) {
            *result = false;
            return;
        }

        // Skulltulas follow the same post-init runtime lock as enemies.  Do not
        // cancel actor initialization here: En_Sw/En_Si can establish scene
        // bookkeeping during init, and the OnActorInit/ShouldActorUpdate hooks
        // immediately hide/freeze them for Gone Until Found (or taint them for
        // Invincible Until Found).  This also makes already-loaded Skulltulas
        // react correctly when AP settings/souls arrive after scene creation.

        if (RAND_GET_OPTION(RSK_SHUFFLE_SIGN_SOUL) && !MegaHas(RAND_INF_SIGN_SOUL) && IsMegaSignActor(actor->id)) {
            *result = false;
            return;
        }
    });

    // A native terminal-defeat callback is required. A zero-health actor can
    // also be initializing, splitting or reviving and must not award a check.
    // The actor-update hook only retries a failed pickup allocation after death.
    auto handleEnemyDeath = [](Actor* actor) {
        if (actor == nullptr) {
            return;
        }

        // Business Scrubs and Gold Skulltulas retain their existing checks.
        // Ordinary spiders and newly catalogued flying pots are included here.
        const bool ordinaryEnemy = IsMegaEnemySoulActor(actor) &&
                                   !IsMegaScrubActor(actor->id) &&
                                   !IsGoldSkulltulaActor(actor) &&
                                   (!IsMegaPotActor(actor->id) || actor->id == ACTOR_EN_TUBO_TRAP);
        if (!ordinaryEnemy || !HasRequiredEnemySoul(actor)) {
            return;
        }

        auto* identity = ObjectExtension::GetInstance().Get<EnemyDefeatIdentity>(actor);
        if (identity != nullptr && identity->defeatHandled) {
            return;
        }

        int32_t placementIndex = -1;
        int64_t locationId = -1;
        if (identity != nullptr) {
            placementIndex = identity->placementIndex;
            locationId = identity->locationId;
        }

        bool firstUncheckedDefeat = false;
        if (placementIndex >= 0 && locationId >= 0) {
            firstUncheckedDefeat = EnemyDefeatLocationStillPending(placementIndex, locationId);
            if (firstUncheckedDefeat) {
                // The location is completed only when Link collects this physical
                // pickup. The per-life rewardWasAp flag suppresses subsequent normal loot.
                if (identity != nullptr) identity->rewardWasAp = true;
                MarkEnemyDefeatEarned(static_cast<size_t>(placementIndex));
                EnItem00* pickup = SpawnEnemyDefeatPickup(actor, placementIndex, locationId);
                if (pickup == nullptr) {
                    // Do not mark handled: the observed-death update hook may retry on a
                    // following death-animation frame instead of losing the check.
                    fprintf(stderr, "[SOH-EXTREME] Failed to spawn enemy AP pickup for location %lld\n",
                            static_cast<long long>(locationId));
                    return;
                }
            }
        }

        // Once the exact AP enemy location is already complete, repeat kills are
        // normal enemies again and may use the configured randomized enemy drop.
        if (RAND_GET_OPTION(RSK_SHUFFLE_ENEMY_DROPS) && !firstUncheckedDefeat) {
            Vec3f dropPos = actor->world.pos;
            Item_DropCollectibleRandom(gPlayState, actor, &dropPos, 0);
        }

        if (identity != nullptr) {
            identity->defeatHandled = true;
        }
    };

    COND_HOOK(OnEnemyDefeat, shouldRegister, [handleEnemyDeath](void* actorRef) {
        Actor* actor = static_cast<Actor*>(actorRef);
        if (actor != nullptr) {
            auto* identity = ObjectExtension::GetInstance().Get<EnemyDefeatIdentity>(actor);
            if (identity != nullptr) identity->deathObserved = true;
        }
        handleEnemyDeath(actor);
    });

    // Retry a failed allocation only after an actual native defeat callback.
    // health==0 alone is NOT a death signal (initialization, splitting/revival).
    COND_HOOK(OnActorUpdate, shouldRegister, [handleEnemyDeath](void* actorRef) {
        Actor* actor = static_cast<Actor*>(actorRef);
        if (actor == nullptr) return;
        if (IsPoeSisterIntroActor(actor) && IsMegaEnemySoulGone(actor)) HideGoneEnemy(actor);
        const auto* identity = ObjectExtension::GetInstance().Get<EnemyDefeatIdentity>(actor);
        if (identity != nullptr && identity->deathObserved && !identity->defeatHandled) handleEnemyDeath(actor);
    });

    // NPCs are scene-sensitive, so do not cancel their initialization. Hiding them after init
    // keeps scripts and room bookkeeping alive while the NPC Soul talk/logic gates prevent use.
    // Fishing is a combined NPC/scene controller and gates its model/dialog in z_fishing.c.
    // Other NPCs retain their existing re-entry restoration behavior.
    COND_HOOK(OnActorInit, shouldRegister, [](void* actorRef) {
        Actor* actor = static_cast<Actor*>(actorRef);
        if (actor == nullptr) {
            return;
        }
        if (actor->id != ACTOR_FISHING &&
            RAND_GET_OPTION(RSK_SHUFFLE_NPC_SOUL) && !MegaHas(RAND_INF_NPC_SOUL) &&
            IsMegaNpcSoulActor(actor)) {
            actor->draw = nullptr;
            actor->flags &= ~ACTOR_FLAG_ATTENTION_ENABLED;
        }

        // Identity was captured in Actor_Spawn before actor-specific init could
        // mutate params/home/room. Never reconstruct it from post-init fields.

        // Crucially this runs AFTER actor->init().  Any puzzle setup or child
        // actor spawning therefore happens before Gone Until Found makes the
        // enemy invisible/inert.
        if (IsMegaEnemySoulGone(actor)) {
            HideGoneEnemy(actor);
        }
    });

    // Prevent stale Actor* entries when leaving rooms/scenes.
    COND_HOOK(OnActorDestroy, shouldRegister, [](void* actorRef) {
        Actor* actor = static_cast<Actor*>(actorRef);
        gGoneEnemyRuntimeStates.erase(actor);
        const auto* enemy = ObjectExtension::GetInstance().Get<EnemyDefeatIdentity>(actor);
        if (enemy != nullptr && enemy->placementIndex >= 0 &&
            static_cast<size_t>(enemy->placementIndex) < kEnemyPlacementCount &&
            gLiveEnemyPlacements[enemy->placementIndex] == actor) gLiveEnemyPlacements[enemy->placementIndex] = nullptr;
        const auto* drop = ObjectExtension::GetInstance().Get<EnemyDefeatDropIdentity>(actor);
        if (drop != nullptr && drop->placementIndex >= 0 &&
            static_cast<size_t>(drop->placementIndex) < kEnemyPlacementCount &&
            gLiveEnemyPickups[drop->placementIndex] == actor) gLiveEnemyPickups[drop->placementIndex] = nullptr;
        ObjectExtension::GetInstance().Remove<EnemySourceIdentity>(actor);
        ObjectExtension::GetInstance().Remove<EnemyDefeatIdentity>(actor);
        ObjectExtension::GetInstance().Remove<EnemyDefeatDropIdentity>(actor);
    });
}

static RegisterShipInitFunc registerEnemyDefeatSaveData(RegisterEnemyDefeatSaveData);
static RegisterShipInitFunc registerMegaSouls(RegisterMegaSouls, { "IS_RANDO" });
