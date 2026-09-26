#include "ArchipelagoClient.h"
#include "TrackerWorkerConfig.h"

static bool ParseFlatStringIntObject(const std::string& raw, std::unordered_map<std::string, int64_t>& out);

#include <Archipelago.h>
#include <spdlog/spdlog.h>
#include <algorithm>
#include <cctype>
#include <chrono>
#include <set>
#include <random>
#include <ship/Context.h>
#include <ship/window/Window.h>

#include "soh/OTRGlobals.h"
#include "soh/SaveManager.h"
#include "soh/ShipInit.hpp"
#include "soh/cvar_prefixes.h"
#include "soh/Enhancements/game-interactor/GameInteractor.h"
#include "soh/Enhancements/randomizer/item.h"
#include "soh/Enhancements/randomizer/randomizer.h"
#include "soh/Enhancements/randomizer/randomizer_check_tracker.h"
#include "soh/Enhancements/randomizer/savefile.h"
#include "soh/Enhancements/randomizer/settings.h"
#include "soh/Network/Archipelago/ArchipelagoC.h"
#include "soh/Enhancements/randomizer/SeedContext.h"
#include "soh/Enhancements/randomizer/static_data.h"
#include "soh/Enhancements/randomizer/randomizerEnums/RandomizerCheck.h"
#include "soh/Enhancements/randomizer/randomizerEnums.h"
#include "soh/Enhancements/randomizer/randomizerEnums/RandomizerInf.h"
#include "soh/Enhancements/randomizer/randomizerEnums/RandomizerMiscEnums.h"
#include "soh/Notification/Notification.h"

extern "C" {
#include "macros.h"
#include "z64.h"
#include "functions.h"
#include "variables.h"
#include "overlays/actors/ovl_En_Ossan/z_en_ossan.h"
extern PlayState* gPlayState;
}

extern "C" u16 Randomizer_Item_Give(PlayState* play, GetItemEntry giEntry);
extern "C" void Save_SaveFile(void);

namespace {
std::string NormalizeApLocationName(const std::string& value) {
    std::string out;
    out.reserve(value.size());
    for (unsigned char c : value) {
        if (std::isalnum(c)) {
            out.push_back(static_cast<char>(std::tolower(c)));
        }
    }
    return out;
}

constexpr int64_t AP_EXTREME_ITEM_BASE = 9500000;
constexpr int64_t AP_EXTREME_SPEECH_BASE = 9600000;
constexpr int64_t AP_EXTREME_SPEECH_FALLBACK_BASE = 9650000;
constexpr int64_t AP_EXTREME_SPEECH_FALLBACK_COUNT = 512;

// AP hot-path state intentionally lives in this translation unit.  None of this
// needs to be serialized: saved RandomizerCheck state and ReceivedItems replay
// are the durable sources of truth.
std::deque<int64_t> gDeferredLocationReports;
uint64_t gNewSaveReplayTargetCount = 0;
int gNewSaveReplayGraceFrames = 0;

constexpr int AP_NEW_SAVE_REPLAY_GRACE_FRAMES = 90;
constexpr int AP_NEW_SAVE_REPLAY_ITEMS_PER_FRAME = 8;
constexpr int AP_LOCATION_REPORTS_PER_FRAME = 4;

// Some SoH major/randomizer items successfully finish their hold-item sequence
// without producing the generic OnItemReceive callback AP normally uses as its
// transaction completion. Never let that wedge the entire receive queue forever.
// We only use the fallback AFTER the item/cutscene state has ended and Link is alive.
uint32_t gAwaitingMajorFrames = 0;
constexpr uint32_t AP_MAJOR_RECEIVE_FALLBACK_MIN_FRAMES = 12;
constexpr uint32_t AP_MAJOR_RECEIVE_VERIFY_TIMEOUT_FRAMES = 90;

// A get-item animation or OnItemReceive callback alone is not proof that the
// reward reached the save. Important AP receives are committed only after the
// persistent state changes too.
uint64_t gAwaitingMajorStateDigestBefore = 0;
bool gAwaitingMajorCallbackSeen = false;

static uint64_t HashApReceiptBytes(uint64_t hash, const void* data, size_t size) {
    const auto* bytes = static_cast<const uint8_t*>(data);
    for (size_t i = 0; i < size; ++i) {
        hash ^= bytes[i];
        hash *= 1099511628211ULL;
    }
    return hash;
}

template <typename T>
static uint64_t HashApReceiptValue(uint64_t hash, const T& value) {
    return HashApReceiptBytes(hash, &value, sizeof(T));
}

static uint64_t CaptureApPersistentGrantDigest() {
    uint64_t hash = 1469598103934665603ULL;

    hash = HashApReceiptBytes(hash, &gSaveContext.inventory, sizeof(gSaveContext.inventory));
    hash = HashApReceiptBytes(hash, &gSaveContext.ship.randomizerInf,
                             sizeof(gSaveContext.ship.randomizerInf));

    hash = HashApReceiptValue(hash, gSaveContext.healthCapacity);
    hash = HashApReceiptValue(hash, gSaveContext.magicLevel);
    hash = HashApReceiptValue(hash, gSaveContext.isMagicAcquired);
    hash = HashApReceiptValue(hash, gSaveContext.isDoubleMagicAcquired);
    hash = HashApReceiptValue(hash, gSaveContext.isDoubleDefenseAcquired);
    hash = HashApReceiptValue(hash, gSaveContext.bgsFlag);
    hash = HashApReceiptValue(hash, gSaveContext.rupees);
    hash = HashApReceiptValue(hash, gSaveContext.ship.quest.data.randomizer.bombchuUpgradeLevel);
    hash = HashApReceiptValue(hash, gSaveContext.ship.quest.data.randomizer.triforcePiecesCollected);

    // Silver Rupee group progress uses dedicated native counters. Hash every
    // counter so an important AP silver piece is not acknowledged until the
    // exact SOH randomizer state proves that it was applied.
    const auto& apRando = gSaveContext.ship.quest.data.randomizer;
    hash = HashApReceiptValue(hash, apRando.silverShadowBlades);
    hash = HashApReceiptValue(hash, apRando.silverShadowPit);
    hash = HashApReceiptValue(hash, apRando.silverShadowSpikes);
    hash = HashApReceiptValue(hash, apRando.silverSpiritChild);
    hash = HashApReceiptValue(hash, apRando.silverSpiritSun);
    hash = HashApReceiptValue(hash, apRando.silverSpiritBoulders);
    hash = HashApReceiptValue(hash, apRando.silverBotw);
    hash = HashApReceiptValue(hash, apRando.silverIceCavernBlades);
    hash = HashApReceiptValue(hash, apRando.silverIceCavernBlock);
    hash = HashApReceiptValue(hash, apRando.silverGtgSlope);
    hash = HashApReceiptValue(hash, apRando.silverGtgLava);
    hash = HashApReceiptValue(hash, apRando.silverGtgWater);
    hash = HashApReceiptValue(hash, apRando.silverGanonLight);
    hash = HashApReceiptValue(hash, apRando.silverGanonForest);
    hash = HashApReceiptValue(hash, apRando.silverGanonFire);
    hash = HashApReceiptValue(hash, apRando.silverGanonSpirit);
    hash = HashApReceiptValue(hash, apRando.silverMqDodongosCavern);
    hash = HashApReceiptValue(hash, apRando.silverMqShadowInvisibleBlades);
    hash = HashApReceiptValue(hash, apRando.silverMqSpiritLobby);
    hash = HashApReceiptValue(hash, apRando.silverMqSpiritBigWall);
    hash = HashApReceiptValue(hash, apRando.silverMqGanonWater);
    hash = HashApReceiptValue(hash, apRando.silverMqGanonShadow);

    return hash;
}

static void ResetApMajorVerificationState() {
    gAwaitingMajorStateDigestBefore = 0;
    gAwaitingMajorCallbackSeen = false;
}

constexpr int64_t AP_ITEM_ROLL = 9500000;
constexpr int64_t AP_ITEM_GRAB = 9500001;
constexpr int64_t AP_ITEM_CLIMB = 9500002;
constexpr int64_t AP_ITEM_CRAWL = 9500003;
constexpr int64_t AP_ITEM_SPEAK = 9500004;
constexpr int64_t AP_ITEM_OPEN_CHEST = 9500005;
constexpr int64_t AP_ITEM_ENEMY_SOUL = 9500006;
constexpr int64_t AP_ITEM_NPC_SOUL = 9500007;
constexpr int64_t AP_ITEM_ANIMAL_SOUL = 9500008;
constexpr int64_t AP_ITEM_POT_SOUL = 9500009;
constexpr int64_t AP_ITEM_CRATE_SOUL = 9500010;
constexpr int64_t AP_ITEM_GRASS_SOUL = 9500011;
constexpr int64_t AP_ITEM_ROCK_SOUL = 9500012;
constexpr int64_t AP_ITEM_TREE_SOUL = 9500013;
constexpr int64_t AP_ITEM_BEEHIVE_SOUL = 9500014;
constexpr int64_t AP_ITEM_SIGN_SOUL = 9500015;
constexpr int64_t AP_ITEM_SKULLTULA_SOUL = 9500016;
constexpr int64_t AP_ITEM_BUSINESS_SCRUB_SOUL = 9500017;
constexpr int64_t AP_ITEM_SHOVEL = 9500018;
constexpr int64_t AP_ITEM_FLOW_OF_TIME = 9500019;

constexpr int64_t AP_ITEM_DMC_BEAN_SOUL = 9500095;
constexpr int64_t AP_ITEM_DMT_BEAN_SOUL = 9500096;
constexpr int64_t AP_ITEM_COLOSSUS_BEAN_SOUL = 9500097;
constexpr int64_t AP_ITEM_GV_BEAN_SOUL = 9500098;
constexpr int64_t AP_ITEM_GRAVEYARD_BEAN_SOUL = 9500099;
constexpr int64_t AP_ITEM_KF_BEAN_SOUL = 9500100;
constexpr int64_t AP_ITEM_LH_BEAN_SOUL = 9500101;
constexpr int64_t AP_ITEM_LW_BRIDGE_BEAN_SOUL = 9500102;
constexpr int64_t AP_ITEM_LW_BEAN_SOUL = 9500103;
constexpr int64_t AP_ITEM_ZR_BEAN_SOUL = 9500104;

constexpr int64_t AP_ITEM_SPEAK_DEKU = 9500105;
constexpr int64_t AP_ITEM_SPEAK_GERUDO = 9500106;
constexpr int64_t AP_ITEM_SPEAK_GORON = 9500107;
constexpr int64_t AP_ITEM_SPEAK_HYLIAN = 9500108;
constexpr int64_t AP_ITEM_SPEAK_KOKIRI = 9500109;
constexpr int64_t AP_ITEM_SPEAK_ZORA = 9500110;
constexpr int64_t AP_ITEM_ANIMAL_SOUL_COW = 9500111;
constexpr int64_t AP_ITEM_ANIMAL_SOUL_CUCCO = 9500112;
constexpr int64_t AP_ITEM_ANIMAL_SOUL_DOG = 9500113;
constexpr int64_t AP_ITEM_ANIMAL_SOUL_FISH = 9500114;
constexpr int64_t AP_ITEM_ANIMAL_SOUL_BUG = 9500115;
constexpr int64_t AP_ITEM_ANIMAL_SOUL_BUTTERFLY = 9500116;
constexpr int64_t AP_ITEM_ANIMAL_SOUL_FROG = 9500117;
constexpr int64_t AP_ITEM_ANIMAL_SOUL_HORSE = 9500118;
constexpr int64_t AP_ITEM_ENEMY_SOUL_STALFOS = 9500119;
constexpr int64_t AP_ITEM_ENEMY_SOUL_OCTOROK = 9500120;
constexpr int64_t AP_ITEM_ENEMY_SOUL_WALLMASTER = 9500121;
constexpr int64_t AP_ITEM_ENEMY_SOUL_DODONGO = 9500122;
constexpr int64_t AP_ITEM_ENEMY_SOUL_KEESE = 9500123;
constexpr int64_t AP_ITEM_ENEMY_SOUL_TEKTITE = 9500124;
constexpr int64_t AP_ITEM_ENEMY_SOUL_PEAHAT = 9500125;
constexpr int64_t AP_ITEM_ENEMY_SOUL_LIZALFOS_DINOLFOS = 9500126;
constexpr int64_t AP_ITEM_ENEMY_SOUL_GOHMA_LARVA = 9500127;
constexpr int64_t AP_ITEM_ENEMY_SOUL_SHABOM = 9500128;
constexpr int64_t AP_ITEM_ENEMY_SOUL_BABY_DODONGO = 9500129;
constexpr int64_t AP_ITEM_ENEMY_SOUL_BIRI_BARI = 9500130;
constexpr int64_t AP_ITEM_ENEMY_SOUL_TAILPASARAN = 9500131;
constexpr int64_t AP_ITEM_ENEMY_SOUL_TORCH_SLUG = 9500132;
constexpr int64_t AP_ITEM_ENEMY_SOUL_MOBLIN = 9500133;
constexpr int64_t AP_ITEM_ENEMY_SOUL_ARMOS = 9500134;
constexpr int64_t AP_ITEM_ENEMY_SOUL_DEKU_BABA = 9500135;
constexpr int64_t AP_ITEM_ENEMY_SOUL_DEKU_SCRUB = 9500136;
constexpr int64_t AP_ITEM_ENEMY_SOUL_BUBBLE = 9500137;
constexpr int64_t AP_ITEM_ENEMY_SOUL_BEAMOS = 9500138;
constexpr int64_t AP_ITEM_ENEMY_SOUL_FLOORMASTER = 9500139;
constexpr int64_t AP_ITEM_ENEMY_SOUL_REDEAD_GIBDO = 9500140;
constexpr int64_t AP_ITEM_ENEMY_SOUL_FLARE_DANCER = 9500141;
constexpr int64_t AP_ITEM_ENEMY_SOUL_DEAD_HAND = 9500142;
constexpr int64_t AP_ITEM_ENEMY_SOUL_SHELL_BLADE = 9500143;
constexpr int64_t AP_ITEM_ENEMY_SOUL_LIKE_LIKE = 9500144;
constexpr int64_t AP_ITEM_ENEMY_SOUL_SPIKE = 9500145;
constexpr int64_t AP_ITEM_ENEMY_SOUL_ANUBIS = 9500146;
constexpr int64_t AP_ITEM_ENEMY_SOUL_IRON_KNUCKLE = 9500147;
constexpr int64_t AP_ITEM_ENEMY_SOUL_SKULL_KID = 9500148;
constexpr int64_t AP_ITEM_ENEMY_SOUL_FLYING_POT = 9500149;
constexpr int64_t AP_ITEM_ENEMY_SOUL_FREEZARD = 9500150;
constexpr int64_t AP_ITEM_ENEMY_SOUL_STINGER = 9500151;
constexpr int64_t AP_ITEM_ENEMY_SOUL_WOLFOS = 9500152;
constexpr int64_t AP_ITEM_ENEMY_SOUL_GUAY = 9500153;
constexpr int64_t AP_ITEM_ENEMY_SOUL_JABU_TENTACLE = 9500154;
constexpr int64_t AP_ITEM_ENEMY_SOUL_DARK_LINK = 9500155;
constexpr int64_t AP_ITEM_ENEMY_SOUL_DOOR_TRAP = 9500156;
constexpr int64_t AP_ITEM_ENEMY_SOUL_FLYING_FLOOR_TILE = 9500157;
constexpr int64_t AP_ITEM_ENEMY_SOUL_GERUDO_THIEF = 9500158;
constexpr int64_t AP_ITEM_ENEMY_SOUL_POE_SISTER = 9500159;
constexpr int64_t AP_ITEM_ENEMY_SOUL_POE = 9500182;
constexpr int64_t AP_ITEM_ENEMY_SOUL_LEEVER = 9500183;
constexpr int64_t AP_ITEM_ENEMY_SOUL_STALCHILD = 9500184;
constexpr int64_t AP_ITEM_ENEMY_SOUL_BIG_OCTO = 9500185;


// Native Silver Rupee group progression.
constexpr int64_t AP_ITEM_SHADOW_SILVER_BLADES = 9500160;
constexpr int64_t AP_ITEM_SHADOW_SILVER_PIT = 9500161;
constexpr int64_t AP_ITEM_SHADOW_SILVER_SPIKES = 9500162;
constexpr int64_t AP_ITEM_SPIRIT_SILVER_CHILD = 9500163;
constexpr int64_t AP_ITEM_SPIRIT_SILVER_SUN = 9500164;
constexpr int64_t AP_ITEM_SPIRIT_SILVER_BOULDERS = 9500165;
constexpr int64_t AP_ITEM_BOTW_SILVER = 9500166;
constexpr int64_t AP_ITEM_ICE_CAVERN_SILVER_BLADES = 9500167;
constexpr int64_t AP_ITEM_ICE_CAVERN_SILVER_BLOCK = 9500168;
constexpr int64_t AP_ITEM_GTG_SILVER_SLOPE = 9500169;
constexpr int64_t AP_ITEM_GTG_SILVER_LAVA = 9500170;
constexpr int64_t AP_ITEM_GTG_SILVER_WATER = 9500171;
constexpr int64_t AP_ITEM_GANONS_CASTLE_SILVER_LIGHT = 9500172;
constexpr int64_t AP_ITEM_GANONS_CASTLE_SILVER_FOREST = 9500173;
constexpr int64_t AP_ITEM_GANONS_CASTLE_SILVER_FIRE = 9500174;
constexpr int64_t AP_ITEM_GANONS_CASTLE_SILVER_SPIRIT = 9500175;
constexpr int64_t AP_ITEM_DODONGOS_CAVERN_MQ_SILVER = 9500176;
constexpr int64_t AP_ITEM_SHADOW_MQ_SILVER_INVISIBLE_BLADES = 9500177;
constexpr int64_t AP_ITEM_SPIRIT_MQ_SILVER_LOBBY = 9500178;
constexpr int64_t AP_ITEM_SPIRIT_MQ_SILVER_BIG_WALL = 9500179;
constexpr int64_t AP_ITEM_GANONS_CASTLE_MQ_SILVER_WATER = 9500180;
constexpr int64_t AP_ITEM_GANONS_CASTLE_MQ_SILVER_SHADOW = 9500181;
constexpr int64_t AP_FIRST_SILVER_ITEM = AP_ITEM_SHADOW_SILVER_BLADES;
constexpr int64_t AP_LAST_SILVER_ITEM = AP_ITEM_GANONS_CASTLE_MQ_SILVER_SHADOW;


// Archipelago NetworkItem.flags:
//   0x01 progression, 0x02 useful, 0x04 trap.
// Treat progression OR useful as "important" for the colored AP icon.
// Filler/junk/trap-only remote items use the grayscale icon.
static RandomizerGet GetRemoteArchipelagoDisplay(int flags) {
    return (flags & 0x03) != 0 ? RG_AP_REMOTE_IMPORTANT : RG_AP_REMOTE_NORMAL;
}
constexpr int64_t AP_FIRST_SONG_NOTE = 9500020;
constexpr int64_t AP_LAST_SONG_NOTE = 9500093;

// AP base item IDs 1..276 intentionally match SoH RandomizerGet IDs in the
// 9.2.3-based world. This is the same numbering used by Items.py.
constexpr int64_t AP_BASE_ITEM_MIN = 1;
constexpr int64_t AP_BASE_ITEM_MAX = 276;

static void SetQuestSong(int quest) {
    gSaveContext.inventory.questItems |= (1u << quest);
}

static bool HasNote(RandomizerInf first, int offset) {
    return Flags_GetRandomizerInf(static_cast<RandomizerInf>(static_cast<int>(first) + offset));
}

static RandomizerGet MapApItemNameToRandomizerGet(const std::string& itemName) {
    static const std::unordered_map<std::string, RandomizerGet> kItemNameMap = {
#include "ArchipelagoNameMap.inc"
    };

    auto it = kItemNameMap.find(itemName);
    if (it != kItemNameMap.end()) {
        return it->second;
    }

    // All 74 SOH-EXTREME Song Notes intentionally share one physical display model.
    // Their actual reward is still the exact AP note ID handled by ProcessItem().
    if (itemName.rfind("Song Note", 0) == 0) {
        return RG_SONG_OF_TIME;
    }

    return RG_NONE;
}

// Ice Traps should mimic valuable items instead of exposing themselves with one
// fixed model. The disguise is stable per AP location.
static RandomizerGet GetIceTrapDisguise(int64_t apLocation) {
    static constexpr const char* kMajorDisguises[] = {
        "Progressive Hookshot",
        "Bow",
        "Boomerang",
        "Lens of Truth",
        "Megaton Hammer",
        "Progressive Strength Upgrade",
        "Progressive Scale",
        "Progressive Wallet",
        "Magic Meter",
        "Ocarina",
        "Mirror Shield",
        "Iron Boots",
        "Hover Boots",
        "Dins Fire",
        "Farores Wind",
        "Nayrus Love",
    };

    uint64_t x = static_cast<uint64_t>(apLocation);
    x ^= x >> 30;
    x *= 0xbf58476d1ce4e5b9ULL;
    x ^= x >> 27;
    x *= 0x94d049bb133111ebULL;
    x ^= x >> 31;

    const char* fakeName =
        kMajorDisguises[x % (sizeof(kMajorDisguises) / sizeof(kMajorDisguises[0]))];
    RandomizerGet display = MapApItemNameToRandomizerGet(fakeName);
    return display != RG_NONE ? display : RG_PROGRESSIVE_HOOKSHOT;
}

static std::string GetApItemDisplayName(int64_t itemId) {
    switch (itemId) {
        case AP_ITEM_ROLL: return "Roll";
        case AP_ITEM_GRAB: return "Grab / Power Bracelet";
        case AP_ITEM_CLIMB: return "Climb";
        case AP_ITEM_CRAWL: return "Crawl";
        case AP_ITEM_SPEAK: return "Speak";
        case AP_ITEM_OPEN_CHEST: return "Open Chest";
        case AP_ITEM_ENEMY_SOUL: return "Enemy Soul";
        case AP_ITEM_NPC_SOUL: return "NPC Soul";
        case AP_ITEM_ANIMAL_SOUL: return "Animal Soul";
        case AP_ITEM_POT_SOUL: return "Pot Soul";
        case AP_ITEM_CRATE_SOUL: return "Crate Soul";
        case AP_ITEM_GRASS_SOUL: return "Grass / Bush Soul";
        case AP_ITEM_ROCK_SOUL: return "Rock / Boulder Soul";
        case AP_ITEM_TREE_SOUL: return "Tree Soul";
        case AP_ITEM_BEEHIVE_SOUL: return "Beehive Soul";
        case AP_ITEM_SIGN_SOUL: return "Sign Soul";
        case AP_ITEM_SKULLTULA_SOUL: return "Skulltula Soul";
        case AP_ITEM_BUSINESS_SCRUB_SOUL: return "Scrub Soul";
        case AP_ITEM_SHOVEL: return "Shovel";
        case AP_ITEM_FLOW_OF_TIME: return "Flow of Time";
        case AP_ITEM_DMC_BEAN_SOUL: return "Death Mountain Crater Bean Soul";
        case AP_ITEM_DMT_BEAN_SOUL: return "Death Mountain Trail Bean Soul";
        case AP_ITEM_COLOSSUS_BEAN_SOUL: return "Desert Colossus Bean Soul";
        case AP_ITEM_GV_BEAN_SOUL: return "Gerudo Valley Bean Soul";
        case AP_ITEM_GRAVEYARD_BEAN_SOUL: return "Graveyard Bean Soul";
        case AP_ITEM_KF_BEAN_SOUL: return "Kokiri Forest Bean Soul";
        case AP_ITEM_LH_BEAN_SOUL: return "Lake Hylia Bean Soul";
        case AP_ITEM_LW_BRIDGE_BEAN_SOUL: return "Lost Woods Bridge Bean Soul";
        case AP_ITEM_LW_BEAN_SOUL: return "Lost Woods Bean Soul";
        case AP_ITEM_ZR_BEAN_SOUL: return "Zora's River Bean Soul";
        case AP_ITEM_SPEAK_DEKU: return "Speak Deku";
        case AP_ITEM_SPEAK_GERUDO: return "Speak Gerudo";
        case AP_ITEM_SPEAK_GORON: return "Speak Goron";
        case AP_ITEM_SPEAK_HYLIAN: return "Speak Hylian";
        case AP_ITEM_SPEAK_KOKIRI: return "Speak Kokiri";
        case AP_ITEM_SPEAK_ZORA: return "Speak Zora";
        case AP_ITEM_ANIMAL_SOUL_COW: return "Cow Soul";
        case AP_ITEM_ANIMAL_SOUL_CUCCO: return "Cucco Soul";
        case AP_ITEM_ANIMAL_SOUL_DOG: return "Dog Soul";
        case AP_ITEM_ANIMAL_SOUL_FISH: return "Fish Soul";
        case AP_ITEM_ANIMAL_SOUL_BUG: return "Bug Soul";
        case AP_ITEM_ANIMAL_SOUL_BUTTERFLY: return "Butterfly Soul";
        case AP_ITEM_ANIMAL_SOUL_FROG: return "Frog Soul";
        case AP_ITEM_ANIMAL_SOUL_HORSE: return "Horse Soul";
        case AP_ITEM_ENEMY_SOUL_STALFOS: return "Stalfos Soul";
        case AP_ITEM_ENEMY_SOUL_OCTOROK: return "Octorok Soul";
        case AP_ITEM_ENEMY_SOUL_WALLMASTER: return "Wallmaster Soul";
        case AP_ITEM_ENEMY_SOUL_DODONGO: return "Dodongo Soul";
        case AP_ITEM_ENEMY_SOUL_KEESE: return "Keese Soul";
        case AP_ITEM_ENEMY_SOUL_TEKTITE: return "Tektite Soul";
        case AP_ITEM_ENEMY_SOUL_PEAHAT: return "Peahat Soul";
        case AP_ITEM_ENEMY_SOUL_LIZALFOS_DINOLFOS: return "Lizalfos and Dinolfos Soul";
        case AP_ITEM_ENEMY_SOUL_GOHMA_LARVA: return "Gohma Larva Soul";
        case AP_ITEM_ENEMY_SOUL_SHABOM: return "Shabom Soul";
        case AP_ITEM_ENEMY_SOUL_BABY_DODONGO: return "Baby Dodongo Soul";
        case AP_ITEM_ENEMY_SOUL_BIRI_BARI: return "Biri and Bari Soul";
        case AP_ITEM_ENEMY_SOUL_TAILPASARAN: return "Tailpasaran Soul";
        case AP_ITEM_ENEMY_SOUL_TORCH_SLUG: return "Torch Slug Soul";
        case AP_ITEM_ENEMY_SOUL_MOBLIN: return "Moblin Soul";
        case AP_ITEM_ENEMY_SOUL_ARMOS: return "Armos Soul";
        case AP_ITEM_ENEMY_SOUL_DEKU_BABA: return "Deku Baba Soul";
        case AP_ITEM_ENEMY_SOUL_DEKU_SCRUB: return "Deku Scrub Soul";
        case AP_ITEM_ENEMY_SOUL_BUBBLE: return "Bubble Soul";
        case AP_ITEM_ENEMY_SOUL_BEAMOS: return "Beamos Soul";
        case AP_ITEM_ENEMY_SOUL_FLOORMASTER: return "Floormaster Soul";
        case AP_ITEM_ENEMY_SOUL_REDEAD_GIBDO: return "Redead and Gibdo Soul";
        case AP_ITEM_ENEMY_SOUL_FLARE_DANCER: return "Flare Dancer Soul";
        case AP_ITEM_ENEMY_SOUL_DEAD_HAND: return "Dead Hand Soul";
        case AP_ITEM_ENEMY_SOUL_SHELL_BLADE: return "Shell Blade Soul";
        case AP_ITEM_ENEMY_SOUL_LIKE_LIKE: return "Like Like Soul";
        case AP_ITEM_ENEMY_SOUL_SPIKE: return "Spike Soul";
        case AP_ITEM_ENEMY_SOUL_ANUBIS: return "Anubis Soul";
        case AP_ITEM_ENEMY_SOUL_IRON_KNUCKLE: return "Iron Knuckle Soul";
        case AP_ITEM_ENEMY_SOUL_SKULL_KID: return "Skull Kid Soul";
        case AP_ITEM_ENEMY_SOUL_FLYING_POT: return "Flying Pot Soul";
        case AP_ITEM_ENEMY_SOUL_FREEZARD: return "Freezard Soul";
        case AP_ITEM_ENEMY_SOUL_STINGER: return "Stinger Soul";
        case AP_ITEM_ENEMY_SOUL_WOLFOS: return "Wolfos Soul";
        case AP_ITEM_ENEMY_SOUL_GUAY: return "Guay Soul";
        case AP_ITEM_ENEMY_SOUL_JABU_TENTACLE: return "Jabu Jabu Tentacle Soul";
        case AP_ITEM_ENEMY_SOUL_DARK_LINK: return "Dark Link Soul";
        case AP_ITEM_ENEMY_SOUL_DOOR_TRAP: return "Door Trap Soul";
        case AP_ITEM_ENEMY_SOUL_FLYING_FLOOR_TILE: return "Flying Floor Tile Soul";
        case AP_ITEM_ENEMY_SOUL_GERUDO_THIEF: return "Gerudo Thief Soul";
        case AP_ITEM_ENEMY_SOUL_POE_SISTER: return "Poe Sister Soul";
        case AP_ITEM_ENEMY_SOUL_POE: return "Poe Soul";
        case AP_ITEM_ENEMY_SOUL_LEEVER: return "Leever Soul";
        case AP_ITEM_ENEMY_SOUL_STALCHILD: return "Stalchild Soul";
        case AP_ITEM_ENEMY_SOUL_BIG_OCTO: return "Big Octo Soul";

        case AP_ITEM_SHADOW_SILVER_BLADES: return "Shadow Silver: Blades";
        case AP_ITEM_SHADOW_SILVER_PIT: return "Shadow Silver: Pit";
        case AP_ITEM_SHADOW_SILVER_SPIKES: return "Shadow Silver: Spikes";
        case AP_ITEM_SPIRIT_SILVER_CHILD: return "Spirit Silver: Child";
        case AP_ITEM_SPIRIT_SILVER_SUN: return "Spirit Silver: Sun";
        case AP_ITEM_SPIRIT_SILVER_BOULDERS: return "Spirit Silver: Boulders";
        case AP_ITEM_BOTW_SILVER: return "Bottom of the Well Silver";
        case AP_ITEM_ICE_CAVERN_SILVER_BLADES: return "Ice Cavern Silver: Blades";
        case AP_ITEM_ICE_CAVERN_SILVER_BLOCK: return "Ice Cavern Silver: Block";
        case AP_ITEM_GTG_SILVER_SLOPE: return "Training Ground Silver: Slope";
        case AP_ITEM_GTG_SILVER_LAVA: return "Training Ground Silver: Lava";
        case AP_ITEM_GTG_SILVER_WATER: return "Training Ground Silver: Water";
        case AP_ITEM_GANONS_CASTLE_SILVER_LIGHT: return "Ganon's Castle Silver: Light";
        case AP_ITEM_GANONS_CASTLE_SILVER_FOREST: return "Ganon's Castle Silver: Forest";
        case AP_ITEM_GANONS_CASTLE_SILVER_FIRE: return "Ganon's Castle Silver: Fire";
        case AP_ITEM_GANONS_CASTLE_SILVER_SPIRIT: return "Ganon's Castle Silver: Spirit";
        case AP_ITEM_DODONGOS_CAVERN_MQ_SILVER: return "Dodongo's Cavern Silver";
        case AP_ITEM_SHADOW_MQ_SILVER_INVISIBLE_BLADES: return "Shadow Silver: Invisible Blades";
        case AP_ITEM_SPIRIT_MQ_SILVER_LOBBY: return "Spirit Silver: Lobby";
        case AP_ITEM_SPIRIT_MQ_SILVER_BIG_WALL: return "Spirit Silver: Big Wall";
        case AP_ITEM_GANONS_CASTLE_MQ_SILVER_WATER: return "Ganon's Castle Silver: Water";
        case AP_ITEM_GANONS_CASTLE_MQ_SILVER_SHADOW: return "Ganon's Castle Silver: Shadow";
        default: break;
    }

    if (itemId >= AP_FIRST_SONG_NOTE && itemId <= AP_LAST_SONG_NOTE) {
        return "Song Note " + std::to_string(static_cast<int>(itemId - AP_FIRST_SONG_NOTE) + 1);
    }

    if (itemId >= AP_BASE_ITEM_MIN && itemId <= AP_BASE_ITEM_MAX) {
        RandomizerGet randoGet = RG_NONE;
        switch (itemId) {
#include "ArchipelagoItemMap.inc"
            default: break;
        }
        if (randoGet != RG_NONE) {
            return Rando::StaticData::RetrieveItem(randoGet).GetName().english;
        }
    }

    return "Item " + std::to_string(itemId);
}

static bool BounceHasTag(const AP_Bounce& bounce, const std::string& tag) {
    if (bounce.tags == nullptr) return false;
    return std::find(bounce.tags->begin(), bounce.tags->end(), tag) != bounce.tags->end();
}

static std::string ExtractJsonString(const std::string& json, const std::string& key) {
    const std::string token = "\"" + key + "\"";
    size_t pos = json.find(token);
    if (pos == std::string::npos) return {};
    pos = json.find(':', pos + token.size());
    if (pos == std::string::npos) return {};
    pos = json.find('"', pos + 1);
    if (pos == std::string::npos) return {};
    ++pos;
    std::string out;
    bool escaped = false;
    for (; pos < json.size(); ++pos) {
        const char c = json[pos];
        if (escaped) {
            switch (c) {
                case 'n': out.push_back('\n'); break;
                case 'r': out.push_back('\r'); break;
                case 't': out.push_back('\t'); break;
                default: out.push_back(c); break;
            }
            escaped = false;
        } else if (c == '\\') {
            escaped = true;
        } else if (c == '"') {
            break;
        } else {
            out.push_back(c);
        }
    }
    return out;
}

static std::string EscapeJsonString(const std::string& value) {
    std::string out;
    out.reserve(value.size() + 8);
    for (char c : value) {
        switch (c) {
            case '\\': out += "\\\\"; break;
            case '"': out += "\\\""; break;
            case '\n': out += "\\n"; break;
            case '\r': out += "\\r"; break;
            case '\t': out += "\\t"; break;
            default: out.push_back(c); break;
        }
    }
    return out;
}
}

ArchipelagoClient& ArchipelagoClient::GetInstance() {
    static ArchipelagoClient instance;
    return instance;
}

bool ArchipelagoClient::IsAuthenticated() const {
    return AP_IsInit() && AP_GetConnectionStatus() == AP_ConnectionStatus::Authenticated;
}

bool ArchipelagoClient::IsConnectionRefused() const {
    return AP_IsInit() && AP_GetConnectionStatus() == AP_ConnectionStatus::ConnectionRefused;
}

std::string ArchipelagoClient::GetStatusText() const {
    if (!enabled.load()) {
        return "Disabled";
    }
    if (!AP_IsInit()) {
        return "Starting...";
    }
    switch (AP_GetConnectionStatus()) {
        // APCpp can report Disconnected briefly while AP_Start() is establishing the
        // websocket.  Treat that as an in-progress connection while this client is
        // enabled instead of showing the contradictory "Disconnect / Disconnected" UI.
        case AP_ConnectionStatus::Disconnected: return "Connecting...";
        case AP_ConnectionStatus::Connected: return "Connected - authenticating...";
        case AP_ConnectionStatus::Authenticated:
            if (!slotSettingsLoaded) return "Authenticated - loading AP settings...";
            if (!activeLocationsLoaded) return "Authenticated - loading AP locations...";
            if (!shopPricesLoaded) return "Authenticated - loading AP prices...";
            if (expectedScoutCount > 0 && scoutedLocations.size() < expectedScoutCount) {
                return "Authenticated - loading AP placements " + std::to_string(scoutedLocations.size()) + "/" +
                       std::to_string(expectedScoutCount);
            }
            return "Authenticated - ready";
        case AP_ConnectionStatus::ConnectionRefused: return "Connection refused - check server/slot/password";
        default: return "Connecting...";
    }
}

void ArchipelagoClient::RegisterCallbacks() {
    AP_SetLoggingCallback([](std::string line) { SPDLOG_INFO("[Archipelago] {}", line); });
    AP_SetItemClearCallback([]() {
        // APCpp calls this before replaying the complete ReceivedItems list.  Do NOT
        // clear SoH inventory here: the save already persists awarded items.  Instead
        // reset our receive ordinal so the full replay can be deduplicated against the
        // number of AP items this local save has already consumed.
        ArchipelagoClient::GetInstance().BeginItemReplay();
    });
    AP_SetItemRecvCallback([](int64_t item, bool notify) {
        ArchipelagoClient::GetInstance().QueueItem(item, notify);
    });
    AP_SetLocationCheckedCallback([](int64_t location) {
        ArchipelagoClient::GetInstance().QueueCheckedLocation(location);
    });
    AP_SetLocationInfoCallback([](std::vector<AP_NetworkItem> locations) {
        auto& client = ArchipelagoClient::GetInstance();
        for (const auto& item : locations) {
            client.QueueLocationInfo(item.location, item.item, item.player, item.flags, item.itemName, item.playerName,
                                     item.locationName);
        }
    });

    // Do not mutate gameplay CVars from APCpp's networking callback thread.
    // extreme_soh_cvars below is the authoritative snapshot; it is applied only
    // after the user starts/loads an AP randomizer save on the gameplay thread.

    // Raw Bounce handling is used for TrapLink. APCpp documents that registering a
    // Bounced callback disables its automatic DeathLink handling, so SOH-EXTREME
    // handles BOTH link protocols here and advertises the matching tags after auth.
    AP_RegisterSlotDataIntCallback("death_link", [](int value) {
        ArchipelagoClient::GetInstance().deathLinkEnabled = value != 0;
    });
    AP_RegisterSlotDataIntCallback("trap_link", [](int value) {
        ArchipelagoClient::GetInstance().trapLinkEnabled = value != 0;
    });
    AP_RegisterBouncedCallback([](AP_Bounce bounce) {
        auto& client = ArchipelagoClient::GetInstance();
        // The callback copies only a bounded payload. Decode and UI mutation
        // happen on the gameplay thread when the Check Finder is open.
        if (bounce.data.size() <= 1000100 &&
            ExtractJsonString(bounce.data, "soh_extreme_tracker") == SohExtreme::kTrackerProtocol &&
            ExtractJsonString(bounce.data, "kind") == "snapshot") {
            const auto payload = ExtractJsonString(bounce.data, "payload");
            if (!payload.empty() && payload.size() <= 1000000) {
                const auto nonce = ExtractJsonString(bounce.data, "nonce");
                std::scoped_lock lock(client.queueMutex);
                if (nonce == client.finderMirror.Nonce()) client.pendingFinderPayload = payload;
            }
        }
        if (BounceHasTag(bounce, "DeathLink") && client.deathLinkEnabled) {
            client.QueueDeathLink(ExtractJsonString(bounce.data, "source"),
                                  ExtractJsonString(bounce.data, "cause"));
        }
        if (BounceHasTag(bounce, "TrapLink") && client.trapLinkEnabled) {
            client.QueueTrapLink(ExtractJsonString(bounce.data, "source"),
                                 ExtractJsonString(bounce.data, "trap_name"));
        }
    });

    // v0.4.5 publishes one authoritative snapshot already translated into this
    // fork's native gRando.Settings CVar names. It is intentionally raw JSON so all
    // settings arrive as one readiness boundary before file-select is allowed to start.
    AP_RegisterSlotDataRawCallback("extreme_soh_cvars", [](std::string raw) {
        ArchipelagoClient::GetInstance().SetSlotSettingsFromJson(raw);
    });
    AP_RegisterSlotDataRawCallback("extreme_shop_prices", [](std::string raw) {
        ArchipelagoClient::GetInstance().SetShopPricesFromJson(raw);
    });
    AP_RegisterSlotDataIntCallback("extreme_kakariko_gate_open", [](int value) {
        ArchipelagoClient::GetInstance().kakarikoGateOpen = value != 0;
    });

    // The AP server only allows LocationScouts for locations that actually exist in
    // this slot. SOH-EXTREME publishes that exact set in slot data. Scouting the entire
    // static SoH location table is invalid when options remove locations and causes the
    // AP 0.6.7 server to close the connection (for example: "No location 61 for player").
    AP_RegisterSlotDataRawCallback("extreme_active_locations", [](std::string raw) {
        ArchipelagoClient::GetInstance().SetActiveLocationsFromJson(raw);
    });
    // Standalone SOH-EXTREME owns its own location namespace.  Never assume the
    // compiled ArchipelagoLocationMap.inc still has the seed's exact ids/names.
    // The APWorld publishes the authoritative active name -> id table per slot.
    AP_RegisterSlotDataRawCallback("extreme_location_name_to_id", [](std::string raw) {
        ArchipelagoClient::GetInstance().SetLocationNameMapFromJson(raw);
    });

    // The old per-setting native callbacks were intentionally removed here.
    // extreme_soh_cvars is the single authoritative snapshot and includes enum
    // translations that cannot be represented by a direct 1:1 callback.

}

namespace {
double FinderMirrorClock() {
    return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count();
}
}

void ArchipelagoClient::ResetFinderMirror() {
    finderWorker.Stop();
    finderWorkerStarted = false;
    finderWorkerAttempts = 0;
    finderWorkerNextPoll = 0.0;
    finderWorkerRetryAt = 0.0;
    finderWorkerError.clear();
    // Not an authentication secret: a collision-resistant per-save/connection
    // token preventing accidental use of another slot's or an old save's data.
    static constexpr char hex[] = "0123456789abcdef";
    std::random_device random;
    std::string nonce(32, '0');
    for (auto& c : nonce) c = hex[random() & 15u];
    finderMirror.Reset(nonce);
    pendingFinderPayload.clear();
    finderMirrorError.clear();
    finderNextRequest = 0.0;
}

void ArchipelagoClient::RefreshFinderMirror() {
    // Called from the game UI; do not erase a valid snapshot just for a refresh.
    finderNextRequest = 0.0;
}

void ArchipelagoClient::RestartFinderWorker() {
    std::scoped_lock lock(queueMutex);
    ResetFinderMirror();
}

const std::string& ArchipelagoClient::GetFinderRuntimePath() const {
    return finderWorker.RuntimePath();
}

int32_t ArchipelagoClient::GetFinderNativeCheck(int64_t locationId) const {
    const auto found = apLocationToRc.find(locationId);
    return found == apLocationToRc.end() ? -1 : found->second;
}

void ArchipelagoClient::ServiceFinderWorker() {
    // Starts only for a loaded, authenticated AP gameplay save. Returning to
    // file select, loading a local save, or losing auth stops our own worker.
    // The native/local randomizer never starts or consults this service.
    const bool wanted = enabled.load() && currentSaveIsArchipelago && !saveIdentityMismatch &&
                        IsGameplaySessionActive() && IsAuthenticated();
    if (!wanted) {
        if (finderWorkerStarted) {
            std::scoped_lock lock(queueMutex);
            ResetFinderMirror();
        }
        return;
    }
    // 0.11.21a: Update() services this method BEFORE its authentication
    // reconciliation. Starting here on the first frame launched a host which
    // that reconciliation immediately stopped, then launched a second host on
    // the next frame. Wait for BOTH boundaries; never flap a new connection.
    if (!wasAuthenticated || !saveRuntimeSynchronized || !activeLocationsLoaded) return;
    const double now = FinderMirrorClock();
    if (now < finderWorkerNextPoll) return;
    finderWorkerNextPoll = now + 0.5;
    if (finderWorkerStarted && !finderWorker.IsRunning(finderWorkerError)) {
        const auto attempts = finderWorkerAttempts;
        const auto error = finderWorkerError;
        {
            std::scoped_lock lock(queueMutex);
            ResetFinderMirror();
        }
        finderWorkerAttempts = attempts;
        finderWorkerError = error;
        finderWorkerRetryAt = now + 5.0;
        finderWorkerNextPoll = now + 0.5;
        SPDLOG_WARN("[Archipelago] {}", finderWorkerError);
    }
    if (!finderWorkerStarted && finderWorkerAttempts < 3 && now >= finderWorkerRetryAt) {
        ++finderWorkerAttempts;
        const char* server = CVarGetString(CVAR_REMOTE_ARCHIPELAGO("ServerAddress"), "");
        const char* name = CVarGetString(CVAR_REMOTE_ARCHIPELAGO("SlotName"), "");
        const char* password = CVarGetString(CVAR_REMOTE_ARCHIPELAGO("Password"), "");
        const char* runtime = CVarGetString(CVAR_REMOTE_ARCHIPELAGO("TrackerRuntimePath"), "");
        try {
            const auto config = SohExtreme::MakeTrackerWorkerBootstrap(server ? server : "", name ? name : "",
                password ? password : "", static_cast<uint32_t>(AP_GetPlayerID()), finderMirror.Nonce());
            finderWorkerStarted = finderWorker.Start(runtime ? runtime : "", config, finderWorkerError);
        } catch (const std::exception&) {
            finderWorkerError = "The AP tracker could not read valid game connection settings.";
        }
        finderWorkerRetryAt = now + 15.0 * finderWorkerAttempts;
        if (finderWorkerStarted) {
            finderNextRequest = 0.0;
            SPDLOG_INFO("[Archipelago] Automatic Universal Tracker host started using {}", finderWorker.RuntimePath());
        } else {
            SPDLOG_WARN("[Archipelago] {}", finderWorkerError);
        }
    }
    if (finderWorkerStarted) {
        // Requests and replies continue even with the tracker UI closed. No
        // Python generation, rule evaluation, or network waiting occurs here.
        std::string status;
        if (GetFinderSnapshot(status) != nullptr) finderWorkerAttempts = 0;
    }
}

const SohExtreme::TrackerSnapshot* ArchipelagoClient::GetFinderSnapshot(std::string& status) {
    if (!currentSaveIsArchipelago || !IsAuthenticated()) {
        status = "Connect this Archipelago save to its server to start automatic tracking.";
        return nullptr;
    }
    if (!activeLocationsLoaded) {
        status = "Waiting for the server's active location manifest...";
        return nullptr;
    }
    std::string payload;
    uint64_t received = 0;
    std::set<int64_t> active;
    {
        std::scoped_lock lock(queueMutex);
        payload.swap(pendingFinderPayload);
        received = incomingItemOrdinal;
        active.insert(activeLocations.begin(), activeLocations.end());
    }
    const double now = FinderMirrorClock();
    const auto slot = static_cast<uint32_t>(AP_GetPlayerID());
    if (!payload.empty()) {
        try {
            finderMirror.Accept(SohExtreme::DecodeTrackerSnapshot(payload), slot, now, finderMirrorError);
        } catch (const std::exception& error) {
            finderMirrorError = std::string("Invalid tracker snapshot: ") + error.what();
        }
    }
    if (finderWorkerStarted && now >= finderNextRequest) {
        const uint64_t request = finderMirror.NextRequest();
        AP_Bounce bounce{};
        std::vector<std::string> tags{ "SOHExtremeUT" };
        bounce.tags = &tags;
        bounce.data = "{\"soh_extreme_tracker\":\"SOHExtremeFinder1\",\"kind\":\"request\",\"slot\":" +
            std::to_string(slot) + ",\"nonce\":\"" + finderMirror.Nonce() + "\",\"request\":" +
            std::to_string(request) + "}";
        AP_SendBounce(bounce);
        finderNextRequest = now + 2.0;
    }
    std::set<int64_t> checked;
    for (const auto id : reportedLocations) if (active.count(id)) checked.insert(id);
    const auto* result = finderMirror.Current(slot, received, active, checked, now, status);
    if (!result && !finderWorkerError.empty()) status = finderWorkerError;
    else if (!result && !finderMirrorError.empty()) status += " " + finderMirrorError;
    return result;
}

void ArchipelagoClient::Enable() {
    if (enabled.load()) {
        return;
    }

    // A refused/failed APCpp session can remain initialized even after the UI considers
    // it inactive.  Always tear down stale state before starting a fresh connection.
    if (AP_IsInit()) {
        AP_Shutdown();
    }

    const char* server = CVarGetString(CVAR_REMOTE_ARCHIPELAGO("ServerAddress"), "archipelago.gg:38281");
    const char* slot = CVarGetString(CVAR_REMOTE_ARCHIPELAGO("SlotName"), "");
    const char* password = CVarGetString(CVAR_REMOTE_ARCHIPELAGO("Password"), "");

    if (slot == nullptr || slot[0] == '\0') {
        SPDLOG_ERROR("[Archipelago] Slot name is empty");
        enabled = false;
        return;
    }

    // Reset per-connection state before APCpp callbacks can begin filling it.
    {
        std::scoped_lock lock(queueMutex);
        ResetFinderMirror();
        pendingItems.clear();
        pendingCheckedLocations.clear();
        pendingScouts.clear();
        pendingDeathLinks.clear();
        pendingTrapLinks.clear();
        chatMessages.clear();
    }
    scoutedLocations.clear();
    scoutedLocationNameIndex.clear();
    reportedLocations.clear();
    activeLocations.clear();
    authoritativeLocationNameIndex.clear();
    locationNameMapLoaded = false;
    slotSettings.clear();
    shopPrices.clear();
    activeLocationsLoaded = false;
    slotSettingsLoaded = false;
    shopPricesLoaded = false;
    kakarikoGateOpen = false;
    deathLinkEnabled = false;
    trapLinkEnabled = false;
    linkTagsSynchronized = false;
    deathStateInitialized = false;
    lastPlayerAlive = true;
    suppressNextDeathLinkSend = false;
    expectedScoutCount = 0;
    scoutsRequested = false;
    saveRuntimeSynchronized = false;
    fileSelectActivationRequested = false;
    slotSettingsPendingApply.store(false);
    activeLocationsPendingRefresh.store(false);
    settingsEnforceFrameCounter = 0;
    wasAuthenticated = false;
    syncFrameCounter = 0;
    incomingItemOrdinal = 0;
    receivedItemSnapshot.clear();
    gDeferredLocationReports.clear();
    gNewSaveReplayTargetCount = 0;
    gNewSaveReplayGraceFrames = 0;
    awaitingMajorItemReceipt = false;
    awaitingMajorSequence = 0;
    awaitingMajorApItemId = 0;
    gAwaitingMajorFrames = 0;
    currentSaveIsArchipelago = false;
    saveMetadataLoaded = false;
    saveIdentityMismatch = false;
    saveServer.clear();
    saveSlot.clear();
    // Migration fallback for pre-0.5.9 saves.  A real AP save overrides this
    // with its own serialized receive count as soon as SaveManager loads it.
    appliedItemCount = static_cast<uint64_t>(std::max(0, CVarGetInteger(GetReceivedCountCVar().c_str(), 0)));
    SPDLOG_INFO("[Archipelago] Loaded persisted received-item count {}", appliedItemCount);

    enabled = true;
    AP_Init(server, "SOH-EXTREME", slot, password == nullptr ? "" : password);
    AP_NetworkVersion version{ 0, 6, 7 };
    AP_SetClientVersion(&version);
    RegisterCallbacks();
    AP_EnableQueueItemRecvMsgs(true);
    AP_Start();
    SPDLOG_INFO("[Archipelago] Starting connection to {} as {}", server, slot);
}

void ArchipelagoClient::Disable() {
    // Shutdown should be safe even if our UI state and APCpp state got out of sync.
    enabled = false;
    if (AP_IsInit()) {
        AP_Shutdown();
    }
    std::scoped_lock lock(queueMutex);
    ResetFinderMirror();
    pendingItems.clear();
    pendingCheckedLocations.clear();
    pendingScouts.clear();
    pendingDeathLinks.clear();
    pendingTrapLinks.clear();
    scoutedLocations.clear();
    scoutedLocationNameIndex.clear();
    activeLocations.clear();
    authoritativeLocationNameIndex.clear();
    locationNameMapLoaded = false;
    slotSettings.clear();
    shopPrices.clear();
    activeLocationsLoaded = false;
    slotSettingsLoaded = false;
    shopPricesLoaded = false;
    kakarikoGateOpen = false;
    deathLinkEnabled = false;
    trapLinkEnabled = false;
    linkTagsSynchronized = false;
    deathStateInitialized = false;
    lastPlayerAlive = true;
    suppressNextDeathLinkSend = false;
    expectedScoutCount = 0;
    scoutsRequested = false;
    saveRuntimeSynchronized = false;
    fileSelectActivationRequested = false;
    awaitingMajorItemReceipt = false;
    awaitingMajorSequence = 0;
    awaitingMajorApItemId = 0;
    gAwaitingMajorFrames = 0;
    currentSaveIsArchipelago = false;
    newSaveReplayPending = false;
    gDeferredLocationReports.clear();
    gNewSaveReplayTargetCount = 0;
    gNewSaveReplayGraceFrames = 0;
    saveMetadataLoaded = false;
    saveIdentityMismatch = false;
    saveServer.clear();
    saveSlot.clear();
    chatMessages.clear();
}

void ArchipelagoClient::Toggle() {
    if (IsEnabled()) Disable(); else Enable();
}

std::string ArchipelagoClient::GetReceivedCountCVar() const {
    const char* server = CVarGetString(CVAR_REMOTE_ARCHIPELAGO("ServerAddress"), "");
    const char* slot = CVarGetString(CVAR_REMOTE_ARCHIPELAGO("SlotName"), "");
    std::string identity = std::string(server ? server : "") + "_" + std::string(slot ? slot : "");
    for (char& c : identity) {
        if (!std::isalnum(static_cast<unsigned char>(c))) c = '_';
    }
    return std::string("gNetwork.Archipelago.ReceivedItemCount.") + identity;
}

void ArchipelagoClient::LoadSaveMetadata(bool isArchipelagoSave, uint64_t receivedItemCount,
                                               const std::string& server, const std::string& slot,
                                               const std::string& cachedSettingsJson) {
    std::unique_lock<std::mutex> lock(queueMutex);

    ResetFinderMirror();
    currentSaveIsArchipelago = isArchipelagoSave;
    newSaveReplayPending = false;
    gDeferredLocationReports.clear();
    gNewSaveReplayTargetCount = 0;
    gNewSaveReplayGraceFrames = 0;
    // A death/reset can abort a get-item animation. Never carry an uncommitted
    // major-item transaction across a save reload; the saved receive count below
    // will cause APCpp's ReceivedItems history to replay it.
    awaitingMajorItemReceipt = false;
    awaitingMajorSequence = 0;
    awaitingMajorApItemId = 0;
    gAwaitingMajorFrames = 0;
    saveMetadataLoaded = true;
    saveServer = server;
    saveSlot = slot;

    // If Connected slot_data already arrived while file select was open, prefer
    // that live server snapshot over the older copy serialized in this save.
    // Otherwise retain the cached snapshot so actor-gating settings are available
    // before the first gameplay scene initializes.
    const bool liveSettingsAlreadyLoaded = slotSettingsLoaded && !slotSettings.empty();
    if (!liveSettingsAlreadyLoaded) {
        cachedSlotSettingsJson = cachedSettingsJson;
    }

    // 0.7.39: Restore the last server-authoritative settings snapshot from THIS save
    // before the first gameplay scene creates its actors.  Reconnecting to AP happens
    // asynchronously, which is too late for ShouldActorInit-based systems such as Pot
    // Soul, Grass/Bush Soul, Enemy Soul, etc.  The live server snapshot will replace
    // this cache as soon as Connected slot_data arrives.
    bool applySettingsBeforeScene = false;
    size_t restoredSettingCount = 0;
    if (isArchipelagoSave && liveSettingsAlreadyLoaded) {
        // Apply the already-received live server snapshot before scene actors spawn.
        restoredSettingCount = slotSettings.size();
        applySettingsBeforeScene = true;
    } else if (isArchipelagoSave && !cachedSettingsJson.empty()) {
        std::unordered_map<std::string, int64_t> parsed;
        if (ParseFlatStringIntObject(cachedSettingsJson, parsed)) {
            slotSettings.clear();
            for (const auto& [key, value] : parsed) {
                slotSettings[key] = static_cast<int>(value);
            }
            slotSettingsLoaded = true;
            restoredSettingCount = slotSettings.size();
            applySettingsBeforeScene = true;
        } else {
            SPDLOG_WARN("[Archipelago] Ignoring invalid cached AP settings stored in save");
        }
    }
    saveIdentityMismatch = false;

    if (!isArchipelagoSave) {
        lock.unlock();
        if (applySettingsBeforeScene) {
            ApplySlotSettings();
        }
        return;
    }

    const char* configuredServerRaw = CVarGetString(CVAR_REMOTE_ARCHIPELAGO("ServerAddress"), "");
    const char* configuredSlotRaw = CVarGetString(CVAR_REMOTE_ARCHIPELAGO("SlotName"), "");
    const std::string configuredServer = configuredServerRaw ? configuredServerRaw : "";
    const std::string configuredSlot = configuredSlotRaw ? configuredSlotRaw : "";

    // Slot is the strongest identity we can safely require here.  Server is also
    // checked when both sides have one, but an old migrated save may not have it.
    if ((!slot.empty() && !configuredSlot.empty() && slot != configuredSlot) ||
        (!server.empty() && !configuredServer.empty() && server != configuredServer)) {
        saveIdentityMismatch = true;
        pendingItems.clear();
        SPDLOG_ERROR("[Archipelago] Save belongs to AP slot '{}' at '{}', but client is configured for '{}' at '{}'; "
                     "item replay is blocked to protect the save",
                     slot, server, configuredSlot, configuredServer);
        lock.unlock();
        if (applySettingsBeforeScene) {
            ApplySlotSettings();
            SPDLOG_INFO("[Archipelago] Applied {} AP settings before scene init",
                        restoredSettingCount);
        }
        return;
    }

    appliedItemCount = receivedItemCount;

    // 0.10.4: SaveManager can load this custom byte from the previously active
    // randomizer context before a brand-new AP file's metadata is reconciled.
    // If this AP save has applied zero ReceivedItems, it cannot legitimately own
    // any AP Triforce Pieces yet, so clear the stale RAM value here as well.
    // Once AP actually grants a Triforce Piece the normal item path increments it.
    if (receivedItemCount == 0) {
        gSaveContext.ship.quest.data.randomizer.triforcePiecesCollected = 0;
    }

    // APCpp may already have replayed ReceivedItems while the user was on file select.
    // Rebuild the pending queue against the count stored *inside this save*.
    pendingItems.clear();
    for (uint64_t i = appliedItemCount; i < receivedItemSnapshot.size(); ++i) {
        pendingItems.push_back({ receivedItemSnapshot[i], false, i });
    }

    SPDLOG_INFO("[Archipelago] Loaded AP save metadata: slot='{}', receive count={}, queued {} newer items",
                saveSlot, appliedItemCount, pendingItems.size());

    lock.unlock();
    if (applySettingsBeforeScene) {
        ApplySlotSettings();
        SPDLOG_INFO("[Archipelago] Applied {} AP settings before scene init",
                    restoredSettingCount);
    }
}

void ArchipelagoClient::BeginItemReplay() {
    std::scoped_lock lock(queueMutex);
    incomingItemOrdinal = 0;
    receivedItemSnapshot.clear();
    SPDLOG_INFO("[Archipelago] Beginning server item-state replay; {} AP items already applied locally",
                appliedItemCount);
}

void ArchipelagoClient::QueueItem(int64_t itemId, bool notify) {
    std::scoped_lock lock(queueMutex);

    const uint64_t sequence = incomingItemOrdinal++;
    receivedItemSnapshot.push_back(itemId);

    // APCpp always invokes the item callback for the complete ReceivedItems replay,
    // including items the player already owns.  Its notify flag is not a reliable
    // persistence boundary across process restarts, so use our own monotonically
    // increasing receive count instead.  This is what prevents a starting item from
    // being granted again forever on reconnect/startup.
    if (sequence < appliedItemCount) {
        SPDLOG_DEBUG("[Archipelago] Replay item #{} id {} already applied; skipping", sequence, itemId);
        return;
    }

    const std::string itemName = GetApItemDisplayName(itemId);
    SPDLOG_INFO("[Archipelago] Received {} (item id {}, receive #{}, notify={})", itemName, itemId, sequence, notify);
    pendingItems.push_back({ itemId, notify, sequence });
}

void ArchipelagoClient::MarkItemApplied(uint64_t sequence) {
    const uint64_t newCount = sequence + 1;
    if (newCount <= appliedItemCount) return;

    // 0.7.47: the queue itself is transactional.  An AP item stays at the front
    // until the game has REALLY applied it.  Major items are removed only from
    // OnItemReceive; immediate items are removed after their give routine returns.
    // Death, void-out, scene transition, pause/cutscene blocking, or a failed
    // GiveItemEntryWithoutActor therefore cannot silently consume the queue entry.
    int64_t appliedItemId = 0;
    {
        std::scoped_lock lock(queueMutex);
        if (!pendingItems.empty() && pendingItems.front().sequence == sequence) {
            appliedItemId = pendingItems.front().id;
            pendingItems.pop_front();
        } else {
            auto it = std::find_if(pendingItems.begin(), pendingItems.end(),
                                   [sequence](const PendingItem& item) { return item.sequence == sequence; });
            if (it != pendingItems.end()) {
                appliedItemId = it->id;
                pendingItems.erase(it);
            }
        }
    }

    appliedItemCount = newCount;
    // Keep the old CVar as a migration mirror, but SaveManager's per-save field is
    // authoritative from 0.5.9 onward.
    CVarSetInteger(GetReceivedCountCVar().c_str(), static_cast<int>(appliedItemCount));
    SPDLOG_INFO("[Archipelago] Committed receive #{}; removed from queue only after grant; current save receive count is now {}", sequence, appliedItemCount);

    // Do NOT queue a full Save_SaveFile() for every AP item. SaveManager writes
    // asynchronously and Reset/Exit waits for its thread pool. A received-item burst
    // (especially a brand-new local AP file reconstructing server history) used to
    // queue dozens/hundreds of full saves and make Reset look permanently frozen.
    //
    // The normal/manual save path persists BOTH inventory/RandomizerInf and
    // archipelagoReceivedItemCount together. If gameplay reloads before a save,
    // both values revert together and APCpp's ReceivedItems replay safely grants
    // the item again, so no item can be eaten by removing this per-item autosave.
    // Do not run the Check Tracker/Check Finder reachability search on the item
    // pickup/receive frame.  SOH-EXTREME's expanded graph makes that search
    // expensive enough to cause a visible hitch whenever progression arrives.
    // Tracker availability is refreshed by normal load/slot synchronization
    // paths instead of blocking item pickup here.
    SPDLOG_DEBUG("[Archipelago] Receive #{} item {} committed", sequence, appliedItemId);

    // Available Checks is opt-in. When enabled, progression receives should make
    // the finder accurate again, but never run ReachabilitySearch inside the AP
    // receive callback itself. RecalculateAvailableChecks() only schedules one
    // deferred pass; multiple items in the same burst collapse into that one pass.
    //
    // During a new-save historical replay, wait until the replay reaches its end
    // so we do not run a world search after each reconstructed item.
    if (CVarGetInteger(CVAR_TRACKER_CHECK("EnableAvailableChecks"), 0) &&
        (gNewSaveReplayTargetCount == 0 || newCount >= gNewSaveReplayTargetCount)) {
        // Live Check Finder depends on some non-major state too (most notably
        // current Bombchu ammo).  Do not filter refreshes by advancement/major
        // classification: RecalculateAvailableChecks() is deferred/debounced, so
        // bursts still collapse to one graph pass while ammo/refills cannot leave
        // the finder stale.
        CheckTracker::RecalculateAvailableChecks();
    }
}


static bool ApplyExtremePersistentApItem(int64_t apItemId) {
    switch (apItemId) {
        case AP_ITEM_ROLL: Flags_SetRandomizerInf(RAND_INF_HAS_ROLL); return true;
        case AP_ITEM_GRAB: Flags_SetRandomizerInf(RAND_INF_CAN_GRAB); return true;
        case AP_ITEM_CLIMB: Flags_SetRandomizerInf(RAND_INF_CAN_CLIMB); return true;
        case AP_ITEM_CRAWL: Flags_SetRandomizerInf(RAND_INF_CAN_CRAWL); return true;
        case AP_ITEM_SPEAK:
            Flags_SetRandomizerInf(RAND_INF_CAN_SPEAK_DEKU);
            Flags_SetRandomizerInf(RAND_INF_CAN_SPEAK_GERUDO);
            Flags_SetRandomizerInf(RAND_INF_CAN_SPEAK_GORON);
            Flags_SetRandomizerInf(RAND_INF_CAN_SPEAK_HYLIAN);
            Flags_SetRandomizerInf(RAND_INF_CAN_SPEAK_KOKIRI);
            Flags_SetRandomizerInf(RAND_INF_CAN_SPEAK_ZORA);
            return true;
        case AP_ITEM_SPEAK_DEKU: Flags_SetRandomizerInf(RAND_INF_CAN_SPEAK_DEKU); return true;
        case AP_ITEM_SPEAK_GERUDO: Flags_SetRandomizerInf(RAND_INF_CAN_SPEAK_GERUDO); return true;
        case AP_ITEM_SPEAK_GORON: Flags_SetRandomizerInf(RAND_INF_CAN_SPEAK_GORON); return true;
        case AP_ITEM_SPEAK_HYLIAN: Flags_SetRandomizerInf(RAND_INF_CAN_SPEAK_HYLIAN); return true;
        case AP_ITEM_SPEAK_KOKIRI: Flags_SetRandomizerInf(RAND_INF_CAN_SPEAK_KOKIRI); return true;
        case AP_ITEM_SPEAK_ZORA: Flags_SetRandomizerInf(RAND_INF_CAN_SPEAK_ZORA); return true;
        case AP_ITEM_ENEMY_SOUL: Flags_SetRandomizerInf(RAND_INF_ENEMY_SOUL); return true;
        case AP_ITEM_NPC_SOUL: Flags_SetRandomizerInf(RAND_INF_NPC_SOUL); return true;
        case AP_ITEM_ANIMAL_SOUL: Flags_SetRandomizerInf(RAND_INF_ANIMAL_SOUL); return true;
        case AP_ITEM_ANIMAL_SOUL_COW: Flags_SetRandomizerInf(RAND_INF_ANIMAL_SOUL_COW); return true;
        case AP_ITEM_ANIMAL_SOUL_CUCCO: Flags_SetRandomizerInf(RAND_INF_ANIMAL_SOUL_CUCCO); return true;
        case AP_ITEM_ANIMAL_SOUL_DOG: Flags_SetRandomizerInf(RAND_INF_ANIMAL_SOUL_DOG); return true;
        case AP_ITEM_ANIMAL_SOUL_FISH: Flags_SetRandomizerInf(RAND_INF_ANIMAL_SOUL_FISH); return true;
        case AP_ITEM_ANIMAL_SOUL_BUG: Flags_SetRandomizerInf(RAND_INF_ANIMAL_SOUL_BUG); return true;
        case AP_ITEM_ANIMAL_SOUL_BUTTERFLY: Flags_SetRandomizerInf(RAND_INF_ANIMAL_SOUL_BUTTERFLY); return true;
        case AP_ITEM_ANIMAL_SOUL_FROG: Flags_SetRandomizerInf(RAND_INF_ANIMAL_SOUL_FROG); return true;
        case AP_ITEM_ANIMAL_SOUL_HORSE: Flags_SetRandomizerInf(RAND_INF_ANIMAL_SOUL_HORSE); return true;
        case AP_ITEM_ENEMY_SOUL_STALFOS: Flags_SetRandomizerInf(RAND_INF_ENEMY_SOUL_STALFOS); return true;
        case AP_ITEM_ENEMY_SOUL_OCTOROK: Flags_SetRandomizerInf(RAND_INF_ENEMY_SOUL_OCTOROK); return true;
        case AP_ITEM_ENEMY_SOUL_WALLMASTER: Flags_SetRandomizerInf(RAND_INF_ENEMY_SOUL_WALLMASTER); return true;
        case AP_ITEM_ENEMY_SOUL_DODONGO: Flags_SetRandomizerInf(RAND_INF_ENEMY_SOUL_DODONGO); return true;
        case AP_ITEM_ENEMY_SOUL_KEESE: Flags_SetRandomizerInf(RAND_INF_ENEMY_SOUL_KEESE); return true;
        case AP_ITEM_ENEMY_SOUL_TEKTITE: Flags_SetRandomizerInf(RAND_INF_ENEMY_SOUL_TEKTITE); return true;
        case AP_ITEM_ENEMY_SOUL_PEAHAT: Flags_SetRandomizerInf(RAND_INF_ENEMY_SOUL_PEAHAT); return true;
        case AP_ITEM_ENEMY_SOUL_LIZALFOS_DINOLFOS: Flags_SetRandomizerInf(RAND_INF_ENEMY_SOUL_LIZALFOS_DINOLFOS); return true;
        case AP_ITEM_ENEMY_SOUL_GOHMA_LARVA: Flags_SetRandomizerInf(RAND_INF_ENEMY_SOUL_GOHMA_LARVA); return true;
        case AP_ITEM_ENEMY_SOUL_SHABOM: Flags_SetRandomizerInf(RAND_INF_ENEMY_SOUL_SHABOM); return true;
        case AP_ITEM_ENEMY_SOUL_BABY_DODONGO: Flags_SetRandomizerInf(RAND_INF_ENEMY_SOUL_BABY_DODONGO); return true;
        case AP_ITEM_ENEMY_SOUL_BIRI_BARI: Flags_SetRandomizerInf(RAND_INF_ENEMY_SOUL_BIRI_BARI); return true;
        case AP_ITEM_ENEMY_SOUL_TAILPASARAN: Flags_SetRandomizerInf(RAND_INF_ENEMY_SOUL_TAILPASARAN); return true;
        case AP_ITEM_ENEMY_SOUL_TORCH_SLUG: Flags_SetRandomizerInf(RAND_INF_ENEMY_SOUL_TORCH_SLUG); return true;
        case AP_ITEM_ENEMY_SOUL_MOBLIN: Flags_SetRandomizerInf(RAND_INF_ENEMY_SOUL_MOBLIN); return true;
        case AP_ITEM_ENEMY_SOUL_ARMOS: Flags_SetRandomizerInf(RAND_INF_ENEMY_SOUL_ARMOS); return true;
        case AP_ITEM_ENEMY_SOUL_DEKU_BABA: Flags_SetRandomizerInf(RAND_INF_ENEMY_SOUL_DEKU_BABA); return true;
        case AP_ITEM_ENEMY_SOUL_DEKU_SCRUB: Flags_SetRandomizerInf(RAND_INF_ENEMY_SOUL_DEKU_SCRUB); return true;
        case AP_ITEM_ENEMY_SOUL_BUBBLE: Flags_SetRandomizerInf(RAND_INF_ENEMY_SOUL_BUBBLE); return true;
        case AP_ITEM_ENEMY_SOUL_BEAMOS: Flags_SetRandomizerInf(RAND_INF_ENEMY_SOUL_BEAMOS); return true;
        case AP_ITEM_ENEMY_SOUL_FLOORMASTER: Flags_SetRandomizerInf(RAND_INF_ENEMY_SOUL_FLOORMASTER); return true;
        case AP_ITEM_ENEMY_SOUL_REDEAD_GIBDO: Flags_SetRandomizerInf(RAND_INF_ENEMY_SOUL_REDEAD_GIBDO); return true;
        case AP_ITEM_ENEMY_SOUL_FLARE_DANCER: Flags_SetRandomizerInf(RAND_INF_ENEMY_SOUL_FLARE_DANCER); return true;
        case AP_ITEM_ENEMY_SOUL_DEAD_HAND: Flags_SetRandomizerInf(RAND_INF_ENEMY_SOUL_DEAD_HAND); return true;
        case AP_ITEM_ENEMY_SOUL_SHELL_BLADE: Flags_SetRandomizerInf(RAND_INF_ENEMY_SOUL_SHELL_BLADE); return true;
        case AP_ITEM_ENEMY_SOUL_LIKE_LIKE: Flags_SetRandomizerInf(RAND_INF_ENEMY_SOUL_LIKE_LIKE); return true;
        case AP_ITEM_ENEMY_SOUL_SPIKE: Flags_SetRandomizerInf(RAND_INF_ENEMY_SOUL_SPIKE); return true;
        case AP_ITEM_ENEMY_SOUL_ANUBIS: Flags_SetRandomizerInf(RAND_INF_ENEMY_SOUL_ANUBIS); return true;
        case AP_ITEM_ENEMY_SOUL_IRON_KNUCKLE: Flags_SetRandomizerInf(RAND_INF_ENEMY_SOUL_IRON_KNUCKLE); return true;
        case AP_ITEM_ENEMY_SOUL_SKULL_KID: Flags_SetRandomizerInf(RAND_INF_ENEMY_SOUL_SKULL_KID); return true;
        case AP_ITEM_ENEMY_SOUL_FLYING_POT: Flags_SetRandomizerInf(RAND_INF_ENEMY_SOUL_FLYING_POT); return true;
        case AP_ITEM_ENEMY_SOUL_FREEZARD: Flags_SetRandomizerInf(RAND_INF_ENEMY_SOUL_FREEZARD); return true;
        case AP_ITEM_ENEMY_SOUL_STINGER: Flags_SetRandomizerInf(RAND_INF_ENEMY_SOUL_STINGER); return true;
        case AP_ITEM_ENEMY_SOUL_WOLFOS: Flags_SetRandomizerInf(RAND_INF_ENEMY_SOUL_WOLFOS); return true;
        case AP_ITEM_ENEMY_SOUL_GUAY: Flags_SetRandomizerInf(RAND_INF_ENEMY_SOUL_GUAY); return true;
        case AP_ITEM_ENEMY_SOUL_JABU_TENTACLE: Flags_SetRandomizerInf(RAND_INF_ENEMY_SOUL_JABU_TENTACLE); return true;
        case AP_ITEM_ENEMY_SOUL_DARK_LINK: Flags_SetRandomizerInf(RAND_INF_ENEMY_SOUL_DARK_LINK); return true;
        case AP_ITEM_ENEMY_SOUL_DOOR_TRAP: Flags_SetRandomizerInf(RAND_INF_ENEMY_SOUL_DOOR_TRAP); return true;
        case AP_ITEM_ENEMY_SOUL_FLYING_FLOOR_TILE: Flags_SetRandomizerInf(RAND_INF_ENEMY_SOUL_FLYING_FLOOR_TILE); return true;
        case AP_ITEM_ENEMY_SOUL_GERUDO_THIEF: Flags_SetRandomizerInf(RAND_INF_ENEMY_SOUL_GERUDO_THIEF); return true;
        case AP_ITEM_ENEMY_SOUL_POE_SISTER: Flags_SetRandomizerInf(RAND_INF_ENEMY_SOUL_POE_SISTER); return true;
        case AP_ITEM_ENEMY_SOUL_POE: Flags_SetRandomizerInf(RAND_INF_ENEMY_SOUL_POE); return true;
        case AP_ITEM_ENEMY_SOUL_LEEVER: Flags_SetRandomizerInf(RAND_INF_ENEMY_SOUL_LEEVER); return true;
        case AP_ITEM_ENEMY_SOUL_STALCHILD: Flags_SetRandomizerInf(RAND_INF_ENEMY_SOUL_STALCHILD); return true;
        case AP_ITEM_ENEMY_SOUL_BIG_OCTO: Flags_SetRandomizerInf(RAND_INF_ENEMY_SOUL_BIG_OCTO); return true;

        case AP_ITEM_POT_SOUL: Flags_SetRandomizerInf(RAND_INF_POT_SOUL); return true;
        case AP_ITEM_CRATE_SOUL: Flags_SetRandomizerInf(RAND_INF_CRATE_SOUL); return true;
        case AP_ITEM_GRASS_SOUL: Flags_SetRandomizerInf(RAND_INF_GRASS_SOUL); return true;
        case AP_ITEM_ROCK_SOUL: Flags_SetRandomizerInf(RAND_INF_ROCK_SOUL); return true;
        case AP_ITEM_TREE_SOUL: Flags_SetRandomizerInf(RAND_INF_TREE_SOUL); return true;
        case AP_ITEM_BEEHIVE_SOUL: Flags_SetRandomizerInf(RAND_INF_BEEHIVE_SOUL); return true;
        case AP_ITEM_SIGN_SOUL: Flags_SetRandomizerInf(RAND_INF_SIGN_SOUL); return true;
        case AP_ITEM_SKULLTULA_SOUL: Flags_SetRandomizerInf(RAND_INF_SKULLTULA_SOUL); return true;
        case AP_ITEM_BUSINESS_SCRUB_SOUL: Flags_SetRandomizerInf(RAND_INF_BUSINESS_SCRUB_SOUL); return true;
        case AP_ITEM_SHOVEL: Flags_SetRandomizerInf(RAND_INF_HAS_SHOVEL); return true;
        case AP_ITEM_DMC_BEAN_SOUL: Flags_SetRandomizerInf(RAND_INF_DEATH_MOUNTAIN_CRATER_BEAN_SOUL); return true;
        case AP_ITEM_DMT_BEAN_SOUL: Flags_SetRandomizerInf(RAND_INF_DEATH_MOUNTAIN_TRAIL_BEAN_SOUL); return true;
        case AP_ITEM_COLOSSUS_BEAN_SOUL: Flags_SetRandomizerInf(RAND_INF_DESERT_COLOSSUS_BEAN_SOUL); return true;
        case AP_ITEM_GV_BEAN_SOUL: Flags_SetRandomizerInf(RAND_INF_GERUDO_VALLEY_BEAN_SOUL); return true;
        case AP_ITEM_GRAVEYARD_BEAN_SOUL: Flags_SetRandomizerInf(RAND_INF_GRAVEYARD_BEAN_SOUL); return true;
        case AP_ITEM_KF_BEAN_SOUL: Flags_SetRandomizerInf(RAND_INF_KOKIRI_FOREST_BEAN_SOUL); return true;
        case AP_ITEM_LH_BEAN_SOUL: Flags_SetRandomizerInf(RAND_INF_LAKE_HYLIA_BEAN_SOUL); return true;
        case AP_ITEM_LW_BRIDGE_BEAN_SOUL: Flags_SetRandomizerInf(RAND_INF_LOST_WOODS_BRIDGE_BEAN_SOUL); return true;
        case AP_ITEM_LW_BEAN_SOUL: Flags_SetRandomizerInf(RAND_INF_LOST_WOODS_BEAN_SOUL); return true;
        case AP_ITEM_ZR_BEAN_SOUL: Flags_SetRandomizerInf(RAND_INF_ZORAS_RIVER_BEAN_SOUL); return true;
        default: return false;
    }
}

void ArchipelagoClient::FinalizeMajorItemReceipt(int modIndex, int itemId, int getItemId) {
    if (!awaitingMajorItemReceipt) return;

    // Once GiveItemEntryWithoutActor() has successfully started an AP major-item
    // receive, the next OnItemReceive callback is the transaction completion.
    //
    // Do NOT require the callback's mod/item/get-item tuple to be byte-for-byte
    // identical to the entry we submitted. Several custom SOH-EXTREME abilities and
    // Souls (notably Shovel) are normalized by the native get-item path before
    // OnItemReceive fires. The old strict comparison left awaitingMajorItemReceipt
    // stuck forever. While stuck, every later AP reward (including Grass checks)
    // remained queued until the save was reloaded.
    //
    // Link cannot receive a second pickup while the major get-item cutscene is active,
    // so the first OnItemReceive after our successful GiveItemEntryWithoutActor call
    // is the safe commit point. Keep the tuple comparison as diagnostics only.
    if (modIndex != awaitingMajorModIndex || itemId != awaitingMajorItemId ||
        (awaitingMajorGetItemId != 0 && getItemId != awaitingMajorGetItemId)) {
        SPDLOG_WARN(
            "[Archipelago] Major receive callback normalized by SoH: expected mod/item/get {}/{}/{}, got {}/{}/{}; committing active AP receive",
            awaitingMajorModIndex, awaitingMajorItemId, awaitingMajorGetItemId,
            modIndex, itemId, getItemId);
    }

    const uint64_t sequence = awaitingMajorSequence;
    const int64_t apItemId = awaitingMajorApItemId;

    gAwaitingMajorCallbackSeen = true;

    if (CaptureApPersistentGrantDigest() == gAwaitingMajorStateDigestBefore) {
        SPDLOG_WARN(
            "[Archipelago] Major AP receive #{} item {} got completion callback but persistent state "
            "has not changed; withholding popup and commit",
            sequence, apItemId);
        return;
    }

    // SOH-EXTREME 0.7.55: make the AP receive path authoritative for every custom
    // persistent ability/soul.  Native Randomizer_Item_Give normally sets these,
    // but AP get-item presentation used to leave some custom RandomizerInf flags
    // unset.  Apply them ONLY after OnItemReceive, so a death during the animation
    // cannot consume the AP queue entry or persist a half-received progression item.
    switch (apItemId) {
        case AP_ITEM_ROLL: Flags_SetRandomizerInf(RAND_INF_HAS_ROLL); break;
        case AP_ITEM_GRAB: Flags_SetRandomizerInf(RAND_INF_CAN_GRAB); break;
        case AP_ITEM_CLIMB: Flags_SetRandomizerInf(RAND_INF_CAN_CLIMB); break;
        case AP_ITEM_CRAWL: Flags_SetRandomizerInf(RAND_INF_CAN_CRAWL); break;
        case AP_ITEM_SPEAK:
            Flags_SetRandomizerInf(RAND_INF_CAN_SPEAK_DEKU);
            Flags_SetRandomizerInf(RAND_INF_CAN_SPEAK_GERUDO);
            Flags_SetRandomizerInf(RAND_INF_CAN_SPEAK_GORON);
            Flags_SetRandomizerInf(RAND_INF_CAN_SPEAK_HYLIAN);
            Flags_SetRandomizerInf(RAND_INF_CAN_SPEAK_KOKIRI);
            Flags_SetRandomizerInf(RAND_INF_CAN_SPEAK_ZORA);
            break;
        case AP_ITEM_ENEMY_SOUL: Flags_SetRandomizerInf(RAND_INF_ENEMY_SOUL); break;
        case AP_ITEM_NPC_SOUL: Flags_SetRandomizerInf(RAND_INF_NPC_SOUL); break;
        case AP_ITEM_ANIMAL_SOUL: Flags_SetRandomizerInf(RAND_INF_ANIMAL_SOUL); break;
        case AP_ITEM_POT_SOUL: Flags_SetRandomizerInf(RAND_INF_POT_SOUL); break;
        case AP_ITEM_CRATE_SOUL: Flags_SetRandomizerInf(RAND_INF_CRATE_SOUL); break;
        case AP_ITEM_GRASS_SOUL: Flags_SetRandomizerInf(RAND_INF_GRASS_SOUL); break;
        case AP_ITEM_ROCK_SOUL: Flags_SetRandomizerInf(RAND_INF_ROCK_SOUL); break;
        case AP_ITEM_TREE_SOUL: Flags_SetRandomizerInf(RAND_INF_TREE_SOUL); break;
        case AP_ITEM_BEEHIVE_SOUL: Flags_SetRandomizerInf(RAND_INF_BEEHIVE_SOUL); break;
        case AP_ITEM_SIGN_SOUL: Flags_SetRandomizerInf(RAND_INF_SIGN_SOUL); break;
        case AP_ITEM_SKULLTULA_SOUL: Flags_SetRandomizerInf(RAND_INF_SKULLTULA_SOUL); break;
        case AP_ITEM_BUSINESS_SCRUB_SOUL: Flags_SetRandomizerInf(RAND_INF_BUSINESS_SCRUB_SOUL); break;
        case AP_ITEM_SHOVEL: Flags_SetRandomizerInf(RAND_INF_HAS_SHOVEL); break;
        case AP_ITEM_DMC_BEAN_SOUL: Flags_SetRandomizerInf(RAND_INF_DEATH_MOUNTAIN_CRATER_BEAN_SOUL); break;
        case AP_ITEM_DMT_BEAN_SOUL: Flags_SetRandomizerInf(RAND_INF_DEATH_MOUNTAIN_TRAIL_BEAN_SOUL); break;
        case AP_ITEM_COLOSSUS_BEAN_SOUL: Flags_SetRandomizerInf(RAND_INF_DESERT_COLOSSUS_BEAN_SOUL); break;
        case AP_ITEM_GV_BEAN_SOUL: Flags_SetRandomizerInf(RAND_INF_GERUDO_VALLEY_BEAN_SOUL); break;
        case AP_ITEM_GRAVEYARD_BEAN_SOUL: Flags_SetRandomizerInf(RAND_INF_GRAVEYARD_BEAN_SOUL); break;
        case AP_ITEM_KF_BEAN_SOUL: Flags_SetRandomizerInf(RAND_INF_KOKIRI_FOREST_BEAN_SOUL); break;
        case AP_ITEM_LH_BEAN_SOUL: Flags_SetRandomizerInf(RAND_INF_LAKE_HYLIA_BEAN_SOUL); break;
        case AP_ITEM_LW_BRIDGE_BEAN_SOUL: Flags_SetRandomizerInf(RAND_INF_LOST_WOODS_BRIDGE_BEAN_SOUL); break;
        case AP_ITEM_LW_BEAN_SOUL: Flags_SetRandomizerInf(RAND_INF_LOST_WOODS_BEAN_SOUL); break;
        case AP_ITEM_ZR_BEAN_SOUL: Flags_SetRandomizerInf(RAND_INF_ZORAS_RIVER_BEAN_SOUL); break;
        default: break;
    }

    awaitingMajorItemReceipt = false;
    awaitingMajorSequence = 0;
    awaitingMajorApItemId = 0;
    gAwaitingMajorFrames = 0;

    SPDLOG_INFO("[Archipelago] Major AP item {} receive #{} verified in persistent state; committing now",
                apItemId, sequence);
    ResetApMajorVerificationState();
    MarkItemApplied(sequence);
    Notification::Emit({
        .prefix = "Archipelago",
        .message = "received",
        .suffix = GetApItemDisplayName(apItemId),
        .remainingTime = 4.0f,
    });
}

void ArchipelagoClient::PrimeNewSaveMetadata() {
    // File creation must stay as close as possible to a normal randomizer save.
    // Do not rebuild the ReceivedItems queue here: APCpp may still be publishing a
    // large replay/scout response and queueMutex contention can stall name-entry
    // creation.  Only stamp the durable AP identity/settings needed by SaveManager.
    std::scoped_lock lock(queueMutex);

    appliedItemCount = 0;
    awaitingMajorItemReceipt = false;
    awaitingMajorSequence = 0;
    awaitingMajorApItemId = 0;
    gAwaitingMajorFrames = 0;
    currentSaveIsArchipelago = true;
    newSaveReplayPending = true;
    saveMetadataLoaded = true;
    gSaveContext.ship.quest.data.randomizer.triforcePiecesCollected = 0;
    saveIdentityMismatch = false;

    const char* serverRaw = CVarGetString(CVAR_REMOTE_ARCHIPELAGO("ServerAddress"), "");
    const char* slotRaw = CVarGetString(CVAR_REMOTE_ARCHIPELAGO("SlotName"), "");
    saveServer = serverRaw ? serverRaw : "";
    saveSlot = slotRaw ? slotRaw : "";

    CVarSetInteger(GetReceivedCountCVar().c_str(), 0);
    pendingItems.clear();
    gDeferredLocationReports.clear();

    SPDLOG_INFO("[Archipelago] Primed new AP save metadata; item history replay deferred until gameplay");
}

void ArchipelagoClient::PrepareNewSaveItemReplay() {
    fallbackNpcSpeechHashes.clear();
    fallbackNpcSpeechSeen.clear();

    std::scoped_lock lock(queueMutex);
    newSaveReplayPending = false;

    // A deliberately-created new AP save starts from a clean SoH inventory, so replay
    // the server's current item history exactly once into that new save.  This also
    // means deleting/recreating a local file does not permanently lose AP starting
    // inventory just because the server remembers that it was delivered before.
    appliedItemCount = 0;
    awaitingMajorItemReceipt = false;
    awaitingMajorSequence = 0;
    awaitingMajorApItemId = 0;
    gAwaitingMajorFrames = 0;
    currentSaveIsArchipelago = true;
    saveMetadataLoaded = true;
    saveIdentityMismatch = false;
    const char* serverRaw = CVarGetString(CVAR_REMOTE_ARCHIPELAGO("ServerAddress"), "");
    const char* slotRaw = CVarGetString(CVAR_REMOTE_ARCHIPELAGO("SlotName"), "");
    saveServer = serverRaw ? serverRaw : "";
    saveSlot = slotRaw ? slotRaw : "";
    CVarSetInteger(GetReceivedCountCVar().c_str(), 0); // legacy migration mirror only
    pendingItems.clear();
    gDeferredLocationReports.clear();
    gNewSaveReplayTargetCount = receivedItemSnapshot.size();
    gNewSaveReplayGraceFrames = AP_NEW_SAVE_REPLAY_GRACE_FRAMES;
    for (uint64_t i = 0; i < receivedItemSnapshot.size(); ++i) {
        // Historical reconstruction is intentionally silent. The player already
        // received these server-side; this pass only rebuilds the new local save.
        pendingItems.push_back({ receivedItemSnapshot[i], false, i });
    }
    SPDLOG_INFO("[Archipelago] New AP save: queued {} historical received items for fast one-time reconstruction "
                "after {} grace frames",
                pendingItems.size(), gNewSaveReplayGraceFrames);
}

void ArchipelagoClient::QueueCheckedLocation(int64_t locationId) {
    std::scoped_lock lock(queueMutex);
    pendingCheckedLocations.push_back(locationId);
}

void ArchipelagoClient::QueueLocationInfo(int64_t locationId, int64_t itemId, int playerId, int flags,
                                          const std::string& itemName, const std::string& playerName,
                                          const std::string& locationName) {
    std::scoped_lock lock(queueMutex);
    PendingScout scout;
    scout.locationId = locationId;
    scout.info.itemId = itemId;
    scout.info.playerId = playerId;
    scout.info.flags = flags;
    scout.info.itemName = itemName;
    scout.info.playerName = playerName;
    scout.info.locationName = locationName;
    pendingScouts.push_back(std::move(scout));
}

int32_t ArchipelagoClient::MapApItemToRandomizerGet(int64_t itemId) const {
    // ArchipelagoItemMap.inc is an assignment table.  It expects a local
    // variable named `randoGet`; it is shared with ProcessItem below.
    RandomizerGet randoGet = RG_NONE;

    if (itemId >= AP_BASE_ITEM_MIN && itemId <= AP_BASE_ITEM_MAX) {
        switch (itemId) {
#include "ArchipelagoItemMap.inc"
            default: break;
        }
        return static_cast<int32_t>(randoGet);
    }

    switch (itemId) {
        case AP_ITEM_ROLL: randoGet = RG_ROLL; break;
        case AP_ITEM_GRAB: randoGet = RG_POWER_BRACELET; break;
        case AP_ITEM_CLIMB: randoGet = RG_CLIMB; break;
        case AP_ITEM_CRAWL: randoGet = RG_CRAWL; break;
        case AP_ITEM_SPEAK: randoGet = RG_NPC_SOUL; break; // visual stand-in for flag-only Speak
        case AP_ITEM_OPEN_CHEST: randoGet = RG_OPEN_CHEST; break;
        case AP_ITEM_ENEMY_SOUL: randoGet = RG_ENEMY_SOUL; break;
        case AP_ITEM_NPC_SOUL: randoGet = RG_NPC_SOUL; break;
        case AP_ITEM_ANIMAL_SOUL: randoGet = RG_ANIMAL_SOUL; break;
        case AP_ITEM_POT_SOUL: randoGet = RG_POT_SOUL; break;
        case AP_ITEM_CRATE_SOUL: randoGet = RG_CRATE_SOUL; break;
        case AP_ITEM_GRASS_SOUL: randoGet = RG_GRASS_SOUL; break;
        case AP_ITEM_ROCK_SOUL: randoGet = RG_ROCK_SOUL; break;
        case AP_ITEM_TREE_SOUL: randoGet = RG_TREE_SOUL; break;
        case AP_ITEM_BEEHIVE_SOUL: randoGet = RG_BEEHIVE_SOUL; break;
        case AP_ITEM_SIGN_SOUL: randoGet = RG_SIGN_SOUL; break;
        case AP_ITEM_SKULLTULA_SOUL: randoGet = RG_SKULLTULA_SOUL; break;
        case AP_ITEM_BUSINESS_SCRUB_SOUL: randoGet = RG_BUSINESS_SCRUB_SOUL; break;
        case AP_ITEM_SHOVEL: randoGet = RG_SHOVEL; break;
        case AP_ITEM_FLOW_OF_TIME: randoGet = RG_SUNS_SONG; break; // time-themed visual
        case AP_ITEM_DMC_BEAN_SOUL: randoGet = RG_DEATH_MOUNTAIN_CRATER_BEAN_SOUL; break;
        case AP_ITEM_DMT_BEAN_SOUL: randoGet = RG_DEATH_MOUNTAIN_TRAIL_BEAN_SOUL; break;
        case AP_ITEM_COLOSSUS_BEAN_SOUL: randoGet = RG_DESERT_COLOSSUS_BEAN_SOUL; break;
        case AP_ITEM_GV_BEAN_SOUL: randoGet = RG_GERUDO_VALLEY_BEAN_SOUL; break;
        case AP_ITEM_GRAVEYARD_BEAN_SOUL: randoGet = RG_GRAVEYARD_BEAN_SOUL; break;
        case AP_ITEM_KF_BEAN_SOUL: randoGet = RG_KOKIRI_FOREST_BEAN_SOUL; break;
        case AP_ITEM_LH_BEAN_SOUL: randoGet = RG_LAKE_HYLIA_BEAN_SOUL; break;
        case AP_ITEM_LW_BRIDGE_BEAN_SOUL: randoGet = RG_LOST_WOODS_BRIDGE_BEAN_SOUL; break;
        case AP_ITEM_LW_BEAN_SOUL: randoGet = RG_LOST_WOODS_BEAN_SOUL; break;
        case AP_ITEM_ZR_BEAN_SOUL: randoGet = RG_ZORAS_RIVER_BEAN_SOUL; break;
        case AP_ITEM_SPEAK_DEKU: randoGet = RG_SPEAK_DEKU; break;
        case AP_ITEM_SPEAK_GERUDO: randoGet = RG_SPEAK_GERUDO; break;
        case AP_ITEM_SPEAK_GORON: randoGet = RG_SPEAK_GORON; break;
        case AP_ITEM_SPEAK_HYLIAN: randoGet = RG_SPEAK_HYLIAN; break;
        case AP_ITEM_SPEAK_KOKIRI: randoGet = RG_SPEAK_KOKIRI; break;
        case AP_ITEM_SPEAK_ZORA: randoGet = RG_SPEAK_ZORA; break;
        case AP_ITEM_ANIMAL_SOUL_COW: randoGet = RG_ANIMAL_SOUL_COW; break;
        case AP_ITEM_ANIMAL_SOUL_CUCCO: randoGet = RG_ANIMAL_SOUL_CUCCO; break;
        case AP_ITEM_ANIMAL_SOUL_DOG: randoGet = RG_ANIMAL_SOUL_DOG; break;
        case AP_ITEM_ANIMAL_SOUL_FISH: randoGet = RG_ANIMAL_SOUL_FISH; break;
        case AP_ITEM_ANIMAL_SOUL_BUG: randoGet = RG_ANIMAL_SOUL_BUG; break;
        case AP_ITEM_ANIMAL_SOUL_BUTTERFLY: randoGet = RG_ANIMAL_SOUL_BUTTERFLY; break;
        case AP_ITEM_ANIMAL_SOUL_FROG: randoGet = RG_ANIMAL_SOUL_FROG; break;
        case AP_ITEM_ANIMAL_SOUL_HORSE: randoGet = RG_ANIMAL_SOUL_HORSE; break;
        case AP_ITEM_ENEMY_SOUL_STALFOS: randoGet = RG_ENEMY_SOUL_STALFOS; break;
        case AP_ITEM_ENEMY_SOUL_OCTOROK: randoGet = RG_ENEMY_SOUL_OCTOROK; break;
        case AP_ITEM_ENEMY_SOUL_WALLMASTER: randoGet = RG_ENEMY_SOUL_WALLMASTER; break;
        case AP_ITEM_ENEMY_SOUL_DODONGO: randoGet = RG_ENEMY_SOUL_DODONGO; break;
        case AP_ITEM_ENEMY_SOUL_KEESE: randoGet = RG_ENEMY_SOUL_KEESE; break;
        case AP_ITEM_ENEMY_SOUL_TEKTITE: randoGet = RG_ENEMY_SOUL_TEKTITE; break;
        case AP_ITEM_ENEMY_SOUL_PEAHAT: randoGet = RG_ENEMY_SOUL_PEAHAT; break;
        case AP_ITEM_ENEMY_SOUL_LIZALFOS_DINOLFOS: randoGet = RG_ENEMY_SOUL_LIZALFOS_DINOLFOS; break;
        case AP_ITEM_ENEMY_SOUL_GOHMA_LARVA: randoGet = RG_ENEMY_SOUL_GOHMA_LARVA; break;
        case AP_ITEM_ENEMY_SOUL_SHABOM: randoGet = RG_ENEMY_SOUL_SHABOM; break;
        case AP_ITEM_ENEMY_SOUL_BABY_DODONGO: randoGet = RG_ENEMY_SOUL_BABY_DODONGO; break;
        case AP_ITEM_ENEMY_SOUL_BIRI_BARI: randoGet = RG_ENEMY_SOUL_BIRI_BARI; break;
        case AP_ITEM_ENEMY_SOUL_TAILPASARAN: randoGet = RG_ENEMY_SOUL_TAILPASARAN; break;
        case AP_ITEM_ENEMY_SOUL_TORCH_SLUG: randoGet = RG_ENEMY_SOUL_TORCH_SLUG; break;
        case AP_ITEM_ENEMY_SOUL_MOBLIN: randoGet = RG_ENEMY_SOUL_MOBLIN; break;
        case AP_ITEM_ENEMY_SOUL_ARMOS: randoGet = RG_ENEMY_SOUL_ARMOS; break;
        case AP_ITEM_ENEMY_SOUL_DEKU_BABA: randoGet = RG_ENEMY_SOUL_DEKU_BABA; break;
        case AP_ITEM_ENEMY_SOUL_DEKU_SCRUB: randoGet = RG_ENEMY_SOUL_DEKU_SCRUB; break;
        case AP_ITEM_ENEMY_SOUL_BUBBLE: randoGet = RG_ENEMY_SOUL_BUBBLE; break;
        case AP_ITEM_ENEMY_SOUL_BEAMOS: randoGet = RG_ENEMY_SOUL_BEAMOS; break;
        case AP_ITEM_ENEMY_SOUL_FLOORMASTER: randoGet = RG_ENEMY_SOUL_FLOORMASTER; break;
        case AP_ITEM_ENEMY_SOUL_REDEAD_GIBDO: randoGet = RG_ENEMY_SOUL_REDEAD_GIBDO; break;
        case AP_ITEM_ENEMY_SOUL_FLARE_DANCER: randoGet = RG_ENEMY_SOUL_FLARE_DANCER; break;
        case AP_ITEM_ENEMY_SOUL_DEAD_HAND: randoGet = RG_ENEMY_SOUL_DEAD_HAND; break;
        case AP_ITEM_ENEMY_SOUL_SHELL_BLADE: randoGet = RG_ENEMY_SOUL_SHELL_BLADE; break;
        case AP_ITEM_ENEMY_SOUL_LIKE_LIKE: randoGet = RG_ENEMY_SOUL_LIKE_LIKE; break;
        case AP_ITEM_ENEMY_SOUL_SPIKE: randoGet = RG_ENEMY_SOUL_SPIKE; break;
        case AP_ITEM_ENEMY_SOUL_ANUBIS: randoGet = RG_ENEMY_SOUL_ANUBIS; break;
        case AP_ITEM_ENEMY_SOUL_IRON_KNUCKLE: randoGet = RG_ENEMY_SOUL_IRON_KNUCKLE; break;
        case AP_ITEM_ENEMY_SOUL_SKULL_KID: randoGet = RG_ENEMY_SOUL_SKULL_KID; break;
        case AP_ITEM_ENEMY_SOUL_FLYING_POT: randoGet = RG_ENEMY_SOUL_FLYING_POT; break;
        case AP_ITEM_ENEMY_SOUL_FREEZARD: randoGet = RG_ENEMY_SOUL_FREEZARD; break;
        case AP_ITEM_ENEMY_SOUL_STINGER: randoGet = RG_ENEMY_SOUL_STINGER; break;
        case AP_ITEM_ENEMY_SOUL_WOLFOS: randoGet = RG_ENEMY_SOUL_WOLFOS; break;
        case AP_ITEM_ENEMY_SOUL_GUAY: randoGet = RG_ENEMY_SOUL_GUAY; break;
        case AP_ITEM_ENEMY_SOUL_JABU_TENTACLE: randoGet = RG_ENEMY_SOUL_JABU_TENTACLE; break;
        case AP_ITEM_ENEMY_SOUL_DARK_LINK: randoGet = RG_ENEMY_SOUL_DARK_LINK; break;
        case AP_ITEM_ENEMY_SOUL_DOOR_TRAP: randoGet = RG_ENEMY_SOUL_DOOR_TRAP; break;
        case AP_ITEM_ENEMY_SOUL_FLYING_FLOOR_TILE: randoGet = RG_ENEMY_SOUL_FLYING_FLOOR_TILE; break;
        case AP_ITEM_ENEMY_SOUL_GERUDO_THIEF: randoGet = RG_ENEMY_SOUL_GERUDO_THIEF; break;
        case AP_ITEM_ENEMY_SOUL_POE_SISTER: randoGet = RG_ENEMY_SOUL_POE_SISTER; break;
        case AP_ITEM_ENEMY_SOUL_POE: randoGet = RG_ENEMY_SOUL_POE; break;
        case AP_ITEM_ENEMY_SOUL_LEEVER: randoGet = RG_ENEMY_SOUL_LEEVER; break;
        case AP_ITEM_ENEMY_SOUL_STALCHILD: randoGet = RG_ENEMY_SOUL_STALCHILD; break;
        case AP_ITEM_ENEMY_SOUL_BIG_OCTO: randoGet = RG_ENEMY_SOUL_BIG_OCTO; break;

        case AP_ITEM_SHADOW_SILVER_BLADES: randoGet = RG_SHADOW_SILVER_BLADES; break;
        case AP_ITEM_SHADOW_SILVER_PIT: randoGet = RG_SHADOW_SILVER_PIT; break;
        case AP_ITEM_SHADOW_SILVER_SPIKES: randoGet = RG_SHADOW_SILVER_SPIKES; break;
        case AP_ITEM_SPIRIT_SILVER_CHILD: randoGet = RG_SPIRIT_SILVER_CHILD; break;
        case AP_ITEM_SPIRIT_SILVER_SUN: randoGet = RG_SPIRIT_SILVER_SUN; break;
        case AP_ITEM_SPIRIT_SILVER_BOULDERS: randoGet = RG_SPIRIT_SILVER_BOULDERS; break;
        case AP_ITEM_BOTW_SILVER: randoGet = RG_BOTW_SILVER; break;
        case AP_ITEM_ICE_CAVERN_SILVER_BLADES: randoGet = RG_ICE_CAVERN_SILVER_BLADES; break;
        case AP_ITEM_ICE_CAVERN_SILVER_BLOCK: randoGet = RG_ICE_CAVERN_SILVER_BLOCK; break;
        case AP_ITEM_GTG_SILVER_SLOPE: randoGet = RG_GTG_SILVER_SLOPE; break;
        case AP_ITEM_GTG_SILVER_LAVA: randoGet = RG_GTG_SILVER_LAVA; break;
        case AP_ITEM_GTG_SILVER_WATER: randoGet = RG_GTG_SILVER_WATER; break;
        case AP_ITEM_GANONS_CASTLE_SILVER_LIGHT: randoGet = RG_GANONS_CASTLE_SILVER_LIGHT; break;
        case AP_ITEM_GANONS_CASTLE_SILVER_FOREST: randoGet = RG_GANONS_CASTLE_SILVER_FOREST; break;
        case AP_ITEM_GANONS_CASTLE_SILVER_FIRE: randoGet = RG_GANONS_CASTLE_SILVER_FIRE; break;
        case AP_ITEM_GANONS_CASTLE_SILVER_SPIRIT: randoGet = RG_GANONS_CASTLE_SILVER_SPIRIT; break;
        case AP_ITEM_DODONGOS_CAVERN_MQ_SILVER: randoGet = RG_DODONGOS_CAVERN_MQ_SILVER; break;
        case AP_ITEM_SHADOW_MQ_SILVER_INVISIBLE_BLADES: randoGet = RG_SHADOW_MQ_SILVER_INVISIBLE_BLADES; break;
        case AP_ITEM_SPIRIT_MQ_SILVER_LOBBY: randoGet = RG_SPIRIT_MQ_SILVER_LOBBY; break;
        case AP_ITEM_SPIRIT_MQ_SILVER_BIG_WALL: randoGet = RG_SPIRIT_MQ_SILVER_BIG_WALL; break;
        case AP_ITEM_GANONS_CASTLE_MQ_SILVER_WATER: randoGet = RG_GANONS_CASTLE_MQ_SILVER_WATER; break;
        case AP_ITEM_GANONS_CASTLE_MQ_SILVER_SHADOW: randoGet = RG_GANONS_CASTLE_MQ_SILVER_SHADOW; break;
        default:
            if (itemId >= AP_FIRST_SONG_NOTE && itemId <= AP_LAST_SONG_NOTE) {
                randoGet = RG_SONG_OF_TIME; // note-family visual; reward remains exact note flag
            }
            break;
    }

    return static_cast<int32_t>(randoGet);
}

static bool ParseFlatStringIntObject(const std::string& raw, std::unordered_map<std::string, int64_t>& out) {
    out.clear();
    size_t i = 0;
    auto skipWs = [&]() { while (i < raw.size() && std::isspace(static_cast<unsigned char>(raw[i]))) ++i; };
    skipWs();
    if (i >= raw.size() || raw[i++] != '{') return false;
    for (;;) {
        skipWs();
        if (i < raw.size() && raw[i] == '}') { ++i; break; }
        if (i >= raw.size() || raw[i++] != '"') return false;
        std::string key;
        while (i < raw.size() && raw[i] != '"') {
            if (raw[i] == '\\' && i + 1 < raw.size()) ++i;
            key.push_back(raw[i++]);
        }
        if (i >= raw.size() || raw[i++] != '"') return false;
        skipWs();
        if (i >= raw.size() || raw[i++] != ':') return false;
        skipWs();
        bool negative = false;
        if (i < raw.size() && raw[i] == '-') { negative = true; ++i; }
        if (i >= raw.size() || !std::isdigit(static_cast<unsigned char>(raw[i]))) return false;
        int64_t value = 0;
        while (i < raw.size() && std::isdigit(static_cast<unsigned char>(raw[i]))) {
            value = value * 10 + (raw[i++] - '0');
        }
        out[key] = negative ? -value : value;
        skipWs();
        if (i < raw.size() && raw[i] == ',') { ++i; continue; }
        if (i < raw.size() && raw[i] == '}') { ++i; break; }
        return false;
    }
    skipWs();
    return i == raw.size();
}

static void RefreshArchipelagoRandomizerHooks() {
    // IMPORTANT: use Ship's own native randomizer refresh path instead of trying
    // to maintain a hand-written list of shuffle modules here.  Normal SoH calls
    // this exact dependency path from the randomizer OnLoadGame hook after
    // IS_RANDO becomes true.  AP changes the quest/settings outside the normal
    // randomizer menu, so without this call modules that were disabled at boot
    // keep their hooks unregistered (MegaSouls was the most visible example: a
    // Pot Soul slot could be ON while pots still spawned normally).
    //
    // Running the complete IS_RANDO dependency makes AP behave the same as a
    // normally configured SoH randomizer save and automatically includes future
    // modules that register with RegisterShipInitFunc(..., { "IS_RANDO" }).
    ShipInit::Init("IS_RANDO");
    SPDLOG_INFO("[Archipelago] Refreshed ALL native IS_RANDO hooks from authoritative AP settings");
}

void ArchipelagoClient::SetSlotSettingsFromJson(const std::string& raw) {
    std::unordered_map<std::string, int64_t> parsed;
    if (!ParseFlatStringIntObject(raw, parsed)) {
        SPDLOG_ERROR("[Archipelago] Invalid extreme_soh_cvars slot data");
        return;
    }

    std::unordered_map<std::string, int> nextSettings;
    nextSettings.reserve(parsed.size());
    for (const auto& [key, value] : parsed) {
        nextSettings[key] = static_cast<int>(value);
    }

    size_t loadedCount = 0;
    bool settingsChanged = false;
    {
        std::scoped_lock lock(queueMutex);
        settingsChanged = !slotSettingsLoaded || cachedSlotSettingsJson != raw;
        slotSettings = std::move(nextSettings);
        cachedSlotSettingsJson = raw;
        slotSettingsLoaded = true;
        loadedCount = slotSettings.size();
    }

    // APCpp can invoke this callback away from the gameplay thread. Do not
    // mutate CVars, native Settings/Context, ShipInit hooks, or tracker state here.
    if (settingsChanged) {
        slotSettingsPendingApply.store(true);
        SPDLOG_INFO("[Archipelago] Cached {} changed authoritative SoH/Extreme settings for gameplay-thread apply",
                    loadedCount);
    } else {
        SPDLOG_DEBUG("[Archipelago] Live AP settings match the already-applied/cached snapshot; skipping duplicate refresh");
    }
}

void ArchipelagoClient::SetLocationNameMapFromJson(const std::string& raw) {
    std::unordered_map<std::string, int64_t> parsed;
    if (!ParseFlatStringIntObject(raw, parsed)) {
        SPDLOG_ERROR("[Archipelago] Invalid extreme_location_name_to_id slot data");
        return;
    }

    std::unordered_map<std::string, int64_t> next;
    next.reserve(parsed.size());
    for (const auto& [name, locationId] : parsed) {
        const std::string normalized = NormalizeApLocationName(name);
        if (normalized.empty()) {
            continue;
        }
        auto [it, inserted] = next.emplace(normalized, locationId);
        if (!inserted && it->second != locationId) {
            // Never guess if two server locations collapse to the same normalized name.
            it->second = -1;
        }
    }

    {
        std::scoped_lock lock(queueMutex);
        authoritativeLocationNameIndex = std::move(next);
        locationNameMapLoaded = true;
        checkFinderMappingsPrepared = false;
    }

    SPDLOG_INFO("[Archipelago] Loaded {} authoritative SOH-EXTREME location name mappings",
                authoritativeLocationNameIndex.size());
}

void ArchipelagoClient::SetShopPricesFromJson(const std::string& raw) {
    std::unordered_map<std::string, int64_t> parsed;
    if (!ParseFlatStringIntObject(raw, parsed)) {
        SPDLOG_ERROR("[Archipelago] Invalid extreme_shop_prices slot data");
        return;
    }
    shopPrices.clear();
    for (const auto& [key, value] : parsed) {
        try {
            const int64_t location = std::stoll(key);
            shopPrices[location] = static_cast<uint16_t>(std::clamp<int64_t>(value, 0, 65535));
        } catch (...) {
            SPDLOG_WARN("[Archipelago] Ignoring malformed shop location id {}", key);
        }
    }
    shopPricesLoaded = true;
    SPDLOG_INFO("[Archipelago] Loaded {} exact AP shop prices", shopPrices.size());
}

void ArchipelagoClient::ApplySlotSettings() {
    slotSettingsPendingApply.store(false);
    std::unordered_map<std::string, int> settingsSnapshot;
    {
        std::scoped_lock lock(queueMutex);
        if (!slotSettingsLoaded) {
            return;
        }
        settingsSnapshot = slotSettings;
    }

    SPDLOG_INFO("[Archipelago] SOH-EXTREME AP settings runtime 0.8.05 active");

    // APWorld sends extreme_soh_cvars using the *native option suffixes*
    // (ShufflePots, ShuffleGrass, PotSoul, etc.).  Do NOT reconstruct the CVar
    // prefix here.  Ship's Option table is the authority for the exact CVar name
    // consumed by Option::GetOptionIndex()/RAND_GET_OPTION().
    //
    // This fixes the failure where AP successfully wrote/read 223 synthetic CVars,
    // but the real Randomizer Options still read 0.  A normal SoH randomizer menu
    // worked because it writes Option::GetCVarName() directly.
    auto settings = Rando::Settings::GetInstance();
    if (!settings) {
        SPDLOG_ERROR("[Archipelago] Randomizer Settings singleton unavailable; cannot apply AP settings");
        return;
    }

    size_t mappedNativeOptions = 0;
    size_t nativeReadbackMismatches = 0;
    std::set<std::string> consumedKeys;

    for (const auto& option : settings->GetAllOptions()) {
        const std::string& nativeCVar = option.GetCVarName();
        if (nativeCVar.empty()) {
            continue;
        }

        // AP keys are the final component of the native CVar, e.g.
        // gRandoSettings.ShufflePots -> ShufflePots.
        const size_t dot = nativeCVar.find_last_of('.');
        const std::string nativeKey = dot == std::string::npos ? nativeCVar : nativeCVar.substr(dot + 1);
        auto it = settingsSnapshot.find(nativeKey);
        if (it == settingsSnapshot.end()) {
            continue;
        }

        const int requested = it->second;
        CVarSetInteger(nativeCVar.c_str(), requested);
        consumedKeys.insert(nativeKey);
        ++mappedNativeOptions;

        const int readBack = CVarGetInteger(nativeCVar.c_str(), requested - 1);
        if (readBack != requested) {
            ++nativeReadbackMismatches;
            SPDLOG_ERROR("[Archipelago] Native option CVar write failed: {} (AP key {}) requested={} readback={}",
                         nativeCVar, nativeKey, requested, readBack);
        }
    }

    // Preserve AP-only/custom CVars that are not represented by Settings::mOptions.
    // These are intentionally secondary; gameplay randomizer settings above always
    // use the exact CVar name from Ship's native Option table.
    for (const auto& [key, value] : settingsSnapshot) {
        if (consumedKeys.contains(key)) {
            continue;
        }
        const std::string fallbackCVar = std::string("gRandoSettings.") + key;
        CVarSetInteger(fallbackCVar.c_str(), value);
    }

    // Callbacks may change visibility/availability, then copy the now-correct native
    // menu indices into the live Context used by RAND_GET_OPTION.
    settings->UpdateAllOptions();
    settings->SetAllToContext();

    // AP is the authority for logic on an Archipelago save. Native trick flags are
    // stored separately from the normal option array, so a local SoH randomizer
    // session can otherwise leak enabled tricks into Check Finder/reachability even
    // when the AP YAML has no tricks enabled. The current AP slot-data format does
    // not publish a native trick list, so fail closed: no local trick is allowed to
    // alter an AP seed's logic. (The resolved AP world already accounts for any
    // tricks selected on the server side.)
    if (auto randoContext = Rando::Context::GetInstance(); randoContext != nullptr) {
        randoContext->ResetTrickOptions();
    }
    CVarSetString(CVAR_RANDOMIZER_SETTING("EnabledTricks"), "");

    if (IS_RANDO && gPlayState != nullptr) {
        // AP settings are authoritative for BOTH physical SoH behavior and the
        // Check Finder. Refresh native randomizer hooks first, then schedule one
        // deferred reachability pass so the tracker cannot keep logic computed
        // from stale/local menu settings.
        RefreshArchipelagoRandomizerHooks();
        if (CVarGetInteger(CVAR_TRACKER_CHECK("EnableAvailableChecks"), 0)) {
            CheckTracker::RecalculateAvailableChecks();
        }
    }

    auto slotValue = [&settingsSnapshot](const char* key, int fallback = 0) {
        auto it = settingsSnapshot.find(key);
        return it == settingsSnapshot.end() ? fallback : it->second;
    };
    // 0.11.21b: ExtraTraps.* are persistent local menu preferences, not AP
    // slot settings. Writing them here erased the player's choices on create,
    // load and reconnect (and SaveConsoleVariablesNextFrame persisted the loss).
    // ExtraTraps.cpp now reads the authoritative RSK_EXTREME_* options directly
    // for an AP save, without changing any local enhancement preference.

    // Mirror the authoritative AP seed into the same persisted native CVars used
    // by the local Randomizer menu. The local menu therefore shows the AP seed's
    // configuration instead of stale pre-connection values, and local/randomizer
    // runtime logic reads the same settings snapshot.
    Ship::Context::GetRawInstance()->GetWindow()->GetGui()->SaveConsoleVariablesNextFrame();

    // Log AP input AND the live RSK result.  If these differ now, the log tells us
    // which exact layer is wrong instead of merely proving a synthetic CVar exists.
    SPDLOG_INFO(
        "[Archipelago] AP native settings: mapped={}/{} readback_mismatches={} | "
        "Pots AP={} RSK={} PotSoul AP={} RSK={} Grass AP={} RSK={} GrassSoul AP={} RSK={} "
        "Rocks AP={} RSK={} RockSoul AP={} RSK={} Crates AP={} RSK={} CrateSoul AP={} RSK={} "
        "Speak AP={} RSK={} NPCSpeech AP={} RSK={} FlowOfTime AP={} RSK={}",
        mappedNativeOptions, settingsSnapshot.size(), nativeReadbackMismatches,
        slotValue("ShufflePots"), RAND_GET_OPTION(RSK_SHUFFLE_POTS).Get(),
        slotValue("PotSoul"), RAND_GET_OPTION(RSK_SHUFFLE_POT_SOUL).Get(),
        slotValue("ShuffleGrass"), RAND_GET_OPTION(RSK_SHUFFLE_GRASS).Get(),
        slotValue("GrassSoul"), RAND_GET_OPTION(RSK_SHUFFLE_GRASS_SOUL).Get(),
        slotValue("ShuffleRocks"), RAND_GET_OPTION(RSK_SHUFFLE_ROCKS).Get(),
        slotValue("RockSoul"), RAND_GET_OPTION(RSK_SHUFFLE_ROCK_SOUL).Get(),
        slotValue("ShuffleCrates"), RAND_GET_OPTION(RSK_SHUFFLE_CRATES).Get(),
        slotValue("CrateSoul"), RAND_GET_OPTION(RSK_SHUFFLE_CRATE_SOUL).Get(),
        slotValue("ShuffleSpeak"), RAND_GET_OPTION(RSK_SHUFFLE_SPEAK).Get(),
        slotValue("NPCSpeechSanity"), RAND_GET_OPTION(RSK_NPC_SPEECH_SANITY).Get(),
        slotValue("FlowOfTime"), RAND_GET_OPTION(RSK_SHUFFLE_FLOW_OF_TIME).Get());
}

void ArchipelagoClient::EnforceSlotSettings() {
    if (!slotSettingsLoaded || !currentSaveIsArchipelago || gSaveContext.ship.quest.id != QUEST_RANDOMIZER) {
        return;
    }

    std::unordered_map<std::string, int> settingsSnapshot;
    {
        std::scoped_lock lock(queueMutex);
        settingsSnapshot = slotSettings;
    }

    // AP owns randomizer settings for an AP save. The local randomizer menu is not
    // allowed to silently change physical checks/logic after connection. If a user
    // changes one of those CVars locally, restore the server value and refresh the
    // affected hooks before the next gameplay update.
    auto settings = Rando::Settings::GetInstance();
    if (!settings) return;
    for (const auto& option : settings->GetAllOptions()) {
        const std::string& nativeCVar = option.GetCVarName();
        if (nativeCVar.empty()) continue;
        const size_t dot = nativeCVar.find_last_of('.');
        const std::string key = dot == std::string::npos ? nativeCVar : nativeCVar.substr(dot + 1);
        auto it = settingsSnapshot.find(key);
        if (it == settingsSnapshot.end()) continue;
        const int actual = CVarGetInteger(nativeCVar.c_str(), it->second);
        if (actual != it->second) {
            SPDLOG_WARN("[Archipelago] Native randomizer setting {}={} disagrees with AP {}; restoring server snapshot",
                        nativeCVar, actual, it->second);
            ApplySlotSettings();
            return;
        }
    }
}

bool ArchipelagoClient::IsReadyForFileSelect() const {
    // Do not make file creation wait for every LocationScout reply.  Large
    // all-sanity slots can contain thousands of locations and the old barrier
    // made "New Archipelago File" appear frozen.  Settings + active-location
    // ownership + exact shop prices are the data that must exist before native
    // randomizer initialization.  Scout/model data can finish in the background;
    // actors refresh their concrete placement lazily before drawing/interaction.
    return IsAuthenticated() && slotSettingsLoaded && activeLocationsLoaded && shopPricesLoaded;
}

void ArchipelagoClient::ApplyPostInitSlotState() {
    // Kakariko Gate was removed as a normal setting in this SoH fork. AP still has
    // that setting, so apply its resolved open state after save initialization.
    if (kakarikoGateOpen) {
        Flags_SetInfTable(INFTABLE_SHOWED_ZELDAS_LETTER_TO_GATE_GUARD);
    }
}

void ArchipelagoClient::SetActiveLocationsFromJson(const std::string& raw) {
    // APCpp gives raw slot data as JSON text.  This value is deliberately just a flat
    // array of positive integer location IDs, so do not pull jsoncpp into soh.exe only
    // to parse it.  jsoncpp in APCpp is built /MD while SoH is /MT, which causes
    // LNK2038 RuntimeLibrary mismatches on MSVC.  Scanning the integers here keeps the
    // Archipelago DLL boundary clean and avoids any extra CRT dependency.
    std::unordered_set<int64_t> parsed;
    int64_t value = 0;
    bool inNumber = false;

    for (char c : raw) {
        if (c >= '0' && c <= '9') {
            inNumber = true;
            value = (value * 10) + static_cast<int64_t>(c - '0');
            continue;
        }

        if (inNumber) {
            parsed.insert(value);
            value = 0;
            inNumber = false;
        }
    }
    if (inNumber) {
        parsed.insert(value);
    }

    // An empty array is valid (for example, a pathological option combination), but
    // malformed non-array slot data should not be treated as successfully loaded.
    const auto first = raw.find_first_not_of(" \t\r\n");
    const auto last = raw.find_last_not_of(" \t\r\n");
    if (first == std::string::npos || last == std::string::npos ||
        raw[first] != '[' || raw[last] != ']') {
        SPDLOG_ERROR("[Archipelago] Invalid extreme_active_locations slot data: {}", raw);
        return;
    }

    activeLocations = std::move(parsed);
    activeLocationsLoaded = true;
    scoutsRequested = false;
    scoutedLocations.clear();
    scoutedLocationNameIndex.clear();
    checkFinderMappingsPrepared = false;
    SPDLOG_INFO("[Archipelago] Loaded {} active server locations from slot data", activeLocations.size());

    // Network callback: defer tracker mutation/reachability to Update().
    activeLocationsPendingRefresh.store(true);
}

void ArchipelagoClient::RequestLocationScouts() {
    if (!IsAuthenticated() || scoutsRequested) return;

    // Never scout the full static map. Archipelago validates LocationScouts against the
    // current slot, and many SoH checks do not exist for every option combination.
    if (!activeLocationsLoaded) {
        SPDLOG_DEBUG("[Archipelago] Waiting for extreme_active_locations slot data before scouting");
        return;
    }

    // extreme_active_locations already came from the server-generated APWorld, so every
    // ID in it is valid for this slot. Scout the COMPLETE active set, not only locations
    // that happen to exist in the baked rcToApLocation table. The latter was missing a
    // large number of stock SoH freestanding checks (for example KF Behind Mido's House
    // Rupee), which made them impossible to report or receive placements for.
    std::set<int64_t> locations(activeLocations.begin(), activeLocations.end());

    if (locations.empty()) {
        expectedScoutCount = 0;
        scoutsRequested = true;
        return;
    }

    expectedScoutCount = locations.size();
    scoutsRequested = true;
    SPDLOG_INFO("[Archipelago] Scouting all {} ACTIVE SOH-EXTREME locations in chunks", locations.size());

    // Large all-sanity slots can exceed 2,000 locations.  Split scout requests
    // into modest packets instead of asking APCpp/server to process one giant
    // set in a single callback burst.
    constexpr size_t kScoutChunkSize = 256;
    std::set<int64_t> chunk;
    for (int64_t locationId : locations) {
        chunk.insert(locationId);
        if (chunk.size() >= kScoutChunkSize) {
            AP_SendLocationScouts(chunk, false);
            chunk.clear();
        }
    }
    if (!chunk.empty()) {
        AP_SendLocationScouts(chunk, false);
    }
}

void ArchipelagoClient::IndexScoutedLocation(int64_t locationId, const ScoutedLocation& info) {
    checkFinderMappingsPrepared = false;
    const std::string normalized = NormalizeApLocationName(info.locationName);
    if (normalized.empty()) {
        return;
    }

    auto [it, inserted] = scoutedLocationNameIndex.emplace(normalized, locationId);
    if (!inserted && it->second != locationId) {
        // Never guess when two AP locations normalize to the same name.
        it->second = -1;
    }
}

bool ArchipelagoClient::IsLocationActive(int64_t locationId) const {
    return activeLocationsLoaded && activeLocations.find(locationId) != activeLocations.end();
}

bool ArchipelagoClient::IsLocationReported(int64_t locationId) const {
    return reportedLocations.find(locationId) != reportedLocations.end();
}

size_t ArchipelagoClient::GetActiveLocationCount() const {
    return activeLocationsLoaded ? activeLocations.size() : 0;
}

size_t ArchipelagoClient::GetReportedActiveLocationCount() const {
    if (!activeLocationsLoaded) {
        return 0;
    }
    size_t count = 0;
    for (const int64_t locationId : activeLocations) {
        if (reportedLocations.find(locationId) != reportedLocations.end()) {
            ++count;
        }
    }
    return count;
}

bool ArchipelagoClient::PrepareCheckFinderMappings() {
    if (!enabled.load() || !activeLocationsLoaded) {
        return false;
    }

    // Missing native mappings need scout names. Do not run a partial Check Finder
    // that silently omits unvisited scenes; wait until the initial active scout set
    // is resident. Normal gameplay remains scene-local and does not wait on this.
    if (expectedScoutCount > 0 && scoutedLocations.size() < expectedScoutCount) {
        RequestLocationScouts();
        SPDLOG_DEBUG("[Archipelago] Check Finder mapping waiting for scouts ({}/{})",
                     scoutedLocations.size(), expectedScoutCount);
        return false;
    }

    if (checkFinderMappingsPrepared) {
        return true;
    }

    const auto started = std::chrono::steady_clock::now();
    size_t exactMapped = 0;
    size_t suffixMapped = 0;
    size_t ambiguous = 0;
    size_t unresolved = 0;

    // v6 deliberately stopped resolving the entire world on load. Check Finder is
    // the one feature that needs a complete active RC set, so build it on demand.
    //
    // Important performance difference from the old startup path:
    // - AP scout names were normalized ONCE by IndexScoutedLocation().
    // - exact matches are O(1).
    // - suffix fallback compares already-normalized strings and never allocates/
    //   normalizes every scout inside the inner loop.
    // This keeps the scene-local placement architecture while allowing a full-world
    // reachability query when the user explicitly enables Available Checks.
    for (const auto& entry : Rando::StaticData::GetLocationTable()) {
        const int32_t rc = static_cast<int32_t>(entry.GetRandomizerCheck());
        if (rc <= static_cast<int32_t>(RC_UNKNOWN_CHECK)) {
            continue;
        }

        auto existing = rcToApLocation.find(rc);
        if (existing != rcToApLocation.end()) {
            continue;
        }

        const std::string fullName = NormalizeApLocationName(entry.GetName());
        const std::string shortName = NormalizeApLocationName(entry.GetShortName());

        int64_t matched = -1;

        auto tryAuthoritativeExact = [&](const std::string& normalized) {
            if (normalized.empty() || matched >= 0) {
                return;
            }
            auto it = authoritativeLocationNameIndex.find(normalized);
            if (it != authoritativeLocationNameIndex.end() && it->second >= 0 &&
                activeLocations.find(it->second) != activeLocations.end()) {
                matched = it->second;
            }
        };

        // Prefer the exact seed namespace from slot data.  This is the primary path
        // for standalone SOH-EXTREME and survives APWorld location renames.
        tryAuthoritativeExact(fullName);
        tryAuthoritativeExact(shortName);

        auto tryExact = [&](const std::string& normalized) {
            if (normalized.empty() || matched >= 0) {
                return;
            }
            auto it = scoutedLocationNameIndex.find(normalized);
            if (it != scoutedLocationNameIndex.end() && it->second >= 0 &&
                activeLocations.find(it->second) != activeLocations.end()) {
                matched = it->second;
            }
        };

        tryExact(fullName);
        tryExact(shortName);

        if (matched >= 0) {
            ++exactMapped;
        } else if (!shortName.empty()) {
            int64_t authoritativeSuffix = -1;
            bool authoritativeAmbiguous = false;
            for (const auto& [apName, apLocation] : authoritativeLocationNameIndex) {
                if (apLocation < 0 || activeLocations.find(apLocation) == activeLocations.end() ||
                    shortName.size() > apName.size()) {
                    continue;
                }
                if (apName.compare(apName.size() - shortName.size(), shortName.size(), shortName) != 0) {
                    continue;
                }
                if (authoritativeSuffix >= 0 && authoritativeSuffix != apLocation) {
                    authoritativeAmbiguous = true;
                    break;
                }
                authoritativeSuffix = apLocation;
            }
            if (!authoritativeAmbiguous && authoritativeSuffix >= 0) {
                matched = authoritativeSuffix;
                ++suffixMapped;
            }

            int64_t suffixMatch = -1;
            bool suffixAmbiguous = false;

            if (matched < 0) for (const auto& [apName, apLocation] : scoutedLocationNameIndex) {
                if (apLocation < 0 || activeLocations.find(apLocation) == activeLocations.end() ||
                    shortName.size() > apName.size()) {
                    continue;
                }

                if (apName.compare(apName.size() - shortName.size(), shortName.size(), shortName) != 0) {
                    continue;
                }

                if (suffixMatch >= 0 && suffixMatch != apLocation) {
                    suffixAmbiguous = true;
                    break;
                }
                suffixMatch = apLocation;
            }

            if (matched < 0 && !suffixAmbiguous && suffixMatch >= 0) {
                matched = suffixMatch;
                ++suffixMapped;
            } else if (matched < 0 && suffixAmbiguous) {
                ++ambiguous;
            }
        }

        if (matched < 0) {
            ++unresolved;
            continue;
        }

        rcToApLocation[rc] = matched;
        apLocationToRc[matched] = rc;
    }

    checkFinderMappingsPrepared = true;

    size_t activeMapped = 0;
    for (const auto& [rc, apLocation] : rcToApLocation) {
        if (activeLocations.find(apLocation) != activeLocations.end()) {
            ++activeMapped;
        }
    }

    const auto elapsedMs = std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::steady_clock::now() - started).count();

    SPDLOG_INFO(
        "[Archipelago] Check Finder mapping ready in {}ms: activeMapped={} / activeLocations={}, "
        "newExact={}, newSuffix={}, ambiguous={}, unresolvedNative={}",
        elapsedMs, activeMapped, activeLocations.size(), exactMapped, suffixMapped, ambiguous, unresolved);

    return true;
}

int64_t ArchipelagoClient::ResolveApLocationForCheck(int32_t randomizerCheck) {
    auto direct = rcToApLocation.find(randomizerCheck);
    if (direct != rcToApLocation.end()) {
        return direct->second;
    }

    // Missing static mappings are resolved lazily for the one concrete RC that
    // the game is currently touching.  Do NOT scan every RandomizerCheck at
    // runtime: some table entries are intentionally sparse/conditional, and a
    // full RC_MAX walk added unnecessary crash risk during scout processing.
    auto* location = Rando::StaticData::GetLocation(static_cast<RandomizerCheck>(randomizerCheck));
    if (location == nullptr) {
        return -1;
    }

    const std::string fullName = NormalizeApLocationName(location->GetName());
    const std::string shortName = NormalizeApLocationName(location->GetShortName());
    if (fullName.empty() && shortName.empty()) {
        return -1;
    }

    // Primary path for standalone SOH-EXTREME: use the exact name -> id table
    // published by this seed.  Do not depend on the compiled stock-SoH id map.
    int64_t matched = -1;
    auto tryAuthoritative = [&](const std::string& normalized) {
        if (normalized.empty() || matched >= 0) return;
        auto it = authoritativeLocationNameIndex.find(normalized);
        if (it != authoritativeLocationNameIndex.end() && it->second >= 0 &&
            activeLocations.find(it->second) != activeLocations.end()) {
            matched = it->second;
        }
    };
    tryAuthoritative(fullName);
    tryAuthoritative(shortName);

    // Compatibility fallback for old slots that do not publish the map yet.
    // The scout callback builds a normalized name index once.
    if (matched < 0 && !fullName.empty()) {
        auto indexed = scoutedLocationNameIndex.find(fullName);
        if (indexed != scoutedLocationNameIndex.end() && indexed->second >= 0) {
            matched = indexed->second;
        }
    }

    // Some native short names intentionally omit the AP prefix. First try a
    // unique suffix against the server-authoritative map, then fall back to scouts.
    if (matched < 0 && !shortName.empty()) {
        int64_t suffixMatch = -1;
        for (const auto& [apName, apLocation] : authoritativeLocationNameIndex) {
            if (apLocation < 0 || activeLocations.find(apLocation) == activeLocations.end() ||
                shortName.size() > apName.size() ||
                apName.compare(apName.size() - shortName.size(), shortName.size(), shortName) != 0) {
                continue;
            }
            if (suffixMatch >= 0 && suffixMatch != apLocation) {
                suffixMatch = -1;
                break;
            }
            suffixMatch = apLocation;
        }
        if (suffixMatch >= 0) matched = suffixMatch;
    }

    // Legacy/scout fallback for old slots.
    if (matched < 0 && !shortName.empty()) {
        for (const auto& [apLocation, info] : scoutedLocations) {
            const std::string apName = NormalizeApLocationName(info.locationName);
            if (shortName.size() > apName.size() ||
                apName.compare(apName.size() - shortName.size(), shortName.size(), shortName) != 0) {
                continue;
            }
            if (matched != -1 && matched != apLocation) {
                SPDLOG_WARN("[Archipelago] Ambiguous lazy RC mapping for {} ({})", randomizerCheck, location->GetName());
                return -1;
            }
            matched = apLocation;
        }
    }

    if (matched < 0) {
        return -1;
    }

    rcToApLocation[randomizerCheck] = matched;
    apLocationToRc[matched] = randomizerCheck;
    SPDLOG_DEBUG("[Archipelago] Lazily resolved missing RC mapping: {} -> {} ({})",
                randomizerCheck, matched, location->GetName());
    return matched;
}

std::string ArchipelagoClient::GetRemoteItemDescription(int32_t randomizerCheck) {
    if (!IsAuthenticated() || scoutedLocations.empty()) return {};
    const int64_t apLocation = ResolveApLocationForCheck(randomizerCheck);
    if (apLocation < 0) return {};
    auto scoutIt = scoutedLocations.find(apLocation);
    if (scoutIt == scoutedLocations.end()) return {};
    const auto& info = scoutIt->second;
    if (info.playerId == AP_GetPlayerID()) return {};

    std::string result = info.itemName.empty() ? "Archipelago Item" : info.itemName;
    result += " for ";
    if (!info.playerName.empty()) {
        result += info.playerName;
    } else if (info.playerId > 0) {
        result += "Player " + std::to_string(info.playerId);
    } else {
        result += "another player";
    }
    result += "'s world";
    return result;
}

void ArchipelagoClient::EnsureLocationScouts() {
    RequestLocationScouts();
}
void ArchipelagoClient::RefreshPlacementForCheck(int32_t randomizerCheck) {
    // Actor draw/drop code can ask for a GetItemEntry long after the initial AP
    // placement reconciliation.  Always make the scouted AP placement authoritative
    // immediately before SoH chooses a model.  This fixes stale native models for
    // freestanding items, shops, and item drops spawned from grass/rocks/etc.
    if (!IsEnabled() || !IsAuthenticated() || scoutedLocations.empty()) return;

    auto ctx = Rando::Context::GetInstance();
    if (!ctx) return;

    const int64_t apLocation = ResolveApLocationForCheck(randomizerCheck);
    if (apLocation < 0) return;

    auto scoutIt = scoutedLocations.find(apLocation);
    if (scoutIt == scoutedLocations.end()) return;

    auto* loc = ctx->GetItemLocation(static_cast<RandomizerCheck>(randomizerCheck));
    if (loc == nullptr || loc->HasObtained()) return;

    auto priceIt = shopPrices.find(apLocation);
    if (priceIt != shopPrices.end()) {
        loc->SetPrice(priceIt->second);
    }

    const auto& info = scoutIt->second;
    RandomizerGet display = RG_NONE;
    if (info.playerId == AP_GetPlayerID()) {
        display = MapApItemNameToRandomizerGet(info.itemName);
        if (display == RG_NONE) {
            display = static_cast<RandomizerGet>(MapApItemToRandomizerGet(info.itemId));
        }
        if (display == RG_ICE_TRAP || info.itemName == "Ice Trap") {
            display = GetIceTrapDisguise(apLocation);
        }
    } else {
        display = GetRemoteArchipelagoDisplay(info.flags);
    }

    if (display == RG_NONE) {
        display = GetRemoteArchipelagoDisplay(info.flags);
    }

    if (loc->GetPlacedRandomizerGet() != display) {
        SPDLOG_INFO("[Archipelago] Live model refresh RC {} / {} <- {} (AP item {}, RandomizerGet {}, recipient {})",
                    randomizerCheck, info.locationName, info.itemName, info.itemId, static_cast<int>(display),
                    info.playerName);
        loc->SetPlacedItem(display);
    }
}

void ArchipelagoClient::RefreshPlacementsForScene(int16_t sceneNum) {
    if (!IsEnabled() || !IsAuthenticated() || scoutedLocations.empty()) return;

    // Build the native scene -> RC list once. This cache is static game data and
    // does not depend on the AP slot.
    static const std::unordered_map<int16_t, std::vector<int32_t>> checksByScene = []() {
        std::unordered_map<int16_t, std::vector<int32_t>> result;
        for (const auto& entry : Rando::StaticData::GetLocationTable()) {
            const RandomizerCheck rc = entry.GetRandomizerCheck();
            if (rc == RC_UNKNOWN_CHECK || rc == RC_MAX || rc == RC_LINKS_POCKET) continue;
            result[static_cast<int16_t>(entry.GetScene())].push_back(static_cast<int32_t>(rc));
        }
        return result;
    }();

    auto sceneIt = checksByScene.find(sceneNum);
    if (sceneIt == checksByScene.end()) return;

    size_t refreshed = 0;
    for (int32_t rc : sceneIt->second) {
        const size_t before = rcToApLocation.size();
        RefreshPlacementForCheck(rc);
        if (rcToApLocation.size() != before || OwnsCheckCached(rc)) {
            ++refreshed;
        }
    }

    SPDLOG_DEBUG("[Archipelago] Scene-local placement refresh scene={} checks={} mapped/active={}",
                 sceneNum, sceneIt->second.size(), refreshed);
}

void ArchipelagoClient::ApplyScoutedPlacements() {
    auto ctx = Rando::Context::GetInstance();
    if (!ctx || scoutedLocations.empty()) return;

    const int selfPlayer = AP_GetPlayerID();
    for (const auto& [apLocation, info] : scoutedLocations) {
        auto rcIt = apLocationToRc.find(apLocation);
        if (rcIt == apLocationToRc.end()) {
            // Do not perform the old AP-location x all-native-locations name
            // search here. On a large all-sanity slot that became an O(N*M)
            // reload stall. Missing static mappings are resolved lazily by
            // RefreshPlacementForCheck()/ResolveApLocationForCheck() only when
            // that concrete actor/check is actually touched.
            continue;
        }

        auto* loc = ctx->GetItemLocation(static_cast<RandomizerCheck>(rcIt->second));
        if (loc == nullptr) continue;

        auto priceIt = shopPrices.find(apLocation);
        if (priceIt != shopPrices.end()) {
            loc->SetPrice(priceIt->second);
        }
        if (loc->HasObtained()) continue;

        RandomizerGet display = RG_NONE;
        if (info.playerId == selfPlayer) {
            // Match the working Shipwright reference: prefer the AP item name when
            // converting a scouted placement into SoH's native RandomizerGet table.
            // SOH-EXTREME numeric IDs remain a fallback for custom/newer items.
            display = MapApItemNameToRandomizerGet(info.itemName);
            if (display == RG_NONE) {
                display = static_cast<RandomizerGet>(MapApItemToRandomizerGet(info.itemId));
            }
            if (display == RG_ICE_TRAP || info.itemName == "Ice Trap") {
                display = GetIceTrapDisguise(apLocation);
            }
        } else {
            // A location containing another player's item cannot use that game's native model.
            // Show the Archipelago logo instead. Progression/useful AP items are colored;
            // filler/junk/trap-only items use the grayscale Archipelago logo.
            display = GetRemoteArchipelagoDisplay(info.flags);
        }

        if (display == RG_NONE) {
            // Unknown same-slot/custom items should also avoid the unrelated Triforce model.
            display = GetRemoteArchipelagoDisplay(info.flags);
        }

        if (loc->GetPlacedRandomizerGet() != display) {
            SPDLOG_INFO("[Archipelago] Placement RC {} / {} <- {} (AP item {}, RandomizerGet {}, recipient {})",
                        rcIt->second, info.locationName, info.itemName, info.itemId, static_cast<int>(display),
                        info.playerName);
            loc->SetPlacedItem(display);
        }
    }
}

bool ArchipelagoClient::ProcessItem(int64_t itemId, bool /*notify*/, uint64_t sequence) {
    if (gPlayState == nullptr) {
        SPDLOG_DEBUG("[Archipelago] Deferring item {} until a save is loaded", itemId);
        return false;
    }

    Player* player = GET_PLAYER(gPlayState);
    if (player == nullptr || Player_InBlockingCsMode(gPlayState, player) ||
        (player->stateFlags1 & (PLAYER_STATE1_IN_ITEM_CS | PLAYER_STATE1_GETTING_ITEM | PLAYER_STATE1_CARRYING_ACTOR))) {
        return false;
    }

    const bool historicalNewSaveReplay =
        gNewSaveReplayTargetCount != 0 && sequence < gNewSaveReplayTargetCount;

    RandomizerGet randoGet = RG_NONE;
    if (itemId >= AP_BASE_ITEM_MIN && itemId <= AP_BASE_ITEM_MAX) {
        switch (itemId) {
#include "ArchipelagoItemMap.inc"
            default:
                SPDLOG_WARN("[Archipelago] Base item id {} has no SoH mapping yet", itemId);
                return true;
        }
    } else {
        switch (itemId) {
            case AP_ITEM_ROLL: randoGet = RG_ROLL; break;
            case AP_ITEM_GRAB: randoGet = RG_POWER_BRACELET; break;
            case AP_ITEM_CLIMB: randoGet = RG_CLIMB; break;
            case AP_ITEM_CRAWL: randoGet = RG_CRAWL; break;
            case AP_ITEM_SPEAK:
                // Important AP progression item.  Do NOT set the ability here: starting
                // the get-item animation is not a committed receive.  The consolidated
                // Speak flags are applied by FinalizeMajorItemReceipt only after SoH's
                // OnItemReceive confirms the item survived the animation/death boundary.
                randoGet = RG_SPEAK_HYLIAN;
                break;
            case AP_ITEM_OPEN_CHEST: randoGet = RG_OPEN_CHEST; break;
            case AP_ITEM_ENEMY_SOUL: randoGet = RG_ENEMY_SOUL; break;
            case AP_ITEM_NPC_SOUL: randoGet = RG_NPC_SOUL; break;
            case AP_ITEM_ANIMAL_SOUL: randoGet = RG_ANIMAL_SOUL; break;
            case AP_ITEM_POT_SOUL: randoGet = RG_POT_SOUL; break;
            case AP_ITEM_CRATE_SOUL: randoGet = RG_CRATE_SOUL; break;
            case AP_ITEM_GRASS_SOUL: randoGet = RG_GRASS_SOUL; break;
            case AP_ITEM_ROCK_SOUL: randoGet = RG_ROCK_SOUL; break;
            case AP_ITEM_TREE_SOUL: randoGet = RG_TREE_SOUL; break;
            case AP_ITEM_BEEHIVE_SOUL: randoGet = RG_BEEHIVE_SOUL; break;
            case AP_ITEM_SIGN_SOUL: randoGet = RG_SIGN_SOUL; break;
            case AP_ITEM_SKULLTULA_SOUL: randoGet = RG_SKULLTULA_SOUL; break;
            case AP_ITEM_BUSINESS_SCRUB_SOUL: randoGet = RG_BUSINESS_SCRUB_SOUL; break;
            case AP_ITEM_SHOVEL: randoGet = RG_SHOVEL; break;
            case AP_ITEM_DMC_BEAN_SOUL: randoGet = RG_DEATH_MOUNTAIN_CRATER_BEAN_SOUL; break;
            case AP_ITEM_DMT_BEAN_SOUL: randoGet = RG_DEATH_MOUNTAIN_TRAIL_BEAN_SOUL; break;
            case AP_ITEM_COLOSSUS_BEAN_SOUL: randoGet = RG_DESERT_COLOSSUS_BEAN_SOUL; break;
            case AP_ITEM_GV_BEAN_SOUL: randoGet = RG_GERUDO_VALLEY_BEAN_SOUL; break;
            case AP_ITEM_GRAVEYARD_BEAN_SOUL: randoGet = RG_GRAVEYARD_BEAN_SOUL; break;
            case AP_ITEM_KF_BEAN_SOUL: randoGet = RG_KOKIRI_FOREST_BEAN_SOUL; break;
            case AP_ITEM_LH_BEAN_SOUL: randoGet = RG_LAKE_HYLIA_BEAN_SOUL; break;
            case AP_ITEM_LW_BRIDGE_BEAN_SOUL: randoGet = RG_LOST_WOODS_BRIDGE_BEAN_SOUL; break;
            case AP_ITEM_LW_BEAN_SOUL: randoGet = RG_LOST_WOODS_BEAN_SOUL; break;
            case AP_ITEM_ZR_BEAN_SOUL: randoGet = RG_ZORAS_RIVER_BEAN_SOUL; break;
            case AP_ITEM_SPEAK_DEKU: randoGet = RG_SPEAK_DEKU; break;
            case AP_ITEM_SPEAK_GERUDO: randoGet = RG_SPEAK_GERUDO; break;
            case AP_ITEM_SPEAK_GORON: randoGet = RG_SPEAK_GORON; break;
            case AP_ITEM_SPEAK_HYLIAN: randoGet = RG_SPEAK_HYLIAN; break;
            case AP_ITEM_SPEAK_KOKIRI: randoGet = RG_SPEAK_KOKIRI; break;
            case AP_ITEM_SPEAK_ZORA: randoGet = RG_SPEAK_ZORA; break;
            case AP_ITEM_ANIMAL_SOUL_COW: randoGet = RG_ANIMAL_SOUL_COW; break;
            case AP_ITEM_ANIMAL_SOUL_CUCCO: randoGet = RG_ANIMAL_SOUL_CUCCO; break;
            case AP_ITEM_ANIMAL_SOUL_DOG: randoGet = RG_ANIMAL_SOUL_DOG; break;
            case AP_ITEM_ANIMAL_SOUL_FISH: randoGet = RG_ANIMAL_SOUL_FISH; break;
            case AP_ITEM_ANIMAL_SOUL_BUG: randoGet = RG_ANIMAL_SOUL_BUG; break;
            case AP_ITEM_ANIMAL_SOUL_BUTTERFLY: randoGet = RG_ANIMAL_SOUL_BUTTERFLY; break;
            case AP_ITEM_ANIMAL_SOUL_FROG: randoGet = RG_ANIMAL_SOUL_FROG; break;
            case AP_ITEM_ANIMAL_SOUL_HORSE: randoGet = RG_ANIMAL_SOUL_HORSE; break;
            case AP_ITEM_ENEMY_SOUL_STALFOS: randoGet = RG_ENEMY_SOUL_STALFOS; break;
            case AP_ITEM_ENEMY_SOUL_OCTOROK: randoGet = RG_ENEMY_SOUL_OCTOROK; break;
            case AP_ITEM_ENEMY_SOUL_WALLMASTER: randoGet = RG_ENEMY_SOUL_WALLMASTER; break;
            case AP_ITEM_ENEMY_SOUL_DODONGO: randoGet = RG_ENEMY_SOUL_DODONGO; break;
            case AP_ITEM_ENEMY_SOUL_KEESE: randoGet = RG_ENEMY_SOUL_KEESE; break;
            case AP_ITEM_ENEMY_SOUL_TEKTITE: randoGet = RG_ENEMY_SOUL_TEKTITE; break;
            case AP_ITEM_ENEMY_SOUL_PEAHAT: randoGet = RG_ENEMY_SOUL_PEAHAT; break;
            case AP_ITEM_ENEMY_SOUL_LIZALFOS_DINOLFOS: randoGet = RG_ENEMY_SOUL_LIZALFOS_DINOLFOS; break;
            case AP_ITEM_ENEMY_SOUL_GOHMA_LARVA: randoGet = RG_ENEMY_SOUL_GOHMA_LARVA; break;
            case AP_ITEM_ENEMY_SOUL_SHABOM: randoGet = RG_ENEMY_SOUL_SHABOM; break;
            case AP_ITEM_ENEMY_SOUL_BABY_DODONGO: randoGet = RG_ENEMY_SOUL_BABY_DODONGO; break;
            case AP_ITEM_ENEMY_SOUL_BIRI_BARI: randoGet = RG_ENEMY_SOUL_BIRI_BARI; break;
            case AP_ITEM_ENEMY_SOUL_TAILPASARAN: randoGet = RG_ENEMY_SOUL_TAILPASARAN; break;
            case AP_ITEM_ENEMY_SOUL_TORCH_SLUG: randoGet = RG_ENEMY_SOUL_TORCH_SLUG; break;
            case AP_ITEM_ENEMY_SOUL_MOBLIN: randoGet = RG_ENEMY_SOUL_MOBLIN; break;
            case AP_ITEM_ENEMY_SOUL_ARMOS: randoGet = RG_ENEMY_SOUL_ARMOS; break;
            case AP_ITEM_ENEMY_SOUL_DEKU_BABA: randoGet = RG_ENEMY_SOUL_DEKU_BABA; break;
            case AP_ITEM_ENEMY_SOUL_DEKU_SCRUB: randoGet = RG_ENEMY_SOUL_DEKU_SCRUB; break;
            case AP_ITEM_ENEMY_SOUL_BUBBLE: randoGet = RG_ENEMY_SOUL_BUBBLE; break;
            case AP_ITEM_ENEMY_SOUL_BEAMOS: randoGet = RG_ENEMY_SOUL_BEAMOS; break;
            case AP_ITEM_ENEMY_SOUL_FLOORMASTER: randoGet = RG_ENEMY_SOUL_FLOORMASTER; break;
            case AP_ITEM_ENEMY_SOUL_REDEAD_GIBDO: randoGet = RG_ENEMY_SOUL_REDEAD_GIBDO; break;
            case AP_ITEM_ENEMY_SOUL_FLARE_DANCER: randoGet = RG_ENEMY_SOUL_FLARE_DANCER; break;
            case AP_ITEM_ENEMY_SOUL_DEAD_HAND: randoGet = RG_ENEMY_SOUL_DEAD_HAND; break;
            case AP_ITEM_ENEMY_SOUL_SHELL_BLADE: randoGet = RG_ENEMY_SOUL_SHELL_BLADE; break;
            case AP_ITEM_ENEMY_SOUL_LIKE_LIKE: randoGet = RG_ENEMY_SOUL_LIKE_LIKE; break;
            case AP_ITEM_ENEMY_SOUL_SPIKE: randoGet = RG_ENEMY_SOUL_SPIKE; break;
            case AP_ITEM_ENEMY_SOUL_ANUBIS: randoGet = RG_ENEMY_SOUL_ANUBIS; break;
            case AP_ITEM_ENEMY_SOUL_IRON_KNUCKLE: randoGet = RG_ENEMY_SOUL_IRON_KNUCKLE; break;
            case AP_ITEM_ENEMY_SOUL_SKULL_KID: randoGet = RG_ENEMY_SOUL_SKULL_KID; break;
            case AP_ITEM_ENEMY_SOUL_FLYING_POT: randoGet = RG_ENEMY_SOUL_FLYING_POT; break;
            case AP_ITEM_ENEMY_SOUL_FREEZARD: randoGet = RG_ENEMY_SOUL_FREEZARD; break;
            case AP_ITEM_ENEMY_SOUL_STINGER: randoGet = RG_ENEMY_SOUL_STINGER; break;
            case AP_ITEM_ENEMY_SOUL_WOLFOS: randoGet = RG_ENEMY_SOUL_WOLFOS; break;
            case AP_ITEM_ENEMY_SOUL_GUAY: randoGet = RG_ENEMY_SOUL_GUAY; break;
            case AP_ITEM_ENEMY_SOUL_JABU_TENTACLE: randoGet = RG_ENEMY_SOUL_JABU_TENTACLE; break;
            case AP_ITEM_ENEMY_SOUL_DARK_LINK: randoGet = RG_ENEMY_SOUL_DARK_LINK; break;
        case AP_ITEM_ENEMY_SOUL_DOOR_TRAP: randoGet = RG_ENEMY_SOUL_DOOR_TRAP; break;
        case AP_ITEM_ENEMY_SOUL_FLYING_FLOOR_TILE: randoGet = RG_ENEMY_SOUL_FLYING_FLOOR_TILE; break;
        case AP_ITEM_ENEMY_SOUL_GERUDO_THIEF: randoGet = RG_ENEMY_SOUL_GERUDO_THIEF; break;
        case AP_ITEM_ENEMY_SOUL_POE_SISTER: randoGet = RG_ENEMY_SOUL_POE_SISTER; break;
        case AP_ITEM_ENEMY_SOUL_POE: randoGet = RG_ENEMY_SOUL_POE; break;
        case AP_ITEM_ENEMY_SOUL_LEEVER: randoGet = RG_ENEMY_SOUL_LEEVER; break;
        case AP_ITEM_ENEMY_SOUL_STALCHILD: randoGet = RG_ENEMY_SOUL_STALCHILD; break;
        case AP_ITEM_ENEMY_SOUL_BIG_OCTO: randoGet = RG_ENEMY_SOUL_BIG_OCTO; break;

        case AP_ITEM_SHADOW_SILVER_BLADES: randoGet = RG_SHADOW_SILVER_BLADES; break;
        case AP_ITEM_SHADOW_SILVER_PIT: randoGet = RG_SHADOW_SILVER_PIT; break;
        case AP_ITEM_SHADOW_SILVER_SPIKES: randoGet = RG_SHADOW_SILVER_SPIKES; break;
        case AP_ITEM_SPIRIT_SILVER_CHILD: randoGet = RG_SPIRIT_SILVER_CHILD; break;
        case AP_ITEM_SPIRIT_SILVER_SUN: randoGet = RG_SPIRIT_SILVER_SUN; break;
        case AP_ITEM_SPIRIT_SILVER_BOULDERS: randoGet = RG_SPIRIT_SILVER_BOULDERS; break;
        case AP_ITEM_BOTW_SILVER: randoGet = RG_BOTW_SILVER; break;
        case AP_ITEM_ICE_CAVERN_SILVER_BLADES: randoGet = RG_ICE_CAVERN_SILVER_BLADES; break;
        case AP_ITEM_ICE_CAVERN_SILVER_BLOCK: randoGet = RG_ICE_CAVERN_SILVER_BLOCK; break;
        case AP_ITEM_GTG_SILVER_SLOPE: randoGet = RG_GTG_SILVER_SLOPE; break;
        case AP_ITEM_GTG_SILVER_LAVA: randoGet = RG_GTG_SILVER_LAVA; break;
        case AP_ITEM_GTG_SILVER_WATER: randoGet = RG_GTG_SILVER_WATER; break;
        case AP_ITEM_GANONS_CASTLE_SILVER_LIGHT: randoGet = RG_GANONS_CASTLE_SILVER_LIGHT; break;
        case AP_ITEM_GANONS_CASTLE_SILVER_FOREST: randoGet = RG_GANONS_CASTLE_SILVER_FOREST; break;
        case AP_ITEM_GANONS_CASTLE_SILVER_FIRE: randoGet = RG_GANONS_CASTLE_SILVER_FIRE; break;
        case AP_ITEM_GANONS_CASTLE_SILVER_SPIRIT: randoGet = RG_GANONS_CASTLE_SILVER_SPIRIT; break;
        case AP_ITEM_DODONGOS_CAVERN_MQ_SILVER: randoGet = RG_DODONGOS_CAVERN_MQ_SILVER; break;
        case AP_ITEM_SHADOW_MQ_SILVER_INVISIBLE_BLADES: randoGet = RG_SHADOW_MQ_SILVER_INVISIBLE_BLADES; break;
        case AP_ITEM_SPIRIT_MQ_SILVER_LOBBY: randoGet = RG_SPIRIT_MQ_SILVER_LOBBY; break;
        case AP_ITEM_SPIRIT_MQ_SILVER_BIG_WALL: randoGet = RG_SPIRIT_MQ_SILVER_BIG_WALL; break;
        case AP_ITEM_GANONS_CASTLE_MQ_SILVER_WATER: randoGet = RG_GANONS_CASTLE_MQ_SILVER_WATER; break;
        case AP_ITEM_GANONS_CASTLE_MQ_SILVER_SHADOW: randoGet = RG_GANONS_CASTLE_MQ_SILVER_SHADOW; break;
            case AP_ITEM_FLOW_OF_TIME:
                Flags_SetRandomizerInf(RAND_INF_FLOW_OF_TIME);
                if (!Flags_GetRandomizerInf(RAND_INF_FLOW_OF_TIME)) {
                    SPDLOG_ERROR("[Archipelago] Flow of Time failed persistence verification; retrying");
                    return false;
                }
                if (!historicalNewSaveReplay) {
                    Notification::Emit({ .prefix = "Archipelago", .message = "received", .suffix = "Flow of Time",
                                         .remainingTime = 4.0f });
                }
                return true;
            default:
                if (itemId >= AP_FIRST_SONG_NOTE && itemId <= AP_LAST_SONG_NOTE) {
                    int noteIndex = static_cast<int>(itemId - AP_FIRST_SONG_NOTE);
                    const RandomizerInf noteFlag =
                        static_cast<RandomizerInf>(RAND_INF_SONG_NOTE_0 + noteIndex);
                    Flags_SetRandomizerInf(noteFlag);
                    if (!Flags_GetRandomizerInf(noteFlag)) {
                        SPDLOG_ERROR("[Archipelago] Song Note {} failed persistence verification; retrying",
                                     noteIndex + 1);
                        return false;
                    }
                    RefreshSongNotes();
                    if (!historicalNewSaveReplay) {
                        Notification::Emit({
                            .prefix = "Archipelago",
                            .message = "received",
                            .suffix = "Song Note " + std::to_string(noteIndex + 1),
                            .remainingTime = 3.0f,
                        });
                    }
                    return true;
                }
                SPDLOG_WARN("[Archipelago] Unknown SOH-EXTREME item id {}", itemId);
                return true;
        }
    }

    if (randoGet == RG_NONE) {
        return true;
    }

    // SOH-EXTREME inserts one physical tier before the vanilla Strength/Scale
    // upgrades. Resolve those first AP copies explicitly instead of depending on
    // the generic progressive presentation path to infer the fork-only tier:
    //   Strength #1 -> Grab / Power Bracelet (does not increment UPG_STRENGTH)
    //   Scale    #1 -> Swim / Bronze Scale    (does not increment UPG_SCALE)
    // Subsequent copies remain RG_PROGRESSIVE_* and advance the normal tiers.
    if (randoGet == RG_PROGRESSIVE_STRENGTH && OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_SHUFFLE_GRAB) &&
        !Flags_GetRandomizerInf(RAND_INF_CAN_GRAB)) {
        SPDLOG_INFO("[Archipelago] Resolving first Strength Upgrade as Grab / Power Bracelet");
        randoGet = RG_POWER_BRACELET;
    } else if (randoGet == RG_PROGRESSIVE_SCALE && OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_SHUFFLE_SWIM) &&
               !Flags_GetRandomizerInf(RAND_INF_CAN_SWIM)) {
        SPDLOG_INFO("[Archipelago] Resolving first Progressive Scale as Swim / Bronze Scale");
        randoGet = RG_BRONZE_SCALE;
    }

    // SoH traps are transient effects, not persistent inventory. A brand-new
    // local save reconstructing old ReceivedItems must not retrigger historical
    // traps. Live traps still use the normal pendingIceTrapCount path.
    if (randoGet == RG_ICE_TRAP) {
        if (historicalNewSaveReplay) {
            return true;
        }
        const auto beforeTrapCount = gSaveContext.ship.pendingIceTrapCount;
        gSaveContext.ship.pendingIceTrapCount++;
        if (gSaveContext.ship.pendingIceTrapCount <= beforeTrapCount) {
            SPDLOG_ERROR("[Archipelago] Ice Trap failed to queue; retrying");
            return false;
        }
        SPDLOG_INFO("[Archipelago] Queued Ice Trap (pending={})", gSaveContext.ship.pendingIceTrapCount);
        Notification::Emit({ .prefix = "Archipelago", .message = "received", .suffix = "Ice Trap",
                             .remainingTime = 4.0f });
        SendTrapLink("Ice Trap");
        return true;
    }

    auto item = Rando::StaticData::RetrieveItem(randoGet);
    GetItemEntry giEntry = item.GetGIEntry_Copy();

    // A newly-created local AP file may need to reconstruct a large server-side
    // ReceivedItems history. Starting a hold-item cutscene for every historical
    // major item can leave the first session effectively locked in item presentation
    // for minutes. Apply historical rewards directly and silently instead.
    if (historicalNewSaveReplay) {
        if (ApplyExtremePersistentApItem(itemId)) {
            return true;
        }

        if (giEntry.modIndex == MOD_RANDOMIZER) {
            Randomizer_Item_Give(gPlayState, giEntry);
        } else if (giEntry.itemId != ITEM_NONE) {
            Item_Give(gPlayState, static_cast<uint8_t>(giEntry.itemId));
        } else {
            SPDLOG_WARN("[Archipelago] Historical AP item {} ({}) has no direct give path; treating as consumed",
                        itemId, item.GetName().english);
        }
        return true;
    }

    // Open Chest is a pure randomizer progression flag.  Do not defer it to the
    // over-the-head major-item animation path: AP can mark the network item as
    // received before that animation finishes, leaving generation/tracker state
    // ahead of the actual save flag.  Apply it synchronously here.
    //
    // Randomizer_Item_Give already implements progressive semantics:
    //   first copy  -> RAND_INF_CAN_OPEN_CHEST
    //   second copy -> RAND_INF_CAN_OPEN_LARGE_CHEST
    if (randoGet == RG_OPEN_CHEST) {
        const bool beforeSmallChest = Flags_GetRandomizerInf(RAND_INF_CAN_OPEN_CHEST);
        const bool beforeLargeChest = Flags_GetRandomizerInf(RAND_INF_CAN_OPEN_LARGE_CHEST);
        SPDLOG_INFO("[Archipelago] Applying Open Chest immediately (small={}, large={})",
                    beforeSmallChest, beforeLargeChest);
        Randomizer_Item_Give(gPlayState, giEntry);
        const bool afterSmallChest = Flags_GetRandomizerInf(RAND_INF_CAN_OPEN_CHEST);
        const bool afterLargeChest = Flags_GetRandomizerInf(RAND_INF_CAN_OPEN_LARGE_CHEST);
        SPDLOG_INFO("[Archipelago] Open Chest applied (small={}, large={})",
                    afterSmallChest, afterLargeChest);
        if (afterSmallChest == beforeSmallChest && afterLargeChest == beforeLargeChest) {
            SPDLOG_ERROR("[Archipelago] Open Chest state did not advance; retrying");
            return false;
        }
        Notification::Emit({
            .prefix = "Archipelago",
            .message = "received",
            .suffix = item.GetName().english,
            .remainingTime = 4.0f,
        });
        return true;
    }

    // These AP rewards are vanilla inventory/stat items even though they are looked
    // up through the randomizer table. Apply them through Item_Give unconditionally
    // so their save fields are updated regardless of IsMajorItem classification.
    // This also covers Piece of Heart (WINNER), which maps to RG_PIECE_OF_HEART.
    if (randoGet == RG_GOLD_SKULLTULA_TOKEN || randoGet == RG_PIECE_OF_HEART ||
        randoGet == RG_HEART_CONTAINER) {
        if (giEntry.itemId == ITEM_NONE) {
            SPDLOG_ERROR("[Archipelago] Vanilla stat reward {} ({}) has no vanilla ItemID",
                         itemId, item.GetName().english);
            return true;
        }

        const uint64_t statDigestBefore = CaptureApPersistentGrantDigest();
        SPDLOG_INFO("[Archipelago] Applying vanilla stat reward id {} ({}) with Item_Give (itemId={})",
                    itemId, item.GetName().english, giEntry.itemId);
        Item_Give(gPlayState, static_cast<uint8_t>(giEntry.itemId));
        if (CaptureApPersistentGrantDigest() == statDigestBefore) {
            SPDLOG_ERROR("[Archipelago] Vanilla stat reward {} ({}) did not change persistent state; retrying",
                         itemId, item.GetName().english);
            return false;
        }
        Notification::Emit({
            .prefix = "Archipelago",
            .message = "received",
            .suffix = item.GetName().english,
            .remainingTime = 4.0f,
        });
        return true;
    }

    // Progressive Wallet needs an explicit save-state progression path in AP mode.
    // The generic major get-item path can normalize the child/adult wallet entry to
    // a different vanilla get-item callback and then commit the AP receive even though
    // the wallet tier did not advance.  That was visible as a server-side
    // "Received Progressive Wallet" while the rupee cap stayed at 99.
    //
    // Apply exactly one wallet step and verify the resulting state before allowing
    // the transactional queue entry to commit.  This is idempotent with AP replay
    // because MarkItemApplied() remains the persistence boundary.
    if (randoGet == RG_PROGRESSIVE_WALLET) {
        const bool hadChildWallet = Flags_GetRandomizerInf(RAND_INF_HAS_WALLET);
        const int beforeLevel = CUR_UPG_VALUE(UPG_WALLET);

        if (!hadChildWallet) {
            Flags_SetRandomizerInf(RAND_INF_HAS_WALLET);
        } else if (beforeLevel == 0) {
            Item_Give(gPlayState, ITEM_WALLET_ADULT);
        } else if (beforeLevel == 1) {
            Item_Give(gPlayState, ITEM_WALLET_GIANT);
        } else {
            // Tycoon/infinite wallet tiers are fork-native randomizer entries.
            Randomizer_Item_Give(gPlayState, giEntry);
        }

        const bool hasChildWallet = Flags_GetRandomizerInf(RAND_INF_HAS_WALLET);
        const int afterLevel = CUR_UPG_VALUE(UPG_WALLET);
        const bool advanced = (!hadChildWallet && hasChildWallet) || (afterLevel > beforeLevel);
        SPDLOG_INFO("[Archipelago] Progressive Wallet direct grant: child {} -> {}, level {} -> {}, advanced={}",
                    hadChildWallet, hasChildWallet, beforeLevel, afterLevel, advanced);

        if (!advanced) {
            SPDLOG_ERROR("[Archipelago] Progressive Wallet did not advance; leaving AP receive queued for retry");
            return false;
        }

        Notification::Emit({
            .prefix = "Archipelago",
            .message = "received",
            .suffix = item.GetName().english,
            .remainingTime = 4.0f,
        });
        return true;
    }

    // Match normal randomizer UX more closely: only advancement/major items interrupt
    // gameplay with the hold-item animation. Refills, ammo, rupees, maps/compasses,
    // ordinary hearts, and other non-major rewards are applied immediately and shown
    // in the side notification feed instead. This is especially important for AP
    // starting inventory/replayed filler, which should not repeatedly stop the player.
    const bool isExtremeProgression =
        ((itemId >= AP_EXTREME_ITEM_BASE && itemId <= AP_ITEM_ENEMY_SOUL_BIG_OCTO &&
          !(itemId >= AP_FIRST_SONG_NOTE && itemId <= AP_LAST_SONG_NOTE)) ||
         (itemId >= AP_FIRST_SILVER_ITEM && itemId <= AP_LAST_SILVER_ITEM));
    const GetItemCategory apCategory = item.GetCategory();
    const bool forceHoldAnimation =
        isExtremeProgression ||
        apCategory == ITEM_CATEGORY_MAJOR ||
        apCategory == ITEM_CATEGORY_SMALL_KEY ||
        apCategory == ITEM_CATEGORY_BOSS_KEY;

    if (!item.IsMajorItem() && !forceHoldAnimation) {
        SPDLOG_INFO("[Archipelago] Applying non-major item id {} ({}) without get-item animation",
                    itemId, item.GetName().english);

        // Native-backed randomizer entries (MOD_NONE) must use vanilla Item_Give.
        // Only show the side receipt if persistent state actually changed.
        const uint64_t fillerDigestBefore = CaptureApPersistentGrantDigest();
        if (giEntry.modIndex == MOD_RANDOMIZER) {
            Randomizer_Item_Give(gPlayState, giEntry);
        } else if (giEntry.itemId != ITEM_NONE) {
            Item_Give(gPlayState, static_cast<uint8_t>(giEntry.itemId));
        } else {
            SPDLOG_ERROR("[Archipelago] Non-major item {} ({}) has neither a randomizer handler nor a vanilla ItemID",
                         itemId, item.GetName().english);
            return true;
        }

        const bool fillerStateChanged =
            CaptureApPersistentGrantDigest() != fillerDigestBefore;

        // The side feed is also the user's complete same-game receive history.
        // Capped ammo/rupees/hearts are still real AP receives, so notify them too.
        // Important/progression items remain stricter and are notified only after
        // their persistent save-state verification succeeds.
        Notification::Emit({
            .prefix = "Archipelago",
            .message = "received",
            .suffix = item.GetName().english,
            .remainingTime = 4.0f,
        });

        if (!fillerStateChanged) {
            SPDLOG_INFO("[Archipelago] Non-major item {} ({}) was received but inventory state was capped/unchanged",
                        itemId, item.GetName().english);
        }
        return true;
    }

    SPDLOG_INFO("[Archipelago] Presenting major item id {} as RandomizerGet {}", itemId, static_cast<int>(randoGet));

    // Important hold-item rewards should not start while Link is swimming or
    // airborne. Some SoH get-item paths can begin in water without completing the
    // matching receive lifecycle cleanly. Leave the AP item at the queue front and
    // retry once Link is safely standing on land.
    const bool playerInWater = (player->stateFlags1 & PLAYER_STATE1_IN_WATER) != 0;
    const bool playerGrounded = (player->actor.bgCheckFlags & BGCHECKFLAG_GROUND) != 0;
    if (playerInWater || !playerGrounded) {
        SPDLOG_DEBUG("[Archipelago] Deferring important item {} until Link is grounded on land", itemId);
        return false;
    }

    // Overworld building keys are one-shot RandomizerInf flags. They are not
    // consumable dungeon key counters, and setting their flag twice is harmless.
    // Some of these custom randomizer get-item entries can fail to produce the
    // OnItemReceive completion that the generic AP transaction waits for, leaving
    // the entire receive queue stuck until reload.
    //
    // Keep their normal hold animation, but commit the AP queue as soon as the
    // animation successfully starts and set the persistent key flag ourselves.
    const bool isOverworldDoorKey =
        randoGet >= RG_GUARD_HOUSE_KEY && randoGet <= RG_FISHING_HOLE_KEY;

    // Adult-trade progression from Cojiro through Claim Check is also represented
    // by persistent RandomizerInf flags in SOH-EXTREME. These items can play a
    // perfectly valid hold animation without reliably producing the generic
    // OnItemReceive completion AP was waiting on (Poacher's Saw reproduced this).
    const bool isAdultTradeFlagItem =
        randoGet >= RG_COJIRO && randoGet <= RG_CLAIM_CHECK;

    const bool isImmediateFlagMajor = isOverworldDoorKey || isAdultTradeFlagItem;

    // Custom SOH-EXTREME abilities/souls use a synchronous persistence path below.
    // Other base-game major items (dungeon keys, boss keys, equipment, etc.) use
    // OnItemReceive as the transaction commit point.
    //
    // CRITICAL: arm the transaction BEFORE GiveItemEntryWithoutActor().
    //
    // Some vanilla major items can invoke OnItemReceive synchronously from inside
    // GiveItemEntryWithoutActor(). The old order armed awaitingMajorItemReceipt only
    // AFTER the give call returned, so that callback was missed. The code then set
    // awaitingMajorItemReceipt=true after the only completion callback had already
    // happened, permanently blocking every later AP reward until the save reloaded.
    const bool transactionalBaseMajor = !isExtremeProgression && !isImmediateFlagMajor;
    if (transactionalBaseMajor) {
        awaitingMajorItemReceipt = true;
        awaitingMajorSequence = sequence;
        awaitingMajorApItemId = itemId;
        awaitingMajorModIndex = static_cast<int>(giEntry.modIndex);
        awaitingMajorItemId = static_cast<int>(giEntry.itemId);
        awaitingMajorGetItemId = static_cast<int>(giEntry.getItemId);
        gAwaitingMajorFrames = 0;
        gAwaitingMajorStateDigestBefore = CaptureApPersistentGrantDigest();
        gAwaitingMajorCallbackSeen = false;
    }

    if (!GiveItemEntryWithoutActor(gPlayState, giEntry)) {
        // Give did not begin. Undo only the transaction we just armed; the item
        // remains pendingItems.front() and will be retried on a later safe frame.
        if (transactionalBaseMajor && awaitingMajorItemReceipt &&
            awaitingMajorSequence == sequence) {
            awaitingMajorItemReceipt = false;
            awaitingMajorSequence = 0;
            awaitingMajorApItemId = 0;
            awaitingMajorModIndex = 0;
            awaitingMajorItemId = 0;
            awaitingMajorGetItemId = 0;
            gAwaitingMajorFrames = 0;
            ResetApMajorVerificationState();
        }

        SPDLOG_DEBUG("[Archipelago] Link cannot receive major item {} yet; retrying", itemId);
        return false;
    }

    // Flag-backed majors are idempotent progression state. Apply their RandomizerInf
    // immediately after the hold animation starts so a missing OnItemReceive callback
    // cannot wedge the entire AP queue. This covers overworld building keys and the
    // adult-trade chain (Cojiro -> Claim Check, including Poacher's Saw).
    if (isImmediateFlagMajor) {
        auto randInfIt = Rando::StaticData::RandoGetToRandInf.find(randoGet);
        if (randInfIt != Rando::StaticData::RandoGetToRandInf.end()) {
            const RandomizerInf expectedFlag = static_cast<RandomizerInf>(randInfIt->second);
            Flags_SetRandomizerInf(expectedFlag);
            if (!Flags_GetRandomizerInf(expectedFlag)) {
                SPDLOG_ERROR("[Archipelago] Flag-backed major {} failed persistence verification; retrying",
                             static_cast<int>(randoGet));
                return false;
            }
        } else {
            SPDLOG_ERROR("[Archipelago] Flag-backed major {} had no RandomizerInf mapping; retrying",
                         static_cast<int>(randoGet));
            return false;
        }

        SPDLOG_INFO("[Archipelago] Flag-backed major {} verified in persistent state",
                    static_cast<int>(randoGet));
        Notification::Emit({
            .prefix = "Archipelago",
            .message = "received",
            .suffix = GetApItemDisplayName(itemId),
            .remainingTime = 4.0f,
        });
        return true;
    }

    // Custom SOH-EXTREME abilities/souls are pure RandomizerInf state. Some of
    // their synthetic get-item entries do not emit OnItemReceive at all, so keep
    // their existing synchronous persistence/commit behavior.
    const uint64_t extremeDigestBefore = CaptureApPersistentGrantDigest();
    if (ApplyExtremePersistentApItem(itemId)) {
        bool verified = CaptureApPersistentGrantDigest() != extremeDigestBefore;

        auto randInfIt = Rando::StaticData::RandoGetToRandInf.find(randoGet);
        if (!verified && randInfIt != Rando::StaticData::RandoGetToRandInf.end()) {
            verified = Flags_GetRandomizerInf(static_cast<RandomizerInf>(randInfIt->second));
        }

        if (!verified && itemId == AP_ITEM_SPEAK) {
            verified =
                Flags_GetRandomizerInf(RAND_INF_CAN_SPEAK_DEKU) &&
                Flags_GetRandomizerInf(RAND_INF_CAN_SPEAK_GERUDO) &&
                Flags_GetRandomizerInf(RAND_INF_CAN_SPEAK_GORON) &&
                Flags_GetRandomizerInf(RAND_INF_CAN_SPEAK_HYLIAN) &&
                Flags_GetRandomizerInf(RAND_INF_CAN_SPEAK_KOKIRI) &&
                Flags_GetRandomizerInf(RAND_INF_CAN_SPEAK_ZORA);
        }

        if (!verified) {
            SPDLOG_ERROR("[Archipelago] Custom major item {} failed persistence verification; retrying", itemId);
            return false;
        }

        SPDLOG_INFO("[Archipelago] Custom major item {} verified in persistent state", itemId);
        Notification::Emit({
            .prefix = "Archipelago",
            .message = "received",
            .suffix = GetApItemDisplayName(itemId),
            .remainingTime = 4.0f,
        });
        return true;
    }

    // If OnItemReceive fired synchronously inside GiveItemEntryWithoutActor(),
    // FinalizeMajorItemReceipt() has already cleared the awaiting state and advanced
    // appliedItemCount. That is a successful receive, not a reason to re-arm it.
    if (!awaitingMajorItemReceipt || awaitingMajorSequence != sequence) {
        SPDLOG_INFO("[Archipelago] Major AP receive #{} committed synchronously during give", sequence);
        return true;
    }

    SPDLOG_INFO("[Archipelago] Major AP receive #{} started; waiting for asynchronous OnItemReceive commit", sequence);

    // The side receipt is emitted from FinalizeMajorItemReceipt(), after SoH's
    // OnItemReceive confirms the item was really granted. That avoids claiming a
    // major item was received if a death/reset interrupts its get-item animation.
    return true;
}

void ArchipelagoClient::QueueDeathLink(const std::string& source, const std::string& cause) {
    // Network callback: only copy data under the mutex. Do not read CVars or touch
    // gameplay state from APCpp's websocket thread.
    std::scoped_lock lock(queueMutex);
    pendingDeathLinks.push_back({ source, cause });
}

void ArchipelagoClient::QueueTrapLink(const std::string& source, const std::string& trapName) {
    // Network callback: only copy data under the mutex.
    std::scoped_lock lock(queueMutex);
    pendingTrapLinks.push_back({ source, trapName.empty() ? "Trap" : trapName });
}

void ArchipelagoClient::SendDeathLink() {
    if (!deathLinkEnabled || !IsAuthenticated()) return;
    const char* slot = CVarGetString(CVAR_REMOTE_ARCHIPELAGO("SlotName"), "SOH-EXTREME");
    const auto now = std::chrono::duration_cast<std::chrono::seconds>(
        std::chrono::system_clock::now().time_since_epoch()).count();
    AP_Bounce bounce{};
    std::vector<std::string> tags{ "DeathLink" };
    bounce.tags = &tags;
    bounce.data = "{\"time\":" + std::to_string(now) + ",\"source\":\"" +
                  EscapeJsonString(slot == nullptr ? "SOH-EXTREME" : slot) +
                  "\",\"cause\":\"" + EscapeJsonString(slot == nullptr ? "Link" : slot) +
                  " met with a terrible fate.\"}";
    AP_SendBounce(bounce);
    SPDLOG_INFO("[Archipelago] Sent DeathLink");
}

void ArchipelagoClient::SendTrapLink(const std::string& trapName) {
    if (!trapLinkEnabled || !IsAuthenticated()) return;
    const char* slot = CVarGetString(CVAR_REMOTE_ARCHIPELAGO("SlotName"), "SOH-EXTREME");
    const auto now = std::chrono::duration_cast<std::chrono::seconds>(
        std::chrono::system_clock::now().time_since_epoch()).count();
    AP_Bounce bounce{};
    std::vector<std::string> tags{ "TrapLink" };
    bounce.tags = &tags;
    bounce.data = "{\"time\":" + std::to_string(now) + ",\"source\":\"" +
                  EscapeJsonString(slot == nullptr ? "SOH-EXTREME" : slot) +
                  "\",\"trap_name\":\"" + EscapeJsonString(trapName) + "\"}";
    AP_SendBounce(bounce);
    SPDLOG_INFO("[Archipelago] Sent TrapLink: {}", trapName);
}

void ArchipelagoClient::RefreshSongNotes() {
    struct SongNotes { const char* name; int count; int quest; };
    static constexpr SongNotes songs[] = {
        {"Zelda's Lullaby", 6, QUEST_SONG_LULLABY},
        {"Epona's Song", 6, QUEST_SONG_EPONA},
        {"Saria's Song", 6, QUEST_SONG_SARIA},
        {"Sun's Song", 6, QUEST_SONG_SUN},
        {"Song of Time", 6, QUEST_SONG_TIME},
        {"Song of Storms", 6, QUEST_SONG_STORMS},
        {"Minuet of Forest", 6, QUEST_SONG_MINUET},
        {"Bolero of Fire", 8, QUEST_SONG_BOLERO},
        {"Serenade of Water", 5, QUEST_SONG_SERENADE},
        {"Requiem of Spirit", 6, QUEST_SONG_REQUIEM},
        {"Nocturne of Shadow", 7, QUEST_SONG_NOCTURNE},
        {"Prelude of Light", 6, QUEST_SONG_PRELUDE},
    };

    int offset = 0;
    for (const auto& song : songs) {
        int collected = 0;
        for (int i = 0; i < song.count; ++i) {
            if (HasNote(RAND_INF_SONG_NOTE_0, offset + i)) ++collected;
        }

        const bool complete = collected == song.count;
        const bool alreadyOwned = (gSaveContext.inventory.questItems & (1u << song.quest)) != 0;
        if (complete && !alreadyOwned) {
            SetQuestSong(song.quest);
            SPDLOG_INFO("[Archipelago] Song Notes complete: {} ({}/{}) -> song unlocked",
                        song.name, collected, song.count);
            Notification::Emit({
                .prefix = "Song Notes",
                .message = "completed",
                .suffix = song.name,
                .remainingTime = 5.0f,
            });
        }
        offset += song.count;
    }
}

bool ArchipelagoClient::IsGameplaySessionActive() const {
    return gPlayState != nullptr && gSaveContext.ship.quest.id == QUEST_RANDOMIZER;
}

void ArchipelagoClient::BeginFileSelectActivation() {
    fileSelectActivationRequested = true;
}

void ArchipelagoClient::EndFileSelectActivation() {
    fileSelectActivationRequested = false;
}

std::vector<std::string> ArchipelagoClient::GetChatMessages() {
    std::scoped_lock lock(queueMutex);
    return std::vector<std::string>(chatMessages.begin(), chatMessages.end());
}

void ArchipelagoClient::SendChatMessage(const std::string& message) {
    if (!IsAuthenticated()) return;
    std::string trimmed = message;
    while (!trimmed.empty() && std::isspace(static_cast<unsigned char>(trimmed.front()))) trimmed.erase(trimmed.begin());
    while (!trimmed.empty() && std::isspace(static_cast<unsigned char>(trimmed.back()))) trimmed.pop_back();
    if (trimmed.empty()) return;
    AP_Say(trimmed);
    SPDLOG_INFO("[Archipelago] Chat sent: {}", trimmed);
}

void ArchipelagoClient::Update() {
    ServiceFinderWorker();
    if (!enabled.load()) return;

    // Title/file-select safety boundary. APCpp may stay connected so authentication
    // can complete, but NOTHING that mutates gameplay state is processed until the
    // player actually chooses an AP file or a randomizer save is active.
    if (gPlayState == nullptr) {
        saveRuntimeSynchronized = false;
        deathStateInitialized = false;

        if (!fileSelectActivationRequested) {
            return;
        }

        // The user clicked Start/New AP File. During this narrow preparation phase,
        // only receive scout metadata needed by the file-select readiness barrier.
        // Do not apply placements, items, checks, DeathLink/TrapLink, time, or inventory.
        std::deque<PendingScout> scouts;
        {
            std::scoped_lock lock(queueMutex);
            scouts.swap(pendingScouts);
        }
        for (auto& scout : scouts) {
            IndexScoutedLocation(scout.locationId, scout.info);
            scoutedLocations[scout.locationId] = std::move(scout.info);
        }
        if (IsAuthenticated()) {
            RequestLocationScouts();
        }
        return;
    }

    // A non-randomizer save must never consume AP gameplay queues either.
    if (gSaveContext.ship.quest.id != QUEST_RANDOMIZER) {
        saveRuntimeSynchronized = false;
        deathStateInitialized = false;
        return;
    }

    // From 0.5.9 onward AP ownership is a property of the SAVE, not merely of
    // "being a randomizer file while the AP client happens to be connected".
    // This prevents a normal local randomizer save from consuming server items.
    if (!currentSaveIsArchipelago || saveIdentityMismatch) {
        saveRuntimeSynchronized = false;
        deathStateInitialized = false;
        return;
    }

    fileSelectActivationRequested = false;

    // New AP file creation only stamps metadata. Build the potentially large
    // historical ReceivedItems replay now, after gameplay exists and file-select
    // has already returned. This removes AP queue/history work from Sram_InitSave().
    if (newSaveReplayPending) {
        PrepareNewSaveItemReplay();
    }

    // Consume APCpp-published work only from the gameplay thread.
    if (IsAuthenticated() && slotSettingsLoaded && slotSettingsPendingApply.exchange(false)) {
        ApplySlotSettings();
    }

    if (activeLocationsPendingRefresh.exchange(false)) {
        // The server active-location set is authoritative. Invalidate the full
        // Check Finder map and schedule ONE deferred availability pass instead
        // of letting rows keep stale visibility/reachability until a reload.
        checkFinderMappingsPrepared = false;
        if (CVarGetInteger(CVAR_TRACKER_CHECK("EnableAvailableChecks"), 0)) {
            CheckTracker::RecalculateAvailableChecks();
        }
        SPDLOG_DEBUG("[Archipelago] Active AP location set refreshed; Check Finder resync scheduled");
    }

    // Keep AP authoritative without scanning every randomizer option every frame.
    // A local menu edit is repaired within roughly one second.
    if (IsAuthenticated() && slotSettingsLoaded) {
        if (++settingsEnforceFrameCounter >= 60) {
            settingsEnforceFrameCounter = 0;
            EnforceSlotSettings();
        }
    } else {
        settingsEnforceFrameCounter = 0;
    }

    // Existing-save reconciliation happens exactly once after gameplay really exists.
    // Slot settings were already applied either from the per-save cached snapshot
    // during LoadSaveMetadata() or from slotSettingsPendingApply above. Re-running
    // ApplySlotSettings() here repeats ShipInit::Init("IS_RANDO") on the load frame
    // and causes an avoidable hitch.
    if (!saveRuntimeSynchronized && IsAuthenticated() && slotSettingsLoaded) {
        // Placement data is lazy per-check.  A whole-table pass here recreates
        // the same multi-thousand-entry startup hitch we intentionally avoid in
        // file-select/new-file creation.
        ApplyPostInitSlotState();
        saveRuntimeSynchronized = true;
        SPDLOG_INFO("[Archipelago] Reconciled loaded randomizer save with authoritative AP slot state (lazy placements)");
    }

    // Pull APCpp's presentable message queue only while an AP gameplay session is active.
    // This gives SoH a persistent in-game chat log without touching UI/game state from
    // APCpp's networking callback thread.
    for (int i = 0; i < 16 && AP_IsMessagePending(); ++i) {
        AP_Message* message = AP_GetLatestMessage();
        if (message != nullptr) {
            const std::string line = message->text;
            {
                std::scoped_lock lock(queueMutex);
                chatMessages.push_back(line);
                while (chatMessages.size() > 200) chatMessages.pop_front();
            }
            if (message->type == AP_MessageType::Chat || message->type == AP_MessageType::ServerChat) {
                Notification::Emit({ .prefix = "Archipelago", .message = line, .remainingTime = 6.0f });
            }
            SPDLOG_INFO("[Archipelago Chat] {}", line);
        }
        AP_ClearLatestMessage();
    }

    std::deque<int64_t> checked;
    std::deque<PendingScout> scouts;
    std::deque<PendingDeathLink> deaths;
    std::deque<PendingTrapLink> traps;
    {
        std::scoped_lock lock(queueMutex);
        checked.swap(pendingCheckedLocations);
        scouts.swap(pendingScouts);
        deaths.swap(pendingDeathLinks);
        traps.swap(pendingTrapLinks);
    }

    // Apply link events only on the gameplay thread. APCpp callbacks run from its
    // networking context, so touching gSaveContext/player state in the callback itself
    // would be unsafe. Ignore our own Bounce echo here as well.
    const char* ownSlotPtr = CVarGetString(CVAR_REMOTE_ARCHIPELAGO("SlotName"), "");
    const std::string ownSlot = ownSlotPtr == nullptr ? "" : ownSlotPtr;
    while (!deaths.empty() && !ownSlot.empty() && deaths.front().source == ownSlot) deaths.pop_front();
    while (!traps.empty() && !ownSlot.empty() && traps.front().source == ownSlot) traps.pop_front();

    if (!deaths.empty()) {
        if (gPlayState != nullptr && GET_PLAYER(gPlayState) != nullptr) {
            const auto& death = deaths.front();
            suppressNextDeathLinkSend = true;
            GameInteractor::RawAction::SetPlayerHealth(0);
            Notification::Emit({ .prefix = "DeathLink", .message = "received from", .suffix = death.source,
                                 .remainingTime = 5.0f });
            SPDLOG_INFO("[Archipelago] Applied DeathLink from {}: {}", death.source, death.cause);
            deaths.pop_front();
        }
        if (!deaths.empty()) {
            std::scoped_lock lock(queueMutex);
            while (!deaths.empty()) { pendingDeathLinks.push_front(std::move(deaths.back())); deaths.pop_back(); }
        }
    }

    if (!traps.empty()) {
        if (gPlayState != nullptr && GET_PLAYER(gPlayState) != nullptr) {
            const auto& trap = traps.front();
            gSaveContext.ship.pendingIceTrapCount++;
            Notification::Emit({ .prefix = "TrapLink", .message = "received", .suffix = trap.trapName,
                                 .remainingTime = 5.0f });
            SPDLOG_INFO("[Archipelago] Queued TrapLink '{}' from {}", trap.trapName, trap.source);
            traps.pop_front();
        }
        if (!traps.empty()) {
            std::scoped_lock lock(queueMutex);
            while (!traps.empty()) { pendingTrapLinks.push_front(std::move(traps.back())); traps.pop_back(); }
        }
    }

    // Verified major-item completion.
    //
    // Presentation/callback alone is never enough. The side popup and AP receive
    // cursor advance only after persistent inventory/save state actually changed.
    if (awaitingMajorItemReceipt && gPlayState != nullptr) {
        ++gAwaitingMajorFrames;

        Player* majorPlayer = GET_PLAYER(gPlayState);
        if (majorPlayer != nullptr && gSaveContext.health > 0) {
            const bool stillInMajorReceive =
                Player_InBlockingCsMode(gPlayState, majorPlayer) ||
                (majorPlayer->stateFlags1 &
                 (PLAYER_STATE1_IN_ITEM_CS | PLAYER_STATE1_GETTING_ITEM | PLAYER_STATE1_CARRYING_ACTOR));

            const bool persistentStateChanged =
                CaptureApPersistentGrantDigest() != gAwaitingMajorStateDigestBefore;

            if (persistentStateChanged &&
                (gAwaitingMajorCallbackSeen ||
                 (!stillInMajorReceive &&
                  gAwaitingMajorFrames >= AP_MAJOR_RECEIVE_FALLBACK_MIN_FRAMES))) {
                if (!gAwaitingMajorCallbackSeen) {
                    SPDLOG_WARN(
                        "[Archipelago] Major AP receive #{} item {} changed persistent state without "
                        "OnItemReceive; committing from verified post-animation state",
                        awaitingMajorSequence, awaitingMajorApItemId);
                }

                FinalizeMajorItemReceipt(awaitingMajorModIndex, awaitingMajorItemId,
                                         awaitingMajorGetItemId);
            } else if (!persistentStateChanged && !stillInMajorReceive &&
                       gAwaitingMajorFrames >= AP_MAJOR_RECEIVE_VERIFY_TIMEOUT_FRAMES) {
                SPDLOG_ERROR(
                    "[Archipelago] Major AP receive #{} item {} presentation finished but persistent "
                    "state never changed; NOT committing and NOT notifying; queued item will retry",
                    awaitingMajorSequence, awaitingMajorApItemId);

                awaitingMajorItemReceipt = false;
                awaitingMajorSequence = 0;
                awaitingMajorApItemId = 0;
                awaitingMajorModIndex = 0;
                awaitingMajorItemId = 0;
                awaitingMajorGetItemId = 0;
                gAwaitingMajorFrames = 0;
                ResetApMajorVerificationState();
            }
        }
    }

    // Brand-new local AP files reconstruct already-received server history silently
    // and in a small per-frame batch. Live rewards remain strictly one-at-a-time so
    // normal hold-item animations cannot overwrite one another.
    if (gNewSaveReplayGraceFrames > 0) {
        --gNewSaveReplayGraceFrames;
    } else {
        const bool reconstructing =
            gNewSaveReplayTargetCount != 0 && appliedItemCount < gNewSaveReplayTargetCount;
        const int itemBudget = reconstructing ? AP_NEW_SAVE_REPLAY_ITEMS_PER_FRAME : 1;

        for (int processed = 0; processed < itemBudget; ++processed) {
            PendingItem nextItem{};
            {
                std::scoped_lock lock(queueMutex);
                if (awaitingMajorItemReceipt || pendingItems.empty()) {
                    break;
                }
                // PEEK only. MarkItemApplied() owns removal after a successful grant.
                nextItem = pendingItems.front();
            }

            if (!ProcessItem(nextItem.id, nextItem.notify, nextItem.sequence)) {
                SPDLOG_DEBUG("[Archipelago] Receive #{} not granted yet; leaving it at queue front",
                             nextItem.sequence);
                break;
            }

            if (awaitingMajorItemReceipt && awaitingMajorSequence == nextItem.sequence) {
                SPDLOG_DEBUG("[Archipelago] Receive #{} is awaiting actual major-item grant; cursor not advanced",
                             nextItem.sequence);
                break;
            }

            MarkItemApplied(nextItem.sequence);

            if (gNewSaveReplayTargetCount != 0 && appliedItemCount >= gNewSaveReplayTargetCount) {
                SPDLOG_INFO("[Archipelago] New-save historical item reconstruction complete at {} items",
                            appliedItemCount);
                gNewSaveReplayTargetCount = 0;
                break;
            }
        }
    }

    for (auto& scout : scouts) {
        IndexScoutedLocation(scout.locationId, scout.info);
        scoutedLocations[scout.locationId] = std::move(scout.info);
    }
    if (!scouts.empty()) {
        SPDLOG_INFO("[Archipelago] Received {} scouted placement records ({}/{})", scouts.size(),
                    scoutedLocations.size(), expectedScoutCount);
        // Scout chunks can arrive after a scene has already initialized. Refresh only
        // the current scene; never bulk-apply the accumulated world table.
        if (gPlayState != nullptr) {
            RefreshPlacementsForScene(static_cast<int16_t>(gPlayState->sceneNum));
            const RandomizerCheckArea area = CheckTracker::GetCheckArea();
            if (area != RCAREA_INVALID) {
                CheckTracker::RecalculateAreaTotals(area);
                CheckTracker::UpdateAreas(area);
            }
        }
        // Scout replies can arrive in several chunks. Re-applying the entire
        // accumulated placement table after every chunk makes reload work grow
        // quadratically. Do not bulk-apply the entire accumulated table when the
        // last scout chunk arrives; concrete actors/checks stay scene-local.
        //
        // Check Finder is different: if the user enabled it, the completed scout
        // set is now sufficient to build its fast full RC mapping on demand.
        if (expectedScoutCount == 0 || scoutedLocations.size() >= expectedScoutCount) {
            if (CVarGetInteger(CVAR_TRACKER_CHECK("EnableAvailableChecks"), 0)) {
                CheckTracker::RecalculateAvailableChecks();
            }
        }
    }

    // APCpp tells us about locations already checked on the server. Remember those so
    // the periodic local reconciliation pass does not spam duplicate sends.
    for (int64_t loc : checked) {
        reportedLocations.insert(loc);
        SPDLOG_DEBUG("[Archipelago] Server confirms location {} checked", loc);
    }

    // Newly collected local checks are deferred out of the collection callback, but
    // only until the next normal gameplay update (typically one frame). This avoids
    // synchronous websocket work inside the pickup hook without the old ~1 second delay.
    for (int sent = 0; sent < AP_LOCATION_REPORTS_PER_FRAME && !gDeferredLocationReports.empty(); ++sent) {
        const int64_t locationId = gDeferredLocationReports.front();
        gDeferredLocationReports.pop_front();
        SendLocation(locationId, false);
    }

    const bool authenticated = IsAuthenticated();
    if (authenticated) {
        // Every fresh authentication gets a full local -> server reconciliation. This
        // fixes checks collected before connecting, while loading a save, or during a
        // moment where OnRandoSetCheckStatus was missed.
        if (!wasAuthenticated) {
            {
                std::scoped_lock lock(queueMutex);
                ResetFinderMirror();
            }
            std::vector<std::string> linkTags;
            if (deathLinkEnabled) linkTags.emplace_back("DeathLink");
            if (trapLinkEnabled) linkTags.emplace_back("TrapLink");
            AP_UpdateTags(linkTags);
            linkTagsSynchronized = true;
            SPDLOG_INFO("[Archipelago] Link tags: DeathLink={}, TrapLink={}", deathLinkEnabled, trapLinkEnabled);
            SPDLOG_INFO("[Archipelago] Authenticated; synchronizing collected locations");
            // Do not clear server-confirmed checks here. QueueCheckedLocation()
            // may already have populated speech/fallback locations during the
            // authentication handshake; clearing them here made first-talk checks
            // repeat after reconnect/load.
            syncFrameCounter = 0;
            scoutsRequested = false;
            RequestLocationScouts();
            SyncCollectedLocations();
        } else if (++syncFrameCounter >= 60) {
            // Roughly once per second at 60 FPS. SendLocation() deduplicates locations
            // that the server/client already knows about.
            syncFrameCounter = 0;
            SyncCollectedLocations();
        }


        // If the initial LocationScouts packet was lost or arrived before the
        // server finished authentication, retry until we actually have placement
        // data. Once data is present there is no reason to keep rescouting.
        if (scoutedLocations.empty() && syncFrameCounter == 0) {
            scoutsRequested = false;
            RequestLocationScouts();
        }
    } else if (wasAuthenticated) {
        // Preserve the last server-confirmed location set across a temporary
        // disconnect. Enable() clears it when intentionally connecting to a
        // different session; retaining it here prevents duplicate first-talk
        // checks while reconnecting to the same slot.
        syncFrameCounter = 0;
        scoutsRequested = false;
    }
    wasAuthenticated = authenticated;

    // Detect a local living -> dead transition exactly once. An incoming DeathLink
    // sets suppressNextDeathLinkSend so it cannot echo back into the link group.
    if (gPlayState == nullptr) {
        deathStateInitialized = false;
    } else {
        const bool alive = gSaveContext.health > 0;
        if (!deathStateInitialized) {
            lastPlayerAlive = alive;
            deathStateInitialized = true;
        } else {
            if (lastPlayerAlive && !alive) {
                if (suppressNextDeathLinkSend) {
                    suppressNextDeathLinkSend = false;
                } else {
                    SendDeathLink();
                }
            }
            if (alive) suppressNextDeathLinkSend = false;
            lastPlayerAlive = alive;
        }
    }

    // Keep Flow of Time frozen until its progression item is received.
    if (CVarGetInteger(CVAR_RANDOMIZER_SETTING("ShuffleFlowOfTime"), 0) &&
        !Flags_GetRandomizerInf(RAND_INF_FLOW_OF_TIME) && gPlayState != nullptr) {
        static constexpr u16 kTimes[] = { 0x4555, 0x8000, 0xB555, 0x0000 };
        int selected = CVarGetInteger(CVAR_RANDOMIZER_SETTING("FrozenStartingTime"), 1);
        if (selected <= 0 || selected > 4) selected = 1;
        gSaveContext.dayTime = kTimes[selected - 1];
        gSaveContext.skyboxTime = gSaveContext.dayTime;
    }
}

void ArchipelagoClient::SyncCollectedLocations() {
    if (!IsAuthenticated() || !IsGameplaySessionActive()) return;

    auto ctx = Rando::Context::GetInstance();
    if (!ctx) return;

    if (!activeLocationsLoaded) return;

    // Reconcile missed/already-saved checks in small batches. Fresh checks use the
    // next-frame gDeferredLocationReports queue above, so this path is primarily for
    // reload/reconnect recovery and never needs to flood the websocket.
    constexpr size_t kMaxLocationReportsPerPass = 8;
    size_t sentThisPass = 0;
    for (const auto& [rcValue, apLocation] : rcToApLocation) {
        if (activeLocations.find(apLocation) == activeLocations.end()) continue;
        if (reportedLocations.find(apLocation) != reportedLocations.end()) continue;

        auto* location = ctx->GetItemLocation(static_cast<RandomizerCheck>(rcValue));
        if (location != nullptr && location->HasObtained()) {
            SendLocation(apLocation);
            if (++sentThisPass >= kMaxLocationReportsPerPass) {
                break;
            }
        }
    }
}


bool ArchipelagoClient::OwnsCheck(int32_t randomizerCheck) {
    if (!enabled.load()) return false;

    const int64_t apLocation = ResolveApLocationForCheck(randomizerCheck);
    if (apLocation < 0) return false;

    // Before slot data arrives, stay conservative and prevent the local randomizer from
    // awarding a fake item. Once authenticated slot data is loaded, only actual AP slot
    // locations are owned by Archipelago.
    if (!activeLocationsLoaded) return true;
    return activeLocations.find(apLocation) != activeLocations.end();
}

bool ArchipelagoClient::OwnsCheckCached(int32_t randomizerCheck) const {
    if (!enabled.load()) return false;

    auto it = rcToApLocation.find(randomizerCheck);
    if (it == rcToApLocation.end()) {
        return false;
    }

    if (!activeLocationsLoaded) {
        return true;
    }
    return activeLocations.find(it->second) != activeLocations.end();
}

void ArchipelagoClient::ReportCheck(int32_t randomizerCheck) {
    if (!IsGameplaySessionActive()) return;
    const int64_t apLocation = ResolveApLocationForCheck(randomizerCheck);
    if (apLocation < 0) {
        SPDLOG_WARN("[Archipelago] RandomizerCheck {} has no AP location mapping", randomizerCheck);
        return;
    }
    if (activeLocationsLoaded && activeLocations.find(apLocation) == activeLocations.end()) {
        SPDLOG_DEBUG("[Archipelago] RC {} maps to AP location {}, but that location is not active in this slot",
                     randomizerCheck, apLocation);
        return;
    }

    // Do not serialize/send LocationChecks on the exact gameplay collection frame.
    // SyncCollectedLocations() already reconciles obtained native checks roughly
    // once per second and SendLocation() deduplicates them. Keeping this callback
    // lightweight removes the visible freeze while preserving reliable delivery.
    //
    // Remote-item feedback does not require a network round-trip, so keep that
    // immediate using the scout data that is already resident in memory.
    auto scoutIt = scoutedLocations.find(apLocation);
    if (scoutIt != scoutedLocations.end() && scoutIt->second.playerId != AP_GetPlayerID()) {
        const auto& info = scoutIt->second;
        Notification::Emit({
            .prefix = "Archipelago",
            .message = "sent " + info.itemName + " to",
            .suffix = info.playerName,
            .remainingTime = 5.0f,
        });
    }

    if (reportedLocations.find(apLocation) == reportedLocations.end() &&
        std::find(gDeferredLocationReports.begin(), gDeferredLocationReports.end(), apLocation) ==
            gDeferredLocationReports.end()) {
        gDeferredLocationReports.push_back(apLocation);
    }

    SPDLOG_DEBUG("[Archipelago] Deferred checked location {} to next gameplay update", apLocation);
}




static uint64_t Archipelago_NpcSpeechIdentity(const Actor* actor, int16_t sceneNum) {
    if (actor == nullptr) return 0;

    // FNV-1a over immutable spawn identity. home.pos is the actor's spawn position,
    // not the current animated position. Params separates NPC variants sharing a
    // model/actor type.
    uint64_t hash = 1469598103934665603ULL;
    auto mix = [&hash](uint64_t value) {
        for (int i = 0; i < 8; ++i) {
            hash ^= (value >> (i * 8)) & 0xFFULL;
            hash *= 1099511628211ULL;
        }
    };

    mix(static_cast<uint16_t>(sceneNum));
    mix(static_cast<uint16_t>(actor->id));
    mix(static_cast<uint16_t>(actor->params));
    mix(static_cast<uint16_t>(static_cast<int16_t>(actor->home.pos.x)));
    mix(static_cast<uint16_t>(static_cast<int16_t>(actor->home.pos.y)));
    mix(static_cast<uint16_t>(static_cast<int16_t>(actor->home.pos.z)));
    return hash == 0 ? 1 : hash;
}

static bool Archipelago_IsManualSpeechActor(const Actor* actor) {
    if (actor == nullptr || actor->category != ACTORCAT_NPC ||
        (actor->flags & ACTOR_FLAG_TALK_OFFER_AUTO_ACCEPTED)) {
        return false;
    }

    // Keep this list aligned with RegisterShuffleSpeak().  The generic
    // Archipelago speech bank is only for actors the fork itself considers a
    // manual Speak interaction.  Named/native speech checks are resolved before
    // this fallback and are unaffected by this filter.
    switch (actor->id) {
        case ACTOR_EN_DNS:
        case ACTOR_EN_DNT_JIJI:
        case ACTOR_EN_HINTNUTS:
        case ACTOR_EN_KAKASI:
        case ACTOR_EN_KAKASI2:
        case ACTOR_EN_KAKASI3:
        case ACTOR_OBJ_DEKUJR:
        case ACTOR_EN_GE1:
        case ACTOR_EN_GE3:
        case ACTOR_EN_NB:
        case ACTOR_EN_GO:
        case ACTOR_EN_GO2:
        case ACTOR_EN_GM:
        case ACTOR_EN_DU:
        case ACTOR_EN_ANI:
        case ACTOR_EN_BOM_BOWL_MAN:
        case ACTOR_EN_CS:
        case ACTOR_EN_DAIKU:
        case ACTOR_EN_DAIKU_KAKARIKO:
        case ACTOR_EN_DS:
        case ACTOR_EN_FU:
        case ACTOR_EN_GB:
        case ACTOR_EN_GIRLA:
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
        case ACTOR_EN_MA1:
        case ACTOR_EN_MA2:
        case ACTOR_EN_MA3:
        case ACTOR_EN_MK:
        case ACTOR_EN_MM:
        case ACTOR_EN_MM2:
        case ACTOR_EN_MS:
        case ACTOR_EN_MU:
        case ACTOR_EN_NIW_GIRL:
        case ACTOR_EN_NIW_LADY:
        case ACTOR_EN_SSH:
        case ACTOR_EN_STH:
        case ACTOR_EN_SYATEKI_MAN:
        case ACTOR_EN_TA:
        case ACTOR_EN_TAKARA_MAN:
        case ACTOR_EN_TG:
        case ACTOR_EN_TK:
        case ACTOR_EN_PO_RELAY:
        case ACTOR_EN_TORYO:
        case ACTOR_EN_XC:
        case ACTOR_EN_ZL1:
        case ACTOR_EN_ZL2:
        case ACTOR_EN_ZL3:
        case ACTOR_EN_ZL4:
        case ACTOR_FISHING:
        case ACTOR_EN_KO:
        case ACTOR_EN_SA:
        case ACTOR_EN_MD:
        case ACTOR_EN_SKJ:
        case ACTOR_EN_DIVING_GAME:
        case ACTOR_EN_KZ:
        case ACTOR_EN_RU1:
        case ACTOR_EN_RU2:
        case ACTOR_EN_ZO:
        case ACTOR_EN_OWL:
            return true;

        case ACTOR_EN_OSSAN:
            switch (actor->params) {
                case OSSAN_TYPE_KOKIRI:
                case OSSAN_TYPE_KAKARIKO_POTION:
                case OSSAN_TYPE_BOMBCHUS:
                case OSSAN_TYPE_MARKET_POTION:
                case OSSAN_TYPE_BAZAAR:
                case OSSAN_TYPE_ADULT:
                case OSSAN_TYPE_TALON:
                case OSSAN_TYPE_INGO:
                case OSSAN_TYPE_MASK:
                case OSSAN_TYPE_GORON:
                case OSSAN_TYPE_ZORA:
                    return true;
                default:
                    return false;
            }

        // ACTOR_EN_GE2 is intentionally excluded, matching ShuffleSpeak, so the
        // player can always ask to be thrown in jail.
        default:
            return false;
    }
}

static bool Archipelago_HasExtremeSpeak() {
    // SOH-EXTREME intentionally exposes ONE AP item named "Speak".
    // Receiving it sets every underlying Ship race-speak flag, so checking ANY
    // one of those flags is the canonical runtime test for our single ability.
    return Flags_GetRandomizerInf(RAND_INF_CAN_SPEAK_DEKU) ||
           Flags_GetRandomizerInf(RAND_INF_CAN_SPEAK_GERUDO) ||
           Flags_GetRandomizerInf(RAND_INF_CAN_SPEAK_GORON) ||
           Flags_GetRandomizerInf(RAND_INF_CAN_SPEAK_HYLIAN) ||
           Flags_GetRandomizerInf(RAND_INF_CAN_SPEAK_KOKIRI) ||
           Flags_GetRandomizerInf(RAND_INF_CAN_SPEAK_ZORA);
}

static int64_t Archipelago_ResolveNpcSpeechLocation(const Actor* actor, int16_t sceneNum) {
    if (actor == nullptr) return -1;

    struct SpeechMapEntry {
        int32_t rc;
        int64_t apLocation;
    };
    static const SpeechMapEntry speechMap[] = {
#include "ArchipelagoSpeechMap.inc"
    };

    // First pass: exact scene + actor + params. This is preferred because several
    // scenes contain multiple actors of the same type.
    for (const auto& entry : speechMap) {
        auto* data = Rando::StaticData::GetLocation(static_cast<RandomizerCheck>(entry.rc));
        if (data == nullptr) continue;
        if (static_cast<int16_t>(data->GetScene()) == sceneNum &&
            static_cast<int16_t>(data->GetActorID()) == actor->id &&
            data->GetActorParams() == actor->params) {
            return entry.apLocation;
        }
    }

    // Dialogue-backed checks frequently transform their actor params at runtime.
    // If scene+actor identifies exactly ONE speech check, use it even when params
    // no longer match the spawn-table value.
    int64_t unique = -1;
    for (const auto& entry : speechMap) {
        auto* data = Rando::StaticData::GetLocation(static_cast<RandomizerCheck>(entry.rc));
        if (data == nullptr) continue;
        if (static_cast<int16_t>(data->GetScene()) == sceneNum &&
            static_cast<int16_t>(data->GetActorID()) == actor->id) {
            if (unique != -1 && unique != entry.apLocation) {
                unique = -2; // ambiguous: do not award the wrong NPC
                break;
            }
            unique = entry.apLocation;
        }
    }
    return unique >= 0 ? unique : -1;
}


void ArchipelagoClient::LoadFallbackNpcSpeechHashes(const std::vector<uint64_t>& hashes) {
    fallbackNpcSpeechHashes = hashes;
    fallbackNpcSpeechSeen.clear();
    for (uint64_t hash : fallbackNpcSpeechHashes) {
        if (hash != 0) fallbackNpcSpeechSeen.insert(hash);
    }
    SPDLOG_INFO("[Archipelago] Loaded {} generic NPC first-talk identities", fallbackNpcSpeechHashes.size());
}

std::vector<uint64_t> ArchipelagoClient::GetFallbackNpcSpeechHashes() const {
    return fallbackNpcSpeechHashes;
}

bool ArchipelagoClient::ReportFallbackNpcSpeech(const Actor* actor) {
    if (!IsGameplaySessionActive() || actor == nullptr) return false;
    if (!CVarGetInteger(CVAR_RANDOMIZER_SETTING("NpcSpeechSanity"), 0)) return false;
    if (!Archipelago_IsManualSpeechActor(actor)) return false;

    const uint64_t identity = Archipelago_NpcSpeechIdentity(actor, static_cast<int16_t>(gPlayState->sceneNum));
    if (identity == 0 || fallbackNpcSpeechSeen.find(identity) != fallbackNpcSpeechSeen.end()) {
        return false;
    }

    // Use exactly one still-unchecked generic AP location for this persisted
    // manual-talk identity. 0.7.47 makes this bank part of normal AP fill; the
    // APWorld applies Speak/NPC Soul/Flow-of-Time safety gates to the bank.
    int64_t speechLocation = -1;
    for (int64_t i = 0; i < AP_EXTREME_SPEECH_FALLBACK_COUNT; ++i) {
        const int64_t candidate = AP_EXTREME_SPEECH_FALLBACK_BASE + i;
        if (activeLocations.find(candidate) != activeLocations.end() &&
            reportedLocations.find(candidate) == reportedLocations.end()) {
            speechLocation = candidate;
            break;
        }
    }

    if (speechLocation < 0) {
        SPDLOG_WARN("[Archipelago] Generic NPC Speech fallback bank exhausted; scene={} actor={} params={}",
                    gPlayState->sceneNum, actor->id, actor->params);
        return false;
    }

    if (!ReportNpcSpeechLocation(speechLocation)) {
        return false;
    }

    fallbackNpcSpeechSeen.insert(identity);
    fallbackNpcSpeechHashes.push_back(identity);
    SPDLOG_INFO("[Archipelago] Generic NPC first-talk mapped to fallback location {} "
                "(scene={} actor={} params={} home=({}, {}, {}))",
                speechLocation, gPlayState->sceneNum, actor->id, actor->params,
                actor->home.pos.x, actor->home.pos.y, actor->home.pos.z);
    return true;
}

void ArchipelagoClient::ReportNpcSpeech(int32_t randomizerCheck) {
    if (!IsGameplaySessionActive()) return;
    if (!CVarGetInteger(CVAR_RANDOMIZER_SETTING("NpcSpeechSanity"), 0)) return;

    const int64_t baseLocation = ResolveApLocationForCheck(randomizerCheck);
    if (baseLocation < 0) return;
    ReportNpcSpeechLocation(AP_EXTREME_SPEECH_BASE + baseLocation);
}

bool ArchipelagoClient::ReportNpcSpeechLocation(int64_t speechLocation) {
    if (!IsGameplaySessionActive()) return false;
    if (!CVarGetInteger(CVAR_RANDOMIZER_SETTING("NpcSpeechSanity"), 0)) return false;
    if (!activeLocationsLoaded || activeLocations.find(speechLocation) == activeLocations.end()) return false;

    // This is the critical "first interaction" test. reportedLocations is also
    // rebuilt from Archipelago's checked-locations callback after reconnect/load,
    // so an NPC already checked on the server immediately goes back to normal dialog.
    if (reportedLocations.find(speechLocation) != reportedLocations.end()) return false;

    auto scoutIt = scoutedLocations.find(speechLocation);
    const std::string speechName =
        scoutIt != scoutedLocations.end() ? scoutIt->second.locationName : "NPC Speech";

    // SendLocation inserts into reportedLocations synchronously before handing the
    // check to APCpp, so a second A press cannot trigger the speech check twice.
    SendLocation(speechLocation, true);

    if (reportedLocations.find(speechLocation) == reportedLocations.end()) {
        // Authentication/session changed between the tests above and SendLocation.
        return false;
    }

    Notification::Emit({
        .prefix = "Archipelago",
        .message = "checked",
        .suffix = speechName,
        .remainingTime = 4.0f,
    });
    SPDLOG_INFO("[Archipelago] NPC Speech Sanity first-talk intercepted: {}", speechLocation);
    // NPC Speech is a distinct AP-only tracker row.  Queue one deferred finder
    // refresh so its checked/available totals update without hijacking the native
    // reward check that shares the same physical interaction anchor.
    CheckTracker::RecalculateAvailableChecks();
    return true;
}

void ArchipelagoClient::SendLocation(int64_t locationId, bool notifyRemote) {
    if (!IsAuthenticated() || !IsGameplaySessionActive()) return;
    if (!activeLocationsLoaded) return;
    if (activeLocations.find(locationId) == activeLocations.end()) {
        SPDLOG_WARN("[Archipelago] Refusing to send inactive/invalid AP location {}", locationId);
        return;
    }

    // Location checks are idempotent on the AP server, but avoiding repeats makes the
    // server log useful and prevents a per-frame flood during reconciliation.
    if (!reportedLocations.insert(locationId).second) return;

    // Synthetic AP-only tracker rows (NPC Speech and individual Enemy Defeats)
    // have no native RandomizerCheck status to drive the normal tracker callback.
    // Update their area counter immediately when the AP location is accepted.
    CheckTracker::NotifyArchipelagoLocationReported(locationId);

    // A remote item is never received back through our ReceivedItems callback, so
    // the player needs feedback at the moment this location is checked.  Use the
    // scout record we already loaded for the physical placement.  Reconciliation
    // calls SendLocation() with notifyRemote=false, preventing old checks from
    // spamming notifications after reconnect/load.
    if (notifyRemote) {
        auto scoutIt = scoutedLocations.find(locationId);
        if (scoutIt != scoutedLocations.end() && scoutIt->second.playerId != AP_GetPlayerID()) {
            const auto& info = scoutIt->second;
            Notification::Emit({
                .prefix = "Archipelago",
                .message = "sent " + info.itemName + " to",
                .suffix = info.playerName,
                .remainingTime = 5.0f,
            });
            SPDLOG_INFO("[Archipelago] Sent remote item {} to {} from {}",
                        info.itemName, info.playerName, info.locationName);
        }
    }

    SPDLOG_INFO("[Archipelago] Sending checked location {}", locationId);
    AP_SendItem(locationId);
}

void ArchipelagoClient::RegisterHooks() {
    // Legacy fallback only.  Standalone SOH-EXTREME publishes the exact active
    // location namespace in slot data and ResolveApLocationForCheck prefers it.
    rcToApLocation = {
#include "ArchipelagoLocationMap.inc"
    };
    apLocationToRc.clear();
    for (const auto& [rc, apLocation] : rcToApLocation) {
        apLocationToRc[apLocation] = rc;
    }
    GameInteractor::Instance->RegisterGameHook<GameInteractor::OnGameFrameUpdate>([]() {
        ArchipelagoClient::GetInstance().Update();
    });

    // Resolve/apply only the scene being entered. Actor/model hooks can still call
    // RefreshPlacementForCheck() individually, but this warms the whole scene in
    // one small batch before normal gameplay starts.
    GameInteractor::Instance->RegisterGameHook<GameInteractor::OnSceneInit>([](int16_t sceneNum) {
        auto& client = ArchipelagoClient::GetInstance();
        if (client.IsGameplaySessionActive() && client.IsCurrentSaveArchipelago()) {
            client.RefreshPlacementsForScene(sceneNum);
        }
    });

    // A major AP item is durable only after SoH has actually executed its item-give
    // path. This hook closes that transaction and immediately saves both inventory
    // and the per-save AP receive cursor.
    GameInteractor::Instance->RegisterGameHook<GameInteractor::OnItemReceive>([](GetItemEntry itemEntry) {
        ArchipelagoClient::GetInstance().FinalizeMajorItemReceipt(
            static_cast<int>(itemEntry.modIndex), static_cast<int>(itemEntry.itemId),
            static_cast<int>(itemEntry.getItemId));
    });

    // NPC Speech Sanity mirrors shuffled signs:
    // first A press = AP check, later presses = normal dialogue.
    //
    // Mapped NPCs use their real speech location (fully randomized).
    // Flavor/unmapped NPCs use a persistent randomized generic location, but only
    // when Ship's own ShuffleSpeak code considers that actor manually speakable.
    // This prevents unrelated ACTORCAT_NPC actors from silently consuming checks.
    COND_VB_SHOULD(VB_SKIP_TALKING, true, {
        if (!*should || gPlayState == nullptr ||
            !CVarGetInteger(CVAR_RANDOMIZER_SETTING("NpcSpeechSanity"), 0)) {
            return;
        }

        Player* player = GET_PLAYER(gPlayState);
        Actor* actor = player != nullptr ? player->talkActor : nullptr;
        if (actor == nullptr || actor->category != ACTORCAT_NPC ||
            (actor->flags & ACTOR_FLAG_TALK_OFFER_AUTO_ACCEPTED)) {
            return;
        }

        if (RAND_GET_OPTION(RSK_SHUFFLE_NPC_SOUL) &&
            !Flags_GetRandomizerInf(RAND_INF_NPC_SOUL)) {
            return;
        }
        if (RAND_GET_OPTION(RSK_SHUFFLE_SPEAK) && !Archipelago_HasExtremeSpeak()) {
            return;
        }

        int64_t speechLocation = -1;

        auto rando = OTRGlobals::Instance->gRandomizer;
        if (rando != nullptr) {
            Rando::Location* location =
                rando->GetCheckObjectFromActor(actor->id, gPlayState->sceneNum, actor->params);
            if (location == nullptr || location->GetRandomizerCheck() == RC_UNKNOWN_CHECK) {
                location = rando->GetCheckObjectFromActor(actor->id, gPlayState->sceneNum, actor->textId);
            }

            if (location != nullptr && location->GetRandomizerCheck() != RC_UNKNOWN_CHECK) {
                const int64_t baseLocation =
                    ArchipelagoClient::GetInstance().ResolveApLocationForCheck(
                        static_cast<int32_t>(location->GetRandomizerCheck()));
                if (baseLocation >= 0) {
                    const int64_t candidate = AP_EXTREME_SPEECH_BASE + baseLocation;
                    if (ArchipelagoClient::GetInstance().ReportNpcSpeechLocation(candidate)) {
                        *should = false;
                        return;
                    }
                    // Already checked mapped NPC -> normal dialogue.
                    if (ArchipelagoClient::GetInstance().reportedLocations.find(candidate) !=
                        ArchipelagoClient::GetInstance().reportedLocations.end()) {
                        return;
                    }
                }
            }
        }

        if (speechLocation < 0) {
            speechLocation =
                Archipelago_ResolveNpcSpeechLocation(actor, static_cast<int16_t>(gPlayState->sceneNum));
        }
        if (speechLocation >= 0) {
            if (ArchipelagoClient::GetInstance().ReportNpcSpeechLocation(speechLocation)) {
                *should = false;
                return;
            }
            if (ArchipelagoClient::GetInstance().reportedLocations.find(speechLocation) !=
                ArchipelagoClient::GetInstance().reportedLocations.end()) {
                return;
            }
        }

        // No native speech location exists for this NPC (for example ordinary
        // Kokiri/Market flavor NPCs). Only true manual-Speak actors are eligible
        // for the persistent generic first-talk bank.
        if (Archipelago_IsManualSpeechActor(actor) &&
            ArchipelagoClient::GetInstance().ReportFallbackNpcSpeech(actor)) {
            *should = false;
        }
    });

    GameInteractor::Instance->RegisterGameHook<GameInteractor::OnRandoSetCheckStatus>(
        [](RandomizerCheck rc, RandomizerCheckStatus status) {
            // RCSHOW_SAVED is also an obtained check. This matters when loading a file:
            // those checks may never transition through RCSHOW_COLLECTED this session.
            if (status != RCSHOW_COLLECTED && status != RCSHOW_SAVED) return;

            auto& apClient = ArchipelagoClient::GetInstance();

            if (status == RCSHOW_COLLECTED) {
                apClient.ReportCheck(static_cast<int32_t>(rc));
            } else {
                // RCSHOW_SAVED is emitted in bulk while a file is loading. Sending
                // LocationChecks synchronously here bypassed all reconciliation batching
                // and could issue hundreds of websocket sends during Save_LoadFile().
                // SyncCollectedLocations() handles these saved checks safely afterward.
                SPDLOG_DEBUG("[Archipelago] Loaded saved check {}; deferred to batched reconciliation",
                             static_cast<int32_t>(rc));
            }

            // RC_WINCON is SOH's canonical completed-goal check.  LocationChecks
            // alone do not tell an Archipelago server that the client reached its
            // goal, so explicitly send CLIENT_GOAL (StatusUpdate = 30).  This is
            // intentionally done for both a newly-collected and a saved win check:
            // the latter lets an already-completed local file repair a missing goal
            // report after upgrading the client/reconnecting.  AP goal updates are
            // idempotent, and the server's release-on-goal policy is responsible for
            // releasing remaining items without marking their locations collected.
            if (rc == RC_WINCON && apClient.IsAuthenticated() &&
                apClient.IsCurrentSaveArchipelago()) {
                SPDLOG_INFO("[Archipelago] Win condition complete; sending CLIENT_GOAL status");
                AP_StoryComplete();
            }
        });
}

static void InitArchipelagoClient() {
    auto& client = ArchipelagoClient::GetInstance();
    client.RegisterHooks();
    if (CVarGetInteger(CVAR_REMOTE_ARCHIPELAGO("Enabled"), 0)) {
        client.Enable();
    }
}

static RegisterShipInitFunc initArchipelagoClient(InitArchipelagoClient);


extern "C" bool Archipelago_IsAuthenticatedForFileSelect(void) {
    auto& client = ArchipelagoClient::GetInstance();
    if (!client.IsAuthenticated()) return false;
    client.BeginFileSelectActivation();

    // Starting an AP file is now a synchronization barrier, not merely an auth check.
    // Do not enter name-entry/create the save until settings, active locations, exact
    // shop prices, and all physical AP placements have arrived.
    client.EnsureLocationScouts();
    return client.IsReadyForFileSelect();
}

extern "C" bool Archipelago_IsCurrentSaveFile(void) {
    return ArchipelagoClient::GetInstance().IsCurrentSaveArchipelago();
}

extern "C" bool Archipelago_IsCurrentSaveActive(void) {
    auto& client = ArchipelagoClient::GetInstance();
    return client.IsEnabled() && client.IsCurrentSaveArchipelago();
}

extern "C" bool Archipelago_ShouldHandleCheck(int32_t randomizerCheck) {
    return ArchipelagoClient::GetInstance().OwnsCheck(randomizerCheck);
}

extern "C" bool Archipelago_IsCheckMappedActive(int32_t randomizerCheck) {
    return ArchipelagoClient::GetInstance().OwnsCheckCached(randomizerCheck);
}

extern "C" bool Archipelago_PrepareCheckFinderMappings(void) {
    return ArchipelagoClient::GetInstance().PrepareCheckFinderMappings();
}

extern "C" bool Archipelago_IsLocationActive(int64_t locationId) {
    return ArchipelagoClient::GetInstance().IsLocationActive(locationId);
}

extern "C" bool Archipelago_IsLocationReported(int64_t locationId) {
    return ArchipelagoClient::GetInstance().IsLocationReported(locationId);
}

extern "C" uint32_t Archipelago_GetActiveLocationCount(void) {
    return static_cast<uint32_t>(ArchipelagoClient::GetInstance().GetActiveLocationCount());
}

extern "C" uint32_t Archipelago_GetReportedActiveLocationCount(void) {
    return static_cast<uint32_t>(ArchipelagoClient::GetInstance().GetReportedActiveLocationCount());
}

extern "C" void Archipelago_RefreshScenePlacements(int16_t sceneNum) {
    ArchipelagoClient::GetInstance().RefreshPlacementsForScene(sceneNum);
}

extern "C" void Archipelago_ReportCheck(int32_t randomizerCheck) {
    ArchipelagoClient::GetInstance().ReportCheck(randomizerCheck);
}

extern "C" void Archipelago_ReportLocation(int64_t locationId) {
    ArchipelagoClient::GetInstance().SendLocation(locationId);
}

extern "C" const char* Archipelago_GetRemoteItemDescription(int32_t randomizerCheck) {
    static thread_local std::string description;
    description = ArchipelagoClient::GetInstance().GetRemoteItemDescription(randomizerCheck);
    return description.c_str();
}

extern "C" void Archipelago_RefreshPlacementForCheck(int32_t randomizerCheck) {
    ArchipelagoClient::GetInstance().RefreshPlacementForCheck(randomizerCheck);
}

extern "C" void Archipelago_InitSaveFile(void) {
    auto& client = ArchipelagoClient::GetInstance();

    // Keep AP file creation intentionally close to the working normal-randomizer
    // creation path. Only authoritative settings that Randomizer_InitSaveFile()
    // actually needs are applied here. Network/scout/history work is deferred
    // until the first gameplay Update().
    gSaveContext.ship.quest.id = QUEST_RANDOMIZER;
    client.ApplySlotSettings();

    // A brand-new AP file must never inherit Triforce progress from the
    // previously loaded file/save-context.  Randomizer_InitSaveFile() does not
    // guarantee this custom counter is cleared on every AP creation path, so
    // zero it on both sides of initialization.  Historical AP ReceivedItems are
    // replayed later and will legitimately rebuild the count for an existing
    // server slot.
    gSaveContext.ship.quest.data.randomizer.triforcePiecesCollected = 0;
    Randomizer_InitSaveFile();
    gSaveContext.ship.quest.data.randomizer.triforcePiecesCollected = 0;
    client.ApplyPostInitSlotState();

    // SaveManager needs the AP marker/identity on the very first disk write, but
    // rebuilding ReceivedItems here can contend with APCpp callbacks and stall
    // the name-entry transition. Prime metadata only; replay begins in gameplay.
    client.PrimeNewSaveMetadata();

    client.EndFileSelectActivation();
    SPDLOG_INFO("[Archipelago] Initialized new SOH-EXTREME save; AP replay/scout work deferred to gameplay");
}
