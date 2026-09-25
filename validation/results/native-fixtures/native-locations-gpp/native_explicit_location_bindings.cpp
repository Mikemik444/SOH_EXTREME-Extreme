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

#include <unordered_set>
#include <utility>
static const std::pair<int,long long> bindings[] = {
#include "soh/Network/Archipelago/ArchipelagoLocationMap.inc"
};
int main(){std::unordered_set<int>rcs;std::unordered_set<long long>ids;
for(auto p:bindings){check(rcs.insert(p.first).second,"unique native RC");check(ids.insert(p.second).second,"unique AP ID");check(p.second!=943&&p.second!=944,"retired nonexistent pot IDs");}
return finish();}
