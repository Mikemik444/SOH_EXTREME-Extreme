
#include <algorithm>
#include <array>
#include <cstdio>
#include <memory>
#include <set>
#include <string>
#include "z64.h"
#include "macros.h"
#include "soh/Enhancements/randomizer/FishingSoulAccess.h"
#include "soh/Enhancements/randomizer/randomizerEnums.h"
#define EN_FISH_OWNER 1      // param for owner of pond. default if params<100
#define EN_FISH_PARAM 100    // param base for fish in pond.
#define EN_FISH_AQUARIUM 200 // param for record fish in tank.
#define SPDLOG_INFO(...) do {} while(0)
namespace Rando {
class OptionValue {
  public:
    OptionValue() = default;
    OptionValue(uint8_t value_);

    /**
     * @brief Returns the value of the OptionValue's mVal
     *
     * @return uint8_t
     */
    uint8_t Get();

    /**
     * @brief Set the OptionValue's mVal to the provided val.
     *
     * @param val
     */
    void Set(uint8_t val);

    /**
     * @brief Determines if the value/selected index of this Option matches the provided value.
     *
     * @param other The value to compare.
     * @return true
     * @return false
     */
    bool Is(uint32_t other) const {
        return mVal == other;
    }

    /**
     * @brief Determines if the value/selected index of this Option does not match the provided value.
     *
     * @param other The value to compare.
     * @return true
     * @return false
     */
    bool IsNot(uint32_t other) const {
        return !Is(other);
    }

    /**
     * @brief Allows the option to be used as a boolean value directly.
     *
     * @return true
     * @return false
     */
    explicit operator bool() const;

  private:
    uint8_t mVal = 0;
};

OptionValue::OptionValue(uint8_t val) : mVal(val) {
}

uint8_t OptionValue::Get() {
    return mVal;
}

void OptionValue::Set(uint8_t val) {
    mVal = val;
}

OptionValue::operator bool() const {
    return mVal != 0;
}


class Context {public:
 std::array<OptionValue,RSK_MAX> options{};
 OptionValue& GetOption(RandomizerSettingKey k){return options[k];}
};
}
static auto ctx=std::make_shared<Rando::Context>();
static bool testRando=true;
#undef IS_RANDO
#define IS_RANDO testRando
#define RAND_GET_OPTION(k) ctx->GetOption(k)
static std::set<RandomizerInf> flags;
extern "C" s32 Flags_GetRandomizerInf(RandomizerInf f){return flags.contains(f);}
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
static bool IsMegaScrubActor(s16 id) {
    // ACTOR_EN_DNS is the business/sanity Deku Scrub used by the randomized
    // scrub checks. ACTOR_EN_SHOPNUTS is its above-ground sales form.
    return id == ACTOR_EN_DNS || id == ACTOR_EN_SHOPNUTS;
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
namespace Rando {
class Logic {public:
 bool IsChild=true,IsAdult=false;
 std::set<RandomizerGet> items;
 bool HasItem(RandomizerGet r) {
  // Native non-shuffled defaults are granted when the save/logic state is
  // initialized. Supply those defaults without inventing extra received items.
  if(r==RG_FISHING_POLE&&!ctx->GetOption(RSK_SHUFFLE_FISHING_POLE))return true;
  if(r==RG_CHILD_WALLET&&!ctx->GetOption(RSK_SHUFFLE_CHILD_WALLET))return true;
  if(r==RG_SPEAK_HYLIAN&&!ctx->GetOption(RSK_SHUFFLE_SPEAK))return true;
  return items.contains(r);
 }
 bool Get(LogicVal){return false;}
 bool ItemUseAllowed(RandomizerGet){return true;}
 bool BombchuRefill(){return false;}
 bool BombchusEnabled(){return false;}
 bool HasExplosives(){return CanUse(RG_BOMB_BAG);}
 bool CanUse(RandomizerGet);
 bool HasAnimalSoul(RandomizerGet);
 bool CanCutShrubs();bool CanPickUpGrass();
};
bool Logic::CanUse(RandomizerGet itemName) {
    if (!HasItem(itemName))
        return false;

    if (!ItemUseAllowed(itemName)) {
        return false;
    }

    switch (itemName) {
        // Magic items
        case RG_MAGIC_SINGLE:
            return true; // AmmoCanDrop || (HasBottle() && Get(LOGIC_BUY_MAGIC_POTION))
        case RG_DINS_FIRE:
        case RG_FARORES_WIND:
        case RG_NAYRUS_LOVE:
        case RG_LENS_OF_TRUTH:
            return CanUse(RG_MAGIC_SINGLE);
        case RG_FIRE_ARROWS:
        case RG_ICE_ARROWS:
        case RG_LIGHT_ARROWS:
            return CanUse(RG_MAGIC_SINGLE) && CanUse(RG_FAIRY_BOW);

        // Adult items
        // TODO: Uncomment those if we ever implement more item usability settings
        case RG_FAIRY_BOW:
            return IsAdult; // || BowAsChild && (AmmoCanDrop || Get(LOGIC_BUY_ARROW));
        case RG_MEGATON_HAMMER:
            return IsAdult; // || HammerAsChild;
        case RG_IRON_BOOTS:
            // Water contact without Swim voids in EXTREME, even in Iron Boots.
            return IsAdult && HasItem(RG_BRONZE_SCALE);
        case RG_HOVER_BOOTS:
            return IsAdult; // || HoverBootsAsChild;
        case RG_HOOKSHOT:
        case RG_LONGSHOT:
            return IsAdult; // || HookshotAsChild;
        case RG_GORON_TUNIC:
            return IsAdult; // || GoronTunicAsChild;
        case RG_ZORA_TUNIC:
            return IsAdult; // || ZoraTunicAsChild;
        case RG_MIRROR_SHIELD:
            return IsAdult; // || MirrorShieldAsChild;
        case RG_MASTER_SWORD:
            return IsAdult; // || MasterSwordAsChild;
        case RG_PROGRESSIVE_GORONSWORD:
        case RG_GIANTS_KNIFE:
        case RG_BIGGORON_SWORD:
            return IsAdult; // || BiggoronSwordAsChild;
        case RG_SILVER_GAUNTLETS:
        case RG_GOLDEN_GAUNTLETS:
        // Adult Trade
        case RG_POCKET_EGG:
        case RG_COJIRO:
        case RG_ODD_MUSHROOM:
        case RG_ODD_POTION:
        case RG_POACHERS_SAW:
        case RG_BROKEN_SWORD:
        case RG_PRESCRIPTION:
        case RG_EYEBALL_FROG:
        case RG_EYEDROPS:
        case RG_CLAIM_CHECK:
            return IsAdult;

        // Child items
        case RG_FAIRY_SLINGSHOT:
            return IsChild; // || SlingshotAsAdult && (AmmoCanDrop || Get(LOGIC_LOGIC_BUY_SEED));
        case RG_BOOMERANG:
            return IsChild; // || BoomerangAsAdult;
        case RG_KOKIRI_SWORD:
            return IsChild; // || KokiriSwordAsAdult;
        case RG_NUTS:
            return Get(LOGIC_NUT_ACCESS);
        case RG_STICKS:
            return IsChild /* || StickAsAdult;*/ && Get(LOGIC_STICK_ACCESS);
        case RG_DEKU_SHIELD:
            return IsChild; // || DekuShieldAsAdult;
        case RG_PROGRESSIVE_BOMB_BAG:
        case RG_BOMB_BAG:
            return true; // AmmoCanDrop || Get(LOGIC_BUY_BOMB)
        case RG_PROGRESSIVE_BOMBCHU_BAG:
        case RG_BOMBCHU_5:
        case RG_BOMBCHU_10:
        case RG_BOMBCHU_20:
            return BombchuRefill() && BombchusEnabled();
        case RG_WEIRD_EGG:
        case RG_RUTOS_LETTER:
            return IsChild;
        case RG_MAGIC_BEAN:
            return IsChild;
        case RG_SKULL_MASK:
        case RG_MASK_OF_TRUTH:
        case RG_BUNNY_HOOD:
            return IsChild || ctx->GetOption(RSK_MASKS_AS_ADULT);

        // Songs
        case RG_ZELDAS_LULLABY:
        case RG_EPONAS_SONG:
        case RG_PRELUDE_OF_LIGHT:
            return CanUse(RG_FAIRY_OCARINA) && HasItem(RG_OCARINA_C_LEFT_BUTTON) &&
                   HasItem(RG_OCARINA_C_RIGHT_BUTTON) && HasItem(RG_OCARINA_C_UP_BUTTON);
        case RG_SARIAS_SONG:
            return CanUse(RG_FAIRY_OCARINA) && HasItem(RG_OCARINA_C_LEFT_BUTTON) &&
                   HasItem(RG_OCARINA_C_RIGHT_BUTTON) && HasItem(RG_OCARINA_C_DOWN_BUTTON);
        case RG_SUNS_SONG:
            return CanUse(RG_FAIRY_OCARINA) && HasItem(RG_OCARINA_C_RIGHT_BUTTON) && HasItem(RG_OCARINA_C_UP_BUTTON) &&
                   HasItem(RG_OCARINA_C_DOWN_BUTTON);
        case RG_SONG_OF_TIME:
        case RG_BOLERO_OF_FIRE:
        case RG_REQUIEM_OF_SPIRIT:
            return CanUse(RG_FAIRY_OCARINA) && HasItem(RG_OCARINA_A_BUTTON) && HasItem(RG_OCARINA_C_RIGHT_BUTTON) &&
                   HasItem(RG_OCARINA_C_DOWN_BUTTON);
        case RG_SONG_OF_STORMS:
            return CanUse(RG_FAIRY_OCARINA) && HasItem(RG_OCARINA_A_BUTTON) && HasItem(RG_OCARINA_C_UP_BUTTON) &&
                   HasItem(RG_OCARINA_C_DOWN_BUTTON);
        case RG_MINUET_OF_FOREST:
            return CanUse(RG_FAIRY_OCARINA) && HasItem(RG_OCARINA_A_BUTTON) && HasItem(RG_OCARINA_C_LEFT_BUTTON) &&
                   HasItem(RG_OCARINA_C_RIGHT_BUTTON) && HasItem(RG_OCARINA_C_UP_BUTTON);
        case RG_SERENADE_OF_WATER:
        case RG_NOCTURNE_OF_SHADOW:
            return CanUse(RG_FAIRY_OCARINA) && HasItem(RG_OCARINA_A_BUTTON) && HasItem(RG_OCARINA_C_LEFT_BUTTON) &&
                   HasItem(RG_OCARINA_C_RIGHT_BUTTON) && HasItem(RG_OCARINA_C_DOWN_BUTTON);

        // Misc. Items
        case RG_FISHING_POLE:
            // The rod is used through the fishing owner's paid minigame, not
            // merely by entering the pond. Mirror the AP can_use(rod) rule.
            return HasItem(RG_CHILD_WALLET) &&
                   (!ctx->GetOption(RSK_SHUFFLE_NPC_SOUL) || HasItem(RG_NPC_SOUL)) &&
                   (!ctx->GetOption(RSK_SHUFFLE_SPEAK) || HasItem(RG_SPEAK_HYLIAN)) &&
                   HasAnimalSoul(RG_ANIMAL_SOUL_FISH);
        case RG_CRAWL:
            return IsChild;

        // Bottle Items
        case RG_BOTTLE_WITH_BUGS:
            return Get(LOGIC_BUG_ACCESS);
        case RG_BOTTLE_WITH_FISH:
            return Get(LOGIC_FISH_ACCESS);
        case RG_BOTTLE_WITH_BLUE_FIRE:
            return Get(LOGIC_BLUE_FIRE_ACCESS);
        case RG_BOTTLE_WITH_FAIRY:
            return Get(LOGIC_FAIRY_ACCESS);

        case RG_FAIRY_OCARINA:
        case RG_OCARINA_OF_TIME:
            return true;

        default:
            SPDLOG_INFO("CanUse reached `default` for {}. using HasItem is a minor Optimisation.", itemName);
            return true;
    }
}
bool Logic::HasAnimalSoul(RandomizerGet individualSoul) {
    const int mode = ctx->GetOption(RSK_SHUFFLE_ANIMAL_SOUL).Get();
    if (mode == 0) return true;
    if (mode == 1) return HasItem(RG_ANIMAL_SOUL);
    return HasItem(individualSoul);
}
bool Logic::CanCutShrubs() {
    if (ctx->GetOption(RSK_SHUFFLE_GRASS_SOUL) && !HasItem(RG_GRASS_SOUL)) { return false; }
    return CanUse(RG_KOKIRI_SWORD) || CanUse(RG_BOOMERANG) || HasExplosives() || CanUse(RG_MASTER_SWORD) ||
           CanUse(RG_MEGATON_HAMMER) || CanUse(RG_BIGGORON_SWORD) || CanUse(RG_GIANTS_KNIFE);
}
bool Logic::CanPickUpGrass() {
    if (ctx->GetOption(RSK_SHUFFLE_GRASS_SOUL) && !HasItem(RG_GRASS_SOUL)) {
        return false;
    }
    // Shuffle Grab adds a tier before vanilla Strength:
    // 1) Grab / Power Bracelet -> lift grass and small rocks
    // 2) Goron Bracelet        -> bomb flowers / first real Strength tier
    // 3) Silver Gauntlets      -> silver blocks and silver boulders
    // 4) Golden Gauntlets      -> everything
    return HasItem(RG_POWER_BRACELET);
}
}
static auto logic=std::make_shared<Rando::Logic>();
static bool objectInteraction(int kind) {switch(kind) {
        case RCTYPE_GRASS:
            // Grass/Bush Soul is the shared existence gate. A grass check can be
            // collected either by lifting it with Grab OR by destroying it with a
            // normal shrub-breaking method (sword, boomerang, bombs, etc.).
            return logic->CanPickUpGrass() || logic->CanCutShrubs();
        case RCTYPE_BUSH:
            // En_Wood02 bushes yield on movement/contact; En_Kusa grass above
            // still needs a real cut/break/lift method. Soul is existence only.
            return !ctx->GetOption(RSK_SHUFFLE_GRASS_SOUL) || logic->HasItem(RG_GRASS_SOUL);

 default:return false;
}}
static int cases=0,failures=0;
static void ck(bool got,bool expected,const char* what){++cases;if(got!=expected){++failures;if(failures<10)std::printf("FAIL %s\n",what);}}
int main(){
 // Verify the overloaded actor ID is classified by role, before category.
 for(int category:{ACTORCAT_NPC,ACTORCAT_PROP,ACTORCAT_ENEMY}) {
  for(int param:{1,99,100,114,115,116,200}) {
   Actor a{};a.id=ACTOR_FISHING;a.category=category;a.params=param;
   ck(IsMegaNpcSoulActor(&a),param<100,"fishing owner/fish NPC classification");
  }
 }
 ck(IsMegaNpcSoulActor(nullptr),false,"null actor");
 // Actual runtime soul predicates: NPC visibility, speech, fish presence
 // are three independent facts. A generic soul cannot replace Fish in mode 2.
 for(int rando=0;rando<2;++rando)for(int npcShuffle=0;npcShuffle<2;++npcShuffle)
 for(int speakMode=0;speakMode<3;++speakMode)for(int animalMode=0;animalMode<3;++animalMode)
 for(int mask=0;mask<16;++mask) {
  testRando=rando;ctx->GetOption(RSK_SHUFFLE_NPC_SOUL).Set(npcShuffle);
  ctx->GetOption(RSK_SHUFFLE_SPEAK).Set(speakMode);ctx->GetOption(RSK_SHUFFLE_ANIMAL_SOUL).Set(animalMode);
  flags.clear();if(mask&1)flags.insert(RAND_INF_NPC_SOUL);if(mask&2)flags.insert(RAND_INF_CAN_SPEAK_HYLIAN);
  if(mask&4)flags.insert(RAND_INF_ANIMAL_SOUL);if(mask&8)flags.insert(RAND_INF_ANIMAL_SOUL_FISH);
  const bool owner=!rando||!npcShuffle||(mask&1);
  const bool talk=owner&&(!rando||!speakMode||(mask&2));
  const bool fish=!rando||!animalMode||(animalMode==1?(mask&4):(mask&8));
  ck(MegaSoul_IsFishingOwnerPresent(),owner,"owner presence");
  ck(MegaSoul_CanTalkToFishingOwner(),talk,"owner talk prerequisite");
  ck(MegaSoul_ArePondFishPresent(),fish,"independent fish visibility");
 }
 testRando=true;
 // Repeated in-room receive/remove: callbacks must not need a re-entry.
 flags.clear();ctx->GetOption(RSK_SHUFFLE_NPC_SOUL).Set(1);ctx->GetOption(RSK_SHUFFLE_SPEAK).Set(2);ctx->GetOption(RSK_SHUFFLE_ANIMAL_SOUL).Set(2);
 ck(MegaSoul_ArePondFishPresent(),false,"fish absent initially");flags.insert(RAND_INF_ANIMAL_SOUL_FISH);
 ck(MegaSoul_ArePondFishPresent(),true,"fish receipt reveals fish");ck(MegaSoul_IsFishingOwnerPresent(),false,"fish receipt does not reveal owner");
 flags.insert(RAND_INF_NPC_SOUL);ck(MegaSoul_CanTalkToFishingOwner(),false,"NPC receipt alone cannot speak");
 flags.insert(RAND_INF_CAN_SPEAK_HYLIAN);ck(MegaSoul_CanTalkToFishingOwner(),true,"speak completes owner access");
 flags.erase(RAND_INF_ANIMAL_SOUL_FISH);ck(MegaSoul_ArePondFishPresent(),false,"fish removal hides fish again");
 // Native pond action (complete production CanUse), both ages and modes.
 for(int age=0;age<2;++age)for(int npcShuffle=0;npcShuffle<2;++npcShuffle)
 for(int speakMode=0;speakMode<3;++speakMode)for(int animalMode=0;animalMode<3;++animalMode)
 for(int rodShuffle=0;rodShuffle<2;++rodShuffle)for(int walletShuffle=0;walletShuffle<2;++walletShuffle)
 for(int mask=0;mask<64;++mask) {
  logic->IsAdult=age;logic->IsChild=!age;logic->items.clear();
  ctx->GetOption(RSK_SHUFFLE_NPC_SOUL).Set(npcShuffle);ctx->GetOption(RSK_SHUFFLE_SPEAK).Set(speakMode);
  ctx->GetOption(RSK_SHUFFLE_ANIMAL_SOUL).Set(animalMode);ctx->GetOption(RSK_SHUFFLE_FISHING_POLE).Set(rodShuffle);ctx->GetOption(RSK_SHUFFLE_CHILD_WALLET).Set(walletShuffle);
  if(mask&1)logic->items.insert(RG_NPC_SOUL);if(mask&2)logic->items.insert(RG_SPEAK_HYLIAN);
  if(mask&4)logic->items.insert(RG_ANIMAL_SOUL_FISH);if(mask&8)logic->items.insert(RG_ANIMAL_SOUL);
  if(mask&16)logic->items.insert(RG_FISHING_POLE);if(mask&32)logic->items.insert(RG_CHILD_WALLET);
  bool expected=(!npcShuffle||(mask&1))&&(!speakMode||(mask&2))&&(!animalMode||(animalMode==1?(mask&8):(mask&4)))&&(!rodShuffle||(mask&16))&&(!walletShuffle||(mask&32));
  ck(logic->CanUse(RG_FISHING_POLE),expected,"native pond action");
 }
 // Actual bush/grass switch branches and grass helper bodies. No change to
 // cutting semantics is permitted just to make walk-through bushes available.
 for(int soulShuffle=0;soulShuffle<2;++soulShuffle)for(int mask=0;mask<8;++mask){
  ctx->GetOption(RSK_SHUFFLE_GRASS_SOUL).Set(soulShuffle);logic->IsAdult=false;logic->IsChild=true;logic->items.clear();
  if(mask&1)logic->items.insert(RG_GRASS_SOUL);if(mask&2)logic->items.insert(RG_POWER_BRACELET);if(mask&4)logic->items.insert(RG_KOKIRI_SWORD);
  const bool exists=!soulShuffle||(mask&1);
  ck(objectInteraction(RCTYPE_BUSH),exists,"walk-through bush needs no method");
  ck(objectInteraction(RCTYPE_GRASS),exists&&((mask&2)||(mask&4)),"grass still needs grab or cutting");
 }
 std::printf("cases=%d failures=%d\n",cases,failures);return failures?1:0;
}
