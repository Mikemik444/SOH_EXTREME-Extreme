// Hint-only ArchipelagoClient implementation. Included by ArchipelagoClient.cpp
// after native hint text builders; building text remains strictly read-only.

namespace {
using ApHintIdentity = std::pair<int, int64_t>;

ApHintIdentity HintIdentity(const SohExtreme::HintTarget& target) {
    return {target.finderId, target.locationId};
}

nlohmann::json HintTargetJson(const SohExtreme::HintTarget& target) {
    return {{"item_id", target.itemId}, {"location_id", target.locationId},
            {"finding_player", target.finderId}, {"receiving_player", target.recipientId},
            {"item_flags", target.flags}, {"item", target.item}, {"location", target.location},
            {"finder", target.finder}, {"recipient", target.recipient}, {"game", target.game},
            {"entrance", target.entrance}};
}
} // namespace

SohExtreme::HintTarget ArchipelagoClient::MakeHintTarget(int64_t locationId) const {
    SohExtreme::HintTarget target;
    const auto found = scoutedLocations.find(locationId);
    if (found == scoutedLocations.end() || !IsLocationActive(locationId)) return target;
    const auto& info = found->second;
    if (info.itemName.empty() || info.locationName.empty()) return target;
    target.locationId = locationId;
    target.itemId = info.itemId;
    target.finderId = saveConnectionIdentity.slot;
    target.recipientId = info.playerId;
    target.flags = info.flags;
    target.item = info.itemName;
    target.location = info.locationName;
    target.finder = saveSlot;
    target.recipient = info.playerName.empty() ? "Player " + std::to_string(info.playerId) : info.playerName;
    target.game = "SOH-EXTREME";
    target.seed = saveConnectionIdentity.seed;
    target.team = saveConnectionIdentity.team;
    target.slot = saveConnectionIdentity.slot;
    return target;
}

std::vector<SohExtreme::HintTarget> ArchipelagoClient::GetHintItemTargets(int32_t randomizerCheck) {
    if (!IsGameplaySessionActive()) return {};
    auto target = MakeHintTarget(ResolveApLocationForCheck(randomizerCheck));
    return target.HasLocation() ? std::vector<SohExtreme::HintTarget>{std::move(target)}
                                : std::vector<SohExtreme::HintTarget>{};
}

std::vector<SohExtreme::HintTarget> ArchipelagoClient::GetInGameHintTargets(const std::string& key,
                                                                        int32_t stoneIndex) {
    if (!IsGameplaySessionActive()) return {};
    if (!inGameHints.Get(key).empty()) {
        auto targets = inGameHints.Targets(key);
        std::vector<SohExtreme::HintTarget> result;
        for (auto& target : targets) {
            if (!target.HasLocation() || target.itemId < 0 || target.flags < 0) {
                // Older snapshots have names only. Resolve an exact local
                // placement, never another game's numeric namespace or a
                // similar item/player name. Unknown foreign targets stay text.
                int64_t matched = -1;
                if (target.finder == saveSlot) {
                    for (const auto& [id, info] : scoutedLocations) {
                        if (info.locationName != target.location || info.itemName != target.item ||
                            (!target.recipient.empty() && info.playerName != target.recipient)) continue;
                        if (matched >= 0) { matched = -1; break; }
                        matched = id;
                    }
                }
                if (matched < 0) continue;
                target = MakeHintTarget(matched);
            }
            if (!target.HasLocation() || target.recipientId <= 0 || target.item.empty()) continue;
            target.seed = saveConnectionIdentity.seed;
            target.team = saveConnectionIdentity.team;
            target.slot = saveConnectionIdentity.slot;
            result.push_back(std::move(target));
        }
        return result;
    }
    // Mirror the old-seed text builder's stable candidate selection exactly.
    // The immutable result is attached to that text now; later snapshots cannot
    // change which item a completed textbox reveals.
    if (stoneIndex < 0 && !inGameHints.IsLoaded()) return {};
    if (stoneIndex < 0) stoneIndex = 0;
    if (!scoutsRequested || scoutedLocations.size() < expectedScoutCount) return {};
    std::vector<int64_t> candidates;
    for (const auto& [id, info] : scoutedLocations)
        if (!info.itemName.empty() && !info.locationName.empty() && (info.flags & 1)) candidates.push_back(id);
    if (candidates.empty()) for (const auto& [id, info] : scoutedLocations)
        if (!info.itemName.empty() && !info.locationName.empty()) candidates.push_back(id);
    if (candidates.empty()) return {};
    std::sort(candidates.begin(), candidates.end());
    auto target = MakeHintTarget(candidates[static_cast<size_t>(stoneIndex) % candidates.size()]);
    return target.HasLocation() ? std::vector<SohExtreme::HintTarget>{std::move(target)}
                                : std::vector<SohExtreme::HintTarget>{};
}

void ArchipelagoClient::RecordRevealedHintTargets(const std::vector<SohExtreme::HintTarget>& targets) {
    if (!currentSaveIsArchipelago || !saveConnectionIdentity.Valid()) return;
    bool changed = false;
    {
        std::scoped_lock lock(hintJournalMutex);
        for (const auto& target : targets) {
            if (!target.IsProgression() || !target.HasLocation() || target.itemId < 0 || target.recipientId <= 0 ||
                target.item.empty() || target.location.empty() || target.finder.empty() || target.recipient.empty() ||
                target.seed != saveConnectionIdentity.seed || target.team != saveConnectionIdentity.team ||
                target.slot != saveConnectionIdentity.slot) continue;
            changed |= revealedHintTargets.emplace(HintIdentity(target), target).second;
        }
    }
    if (changed) {
        RebuildHints();
        nextHintPublish = 0.0;
    }
}

void SohExtreme::RecordRevealedHintTargets(const std::vector<SohExtreme::HintTarget>& targets) {
    ArchipelagoClient::GetInstance().RecordRevealedHintTargets(targets);
}

void ArchipelagoClient::RebuildHints() {
    std::map<ApHintIdentity, SohExtreme::ServerHintRecord> combined;
    for (const auto& row : serverHintRows)
        if (row.target.IsProgression()) combined[HintIdentity(row.target)] = row;
    {
        std::scoped_lock lock(hintJournalMutex);
        for (const auto& [identity, target] : revealedHintTargets) {
            if (!target.IsProgression() || target.seed != saveConnectionIdentity.seed ||
                target.team != saveConnectionIdentity.team || target.slot != saveConnectionIdentity.slot) continue;
            combined.try_emplace(identity, SohExtreme::ServerHintRecord{target, false});
        }
    }
    hints.clear();
    for (const auto& [identity, row] : combined) {
        const auto& target = row.target;
        const bool found = row.found || (target.finderId == saveConnectionIdentity.slot &&
                                        reportedLocations.contains(target.locationId));
        hints.push_back({target.item, target.location, target.finder, target.recipient, target.entrance, found});
    }
    std::stable_sort(hints.begin(), hints.end(), [](const HintInfo& a, const HintInfo& b) {
        if (a.found != b.found) return !a.found;
        return a.item < b.item;
    });
}

std::string ArchipelagoClient::GetRevealedHintTargetsJson() const {
    nlohmann::json rows = nlohmann::json::array();
    std::scoped_lock lock(hintJournalMutex);
    for (const auto& [identity, target] : revealedHintTargets) {
        auto row = HintTargetJson(target);
        row["seed"] = target.seed;
        row["team"] = target.team;
        row["slot"] = target.slot;
        rows.push_back(std::move(row));
    }
    return rows.dump();
}

bool ArchipelagoClient::LoadRevealedHintTargetsJson(const std::string& raw) {
    if (raw.size() > 8 * 1024 * 1024) return false;
    const auto rows = nlohmann::json::parse(raw, nullptr, false);
    if (!rows.is_array() || rows.size() > 20000) return false;
    std::map<ApHintIdentity, SohExtreme::HintTarget> next;
    for (const auto& row : rows) {
        if (!row.is_object()) return false;
        auto target = SohExtreme::ReadHintTarget(row);
        const auto team = SohExtreme::HintInteger(row, "team"), slot = SohExtreme::HintInteger(row, "slot");
        target.seed = SohExtreme::HintString(row, "seed");
        if (!target.IsProgression() || !target.HasLocation() || target.itemId < 0 || target.recipientId <= 0 ||
            target.item.empty() || target.location.empty() || target.finder.empty() || target.recipient.empty() ||
            target.seed != saveConnectionIdentity.seed || team != saveConnectionIdentity.team ||
            slot != saveConnectionIdentity.slot || !saveConnectionIdentity.Valid()) return false;
        target.team = static_cast<int>(team);
        target.slot = static_cast<int>(slot);
        next.emplace(HintIdentity(target), std::move(target));
    }
    {
        std::scoped_lock lock(hintJournalMutex);
        // Discoveries are monotonic within one save identity. A Return to Spawn
        // reload may contain an older snapshot than a just-completed textbox.
        revealedHintTargets.merge(next);
    }
    RebuildHints();
    nextHintPublish = 0.0;
    return true;
}

void ArchipelagoClient::ServiceHintBridge() {
    std::string raw;
    {
        std::scoped_lock lock(queueMutex);
        raw.swap(pendingHintPayload);
    }
    if (!IsAuthenticated() || !IsGameplaySessionActive()) return;
    if (!raw.empty()) {
        SohExtreme::ServerHintSnapshot snapshot;
        if (!SohExtreme::ReadServerHintSnapshot(raw, snapshot)) {
            hintSyncStatus = "Progression hint update was invalid; waiting for a fresh server snapshot.";
        } else if (snapshot.nonce == finderMirror.Nonce() && snapshot.slot == AP_GetPlayerID() &&
                   (hintProducer.empty() || hintProducer == snapshot.producer) &&
                   (!hintSnapshotLoaded || snapshot.revision > hintRevision)) {
            hintProducer = snapshot.producer;
            hintRevision = snapshot.revision;
            serverHintRows = std::move(snapshot.rows);
            hintSnapshotLoaded = true;
            hintSyncStatus.clear();
            RebuildHints();
        }
    }
    if (!finderWorkerStarted) return;
    const double now = FinderMirrorClock();
    auto send = [&](nlohmann::json data) {
        data["soh_extreme_tracker"] = SohExtreme::kTrackerProtocol;
        data["nonce"] = finderMirror.Nonce();
        data["slot"] = AP_GetPlayerID();
        data["request"] = ++hintRequest;
        AP_Bounce bounce{};
        std::vector<std::string> tags{"SOHExtremeUT"};
        bounce.tags = &tags;
        bounce.data = data.dump();
        AP_SendBounce(bounce);
    };
    if (now >= nextHintRequest) {
        send({{"kind", "hint_request"}});
        nextHintRequest = now + 3.0;
    }
    if (now >= nextHintPublish) {
        std::set<ApHintIdentity> confirmed;
        for (const auto& row : serverHintRows) confirmed.insert(HintIdentity(row.target));
        nlohmann::json targets = nlohmann::json::array();
        {
            std::scoped_lock lock(hintJournalMutex);
            for (const auto& [identity, target] : revealedHintTargets) {
                if (confirmed.contains(identity) || !target.IsProgression() ||
                    target.seed != saveConnectionIdentity.seed || target.team != saveConnectionIdentity.team ||
                    target.slot != saveConnectionIdentity.slot) continue;
                targets.push_back({{"item_id", target.itemId}, {"location_id", target.locationId},
                                   {"finding_player", target.finderId}, {"receiving_player", target.recipientId},
                                   {"item_flags", target.flags}});
                if (targets.size() == 256) break;
            }
        }
        if (!targets.empty()) send({{"kind", "hint_reveal"}, {"targets", std::move(targets)}});
        nextHintPublish = now + 3.0;
    }
}
