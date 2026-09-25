
#include <algorithm>
#include <array>
#include <cstdint>
#include <cstdio>
#include <set>
#include <map>
#include <functional>
#include <string>
#include <vector>
#include "soh/Enhancements/randomizer/randomizerEnums.h"
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


struct Context {
 std::map<RandomizerSettingKey,OptionValue> options;
 OptionValue& GetOption(RandomizerSettingKey k){return options[k];}
 OptionValue GetTrickOption(RandomizerTrick){return OptionValue(0);}
};
Context c;Context* ctx=&c;
struct Logic {
 bool IsAdult=true,IsChild=false,explosives=true;
 std::set<RandomizerGet> missing;
 bool HasItem(RandomizerGet k){return !missing.count(k);}
 bool CanUse(RandomizerGet k){return !missing.count(k);}
 bool HasExplosives(){return explosives;}
 bool BeanPlanted(LogicVal){return false;}
 bool CanKillEnemy(RandomizerEnemy){return true;}
 bool CanBreakRocks();
};
bool Logic::CanBreakRocks() {
    if (ctx->GetOption(RSK_SHUFFLE_ROCK_SOUL) && !HasItem(RG_ROCK_SOUL)) {
        return false;
    }
    // SOH-EXTREME: rocks/boulders use explosives or the shuffled Grab ability.
    // Hammer is intentionally not a substitute for this physical rule.
    return HasExplosives() || HasItem(RG_POWER_BRACELET);
}
Logic l;Logic* logic=&l;
bool AnyAgeTime(const std::function<bool()>& condition){return condition();}
}
using namespace Rando;
int checks=0;void ck(bool v,const char* msg){++checks;if(!v){std::printf("FAIL %s\n",msg);std::exit(1);}}
int main(){
 std::vector<std::function<bool()>> sheiks={
[]{return (AnyAgeTime([]{return logic->CanKillEnemy(RE_WOLFOS);}) && logic->HasItem(RG_OPEN_CHEST)) && (!ctx->GetOption(RSK_SHUFFLE_NPC_SOUL) || logic->HasItem(RG_NPC_SOUL)) && (!ctx->GetOption(RSK_SHUFFLE_SPEAK) || logic->HasItem(RG_SPEAK_HYLIAN));},
[]{return (logic->CanKillEnemy(RE_STALFOS) && logic->HasItem(RG_OPEN_CHEST)) && (!ctx->GetOption(RSK_SHUFFLE_NPC_SOUL) || logic->HasItem(RG_NPC_SOUL)) && (!ctx->GetOption(RSK_SHUFFLE_SPEAK) || logic->HasItem(RG_SPEAK_HYLIAN));},
[]{return (logic->IsAdult) && (!ctx->GetOption(RSK_SHUFFLE_NPC_SOUL) || logic->HasItem(RG_NPC_SOUL)) && (!ctx->GetOption(RSK_SHUFFLE_SPEAK) || logic->HasItem(RG_SPEAK_HYLIAN));},
[]{return (true) && (!ctx->GetOption(RSK_SHUFFLE_NPC_SOUL) || logic->HasItem(RG_NPC_SOUL)) && (!ctx->GetOption(RSK_SHUFFLE_SPEAK) || logic->HasItem(RG_SPEAK_HYLIAN));},
[]{return (logic->IsAdult && logic->HasItem(RG_FOREST_MEDALLION) && logic->HasItem(RG_FIRE_MEDALLION) && logic->HasItem(RG_WATER_MEDALLION)) && (!ctx->GetOption(RSK_SHUFFLE_NPC_SOUL) || logic->HasItem(RG_NPC_SOUL)) && (!ctx->GetOption(RSK_SHUFFLE_SPEAK) || logic->HasItem(RG_SPEAK_HYLIAN));},
[]{return (logic->IsAdult) && (!ctx->GetOption(RSK_SHUFFLE_NPC_SOUL) || logic->HasItem(RG_NPC_SOUL)) && (!ctx->GetOption(RSK_SHUFFLE_SPEAK) || logic->HasItem(RG_SPEAK_HYLIAN));},
[]{return (logic->IsAdult && logic->HasItem(RG_FOREST_MEDALLION)) && (!ctx->GetOption(RSK_SHUFFLE_NPC_SOUL) || logic->HasItem(RG_NPC_SOUL)) && (!ctx->GetOption(RSK_SHUFFLE_SPEAK) || logic->HasItem(RG_SPEAK_HYLIAN));}
 };
 for(int npcMode=0;npcMode<2;++npcMode)for(int speechMode=0;speechMode<3;++speechMode)
 for(int npc=0;npc<2;++npc)for(int speech=0;speech<2;++speech){
  ctx->options[RSK_SHUFFLE_NPC_SOUL]=npcMode;ctx->options[RSK_SHUFFLE_SPEAK]=speechMode;
  logic->missing.clear();if(!npc)logic->missing.insert(RG_NPC_SOUL);
  if(!speech){logic->missing.insert(RG_SPEAK_HYLIAN);logic->missing.insert(RG_SPEAK_GORON);}
  bool expected=(!npcMode||npc)&&(!speechMode||speech);
  for(const auto& f:sheiks)ck(f()==expected,"Sheik soul/language combination");
  ck((logic->IsAdult && (!ctx->GetOption(RSK_SHUFFLE_NPC_SOUL) || logic->HasItem(RG_NPC_SOUL)) && (!ctx->GetOption(RSK_SHUFFLE_SPEAK) || logic->HasItem(RG_SPEAK_GORON)) && (logic->HasItem(RG_GORONS_BRACELET) || logic->HasExplosives() || logic->CanUse(RG_FAIRY_BOW) ||
                                                                                   (ctx->GetTrickOption(RT_GC_LINK_GORON_DINS) && (logic->CanUse(RG_DINS_FIRE) || (ctx->GetTrickOption(RT_BLUE_FIRE_MUD_WALLS) && logic->CanUse(RG_BOTTLE_WITH_BLUE_FIRE))))))==expected,"Goron door event soul/language");
 }
 ctx->options[RSK_SHUFFLE_ROCK_SOUL]=1;
 logic->missing={RG_ROCK_SOUL};logic->explosives=true;
 ck(!logic->CanBreakRocks(),"Bombchus without soul cannot remove mountain rocks");
 ck(!(AnyAgeTime([]{return logic->CanBreakRocks();}) || (logic->IsAdult && ((logic->BeanPlanted(LOGIC_PLANT_DEATH_MOUNTAIN_TRAIL_BEAN) && logic->HasItem(RG_GORONS_BRACELET)) || (logic->CanUse(RG_HOVER_BOOTS) && ctx->GetTrickOption(RT_DMT_CLIMB_HOVERS))))),"native route blocks missing rock soul");
 logic->missing.clear();ck(logic->CanBreakRocks(),"soul and explosives allow rocks");
 ck((AnyAgeTime([]{return logic->CanBreakRocks();}) || (logic->IsAdult && ((logic->BeanPlanted(LOGIC_PLANT_DEATH_MOUNTAIN_TRAIL_BEAN) && logic->HasItem(RG_GORONS_BRACELET)) || (logic->CanUse(RG_HOVER_BOOTS) && ctx->GetTrickOption(RT_DMT_CLIMB_HOVERS))))),"native mountain rocks restored");
 logic->missing={RG_POWER_BRACELET};logic->explosives=false;
 ck(!logic->CanBreakRocks(),"soul without method cannot break rocks");
 logic->missing.clear();ck(logic->CanBreakRocks(),"Grab is valid rock method");
 logic->missing={RG_CLIMB};ck(!(logic->HasItem(RG_CLIMB) &&
                                           (logic->IsAdult || ctx->GetTrickOption(RT_DMT_SHIELDLESS_CLIMB) || logic->HasItem(RG_HYLIAN_SHIELD) || logic->CanUse(RG_NAYRUS_LOVE))),"summit requires climb");
 logic->missing.clear();ck((logic->HasItem(RG_CLIMB) &&
                                           (logic->IsAdult || ctx->GetTrickOption(RT_DMT_SHIELDLESS_CLIMB) || logic->HasItem(RG_HYLIAN_SHIELD) || logic->CanUse(RG_NAYRUS_LOVE))),"adult summit climb restored");
 logic->missing={RG_DINS_FIRE};ck(!(logic->CanUse(RG_DINS_FIRE) || (ctx->GetTrickOption(RT_GY_SHADOW_FIRE_ARROWS) && logic->IsAdult && logic->CanUse(RG_FIRE_ARROWS))),"Shadow door no Dins Fire and no fire-arrow trick");
 logic->missing.clear();ck((logic->CanUse(RG_DINS_FIRE) || (ctx->GetTrickOption(RT_GY_SHADOW_FIRE_ARROWS) && logic->IsAdult && logic->CanUse(RG_FIRE_ARROWS))),"Shadow door with usable Dins Fire");
 std::printf("CHECKS %d PASS\n",checks);
}
