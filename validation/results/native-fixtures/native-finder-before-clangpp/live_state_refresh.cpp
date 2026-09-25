
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
SaveContext gSaveContext{};
static PlayState play{};
PlayState* gPlayState = &play;
static bool loaded=true, enabled=true;
#ifndef CVAR_PREFIX_TRACKER
#define CVAR_PREFIX_TRACKER "gTrackers"
#endif
uint8_t gItemSlots[256]{};
class GameInteractor { public: static bool IsSaveLoaded() {return loaded;} };
static int CVarGetInteger(const char*,int) {return enabled;}
static int requests=0;
static void RecalculateAvailableChecks(){++requests;}
static SohExtreme::CheckFinderStateSnapshot lastFinderState;

static void ResetLiveFinderStateSnapshot() {
    lastFinderState.Reset();
}

void CheckTrackerLiveLogicStateUpdate() {
    if (!GameInteractor::IsSaveLoaded() || gPlayState == nullptr || !IS_RANDO ||
        !CVarGetInteger(CVAR_TRACKER_CHECK("EnableAvailableChecks"), 0)) {
        ResetLiveFinderStateSnapshot();
        return;
    }

    auto& state = lastFinderState;
    state.BeginSample();
    state.Observe(gSaveContext.fileNum);
    state.Observe(gSaveContext.ship.quest.id);
    state.Observe(gSaveContext.linkAge);
    state.Observe(IS_DAY != 0);
    state.Observe(gSaveContext.nightFlag);
    state.Observe(gPlayState->sceneNum);
    state.Observe(gPlayState->roomCtx.curRoom.num);

    const auto& inventory = gSaveContext.inventory;
    state.ObserveArray(inventory.items);
    state.ObserveArray(inventory.ammo);
    state.Observe(inventory.equipment);
    state.Observe(inventory.upgrades);
    state.Observe(inventory.questItems);
    state.ObserveArray(inventory.dungeonItems);
    state.ObserveArray(inventory.dungeonKeys);
    state.Observe(inventory.gsTokens);
    state.ObserveArray(gSaveContext.ship.stats.dungeonKeys);
    state.ObserveArray(gSaveContext.ship.randomizerInf);
    state.Observe(gSaveContext.healthCapacity);
    state.Observe(gSaveContext.magicLevel);
    state.Observe(gSaveContext.isMagicAcquired);
    state.Observe(gSaveContext.isDoubleMagicAcquired);
    state.Observe(gSaveContext.isDoubleDefenseAcquired);
    state.Observe(gSaveContext.bgsFlag);
    state.Observe(gSaveContext.scarecrowLongSongSet);
    state.Observe(gSaveContext.scarecrowSpawnSongSet);
    state.ObserveArray(gSaveContext.eventChkInf);
    state.ObserveArray(gSaveContext.itemGetInf);
    state.ObserveArray(gSaveContext.infTable);
    state.ObserveArray(gSaveContext.gsFlags);
    state.ObserveArray(gSaveContext.highScores);

    // Room counters and bean/puzzle switches are not inventory items. Observe
    // both saved scenes and the live scene; neither guarantees an item callback.
    for (const auto& flags : gSaveContext.sceneFlags) {
        state.Observe(flags.chest);
        state.Observe(flags.swch);
        state.Observe(flags.clear);
        state.Observe(flags.collect);
    }
    state.Observe(gPlayState->actorCtx.flags.swch);
    state.Observe(gPlayState->actorCtx.flags.tempSwch);
    state.Observe(gPlayState->actorCtx.flags.clear);
    state.Observe(gPlayState->actorCtx.flags.tempClear);
    state.Observe(gPlayState->actorCtx.flags.collect);
    state.Observe(gPlayState->actorCtx.flags.tempCollect);

    const auto& rando = gSaveContext.ship.quest.data.randomizer;
    state.Observe(rando.triforcePiecesCollected);
    state.Observe(rando.bombchuUpgradeLevel);
    state.Observe(rando.silverShadowBlades);
    state.Observe(rando.silverShadowPit);
    state.Observe(rando.silverShadowSpikes);
    state.Observe(rando.silverSpiritChild);
    state.Observe(rando.silverSpiritSun);
    state.Observe(rando.silverSpiritBoulders);
    state.Observe(rando.silverBotw);
    state.Observe(rando.silverIceCavernBlades);
    state.Observe(rando.silverIceCavernBlock);
    state.Observe(rando.silverGtgSlope);
    state.Observe(rando.silverGtgLava);
    state.Observe(rando.silverGtgWater);
    state.Observe(rando.silverGanonLight);
    state.Observe(rando.silverGanonForest);
    state.Observe(rando.silverGanonFire);
    state.Observe(rando.silverGanonSpirit);
    state.Observe(rando.silverMqDodongosCavern);
    state.Observe(rando.silverMqShadowInvisibleBlades);
    state.Observe(rando.silverMqSpiritLobby);
    state.Observe(rando.silverMqSpiritBigWall);
    state.Observe(rando.silverMqGanonWater);
    state.Observe(rando.silverMqGanonShadow);

    // Read the active seed Context, not randomizer-menu CVars. AP slot data
    // remains authoritative. OptionValue intentionally needs an explicit .Get().
    const auto& ctx = Rando::Context::GetInstance();
    for (int key = RSK_NONE + 1; key < RSK_MAX; ++key) {
        state.Observe(ctx->GetOption(static_cast<RandomizerSettingKey>(key)).Get());
    }

    for (int trick = 0; trick < RT_MAX; ++trick) {
        state.Observe(ctx->GetTrickOption(static_cast<RandomizerTrick>(trick)).Get());
    }

    if (state.EndSample()) {
        // This only queues one deferred pass. Multiple changes in a frame do
        // not run multiple searches, save files, or perform AP/network work.
        RecalculateAvailableChecks();
    }
}
static void refreshExpected(bool changed, const char* label) {
    int before=requests; CheckTrackerLiveLogicStateUpdate(); check((requests!=before)==changed,label);
    before=requests; CheckTrackerLiveLogicStateUpdate(); check(requests==before,"unchanged repeated sample");
}
int main(){
    gItemSlots[ITEM_BOMBCHU]=SLOT_BOMBCHU;gItemSlots[ITEM_BEAN]=SLOT_BEAN;
    gSaveContext.ship.quest.id=QUEST_RANDOMIZER;
    ResetLiveFinderStateSnapshot();refreshExpected(true,"initial live sample schedules");
    for (int i=0;i<5;++i) refreshExpected(false,"stable frame");
    const int abilityFlags[] = {RAND_INF_CAN_CLIMB,RAND_INF_CAN_GRAB,RAND_INF_CAN_SWIM};
    for(const int flag:abilityFlags){
        gSaveContext.ship.randomizerInf[flag>>4]^=uint16_t(1u<<(flag&15));refreshExpected(true,"grant ability without receive callback");
        gSaveContext.ship.randomizerInf[flag>>4]^=uint16_t(1u<<(flag&15));refreshExpected(true,"remove ability without receive callback");
    }
    // All flag words use the same typed comparison, including individual souls,
    // Flow of Time, shuffled songs, and collected AP/native checks.
    for(size_t i=0;i<sizeof(gSaveContext.ship.randomizerInf)/sizeof(gSaveContext.ship.randomizerInf[0]);++i){
        gSaveContext.ship.randomizerInf[i]^=uint16_t(0x8001u);refreshExpected(true,"rando flag word changed");
    }
    gSaveContext.inventory.items[SLOT_HOOKSHOT]=ITEM_LONGSHOT;refreshExpected(true,"equipment gained");
    gSaveContext.inventory.items[SLOT_HOOKSHOT]=ITEM_NONE;refreshExpected(true,"equipment lost");
    gSaveContext.inventory.upgrades ^= 1;refreshExpected(true,"progressive level changed");
    gSaveContext.inventory.equipment ^= 1;refreshExpected(true,"sword/shield changed");
    gSaveContext.inventory.questItems ^= 1;refreshExpected(true,"song/medallion changed");
    gSaveContext.inventory.dungeonKeys[3]++;refreshExpected(true,"spendable dungeon key changed");
    gSaveContext.ship.stats.dungeonKeys[3]++;refreshExpected(true,"total dungeon key changed");
    gSaveContext.inventory.dungeonItems[3] ^=1;refreshExpected(true,"dungeon boss key changed");
    gSaveContext.ship.quest.data.randomizer.silverGanonSpirit++;refreshExpected(true,"silver rupee room count changed");
    gSaveContext.ship.quest.data.randomizer.bombchuUpgradeLevel++;refreshExpected(true,"bombchu bag changed");
    gSaveContext.inventory.ammo[SLOT_BOMBCHU]++;refreshExpected(true,"bombchu refill");
    gSaveContext.inventory.ammo[SLOT_BOMBCHU]--;refreshExpected(true,"last bombchu consumed");
    gSaveContext.inventory.ammo[SLOT_BEAN]++;refreshExpected(true,"bean ammo changed");
    gSaveContext.healthCapacity+=FULL_HEART_HEALTH;refreshExpected(true,"heart capacity changed");
    gSaveContext.isMagicAcquired=1;refreshExpected(true,"magic acquired");
    gSaveContext.eventChkInf[0]^=1;refreshExpected(true,"quest event changed");
    gSaveContext.sceneFlags[SCENE_GERUDO_VALLEY].swch^=1;refreshExpected(true,"saved bean puzzle changed");
    play.actorCtx.flags.swch^=1;refreshExpected(true,"live room switch changed");
    play.actorCtx.flags.tempClear^=1;refreshExpected(true,"live room clear changed");
    gSaveContext.linkAge^=1;refreshExpected(true,"age changed");
    gSaveContext.nightFlag^=1;refreshExpected(true,"day/night changed");
    gSaveContext.dayTime++;gSaveContext.health++;gSaveContext.magic++;refreshExpected(false,"clock/health animation does not force searches");
    play.sceneNum++;refreshExpected(true,"scene changed");
    play.roomCtx.curRoom.num++;refreshExpected(true,"room changed");
    Rando::Context::GetInstance()->GetOption(RSK_SHUFFLE_CLIMB).Set(1);refreshExpected(true,"active seed option changed");
    enabled=false;refreshExpected(false,"disabled tracker dormant");
    enabled=true;refreshExpected(true,"reenabled tracker refreshes");
    loaded=false;refreshExpected(false,"unloaded safe");loaded=true;refreshExpected(true,"reload refreshes");
    gPlayState=nullptr;refreshExpected(false,"no play state safe");gPlayState=&play;refreshExpected(true,"restored play state refreshes");
    return finish();
}
