// Included after APCpp's server-data containers, in Archipelago.cpp only.
// Helpers below do not invoke client callbacks. The server-data mutex is
// recursive because offline data-storage resolution can re-enter the API.
#include <mutex>

static std::recursive_mutex sSoHApServerDataMutex;
static std::mutex sSoHApMessageMutex;

static void SoHApCancelPendingRequests() {
    std::lock_guard<std::recursive_mutex> guard(sSoHApServerDataMutex);
    // Do not erase the element being traversed by a range-for loop. That
    // invalidates its hidden iterator and was the reconnect/error-path bug.
    for (const auto& pending : map_server_data) {
        if (pending.second != nullptr) {
            pending.second->status = AP_RequestStatus::Error;
        }
    }
    map_server_data.clear();
    // A disconnect must not leave queued requests/status pointers for a later
    // connection. The public Bulk API still requires caller-owned requests to
    // stay alive until their completion, as in upstream APCpp.
    while (!queue_server_data.empty()) {
        auto* status = queue_server_data.front().second;
        if (status != nullptr) {
            *status = AP_RequestStatus::Error;
        }
        queue_server_data.pop();
    }
}

static AP_DataType SoHApReplyType(const std::string& key) {
    std::lock_guard<std::recursive_mutex> guard(sSoHApServerDataMutex);
    return map_serverdata_typemanage[key];
}

static void SoHApPushMessage(AP_Message* message) {
    std::lock_guard<std::mutex> guard(sSoHApMessageMutex);
    messageQueue.push_back(message);
}
