
#include <algorithm>
#include <array>
#include <cassert>
#include <cstdio>
#include <cstring>
#include <functional>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>
#include "z64.h"
#include "macros.h"
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


class Context {
public:
    std::array<OptionValue, RSK_MAX> options{};
    std::array<OptionValue, RT_MAX> tricks{};
    static std::shared_ptr<Context> GetInstance() { static auto instance = std::make_shared<Context>(); return instance; }
    OptionValue& GetOption(RandomizerSettingKey key) { return options[key]; }
    OptionValue& GetTrickOption(RandomizerTrick key) { return tricks[key]; }
};
}
static int checks=0, failures=0;
static void check(bool value, const char* label) { ++checks; if(!value) { ++failures; if (failures<=8) std::printf("FAIL %s\n",label); } }
static int finish() { std::printf("checks=%d failures=%d\n", checks, failures); return failures ? 1 : 0; }

namespace Rando {
class LocationData { public: ActorID actor=ACTOR_EN_BOX; int params=5<<12; ActorID GetActorID() const{return actor;} int GetActorParams() const{return params;} };
namespace StaticData { static LocationData data; static const LocationData* GetLocation(RandomizerCheck){return &data;} }
}
struct TestLogic {
 bool IsChild=false,IsAdult=false,AtDay=false,AtNight=false;bool chest=true,large=true;
 bool HasItem(RandomizerGet) const{return chest;} bool CanOpenLargeChest() const{return large;}
};
static auto logic=std::make_shared<TestLogic>();
static unsigned baseMask=0,methodMask=0;
static unsigned ageTimeBit(){return (logic->IsChild?1u:logic->IsAdult?4u:0u) << (logic->AtNight?1:0);}
static bool MegaSoulAllowsLocation(RandomizerCheck){return (methodMask&ageTimeBit())!=0;}
struct Region {bool childDay=false,childNight=false,adultDay=false,adultNight=false;};
class LocationAccess {
public:
 RandomizerCheck location=RC_GV_WATERFALL_FREESTANDING_POH;
 bool GetConditionsMet() const{return (baseMask&ageTimeBit())!=0;}
 bool CheckConditionAtAgeTime(bool& age,bool& time) const;
 bool ConditionsMet(Region*,bool) const;
};
bool LocationAccess::CheckConditionAtAgeTime(bool& age, bool& time) const {
    logic->IsChild = false;
    logic->IsAdult = false;
    logic->AtDay = false;
    logic->AtNight = false;

    time = true;
    age = true;

    return GetConditionsMet();
}
bool LocationAccess::ConditionsMet(Region* parentRegion, bool calculatingAvailableChecks) const {
    // SOH-EXTREME 0.7.55: enforce Open Chest at the central reachability boundary.
    // This path is shared by native generation and the in-game Check Tracker, so a
    // chest can never be advertised reachable when the runtime VB_OPEN_CHEST hook
    // would refuse to open it.  Actor params encode EnBox::type in bits 12..15.
    auto ctx = Rando::Context::GetInstance();
    if (ctx->GetOption(RSK_SHUFFLE_OPEN_CHEST)) {
        const auto* locData = Rando::StaticData::GetLocation(location);
        if (locData != nullptr && locData->GetActorID() == ACTOR_EN_BOX) {
            if (!logic->HasItem(RG_OPEN_CHEST)) {
                return false;
            }
            if (ctx->GetOption(RSK_SHUFFLE_OPEN_CHEST).Is(RO_OPEN_CHEST_PROGRESSIVE)) {
                const int chestType = (locData->GetActorParams() >> 12) & 0xF;
                const bool smallChest = chestType == 5 || chestType == 6 || chestType == 7 || chestType == 8;
                if (!smallChest && !logic->CanOpenLargeChest()) {
                    return false;
                }
            }
        }
    }

    // Category gates include AGE-DEPENDENT interaction methods (usable sword,
    // Boomerang, Hammer, etc.), not only age-independent soul ownership. Test
    // them AFTER selecting each reachable age/time and beside the location rule.
    // A method usable as adult must never unlock a child-only route, and the age
    // left by the previously evaluated check must not hide a valid route either.
    const auto canCollectAtAgeTime = [this](bool& age, bool& time) {
        return CheckConditionAtAgeTime(age, time) && MegaSoulAllowsLocation(location);
    };

    // WARNING enterance validation can run this after resetting the access for sphere 0 validation
    // When refactoring ToD access, either fix the above or do not assume that we
    // have any access at all just because this is being run
    bool conditionsMet = false;

    if ((parentRegion->childDay && canCollectAtAgeTime(logic->IsChild, logic->AtDay)) ||
        (parentRegion->childNight && canCollectAtAgeTime(logic->IsChild, logic->AtNight)) ||
        (parentRegion->adultDay && canCollectAtAgeTime(logic->IsAdult, logic->AtDay)) ||
        (parentRegion->adultNight && canCollectAtAgeTime(logic->IsAdult, logic->AtNight))) {
        conditionsMet = true;
    }

    return conditionsMet;
}
int main(){
 LocationAccess loc;
 for (unsigned access=0;access<16;++access) for(baseMask=0;baseMask<16;++baseMask)
 for(methodMask=0;methodMask<16;++methodMask) for(unsigned stale=0;stale<4;++stale){
   Region region{bool(access&1),bool(access&2),bool(access&4),bool(access&8)};
   logic->IsChild=stale<2;logic->IsAdult=stale>=2;logic->AtDay=!(stale&1);logic->AtNight=stale&1;
   check(loc.ConditionsMet(&region,true)==bool(access&baseMask&methodMask),"base and interaction must share reachable age/time");
 }
 baseMask=methodMask=15;Region any{true,true,true,true};auto ctx=Rando::Context::GetInstance();
 ctx->GetOption(RSK_SHUFFLE_OPEN_CHEST).Set(RO_OPEN_CHEST_PROGRESSIVE);
 logic->chest=false;check(!loc.ConditionsMet(&any,true),"missing open chest stays blocked");
 logic->chest=true;logic->large=false;Rando::StaticData::data.params=0;check(!loc.ConditionsMet(&any,true),"large chest tier stays blocked");
 Rando::StaticData::data.params=5<<12;check(loc.ConditionsMet(&any,true),"small chest tier remains valid");
 return finish();
}
