#pragma once
#include <algorithm>
#include <array>
#include <atomic>
#include <cassert>
#include <cstdarg>
#include <cstdint>
#include <cmath>
#include <functional>
#include <iostream>
#include <map>
#include <memory>
#include <mutex>
#include <set>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>
#include "OptionValue.h"
#include "SettingEnum.h"
#include "EntranceEnum.h"
#include "enhancementTypes.h"
#include "ArchipelagoC.h"
#include "ShipInit.hpp"

using s16 = int16_t;
constexpr int QUEST_RANDOMIZER = 1;
constexpr int ITEM_STICK=0, ITEM_NUT=1, ITEM_SLINGSHOT=2, ITEM_BOW=3, ITEM_BOMB=4, ITEM_BOMBCHU=5;
constexpr int ITEM_FISHING_POLE=6, COUNT_ICE_TRAPS=0, MOD_RANDOMIZER=1, RG_ICE_TRAP=11;
constexpr int ACTOR_EN_BOM=16;
constexpr int NA_SE_VO_KZ_MOVE=1, NA_SE_EN_GANON_LAUGH=2, NA_SE_VO_FR_SMILE_0=3;
struct GetItemEntry { int drawItemId=0; };
struct Player { GetItemEntry getItemEntry; };
struct PlayState { int sceneNum=1; };
struct SaveContext {
    struct { struct { int id=QUEST_RANDOMIZER; } quest;
        int pendingIceTrapCount=0;
        struct { int count[1]{}; uint64_t fileCreatedAt=42; } stats;
    } ship;
    struct { int buttonItems[4]{}; } equips;
};
inline SaveContext gSaveContext;
inline PlayState testPlay;
extern "C" { inline PlayState* gPlayState=&testPlay; }
inline Player testPlayer;
#define GET_PLAYER(play) (&testPlayer)
#define IS_RANDO (gSaveContext.ship.quest.id == QUEST_RANDOMIZER)
inline std::array<int8_t,8> ammo{};
#define AMMO(item) (ammo[(item)])
inline int gSfxDefaultPos=0, gSfxDefaultReverb=0;
inline float gSfxDefaultFreqAndVolScale=1;
inline void Audio_PlaySfxGeneral(int,void*,int,void*,void*,void*) {}
inline std::unordered_map<std::string,int> cvars, savedCvars;
inline int guiSaves=0, cvarWrites=0;
#define CVAR_ENHANCEMENT(key) "gEnhancements." key
#define CVAR_RANDOMIZER_SETTING(key) "gRandomizer." key
#define CVAR_TRACKER_CHECK(key) "gTrackers.CheckTracker." key
inline int CVarGetInteger(const char* key,int fallback) {
    auto it=cvars.find(key);return it==cvars.end()?fallback:it->second;
}
inline void CVarSetInteger(const char* key,int value) { cvars[key]=value; ++cvarWrites; }
inline void CVarSetString(const char*,const char*) {}
inline bool isApSave=false;
extern "C" inline bool Archipelago_IsCurrentSaveFile(void) { return isApSave; }

namespace Rando {
struct Context {
    std::array<OptionValue,RSK_MAX> options{};
    static std::shared_ptr<Context> instance;
    static std::shared_ptr<Context> GetInstance() { return instance; }
    OptionValue& GetOption(RandomizerSettingKey k) { return options[k]; }
    void ResetTrickOptions() {}
    uint32_t GetSeed() { return 42; }
};
inline std::shared_ptr<Context> Context::instance=std::make_shared<Context>();
struct TestOption {
    std::string cvar;
    RandomizerSettingKey key;
    const std::string& GetCVarName() const { return cvar; }
};
struct Settings {
    std::vector<TestOption> options={
      {CVAR_RANDOMIZER_SETTING("ExtremeTrapPool"),RSK_EXTREME_TRAP_POOL},
      {CVAR_RANDOMIZER_SETTING("ExtremeIceTraps"),RSK_EXTREME_ICE_TRAPS},
      {CVAR_RANDOMIZER_SETTING("ExtremeFireTraps"),RSK_EXTREME_FIRE_TRAPS},
      {CVAR_RANDOMIZER_SETTING("ExtremeSlowTraps"),RSK_EXTREME_SLOW_TRAPS},
      {CVAR_RANDOMIZER_SETTING("ExtremeMagicSuckTraps"),RSK_EXTREME_MAGIC_SUCK_TRAPS},
      {CVAR_RANDOMIZER_SETTING("ExtremeHealthDrainTraps"),RSK_EXTREME_HEALTH_DRAIN_TRAPS},
      {CVAR_RANDOMIZER_SETTING("ShufflePots"),RSK_SHUFFLE_POTS}
    };
    static Settings* GetInstance() { static Settings obj; return &obj; }
    const std::vector<TestOption>& GetAllOptions() { return options; }
    void UpdateAllOptions() {}
    void SetAllToContext() {
        for(const auto& o:options) Context::instance->GetOption(o.key).Set(static_cast<uint8_t>(CVarGetInteger(o.cvar.c_str(),0)));
    }
};
}
#define RAND_GET_OPTION(key) Rando::Context::GetInstance()->GetOption(key)
inline void RefreshArchipelagoRandomizerHooks() {}
namespace CheckTracker { inline void RecalculateAvailableChecks() {} }
namespace Ship {
struct TestGui { void SaveConsoleVariablesNextFrame() { ++guiSaves; savedCvars=cvars; } };
struct TestWindow { TestGui gui; TestGui* GetGui() { return &gui; } };
struct Context {
    TestWindow window;
    static Context* GetRawInstance() { static Context c;return &c; }
    TestWindow* GetWindow() { return &window; }
};
}
#define SPDLOG_INFO(...) do {} while(0)
#define SPDLOG_ERROR(...) do {} while(0)
struct ArchipelagoClient {
    std::atomic<bool> slotSettingsPendingApply{true};
    std::mutex queueMutex;
    bool slotSettingsLoaded=true;
    std::unordered_map<std::string,int> slotSettings;
    void ApplySlotSettings();
};
struct BeforeClient : ArchipelagoClient { void ApplySlotSettings(); };

inline std::map<std::string,int> actions;
inline EntranceIndex lastTeleport=ENTR_MAX;
inline void Play_TriggerRespawn(PlayState*) { ++actions["void"]; }
namespace Notification {
struct Options { std::string message; };
inline void Emit(Options) { ++actions["notification"]; }
}
inline size_t forcedRandom=0;
namespace ShipUtils {
inline void RandInit(uint64_t seed,uint64_t* state) { *state=seed; }
template<class T> T RandomElement(const std::vector<T>& values,uint64_t*) { return values.at(forcedRandom%values.size()); }
}
enum GIVanillaBehavior { VB_SHORT_CIRCUIT_GIVE_ITEM_PROCESS };
using HOOK_ID=uint32_t;
class GameInteractor {
 public:
    static GameInteractor* Instance;
    struct State { inline static float MovementSpeedMultiplier=1.0f; };
    struct RawAction {
        static void FreezePlayer() { ++actions["freeze"]; }
        static void BurnPlayer() { ++actions["burn"]; }
        static void ElectrocutePlayer() { ++actions["shock"]; }
        static void SetPlayerHealth(int) { ++actions["kill"]; }
        static void AddOrRemoveMagic(int) { ++actions["magic"]; }
        static void HealOrDamagePlayer(int) { ++actions["health"]; }
        static void KnockbackPlayer(int) { ++actions["knock"]; }
        static void SpawnActor(int,int) { ++actions["bomb"]; }
        static void TeleportPlayer(EntranceIndex i) { ++actions["teleport"]; lastTeleport=i; }
    };
    struct OnPlayerUpdate { using Fn=std::function<void()>; };
    struct OnLoadGame { using Fn=std::function<void(int32_t)>; };
    struct OnExitGame { using Fn=std::function<void(int32_t)>; };
    struct OnVanillaBehavior { using Fn=std::function<void(GIVanillaBehavior,bool*,va_list)>; };
    template<class H> static std::map<HOOK_ID,typename H::Fn>& Hooks() { static std::map<HOOK_ID,typename H::Fn> m; return m; }
    template<class H> void UnregisterGameHook(HOOK_ID id) { Hooks<H>().erase(id); }
    template<class H,class F> HOOK_ID RegisterGameHook(F fn) { static HOOK_ID next=1; HOOK_ID id=next++;Hooks<H>()[id]=fn;return id; }
    template<class H> void UnregisterGameHookForID(HOOK_ID id) { UnregisterGameHook<H>(id); }
    template<class H,class F> HOOK_ID RegisterGameHookForID(GIVanillaBehavior,F fn) { return RegisterGameHook<H>(fn); }
    template<class H,class... A> static void Dispatch(A... args) { for(auto entry:Hooks<H>()) entry.second(args...); }
};
inline GameInteractor instance;
inline GameInteractor* GameInteractor::Instance=&instance;
#include "ProductionHookMacros.h"
extern "C" inline GetItemEntry ItemTable_RetrieveEntry(s16,s16) { return {}; }
inline void GameInteractor_ExecuteOnItemReceiveHooks(GetItemEntry) { ++actions["receipt"]; }
inline bool DeliverTrap() {
    auto invoke=[](bool* flag,...) {
        va_list args;va_start(args,flag);
        GameInteractor::Dispatch<GameInteractor::OnVanillaBehavior>(VB_SHORT_CIRCUIT_GIVE_ITEM_PROCESS,flag,args);
        va_end(args);
    };
    bool handled=false;invoke(&handled);return handled;
}

// Controlled menu builder: record the actual labels, bindings and PreFuncs.
enum WidgetType { WIDGET_TEXT,WIDGET_CVAR_CHECKBOX,WIDGET_SEPARATOR_TEXT,WIDGET_CVAR_COMBOBOX };
struct WidgetInfo {
    std::string name, cvar;
    WidgetType type;
    bool isHidden=false;
    std::function<void(WidgetInfo&)> pre;
    WidgetInfo& CVar(const char* value) { cvar=value;return *this; }
    template<class F> WidgetInfo& PreFunc(F f) { pre=f;return *this; }
    template<class T> WidgetInfo& Options(const T&) { return *this; }
};
struct CheckboxOptions { CheckboxOptions& Tooltip(const char*) { return *this; } };
struct ComboboxOptions {
    template<class T> ComboboxOptions& ComboMap(const T&) { return *this; }
    ComboboxOptions& DefaultIndex(int) { return *this; }
    ComboboxOptions& Tooltip(const char*) { return *this; }
};
inline std::vector<WidgetInfo> menu;
inline int path=0;
inline std::map<int,const char*> teleportTrapModes;
inline WidgetInfo& AddWidget(int,const char* name,WidgetType type) { menu.push_back({name,"",type});return menu.back(); }
