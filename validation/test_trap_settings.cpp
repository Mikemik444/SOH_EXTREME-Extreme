// The runner places the delivered production implementations before this file.
static int cases=0;
#define REQUIRE(expr) do { if(!(expr)) { std::cerr << "FAILED line " << __LINE__ << ": " #expr "\n"; return 1; } } while(0)
static std::unordered_map<std::string,int> Preferences() {
    std::unordered_map<std::string,int> prefs;
    for(const auto& [k,v]:cvars) if(k.rfind("gEnhancements.ExtraTraps.",0)==0) prefs[k]=v;
    return prefs;
}
static void SetLocal(bool enabled) {
    cvars.clear();CVarSetInteger(CVAR_EXTRA_TRAPS_NAME,enabled);
    for(int i=0;i<ADD_TRAP_MAX;++i) CVarSetInteger(altTrapTypeCvars[i],i%2);
    CVarSetInteger(altTrapTypeCvars[ADD_TELEPORT_TRAP],TELEPORT_TRAP_ADVANCED);
}
static std::unordered_map<std::string,int> Seed(int pool,int mask) {
    return {{"ExtremeTrapPool",pool},{"ExtremeIceTraps",!!(mask&1)},
      {"ExtremeFireTraps",!!(mask&2)},{"ExtremeSlowTraps",!!(mask&4)},
      {"ExtremeMagicSuckTraps",!!(mask&8)},{"ExtremeHealthDrainTraps",!!(mask&16)},
      {"ShufflePots",3}};
}
static void SetContextSeed(int pool,int mask) {
    ArchipelagoClient c;c.slotSettings=Seed(pool,mask);c.ApplySlotSettings();
}
static WidgetInfo& Widget(const std::string& label) {
    auto it=std::find_if(menu.begin(),menu.end(),[&](const auto& w){return w.name==label;});
    assert(it!=menu.end());if(it->pre) it->pre(*it);return *it;
}
static void QueueOneTrap() { actions.clear();gSaveContext.ship.pendingIceTrapCount=1; }
int main() {
    BuildTrapMenu();
    ShipInit::InitAll();
    isApSave=true;SetLocal(true);
    const auto original=Preferences();
    BeforeClient before;before.slotSettings=Seed(0,16);before.ApplySlotSettings();
    REQUIRE(Preferences()!=original);
    REQUIRE(CVarGetInteger(CVAR_EXTRA_TRAPS_NAME,1)==0);
    REQUIRE(Widget("Trap Options").isHidden);
    REQUIRE(savedCvars.at(CVAR_EXTRA_TRAPS_NAME)==0);
    std::cout << "PASS: original load/apply reproduced lost preferences and hidden controls\n";++cases;

    SetLocal(true);const auto selected=Preferences();
    for(int pool=0;pool<3;++pool) for(int mask=0;mask<32;++mask) {
        SetContextSeed(pool,mask);
        const auto config=GetEffectiveExtraTrapSettings();
        REQUIRE(config.enabled==(pool!=0));
        REQUIRE(config.types[ADD_ICE_TRAP]==(pool==1||(pool==2&&(mask&1))));
        REQUIRE(config.types[ADD_BURN_TRAP]==(pool==2&&!!(mask&2)));
        REQUIRE(config.types[ADD_SPEED_TRAP]==(pool==2&&!!(mask&4)));
        REQUIRE(config.types[ADD_MAGIC_TRAP]==(pool==2&&!!(mask&8)));
        REQUIRE(config.types[ADD_HEALTH_TRAP]==(pool==2&&!!(mask&16)));
        for(int type:{ADD_SHOCK_TRAP,ADD_KNOCK_TRAP,ADD_BOMB_TRAP,ADD_VOID_TRAP,ADD_AMMO_TRAP,ADD_KILL_TRAP,ADD_TELEPORT_TRAP}) REQUIRE(config.types[type]==0);
        REQUIRE(Preferences()==selected);
        REQUIRE(!Widget("Trap Options").isHidden);
        for (auto& widget : menu) {
            if (widget.pre) widget.pre(widget);
            REQUIRE(!widget.isHidden);
        }
        for(const auto& [k,val]:selected) REQUIRE(savedCvars.at(k)==val);
        // Simulated persistent config round-trip after the production save request.
        cvars=savedCvars;REQUIRE(Preferences()==selected);
        REQUIRE(RAND_GET_OPTION(RSK_SHUFFLE_POTS).Get()==3);
    }
    std::cout << "PASS: all 96 valid AP trap policies keep their previous effective selection without editing preferences\n";++cases;

    for(int file=0;file<4;++file) {
        SetContextSeed(file%3,31);
        GameInteractor::Dispatch<GameInteractor::OnLoadGame>(file);
        REQUIRE(Preferences()==selected);
        GameInteractor::Dispatch<GameInteractor::OnExitGame>(file);
        REQUIRE(Preferences()==selected);
    }
    isApSave=false;
    REQUIRE(GetEffectiveExtraTrapSettings().enabled);
    for(int i=0;i<ADD_TRAP_MAX;++i) REQUIRE(GetEffectiveExtraTrapSettings().types[i]==selected.at(altTrapTypeCvars[i]));
    REQUIRE(Widget("AP trap effects follow this seed's YAML.").isHidden);
    REQUIRE(!Widget("Teleport Traps").isHidden);
    std::cout << "PASS: simulated load/exit switches retain local profile and Advanced teleport mode\n";++cases;

    gSaveContext.ship.quest.id=0;isApSave=true; // stale marker cannot alter a non-rando save
    REQUIRE(GetEffectiveExtraTrapSettings().types[ADD_TELEPORT_TRAP]==TELEPORT_TRAP_ADVANCED);
    REQUIRE(Widget("AP trap effects follow this seed's YAML.").isHidden);
    gSaveContext.ship.quest.id=QUEST_RANDOMIZER;
    SetLocal(false);SetContextSeed(2,2);QueueOneTrap();REQUIRE(DeliverTrap());
    REQUIRE(actions["burn"]==1&&actions["freeze"]==0);
    REQUIRE(CVarGetInteger(CVAR_EXTRA_TRAPS_NAME,1)==0);
    REQUIRE(!Widget("AP trap effects follow this seed's YAML.").isHidden);
    std::cout << "PASS: AP burn works with local enhancements off; normal saves ignore AP policy\n";++cases;

    SetLocal(true);SetContextSeed(0,31);QueueOneTrap();REQUIRE(DeliverTrap());
    REQUIRE(actions["freeze"]==1&&actions["burn"]==0&&actions["kill"]==0);
    SetContextSeed(1,0);QueueOneTrap();REQUIRE(DeliverTrap());REQUIRE(actions["freeze"]==1);
    SetContextSeed(2,0);QueueOneTrap();REQUIRE(DeliverTrap());REQUIRE(actions["freeze"]==1);
    SetContextSeed(255,31);QueueOneTrap();REQUIRE(DeliverTrap());REQUIRE(actions["freeze"]==1);
    std::cout << "PASS: AP Off, Ice Only, empty Expanded and invalid policy use the freeze fallback\n";++cases;

    SetLocal(false);SetContextSeed(2,4);QueueOneTrap();REQUIRE(DeliverTrap());
    REQUIRE(GameInteractor::State::MovementSpeedMultiplier==0.5f);
    for(int tick=0;tick<201;++tick) GameInteractor::Dispatch<GameInteractor::OnPlayerUpdate>();
    REQUIRE(GameInteractor::State::MovementSpeedMultiplier==1.0f);
    REQUIRE(GameInteractor::Hooks<GameInteractor::OnPlayerUpdate>().size()==1);
    std::cout << "PASS: AP slowdown expires even while local master toggle is off\n";++cases;

    QueueOneTrap();DeliverTrap();REQUIRE(statusTimer==200);
    gSaveContext.ship.pendingIceTrapCount=4;
    const auto prefs=Preferences();
    GameInteractor::Dispatch<GameInteractor::OnLoadGame>(2);
    REQUIRE(statusTimer==-1&&eventTimer==-1&&roll==ADD_TRAP_MAX&&teleportRoll==ENTR_MAX);
    REQUIRE(GameInteractor::State::MovementSpeedMultiplier==1.0f);
    REQUIRE(Preferences()==prefs&&gSaveContext.ship.pendingIceTrapCount==4);
    std::cout << "PASS: load clears transient effects only, not saved preferences or queued trap count\n";++cases;

    isApSave=false;SetLocal(true);
    for(int type=0;type<ADD_TRAP_MAX;++type) {
        for(int i=0;i<ADD_TRAP_MAX;++i) CVarSetInteger(altTrapTypeCvars[i],i==type);
        ResetExtraTrapEffects();ammo.fill(10);QueueOneTrap();REQUIRE(DeliverTrap());
        REQUIRE(roll==type&&gSaveContext.ship.pendingIceTrapCount==0&&actions["receipt"]==1);
        for(int tick=0;tick<4;++tick) GameInteractor::Dispatch<GameInteractor::OnPlayerUpdate>();
        if(type==ADD_AMMO_TRAP) REQUIRE(ammo[ITEM_BOMBCHU]==5);
        if(type==ADD_KNOCK_TRAP) REQUIRE(actions["knock"]==1);
        if(type==ADD_BOMB_TRAP) REQUIRE(actions["bomb"]==1);
        if(type==ADD_VOID_TRAP) REQUIRE(actions["void"]==1);
        if(type==ADD_TELEPORT_TRAP) REQUIRE(actions["teleport"]==1&&lastTeleport==simpleTeleportDestinations[0]);
    }
    std::cout << "PASS: all 12 local trap types still select and execute, including delayed effects\n";++cases;

    for(int i=0;i<ADD_TRAP_MAX;++i) CVarSetInteger(altTrapTypeCvars[i],i==ADD_TELEPORT_TRAP?TELEPORT_TRAP_ADVANCED:0);
    QueueOneTrap();DeliverTrap();for(int t=0;t<4;++t) OnPlayerUpdate();
    REQUIRE(lastTeleport==advancedTeleportDestinations[0]);
    QueueOneTrap();DeliverTrap();GameInteractor::Dispatch<GameInteractor::OnExitGame>(1);
    REQUIRE(eventTimer==-1&&teleportRoll==ENTR_MAX);OnPlayerUpdate();REQUIRE(actions["teleport"]==0);
    std::cout << "PASS: Advanced teleport preserved; exit cancels old-file delayed effects\n";++cases;

    for(int i=0;i<ADD_TRAP_MAX;++i) CVarSetInteger(altTrapTypeCvars[i],i==ADD_VOID_TRAP||i==ADD_TELEPORT_TRAP);
    gSaveContext.equips.buttonItems[0]=ITEM_FISHING_POLE;
    REQUIRE(getEnabledAddTraps()==std::vector<AltTrapType>{ADD_ICE_TRAP});
    gSaveContext.equips.buttonItems[0]=0;
    REQUIRE(getEnabledAddTraps().size()==2);
    std::cout << "PASS: fishing-pole void/teleport exclusions and empty-list fallback remain\n";++cases;

    for(int i=0;i<ADD_TRAP_MAX;++i) CVarSetInteger(altTrapTypeCvars[i],i==ADD_SPEED_TRAP);
    QueueOneTrap();DeliverTrap();CVarSetInteger(CVAR_EXTRA_TRAPS_NAME,0);
    ShipInit::Init(CVAR_EXTRA_TRAPS_NAME);
    for(int t=0;t<201;++t) OnPlayerUpdate();
    REQUIRE(GameInteractor::State::MovementSpeedMultiplier==1.0f);
    std::cout << "PASS: turning local master off does not strand an active slowdown\n";++cases;

    RegisterExtraTraps();RegisterExtraTraps();
    REQUIRE(GameInteractor::Hooks<GameInteractor::OnPlayerUpdate>().size()==1);
    REQUIRE(GameInteractor::Hooks<GameInteractor::OnLoadGame>().size()==1);
    REQUIRE(GameInteractor::Hooks<GameInteractor::OnExitGame>().size()==1);
    REQUIRE(GameInteractor::Hooks<GameInteractor::OnVanillaBehavior>().size()==1);
    gSaveContext.ship.pendingIceTrapCount=0;actions.clear();REQUIRE(!DeliverTrap());REQUIRE(actions.empty());
    gPlayState=nullptr;OnPlayerUpdate();gPlayState=&testPlay;
    std::cout << "PASS: idempotent hooks, idle update, no pending trap and null-play timer guard\n";++cases;

    // A cached native seed context is sufficient: no auth or network API is consulted.
    isApSave=true;SetLocal(true);SetContextSeed(2,8);QueueOneTrap();DeliverTrap();REQUIRE(actions["magic"]==1);
    auto saved=Rando::Context::instance;Rando::Context::instance=nullptr;
    REQUIRE(!GetEffectiveExtraTrapSettings().enabled);Rando::Context::instance=saved;
    std::cout << "PASS: cached AP policy is independent of network authentication; missing context falls back safely\n";++cases;
    std::cout << "ALL " << cases << " named regression groups passed\n";
}
