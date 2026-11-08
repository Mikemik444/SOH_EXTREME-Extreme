from pathlib import Path
r=Path(__file__).resolve().parent
P=lambda p:r/p

def once(file,old,new):
    file=P(file)
    s=file.read_text(encoding='utf-8')
    if s.count(old)!=1:
        raise AssertionError(f'{file}: expected 1 match got {s.count(old)} for {old[:140]!r}')
    file.write_text(s.replace(old,new),encoding='utf-8')

MAIN='archipelago/soh_extreme/__init__.py'
HELP='archipelago/soh_extreme/_vendor_oot_soh/LogicHelpers.py'
NATIVE='soh/Network/Archipelago/ArchipelagoClient.cpp'
LOGIC='soh/Enhancements/randomizer/logic.cpp'
FLAGS='soh/Enhancements/randomizer/randomizerEnums/RandomizerInf.h'
CHEAT='soh/Enhancements/Cheats/TimelessEquipment.cpp'
ENEMY='archipelago/soh_extreme/EnemyDropRules.py'

once(MAIN, '    "Big Octo Soul": 9500185,\n', '''    "Big Octo Soul": 9500185,
    # Permanent, direction-specific cross-age equipment unlocks. These are
    # distinct progression items, not changes to Link's actual age.
    "Child Can Use Adult Items": 9500400,
    "Adult Can Use Child Items": 9500401,
''')
once(MAIN, '"Extreme Abilities": {"Roll", "Grab / Power Bracelet", "Climb", "Crawl", "Speak", "Open Chest", "Shovel", "Flow of Time"},',
    '"Extreme Abilities": {"Roll", "Grab / Power Bracelet", "Climb", "Crawl", "Speak", "Open Chest", "Shovel", "Flow of Time", "Child Can Use Adult Items", "Adult Can Use Child Items"},')
once(MAIN,'        extras: list[str] = []\n        o = self.options\n', '''        # Always place one of each age-equipment unlock in new seeds. The
        # existing overflow replacer removes filler, never advancement items.
        # Keep them independent; obtaining one must not grant the other.
        extras: list[str] = ["Child Can Use Adult Items", "Adult Can Use Child Items"]
        o = self.options
''')

once(HELP, '        if data[item].adult_only:\n            rule &= is_adult(bundle)\n\n        if data[item].child_only:\n            rule &= is_child(bundle)\n', '''        if data[item].adult_only:
            # Equipping adult equipment as Child requires the AP unlock.
            # This does NOT replace age checks on physical doors, events, etc.
            rule &= is_adult(bundle) | Has("Child Can Use Adult Items")

        if data[item].child_only:
            rule &= is_child(bundle) | Has("Adult Can Use Child Items")
''')

# Native enum append only: shifting existing persisted flags corrupts saves.
once(FLAGS, 'RANDO_ENUM_ITEM(RAND_INF_KAK_ADULT_TREE)\n\nRANDO_ENUM_ITEM(RAND_INF_MAX)', '''RANDO_ENUM_ITEM(RAND_INF_KAK_ADULT_TREE)

// Appended only; preserve every older save bit index.
RANDO_ENUM_ITEM(RAND_INF_CHILD_CAN_USE_ADULT_ITEMS)
RANDO_ENUM_ITEM(RAND_INF_ADULT_CAN_USE_CHILD_ITEMS)

RANDO_ENUM_ITEM(RAND_INF_MAX)''')

once(CHEAT, '''#include "soh/Enhancements/game-interactor/GameInteractor.h"
#include "soh/ShipInit.hpp"
#include "soh/cvar_prefixes.h"

#define CVAR_TIMELESS_EQUIPMENT_NAME CVAR_CHEAT("TimelessEquipment")

static void RegisterTimelessEquipment() {
    bool timelessEquipment = CVarGetInteger(CVAR_TIMELESS_EQUIPMENT_NAME, 0);

    COND_VB_SHOULD(VB_PLAYER_MEETS_AGE_REQ, timelessEquipment, { *should = true; });
    COND_VB_SHOULD(VB_ITEM_MEETS_AGE_REQ, timelessEquipment, { *should = true; });
    COND_VB_SHOULD(VB_SLOT_MEETS_AGE_REQ, timelessEquipment, { *should = true; });
}

static RegisterShipInitFunc initFunc(RegisterTimelessEquipment, { CVAR_TIMELESS_EQUIPMENT_NAME });
''', '''#include "soh/Enhancements/game-interactor/GameInteractor.h"
#include "soh/ShipInit.hpp"
#include "soh/cvar_prefixes.h"

extern "C" {
#include "z64save.h"
#include "variables.h"
#include "macros.h"
extern SaveContext gSaveContext;
extern s32 Flags_GetRandomizerInf(RandomizerInf flag);
}

#define CVAR_TIMELESS_EQUIPMENT_NAME CVAR_CHEAT("TimelessEquipment")

static bool CrossAgeEquipmentEnabledForCurrentAge() {
    // Do not grant cross-age permissions on the title screen, on another
    // game mode or on a file that has not received the AP progression item.
    if (!GameInteractor::IsSaveLoaded(true) || !IS_RANDO) return false;
    return LINK_IS_ADULT
        ? Flags_GetRandomizerInf(RAND_INF_ADULT_CAN_USE_CHILD_ITEMS) != 0
        : Flags_GetRandomizerInf(RAND_INF_CHILD_CAN_USE_ADULT_ITEMS) != 0;
}

static void RegisterTimelessEquipment() {
    // Register once regardless of AP inventory. The flags may change at any
    // frame after a received item; registration-time snapshots go stale.
    COND_VB_SHOULD(VB_PLAYER_MEETS_AGE_REQ, true, {
        if (CVarGetInteger(CVAR_TIMELESS_EQUIPMENT_NAME, 0) || CrossAgeEquipmentEnabledForCurrentAge())
            *should = true;
    });
    COND_VB_SHOULD(VB_ITEM_MEETS_AGE_REQ, true, {
        if (CVarGetInteger(CVAR_TIMELESS_EQUIPMENT_NAME, 0) || CrossAgeEquipmentEnabledForCurrentAge())
            *should = true;
    });
    COND_VB_SHOULD(VB_SLOT_MEETS_AGE_REQ, true, {
        if (CVarGetInteger(CVAR_TIMELESS_EQUIPMENT_NAME, 0) || CrossAgeEquipmentEnabledForCurrentAge())
            *should = true;
    });
}

static RegisterShipInitFunc initFunc(RegisterTimelessEquipment, { CVAR_TIMELESS_EQUIPMENT_NAME });
''')

once(LOGIC, 'bool Logic::CanUse(RandomizerGet itemName) {\n    if (!HasItem(itemName))', '''bool Logic::CanUse(RandomizerGet itemName) {
    const bool mayUseAdultEquipment = IsAdult || CheckRandoInf(RAND_INF_CHILD_CAN_USE_ADULT_ITEMS);
    const bool mayUseChildEquipment = IsChild || CheckRandoInf(RAND_INF_ADULT_CAN_USE_CHILD_ITEMS);
    if (!HasItem(itemName))''')
# Scope the flag to actual age; IsAdult or IsChild are mutually exclusive by the logic evaluator.
# Every distinct age-only item case is replaced, while physical age-only events
# are deliberately untouched.
start=(P(LOGIC)).read_text(); a=start.index('bool Logic::CanUse(RandomizerGet itemName) {'); b=start.index('\n//',a+2000) if False else start.index('\nbool Logic::HasProjectile',a)
area=start[a:b]
area_new=area
area_new=area_new.replace('return IsAdult; // ||', 'return mayUseAdultEquipment; // ||')
area_new=area_new.replace('return IsChild; // ||', 'return mayUseChildEquipment; // ||')
area_new=area_new.replace('return IsAdult && HasItem(RG_BRONZE_SCALE);', 'return mayUseAdultEquipment && HasItem(RG_BRONZE_SCALE);')
area_new=area_new.replace('            return IsAdult;\n', '            return mayUseAdultEquipment;\n')
area_new=area_new.replace('            return IsChild;\n', '            return mayUseChildEquipment;\n')
area_new=area_new.replace('return IsChild /* || StickAsAdult;*/ &&', 'return mayUseChildEquipment /* || StickAsAdult;*/ &&')
area_new=area_new.replace('return IsChild || ctx->GetOption(RSK_MASKS_AS_ADULT);', 'return mayUseChildEquipment || ctx->GetOption(RSK_MASKS_AS_ADULT);')
assert area_new!=area and 'return IsAdult;' not in area_new[:area_new.index('        // Songs')], 'Native adult equipment not updated'
assert 'return IsChild;' not in area_new[:area_new.index('        // Songs')], 'Native child equipment not updated'
assert 'return mayUseAdultEquipment;' in area_new and 'return mayUseChildEquipment;' in area_new
P(LOGIC).write_text(start[:a]+area_new+start[b:])

once(NATIVE,'constexpr int64_t AP_ITEM_FLOW_OF_TIME = 9500019;', '''constexpr int64_t AP_ITEM_FLOW_OF_TIME = 9500019;
constexpr int64_t AP_ITEM_CHILD_CAN_USE_ADULT_ITEMS = 9500400;
constexpr int64_t AP_ITEM_ADULT_CAN_USE_CHILD_ITEMS = 9500401;''')
once(NATIVE, '        case AP_ITEM_FLOW_OF_TIME: return "Flow of Time";', '''        case AP_ITEM_FLOW_OF_TIME: return "Flow of Time";
        case AP_ITEM_CHILD_CAN_USE_ADULT_ITEMS: return "Child Can Use Adult Items";
        case AP_ITEM_ADULT_CAN_USE_CHILD_ITEMS: return "Adult Can Use Child Items";''')
once(NATIVE, '        case AP_ITEM_FLOW_OF_TIME: Flags_SetRandomizerInf(RAND_INF_FLOW_OF_TIME); return true;', '''        case AP_ITEM_FLOW_OF_TIME: Flags_SetRandomizerInf(RAND_INF_FLOW_OF_TIME); return true;
        case AP_ITEM_CHILD_CAN_USE_ADULT_ITEMS:
            Flags_SetRandomizerInf(RAND_INF_CHILD_CAN_USE_ADULT_ITEMS); return true;
        case AP_ITEM_ADULT_CAN_USE_CHILD_ITEMS:
            Flags_SetRandomizerInf(RAND_INF_ADULT_CAN_USE_CHILD_ITEMS); return true;''')
# A user-received custom item is a persistent ability rather than a native
# get-item entry. Grant exactly once on the gameplay thread; no unrelated
# RandomizerGet is awarded or held in Link's hand.
once(NATIVE,'''    const bool historicalNewSaveReplay =
        gNewSaveReplayTargetCount != 0 && sequence < gNewSaveReplayTargetCount;

    RandomizerGet randoGet = RG_NONE;''', '''    const bool historicalNewSaveReplay =
        gNewSaveReplayTargetCount != 0 && sequence < gNewSaveReplayTargetCount;

    if (itemId == AP_ITEM_CHILD_CAN_USE_ADULT_ITEMS ||
        itemId == AP_ITEM_ADULT_CAN_USE_CHILD_ITEMS) {
        // Apply to the *loaded* save, never as a CVar/shared cheat. Historical
        // ReceivedItems replay follows this same path and is silent.
        if (!ApplyExtremePersistentApItem(itemId)) return false;
        if (!historicalNewSaveReplay) {
            Notification::Emit({ .prefix = "Archipelago", .message = "received",
                                 .suffix = GetApItemDisplayName(itemId), .remainingTime = 4.0f });
            CheckTracker::RecalculateAvailableChecks();
        }
        return true;
    }

    RandomizerGet randoGet = RG_NONE;''')
# Remote location preview and item inspection should recognize these IDs, but
# returning RG_NONE prevents us from falsely displaying another native item.
once(NATIVE,'    switch (itemId) {\n        case AP_ITEM_ROLL: randoGet = RG_ROLL; break;', '''    switch (itemId) {
        case AP_ITEM_CHILD_CAN_USE_ADULT_ITEMS:
        case AP_ITEM_ADULT_CAN_USE_CHILD_ITEMS:
            return static_cast<int32_t>(RG_AP_REMOTE_IMPORTANT);
        case AP_ITEM_ROLL: randoGet = RG_ROLL; break;''')

# Combat rules: cross-age permission changes which real weapons Link can use,
# but does not turn Child into Adult for physical height/actor age checks.
once(ENEMY, '''        sword = (can_use(Items.MASTER_SWORD, b) | can_use(Items.BIGGORONS_SWORD, b)) if adult else can_use(Items.KOKIRI_SWORD, b)
        melee = sword | (can_use(Items.MEGATON_HAMMER, b) if adult else can_use(Items.STICKS, b))
        sticks = can_use(Items.STICKS, b) if not adult else False_()
        hammer = can_use(Items.MEGATON_HAMMER, b) if adult else False_()
        sling = can_use(Items.FAIRY_SLINGSHOT, b) if not adult else False_()
        nuts = can_use(Items.NUTS, b)
        bow = can_use(Items.FAIRY_BOW, b) if adult else False_()
        hook = can_use(Items.HOOKSHOT, b) if adult else False_()
        rang = can_use(Items.BOOMERANG, b) if not adult else False_()
        ranged = (bow | hook | can_use(Items.LONGSHOT, b)) if adult else (can_use(Items.FAIRY_SLINGSHOT, b) | rang)
        explosive = has_explosives(b)
        fire = can_use(Items.DINS_FIRE, b) | (can_use(Items.FIRE_ARROW, b) if adult else False_())
        reflect = can_use(Items.HYLIAN_SHIELD, b) if adult else can_use(Items.DEKU_SHIELD, b)
''', '''        # can_use handles direction-specific cross-age equip unlocks. The
        # `adult` parameter still represents the actor/room's real age.
        sword = (can_use(Items.MASTER_SWORD, b) | can_use(Items.BIGGORONS_SWORD, b)
                 | can_use(Items.KOKIRI_SWORD, b))
        melee = sword | can_use(Items.MEGATON_HAMMER, b) | can_use(Items.STICKS, b)
        sticks = can_use(Items.STICKS, b)
        hammer = can_use(Items.MEGATON_HAMMER, b)
        sling = can_use(Items.FAIRY_SLINGSHOT, b)
        nuts = can_use(Items.NUTS, b)
        bow = can_use(Items.FAIRY_BOW, b)
        hook = can_use(Items.HOOKSHOT, b) | can_use(Items.LONGSHOT, b)
        rang = can_use(Items.BOOMERANG, b)
        ranged = bow | hook | sling | rang
        explosive = has_explosives(b)
        fire = can_use(Items.DINS_FIRE, b) | can_use(Items.FIRE_ARROW, b)
        reflect = can_use(Items.HYLIAN_SHIELD, b) | can_use(Items.DEKU_SHIELD, b)
''')
once(ENEMY, '''            # These two Hyrule Field placements are child-only (spawn_mask=3),
            # so their usable weapon in logic is Slingshot. Adult variants
            # could instead use Bow, Hookshot or Longshot.
            "peahat_flying": sling | bow | hook | (can_use(Items.LONGSHOT, b) if adult else False_()),''', '''            # These spawns are child-only: Slingshot works normally. Bow or
            # Hookshot/Longshot work for Child only after the equipment unlock.
            "peahat_flying": sling | bow | hook,''')

print('Patched cross-age equipment and Peahat combat integration')
