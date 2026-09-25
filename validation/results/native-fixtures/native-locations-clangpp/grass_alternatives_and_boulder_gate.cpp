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

namespace Rando { class Logic {public:
 std::set<RandomizerGet> items;bool child=true;
 bool HasItem(RandomizerGet k){
  if(k==RG_POWER_BRACELET&&!ctx->GetOption(RSK_SHUFFLE_GRAB))return true;
  return items.contains(k);
 }
 bool CanUse(RandomizerGet k){
  if((k==RG_MASTER_SWORD||k==RG_MEGATON_HAMMER||k==RG_BIGGORON_SWORD||k==RG_GIANTS_KNIFE)&&child)return false;
  if((k==RG_KOKIRI_SWORD||k==RG_BOOMERANG)&&!child)return false;
  return items.contains(k);
 }
 bool HasExplosives(){return items.contains(RG_BOMB_BAG)||items.contains(RG_BOMBCHU_5);}
 bool CanCutShrubs();bool CanPickUpGrass();bool CanCollectGrass();
};
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
bool Logic::CanCollectGrass() {
    return CanCutShrubs() || CanPickUpGrass();
}
}
static auto logic=std::make_shared<Rando::Logic>();
static bool boulderGate(int t) {switch(t){
        case RCTYPE_BOULDER:
            // The soul is shared, but bronze, silver and bombable boulders do
            // not share a breaking method. Each LOCATION owns its material /
            // route rule (Hammer, strength + Grab, explosives, event, etc.).
            // A generic explosives/Grab AND here incorrectly blocked a bronze
            // boulder even with a usable Hammer and its soul.
            return !ctx->GetOption(RSK_SHUFFLE_ROCK_SOUL) || logic->HasItem(RG_ROCK_SOUL);

 default:return false;}}
int main(){
 const RandomizerGet tools[]={RG_KOKIRI_SWORD,RG_BOOMERANG,RG_BOMB_BAG,RG_BOMBCHU_5,RG_MASTER_SWORD,RG_MEGATON_HAMMER,RG_BIGGORON_SWORD,RG_GIANTS_KNIFE};
 for(int soulShuffle=0;soulShuffle<2;++soulShuffle)for(int grabShuffle=0;grabShuffle<2;++grabShuffle)
 for(int soul=0;soul<2;++soul)for(int grab=0;grab<2;++grab)for(int child=0;child<2;++child)for(unsigned mask=0;mask<256;++mask){
  ctx->GetOption(RSK_SHUFFLE_GRASS_SOUL).Set(soulShuffle);ctx->GetOption(RSK_SHUFFLE_GRAB).Set(grabShuffle);
  logic->items.clear();logic->child=child;
  if(soul)logic->items.insert(RG_GRASS_SOUL);if(grab)logic->items.insert(RG_POWER_BRACELET);
  bool cut=false;
  for(unsigned i=0;i<8;++i)if(mask&(1u<<i)){
   logic->items.insert(tools[i]);
   // Independent age/tool truth table, not a call to the implementation.
   if((i<2&&child)||(i>=2&&i<4)||(i>=4&&!child))cut=true;
  }
  bool exists=!soulShuffle||soul;
  check(logic->CanCollectGrass()==(exists&&(cut||!grabShuffle||grab)),"grass collection OR alternatives");
  check(logic->CanCutShrubs()==(exists&&cut),"resource cutting remains separate");
 }
 for(int shuffle=0;shuffle<2;++shuffle)for(int soul=0;soul<2;++soul){
  ctx->GetOption(RSK_SHUFFLE_ROCK_SOUL).Set(shuffle);logic->items.clear();if(soul)logic->items.insert(RG_ROCK_SOUL);
  check(boulderGate(RCTYPE_BOULDER)==(!shuffle||soul),"boulder material rule not overwritten by generic method");
 }
 return finish();}
