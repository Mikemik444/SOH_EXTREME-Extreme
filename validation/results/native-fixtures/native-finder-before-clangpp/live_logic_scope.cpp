
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

#include "soh/Enhancements/randomizer/CheckFinderState.h"
struct TestLogic {
 SaveContext* mSaveContext=nullptr;
 bool CalculatingAvailableChecks=false,IsChild=false,IsAdult=false,AtDay=false,AtNight=false;
 RandomizerRegion CurrentRegionKey=RR_GERUDO_VALLEY;RandomizerCheck CurrentCheckKey=RC_GV_WATERFALL_FREESTANDING_POH;
 void SetSaveContext(SaveContext* s){mSaveContext=s;}
};
int main(){
 SaveContext original{},live{},nestedSave{};
 for(int bits=0;bits<32;++bits){
  TestLogic logic{&original,bool(bits&1),bool(bits&2),bool(bits&4),bool(bits&8),bool(bits&16)};
  const TestLogic before=logic;
  try {
   SohExtreme::ScopedCheckFinderLogic<TestLogic,SaveContext> scope(logic,live);
   check(logic.mSaveContext==&live&&logic.CalculatingAvailableChecks,"enters live inventory mode");
   // These are the production search's entry/exit operations; keep the mode
   // until AP enemy and speech rows finish, not just until native search returns.
   bool previous=logic.CalculatingAvailableChecks;
   logic.CalculatingAvailableChecks=false;logic.CalculatingAvailableChecks=true;
   logic.CalculatingAvailableChecks=previous;
   check(logic.CalculatingAvailableChecks,"native search leaves synthetic checks live");
   {
    SohExtreme::ScopedCheckFinderLogic<TestLogic,SaveContext> nested(logic,nestedSave);
    logic.IsAdult=true;logic.IsChild=false;
   }
   check(logic.mSaveContext==&live&&logic.CalculatingAvailableChecks,"nested scope restores outer mode");
   logic.CurrentRegionKey=RR_NONE;logic.CurrentCheckKey=RC_UNKNOWN_CHECK;
   logic.IsChild=!before.IsChild;logic.IsAdult=!before.IsAdult;logic.AtDay=!before.AtDay;logic.AtNight=!before.AtNight;
   throw std::runtime_error("test unwind");
  }catch(const std::runtime_error&){}
  check(logic.mSaveContext==before.mSaveContext&&logic.CalculatingAvailableChecks==before.CalculatingAvailableChecks&&
        logic.IsChild==before.IsChild&&logic.IsAdult==before.IsAdult&&logic.AtDay==before.AtDay&&logic.AtNight==before.AtNight&&logic.CurrentRegionKey==before.CurrentRegionKey&&logic.CurrentCheckKey==before.CurrentCheckKey,"scope restores caller after exception");
 }
 SohExtreme::CheckFinderStateSnapshot snapshot;
 snapshot.BeginSample();snapshot.Observe(-1);snapshot.Observe(true);check(snapshot.EndSample(),"first snapshot");
 snapshot.BeginSample();snapshot.Observe(-1);snapshot.Observe(true);check(!snapshot.EndSample(),"identical signed snapshot");
 snapshot.BeginSample();snapshot.Observe(0);snapshot.Observe(true);check(snapshot.EndSample(),"changed snapshot");
 snapshot.BeginSample();snapshot.Observe(0);check(snapshot.EndSample(),"removed field changes");
 snapshot.Reset();snapshot.BeginSample();check(snapshot.EndSample(),"reset snapshot changes");
 return finish();
}
