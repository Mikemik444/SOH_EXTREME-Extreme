#pragma once

#include <cstddef>
#include <cstdint>
#include <type_traits>
#include <utility>
#include <vector>

namespace SohExtreme {

// Compare the actual discrete inputs used by live logic. No byte/padding hashes,
// and no raw clock/animation counters that would force a search every frame.
// Storage is reused after the first sample; a search is requested only on change.
class CheckFinderStateSnapshot {
  public:
    void Reset() {
        initialized = false;
        cursor = 0;
        changed = false;
        values.clear();
    }

    void BeginSample() {
        cursor = 0;
        changed = !initialized;
    }

    template <typename T> void Observe(T value) {
        static_assert(std::is_integral_v<T> || std::is_enum_v<T>,
                      "Check Finder observes discrete logic inputs only");
        const auto current = static_cast<uint64_t>(value);
        if (cursor == values.size()) {
            values.push_back(current);
            changed = true;
        } else if (values[cursor] != current) {
            values[cursor] = current;
            changed = true;
        }
        ++cursor;
    }

    template <typename T, size_t N> void ObserveArray(const T (&array)[N]) {
        for (const auto value : array) {
            Observe(value);
        }
    }

    bool EndSample() {
        if (cursor != values.size()) {
            values.resize(cursor);
            changed = true;
        }
        initialized = true;
        return changed;
    }

  private:
    std::vector<uint64_t> values;
    size_t cursor = 0;
    bool initialized = false;
    bool changed = false;
};

// Keep native and synthetic AP checks in the SAME live-inventory mode. The
// nested ReachabilitySearch restores the flag it found on entry; it must restore
// true until speech/enemy rows have also finished evaluating. Never leave that
// mode, a borrowed SaveContext, or a tested age/time installed after this pass.
template <typename LogicType, typename SaveContextType> class ScopedCheckFinderLogic {
  public:
    ScopedCheckFinderLogic(LogicType& target, SaveContextType& liveSave)
        : logic(target), previousSave(target.mSaveContext),
          previousMode(target.CalculatingAvailableChecks),
          previousChild(target.IsChild), previousAdult(target.IsAdult),
          previousDay(target.AtDay), previousNight(target.AtNight),
          previousRegion(target.CurrentRegionKey), previousCheck(target.CurrentCheckKey) {
        logic.SetSaveContext(&liveSave);
        logic.CalculatingAvailableChecks = true;
    }

    ~ScopedCheckFinderLogic() {
        logic.SetSaveContext(previousSave);
        logic.CalculatingAvailableChecks = previousMode;
        logic.IsChild = previousChild;
        logic.IsAdult = previousAdult;
        logic.AtDay = previousDay;
        logic.AtNight = previousNight;
        logic.CurrentRegionKey = previousRegion;
        logic.CurrentCheckKey = previousCheck;
    }

    ScopedCheckFinderLogic(const ScopedCheckFinderLogic&) = delete;
    ScopedCheckFinderLogic& operator=(const ScopedCheckFinderLogic&) = delete;

  private:
    LogicType& logic;
    SaveContextType* previousSave;
    bool previousMode;
    bool previousChild;
    bool previousAdult;
    bool previousDay;
    bool previousNight;
    decltype(std::declval<LogicType&>().CurrentRegionKey) previousRegion;
    decltype(std::declval<LogicType&>().CurrentCheckKey) previousCheck;
};

} // namespace SohExtreme
