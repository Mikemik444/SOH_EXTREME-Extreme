void ArchipelagoClient::ApplySlotSettings() {
    slotSettingsPendingApply.store(false);
    std::unordered_map<std::string, int> settingsSnapshot;
    {
        std::scoped_lock lock(queueMutex);
        if (!slotSettingsLoaded) {
            return;
        }
        settingsSnapshot = slotSettings;
    }

    SPDLOG_INFO("[Archipelago] SOH-EXTREME AP settings runtime 0.8.05 active");

    // APWorld sends extreme_soh_cvars using the *native option suffixes*
    // (ShufflePots, ShuffleGrass, PotSoul, etc.).  Do NOT reconstruct the CVar
    // prefix here.  Ship's Option table is the authority for the exact CVar name
    // consumed by Option::GetOptionIndex()/RAND_GET_OPTION().
    //
    // This fixes the failure where AP successfully wrote/read 223 synthetic CVars,
    // but the real Randomizer Options still read 0.  A normal SoH randomizer menu
    // worked because it writes Option::GetCVarName() directly.
    auto settings = Rando::Settings::GetInstance();
    if (!settings) {
        SPDLOG_ERROR("[Archipelago] Randomizer Settings singleton unavailable; cannot apply AP settings");
        return;
    }

    size_t mappedNativeOptions = 0;
    size_t nativeReadbackMismatches = 0;
    std::set<std::string> consumedKeys;

    for (const auto& option : settings->GetAllOptions()) {
        const std::string& nativeCVar = option.GetCVarName();
        if (nativeCVar.empty()) {
            continue;
        }

        // AP keys are the final component of the native CVar, e.g.
        // gRandoSettings.ShufflePots -> ShufflePots.
        const size_t dot = nativeCVar.find_last_of('.');
        const std::string nativeKey = dot == std::string::npos ? nativeCVar : nativeCVar.substr(dot + 1);
        auto it = settingsSnapshot.find(nativeKey);
        if (it == settingsSnapshot.end()) {
            continue;
        }

        const int requested = it->second;
        CVarSetInteger(nativeCVar.c_str(), requested);
        consumedKeys.insert(nativeKey);
        ++mappedNativeOptions;

        const int readBack = CVarGetInteger(nativeCVar.c_str(), requested - 1);
        if (readBack != requested) {
            ++nativeReadbackMismatches;
            SPDLOG_ERROR("[Archipelago] Native option CVar write failed: {} (AP key {}) requested={} readback={}",
                         nativeCVar, nativeKey, requested, readBack);
        }
    }

    // Preserve AP-only/custom CVars that are not represented by Settings::mOptions.
    // These are intentionally secondary; gameplay randomizer settings above always
    // use the exact CVar name from Ship's native Option table.
    for (const auto& [key, value] : settingsSnapshot) {
        if (consumedKeys.contains(key)) {
            continue;
        }
        const std::string fallbackCVar = std::string("gRandoSettings.") + key;
        CVarSetInteger(fallbackCVar.c_str(), value);
    }

    // Callbacks may change visibility/availability, then copy the now-correct native
    // menu indices into the live Context used by RAND_GET_OPTION.
    settings->UpdateAllOptions();
    settings->SetAllToContext();

    // AP is the authority for logic on an Archipelago save. Native trick flags are
    // stored separately from the normal option array, so a local SoH randomizer
    // session can otherwise leak enabled tricks into Check Finder/reachability even
    // when the AP YAML has no tricks enabled. The current AP slot-data format does
    // not publish a native trick list, so fail closed: no local trick is allowed to
    // alter an AP seed's logic. (The resolved AP world already accounts for any
    // tricks selected on the server side.)
    if (auto randoContext = Rando::Context::GetInstance(); randoContext != nullptr) {
        randoContext->ResetTrickOptions();
    }
    CVarSetString(CVAR_RANDOMIZER_SETTING("EnabledTricks"), "");

    if (IS_RANDO && gPlayState != nullptr) {
        // AP settings are authoritative for BOTH physical SoH behavior and the
        // Check Finder. Refresh native randomizer hooks first, then schedule one
        // deferred reachability pass so the tracker cannot keep logic computed
        // from stale/local menu settings.
        RefreshArchipelagoRandomizerHooks();
        if (CVarGetInteger(CVAR_TRACKER_CHECK("EnableAvailableChecks"), 0)) {
            CheckTracker::RecalculateAvailableChecks();
        }
    }

    auto slotValue = [&settingsSnapshot](const char* key, int fallback = 0) {
        auto it = settingsSnapshot.find(key);
        return it == settingsSnapshot.end() ? fallback : it->second;
    };
    const int trapPool = slotValue("ExtremeTrapPool");
    const bool expanded = trapPool == 2;
    CVarSetInteger("gEnhancements.ExtraTraps.Enabled", trapPool != 0);
    CVarSetInteger("gEnhancements.ExtraTraps.Ice", trapPool == 1 || (expanded && slotValue("ExtremeIceTraps")));
    CVarSetInteger("gEnhancements.ExtraTraps.Burn", expanded && slotValue("ExtremeFireTraps"));
    CVarSetInteger("gEnhancements.ExtraTraps.Speed", expanded && slotValue("ExtremeSlowTraps"));
    CVarSetInteger("gEnhancements.ExtraTraps.Magic", expanded && slotValue("ExtremeMagicSuckTraps"));
    CVarSetInteger("gEnhancements.ExtraTraps.Health", expanded && slotValue("ExtremeHealthDrainTraps"));
    CVarSetInteger("gEnhancements.ExtraTraps.Shock", 0);
    CVarSetInteger("gEnhancements.ExtraTraps.Knockback", 0);
    CVarSetInteger("gEnhancements.ExtraTraps.Bomb", 0);
    CVarSetInteger("gEnhancements.ExtraTraps.Void", 0);
    CVarSetInteger("gEnhancements.ExtraTraps.Ammo", 0);
    CVarSetInteger("gEnhancements.ExtraTraps.Kill", 0);
    CVarSetInteger("gEnhancements.ExtraTraps.Teleport", 0);

    // Mirror the authoritative AP seed into the same persisted native CVars used
    // by the local Randomizer menu. The local menu therefore shows the AP seed's
    // configuration instead of stale pre-connection values, and local/randomizer
    // runtime logic reads the same settings snapshot.
    Ship::Context::GetRawInstance()->GetWindow()->GetGui()->SaveConsoleVariablesNextFrame();

    // Log AP input AND the live RSK result.  If these differ now, the log tells us
    // which exact layer is wrong instead of merely proving a synthetic CVar exists.
    SPDLOG_INFO(
        "[Archipelago] AP native settings: mapped={}/{} readback_mismatches={} | "
        "Pots AP={} RSK={} PotSoul AP={} RSK={} Grass AP={} RSK={} GrassSoul AP={} RSK={} "
        "Rocks AP={} RSK={} RockSoul AP={} RSK={} Crates AP={} RSK={} CrateSoul AP={} RSK={} "
        "Speak AP={} RSK={} NPCSpeech AP={} RSK={} FlowOfTime AP={} RSK={}",
        mappedNativeOptions, settingsSnapshot.size(), nativeReadbackMismatches,
        slotValue("ShufflePots"), RAND_GET_OPTION(RSK_SHUFFLE_POTS).Get(),
        slotValue("PotSoul"), RAND_GET_OPTION(RSK_SHUFFLE_POT_SOUL).Get(),
        slotValue("ShuffleGrass"), RAND_GET_OPTION(RSK_SHUFFLE_GRASS).Get(),
        slotValue("GrassSoul"), RAND_GET_OPTION(RSK_SHUFFLE_GRASS_SOUL).Get(),
        slotValue("ShuffleRocks"), RAND_GET_OPTION(RSK_SHUFFLE_ROCKS).Get(),
        slotValue("RockSoul"), RAND_GET_OPTION(RSK_SHUFFLE_ROCK_SOUL).Get(),
        slotValue("ShuffleCrates"), RAND_GET_OPTION(RSK_SHUFFLE_CRATES).Get(),
        slotValue("CrateSoul"), RAND_GET_OPTION(RSK_SHUFFLE_CRATE_SOUL).Get(),
        slotValue("ShuffleSpeak"), RAND_GET_OPTION(RSK_SHUFFLE_SPEAK).Get(),
        slotValue("NPCSpeechSanity"), RAND_GET_OPTION(RSK_NPC_SPEECH_SANITY).Get(),
        slotValue("FlowOfTime"), RAND_GET_OPTION(RSK_SHUFFLE_FLOW_OF_TIME).Get());
}
