#pragma once

#include <atomic>
#include <cstddef>
#include <cstdint>
#include <deque>
#include <mutex>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>
#include "TrackerMirror.h"
#include "TrackerWorker.h"


class ArchipelagoClient {
  public:
    static ArchipelagoClient& GetInstance();

    void Enable();
    void Disable();
    void Toggle();
    // Main-thread only. A null result is unknown/stale, not an empty reachable set.
    const SohExtreme::TrackerSnapshot* GetFinderSnapshot(std::string& status);
    void RefreshFinderMirror();
    void RestartFinderWorker();
    const std::string& GetFinderRuntimePath() const;
    int32_t GetFinderNativeCheck(int64_t locationId) const;
    void Update();

    bool IsEnabled() const { return enabled.load(); }
    bool IsAuthenticated() const;
    bool IsConnectionRefused() const;
    std::string GetStatusText() const;

    void SendLocation(int64_t locationId, bool notifyRemote = false);
    void ReportCheck(int32_t randomizerCheck);
    void ReportNpcSpeech(int32_t randomizerCheck);
    bool ReportNpcSpeechLocation(int64_t speechLocation);
    bool ReportFallbackNpcSpeech(const struct Actor* actor);
    void LoadFallbackNpcSpeechHashes(const std::vector<uint64_t>& hashes);
    std::vector<uint64_t> GetFallbackNpcSpeechHashes() const;
    void RegisterHooks();
    bool OwnsCheck(int32_t randomizerCheck);
    bool OwnsCheckCached(int32_t randomizerCheck) const;
    // Build the complete native RC -> active AP location cache for Check Finder.
    // This is intentionally demand-driven so normal save loading stays scene-local.
    bool PrepareCheckFinderMappings();
    bool IsLocationActive(int64_t locationId) const;
    bool IsLocationReported(int64_t locationId) const;
    size_t GetActiveLocationCount() const;
    size_t GetReportedActiveLocationCount() const;
    void ApplyScoutedPlacements();
    void RefreshPlacementForCheck(int32_t randomizerCheck);
    void RefreshPlacementsForScene(int16_t sceneNum);
    void EnsureLocationScouts();
    std::string GetRemoteItemDescription(int32_t randomizerCheck);
    bool IsReadyForFileSelect() const;
    void ApplySlotSettings();
    void EnforceSlotSettings();
    void ApplyPostInitSlotState();
    void PrimeNewSaveMetadata();
    void PrepareNewSaveItemReplay();
    void BeginFileSelectActivation();
    void EndFileSelectActivation();
    bool IsGameplaySessionActive() const;
    std::vector<std::string> GetChatMessages();
    void SendChatMessage(const std::string& message);

    // Per-save Archipelago receipt state.  This is serialized by SaveManager so
    // each save resumes the server ReceivedItems stream at exactly the point
    // represented by that save's inventory.
    void LoadSaveMetadata(bool isArchipelagoSave, uint64_t receivedItemCount, const std::string& server,
                          const std::string& slot, const std::string& cachedSettingsJson);
    bool IsCurrentSaveArchipelago() const { return currentSaveIsArchipelago; }
    uint64_t GetAppliedItemCount() const { return appliedItemCount; }
    std::string GetSaveServer() const { return saveServer; }
    std::string GetSaveSlot() const { return saveSlot; }
    std::string GetCachedSlotSettingsJson() const { return cachedSlotSettingsJson; }

  private:
    ArchipelagoClient() = default;
    ~ArchipelagoClient() = default;
    ArchipelagoClient(const ArchipelagoClient&) = delete;
    ArchipelagoClient& operator=(const ArchipelagoClient&) = delete;

    void BeginItemReplay();
    void ResetFinderMirror();
    void ServiceFinderWorker();
    SohExtreme::TrackerWorker finderWorker;
    bool finderWorkerStarted = false;
    uint32_t finderWorkerAttempts = 0;
    double finderWorkerNextPoll = 0.0;
    double finderWorkerRetryAt = 0.0;
    std::string finderWorkerError;
    SohExtreme::TrackerMirrorState finderMirror;
    std::string pendingFinderPayload;
    std::string finderMirrorError;
    double finderNextRequest = 0.0;
    void QueueItem(int64_t itemId, bool notify);
    void QueueCheckedLocation(int64_t locationId);
    void QueueDeathLink(const std::string& source, const std::string& cause);
    void QueueTrapLink(const std::string& source, const std::string& trapName);
    void SendDeathLink();
    void SendTrapLink(const std::string& trapName);
    void QueueLocationInfo(int64_t locationId, int64_t itemId, int playerId, int flags, const std::string& itemName,
                           const std::string& playerName, const std::string& locationName);
    bool ProcessItem(int64_t itemId, bool notify, uint64_t sequence);
    void MarkItemApplied(uint64_t sequence);
    void FinalizeMajorItemReceipt(int modIndex, int itemId, int getItemId);
    std::string GetReceivedCountCVar() const;
    int32_t MapApItemToRandomizerGet(int64_t itemId) const;
    void RequestLocationScouts();
    int64_t ResolveApLocationForCheck(int32_t randomizerCheck);
    void ApplySlotSetting(const std::string& key, int value);
    void RefreshSongNotes();
    void RegisterCallbacks();
    void SyncCollectedLocations();
    void SetActiveLocationsFromJson(const std::string& raw);
    void SetLocationNameMapFromJson(const std::string& raw);
    void SetSlotSettingsFromJson(const std::string& raw);
    void SetShopPricesFromJson(const std::string& raw);
    struct PendingItem {
        int64_t id;
        bool notify;
        uint64_t sequence = 0;
    };
    struct ScoutedLocation {
        int64_t itemId = 0;
        int playerId = 0;
        int flags = 0;
        std::string itemName;
        std::string playerName;
        std::string locationName;
    };
    void IndexScoutedLocation(int64_t locationId, const ScoutedLocation& info);
    struct PendingScout {
        int64_t locationId = 0;
        ScoutedLocation info;
    };
    struct PendingDeathLink {
        std::string source;
        std::string cause;
    };
    struct PendingTrapLink {
        std::string source;
        std::string trapName;
    };

    std::atomic<bool> enabled{ false };
    std::mutex queueMutex;
    std::deque<PendingItem> pendingItems;
    std::deque<int64_t> pendingCheckedLocations;
    std::deque<PendingScout> pendingScouts;
    std::deque<PendingDeathLink> pendingDeathLinks;
    std::deque<PendingTrapLink> pendingTrapLinks;
    std::deque<std::string> chatMessages;
    std::unordered_map<int, int64_t> rcToApLocation;
    std::unordered_map<int64_t, int> apLocationToRc;
    std::unordered_map<int64_t, ScoutedLocation> scoutedLocations;
    // Fast normalized AP location-name -> AP ID lookup. Missing native RC mappings
    // are resolved against this index on demand instead of scanning every scout.
    // A value of -1 marks an ambiguous normalized name.
    std::unordered_map<std::string, int64_t> scoutedLocationNameIndex;
    // Exact per-seed namespace supplied by standalone SOH-EXTREME slot data.
    // This is authoritative and decouples native RC checks from baked AP ids/names.
    std::unordered_map<std::string, int64_t> authoritativeLocationNameIndex;
    bool locationNameMapLoaded = false;
    std::unordered_set<int64_t> reportedLocations;
    std::unordered_set<int64_t> activeLocations;
    std::unordered_map<std::string, int> slotSettings;
    std::unordered_map<int64_t, uint16_t> shopPrices;
    bool activeLocationsLoaded = false;
    bool slotSettingsLoaded = false;
    bool shopPricesLoaded = false;
    bool kakarikoGateOpen = false;
    bool deathLinkEnabled = false;
    bool trapLinkEnabled = false;
    bool linkTagsSynchronized = false;
    bool deathStateInitialized = false;
    bool lastPlayerAlive = true;
    bool suppressNextDeathLinkSend = false;
    size_t expectedScoutCount = 0;
    bool wasAuthenticated = false;
    uint32_t syncFrameCounter = 0;
    bool scoutsRequested = false;
    // Scene-local gameplay never needs every RC mapped. Check Finder does, but only
    // when the user enables it; this flag prevents rebuilding that cache repeatedly.
    bool checkFinderMappingsPrepared = false;
    // Reset whenever no gameplay save is active. The next loaded AP save gets a full
    // authoritative settings/placement/state reconciliation before normal play continues.
    bool saveRuntimeSynchronized = false;
    bool fileSelectActivationRequested = false;

    // APCpp callbacks only publish data + these flags. Gameplay mutation is
    // deferred to Update()/save-load on the main/gameplay thread.
    std::atomic<bool> slotSettingsPendingApply{ false };
    std::atomic<bool> activeLocationsPendingRefresh{ false };

    // AP remains authoritative, but checking every native randomizer option every
    // frame is unnecessary.
    uint32_t settingsEnforceFrameCounter = 0;

    uint64_t incomingItemOrdinal = 0;
    uint64_t appliedItemCount = 0;
    // Major AP items are not committed when the get-item animation merely starts.
    // They become durable only when SoH fires OnItemReceive after actually granting the item.
    bool awaitingMajorItemReceipt = false;
    uint64_t awaitingMajorSequence = 0;
    int64_t awaitingMajorApItemId = 0;
    int awaitingMajorModIndex = 0;
    int awaitingMajorItemId = 0;
    int awaitingMajorGetItemId = 0;
    std::vector<int64_t> receivedItemSnapshot;
    bool currentSaveIsArchipelago = false;
    bool newSaveReplayPending = false;
    bool saveMetadataLoaded = false;
    bool saveIdentityMismatch = false;
    std::string saveServer;
    std::vector<uint64_t> fallbackNpcSpeechHashes;
    std::unordered_set<uint64_t> fallbackNpcSpeechSeen;
    std::string saveSlot;
    std::string cachedSlotSettingsJson;
};
