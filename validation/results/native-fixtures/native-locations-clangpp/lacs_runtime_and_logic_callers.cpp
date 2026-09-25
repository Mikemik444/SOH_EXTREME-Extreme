#include <array>
#include <algorithm>
#include <string>
#include <memory>
#include <set>
#include <cstdio>
#include "soh/Enhancements/randomizer/randomizerEnums.h"
#include "soh/Enhancements/randomizer/LacsRequirements.h"
#include "soh/Network/Archipelago/ArchipelagoC.h"
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
 std::array<OptionValue,RSK_MAX> values{};
 OptionValue& GetOption(RandomizerSettingKey k){return values[k];}
};
}
static auto ctx=std::make_shared<Rando::Context>();
static bool apSave=false;
extern "C" bool Archipelago_IsCurrentSaveFile(void){return apSave;}
static unsigned tests=0,failures=0;
void check(bool v,const char* l){++tests;if(!v){++failures;if(failures<12)std::printf("FAIL %s\n",l);}}
int finish(){std::printf("assertions=%u failures=%u\n",tests,failures);return failures?1:0;}

struct Inventory {unsigned stones=0,medallions=0,dungeons=0;struct{unsigned gsTokens=0;}inventory;std::set<RandomizerGet>items;};
static Inventory gSaveContext;
#define RAND_GET_OPTION(k) ctx->GetOption(k)
#define CHECK_QUEST_ITEM(q) gSaveContext.items.contains((q)==0?RG_SHADOW_MEDALLION:RG_SPIRIT_MEDALLION)
#define QUEST_MEDALLION_SHADOW 0
#define QUEST_MEDALLION_SPIRIT 1
unsigned CheckStoneCount(){return gSaveContext.stones;}
unsigned CheckMedallionCount(){return gSaveContext.medallions;}
unsigned CheckDungeonCount(){return gSaveContext.dungeons;}
bool Flags_GetRandomizerInf(RandomizerInf k){return k==RAND_INF_GREG_FOUND&&gSaveContext.items.contains(RG_GREG_RUPEE);}
namespace Rando {class Logic {public:
 bool HasItem(RandomizerGet k){return gSaveContext.items.contains(k);}
 unsigned StoneCount(){return gSaveContext.stones;}unsigned MedallionCount(){return gSaveContext.medallions;}
 unsigned DungeonCount(){return gSaveContext.dungeons;}unsigned GetGSCount(){return gSaveContext.inventory.gsTokens;}
 bool CanTriggerLacs();
};
bool Logic::CanTriggerLacs() {
    SohExtreme::LacsRequirements state;
    state.archipelago = Archipelago_IsCurrentSaveFile();
    state.triforceHunt = ctx->GetOption(RSK_TRIFORCE_HUNT_PIECES_TOTAL).Get() > 0;
    state.shadowMedallion = HasItem(RG_SHADOW_MEDALLION);
    state.spiritMedallion = HasItem(RG_SPIRIT_MEDALLION);
    state.bossKeyMode = ctx->GetOption(RSK_GANONS_BOSS_KEY).Get();
    state.stones = StoneCount();
    state.medallions = MedallionCount();
    state.dungeons = DungeonCount();
    state.tokens = GetGSCount();
    state.requiredStones = ctx->GetOption(RSK_GBK_STONE_COUNT).Get();
    state.requiredMedallions = ctx->GetOption(RSK_GBK_MEDALLION_COUNT).Get();
    state.requiredRewards = ctx->GetOption(RSK_GBK_REWARD_COUNT).Get();
    state.requiredDungeons = ctx->GetOption(RSK_GBK_DUNGEON_COUNT).Get();
    state.requiredTokens = ctx->GetOption(RSK_GBK_TOKEN_COUNT).Get();
    // Wildcard may work in-game, but is deliberately not an in-logic substitute.
    state.bonusReward = HasItem(RG_GREG_RUPEE) &&
        ctx->GetOption(RSK_GBK_OPTIONS).Is(RO_CHECK_TRIGGER_GREG_REWARD);
    return SohExtreme::MeetsLacsRequirements(state);
}
}
static bool MeetsLacsRequirementsForSave() {
    SohExtreme::LacsRequirements state;
    state.archipelago = Archipelago_IsCurrentSaveFile();
    state.triforceHunt = RAND_GET_OPTION(RSK_TRIFORCE_HUNT_PIECES_TOTAL).Get() > 0;
    state.shadowMedallion = CHECK_QUEST_ITEM(QUEST_MEDALLION_SHADOW);
    state.spiritMedallion = CHECK_QUEST_ITEM(QUEST_MEDALLION_SPIRIT);
    state.bossKeyMode = RAND_GET_OPTION(RSK_GANONS_BOSS_KEY).Get();
    state.stones = CheckStoneCount();
    state.medallions = CheckMedallionCount();
    state.dungeons = CheckDungeonCount();
    state.tokens = gSaveContext.inventory.gsTokens;
    state.requiredStones = RAND_GET_OPTION(RSK_GBK_STONE_COUNT).Get();
    state.requiredMedallions = RAND_GET_OPTION(RSK_GBK_MEDALLION_COUNT).Get();
    state.requiredRewards = RAND_GET_OPTION(RSK_GBK_REWARD_COUNT).Get();
    state.requiredDungeons = RAND_GET_OPTION(RSK_GBK_DUNGEON_COUNT).Get();
    state.requiredTokens = RAND_GET_OPTION(RSK_GBK_TOKEN_COUNT).Get();
    const auto gregMode = RAND_GET_OPTION(RSK_GBK_OPTIONS).Get();
    state.bonusReward = Flags_GetRandomizerInf(RAND_INF_GREG_FOUND) &&
        (gregMode == RO_CHECK_TRIGGER_GREG_REWARD || gregMode == RO_CHECK_TRIGGER_WILDCARD_REWARD);
    return SohExtreme::MeetsLacsRequirements(state);
}
int main(){
 Rando::Logic logic;
 unsigned modes[]={RO_GANON_BOSS_KEY_VANILLA,RO_GANON_BOSS_KEY_ANYWHERE,RO_GANON_BOSS_KEY_STONES,RO_GANON_BOSS_KEY_MEDALLIONS,RO_GANON_BOSS_KEY_REWARDS,RO_GANON_BOSS_KEY_DUNGEONS,RO_GANON_BOSS_KEY_TOKENS};
 for(auto k:{RSK_GBK_STONE_COUNT,RSK_GBK_MEDALLION_COUNT,RSK_GBK_REWARD_COUNT,RSK_GBK_DUNGEON_COUNT,RSK_GBK_TOKEN_COUNT})ctx->GetOption(k).Set(3);
 for(int ap=0;ap<2;++ap)for(int hunt=0;hunt<2;++hunt)for(auto mode:modes)for(unsigned n=0;n<4;++n)
 for(int shadow=0;shadow<2;++shadow)for(int spirit=0;spirit<2;++spirit)for(int greg=0;greg<2;++greg){
  apSave=ap;ctx->GetOption(RSK_TRIFORCE_HUNT_PIECES_TOTAL).Set(hunt?60:0);ctx->GetOption(RSK_GANONS_BOSS_KEY).Set(mode);ctx->GetOption(RSK_GBK_OPTIONS).Set(RO_CHECK_TRIGGER_GREG_REWARD);
  gSaveContext.items.clear();if(shadow)gSaveContext.items.insert(RG_SHADOW_MEDALLION);if(spirit)gSaveContext.items.insert(RG_SPIRIT_MEDALLION);if(greg)gSaveContext.items.insert(RG_GREG_RUPEE);
  gSaveContext.stones=n;gSaveContext.medallions=n;gSaveContext.dungeons=n;gSaveContext.inventory.gsTokens=n;
  bool expected=shadow&&spirit;
  if(ap&&!hunt){
   if(mode==RO_GANON_BOSS_KEY_STONES||mode==RO_GANON_BOSS_KEY_MEDALLIONS||mode==RO_GANON_BOSS_KEY_DUNGEONS)expected=n+greg>=3;
   if(mode==RO_GANON_BOSS_KEY_REWARDS)expected=2*n+greg>=3;
   if(mode==RO_GANON_BOSS_KEY_TOKENS)expected=n>=3;
  }
  check(logic.CanTriggerLacs()==expected,"native LACS logic policy");
  check(MeetsLacsRequirementsForSave()==expected,"actual save LACS trigger policy");
 }
 // Explicitly preserve the intended wildcard difference: an out-of-logic bonus
 // may trigger in-game, but must not be relied upon by item placement/tracking.
 apSave=true;ctx->GetOption(RSK_TRIFORCE_HUNT_PIECES_TOTAL).Set(0);ctx->GetOption(RSK_GANONS_BOSS_KEY).Set(RO_GANON_BOSS_KEY_STONES);ctx->GetOption(RSK_GBK_OPTIONS).Set(RO_CHECK_TRIGGER_WILDCARD_REWARD);
 gSaveContext.stones=2;gSaveContext.items={RG_GREG_RUPEE};
 check(!logic.CanTriggerLacs(),"wildcard not in logic");check(MeetsLacsRequirementsForSave(),"wildcard still works in game");
 return finish();}
