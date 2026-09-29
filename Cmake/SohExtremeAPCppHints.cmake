# Read-only AP hint subscription for the pinned APCpp revision.
# Validate every edit before writing either file; rerunning CMake is idempotent.
include_guard(GLOBAL)
function(soh_extreme_ap_hints source_dir)
    file(LOCK "${source_dir}/.soh-extreme-hints.lock" GUARD FUNCTION TIMEOUT 120)
    file(READ "${source_dir}/Archipelago.cpp" cpp)
    file(READ "${source_dir}/Archipelago.h" header)
    string(REPLACE "\r\n" "\n" cpp "${cpp}")
    string(REPLACE "\r\n" "\n" header "${header}")
    set(old [==[Plaintext, ItemSend, ItemRecv, Hint, Countdown, Chat, ServerChat]==])
    set(new [==[Plaintext, ItemSend, ItemRecv, Hint, Countdown, Chat, ServerChat, HintList]==])
    string(FIND "${header}" "${new}" fixed)
    if(fixed EQUAL -1)
        string(FIND "${header}" "${old}" found)
        if(found EQUAL -1)
            message(FATAL_ERROR "SOH-EXTREME: APCpp hint patch 1 does not match the pinned source; nothing was overwritten.")
        endif()
        string(REPLACE "${old}" "${new}" header "${header}")
    endif()
    set(old [==[struct AP_CountdownMessage : AP_Message {]==])
    set(new [==[// Complete server-owned hint snapshot, delivered on the normal message queue.
struct AP_StoredHint {
    std::string item, location, finder, recipient, entrance;
    bool found = false;
};
struct AP_HintListMessage : AP_Message {
    std::vector<AP_StoredHint> hints;
};

struct AP_CountdownMessage : AP_Message {]==])
    string(FIND "${header}" "${new}" fixed)
    if(fixed EQUAL -1)
        string(FIND "${header}" "${old}" found)
        if(found EQUAL -1)
            message(FATAL_ERROR "SOH-EXTREME: APCpp hint patch 2 does not match the pinned source; nothing was overwritten.")
        endif()
        string(REPLACE "${old}" "${new}" header "${header}")
    endif()
    set(old [==[bool parse_response(std::string msg, std::string &request) {]==])
    set(new [==[// SOH-EXTREME: hints are read-only server data, never purchased/scouted here.
static std::string sohHintKey;
static Json::Value sohHints;
static bool sohHintsLoaded = false;
static void sohPublishHints() {
    if (!sohHintsLoaded || !datapkg_outdated_games.empty()) return;
    auto* message = new AP_HintListMessage;
    message->type = AP_MessageType::HintList;
    if (sohHints.isArray()) for (const auto& hint : sohHints) {
        if (!hint.isObject() || !hint["finding_player"].isInt() || !hint["receiving_player"].isInt() ||
            !hint["item"].isInt64() || !hint["location"].isInt64()) continue;
        const auto finder = getPlayer(ap_player_team, hint["finding_player"].asInt());
        const auto recipient = getPlayer(ap_player_team, hint["receiving_player"].asInt());
        AP_StoredHint row;
        row.item = getItemName(recipient.game, hint["item"].asInt64());
        row.location = getLocationName(finder.game, hint["location"].asInt64());
        row.finder = finder.alias;
        row.recipient = recipient.alias;
        row.entrance = hint["entrance"].isString() ? hint["entrance"].asString() : "";
        row.found = hint["found"].isBool() && hint["found"].asBool();
        message->hints.push_back(std::move(row));
    }
    AP_QueueMessage(message);
}

bool parse_response(std::string msg, std::string &request) {]==])
    string(FIND "${cpp}" "${new}" fixed)
    if(fixed EQUAL -1)
        string(FIND "${cpp}" "${old}" found)
        if(found EQUAL -1)
            message(FATAL_ERROR "SOH-EXTREME: APCpp hint patch 3 does not match the pinned source; nothing was overwritten.")
        endif()
        string(REPLACE "${old}" "${new}" cpp "${cpp}")
    endif()
    set(old [==[            ap_player_team = root[i]["team"].asInt();]==])
    set(new [==[            ap_player_team = root[i]["team"].asInt();
            sohHintKey = "_read_hints_" + std::to_string(ap_player_team) + "_" + std::to_string(ap_player_id);
            sohHints = Json::nullValue;
            sohHintsLoaded = false;]==])
    string(FIND "${cpp}" "${new}" fixed)
    if(fixed EQUAL -1)
        string(FIND "${cpp}" "${old}" found)
        if(found EQUAL -1)
            message(FATAL_ERROR "SOH-EXTREME: APCpp hint patch 4 does not match the pinned source; nothing was overwritten.")
        endif()
        string(REPLACE "${old}" "${new}" cpp "${cpp}")
    endif()
    set(old [==[            // getDataPkgRequest returns either a Sync or GetDataPackage packet]==])
    set(new [==[            Json::Value hintSubscribe, hintGet;
            hintSubscribe["cmd"] = "SetNotify";
            hintSubscribe["keys"][0] = sohHintKey;
            hintGet["cmd"] = "Get";
            hintGet["keys"][0] = sohHintKey;
            req_t.append(hintSubscribe);
            req_t.append(hintGet);

            // getDataPkgRequest returns either a Sync or GetDataPackage packet]==])
    string(FIND "${cpp}" "${new}" fixed)
    if(fixed EQUAL -1)
        string(FIND "${cpp}" "${old}" found)
        if(found EQUAL -1)
            message(FATAL_ERROR "SOH-EXTREME: APCpp hint patch 5 does not match the pinned source; nothing was overwritten.")
        endif()
        string(REPLACE "${old}" "${new}" cpp "${cpp}")
    endif()
    set(old [==[            cacheDataPkgs(root[i]["data"]);]==])
    set(new [==[            cacheDataPkgs(root[i]["data"]);
            sohPublishHints();]==])
    string(FIND "${cpp}" "${new}" fixed)
    if(fixed EQUAL -1)
        string(FIND "${cpp}" "${old}" found)
        if(found EQUAL -1)
            message(FATAL_ERROR "SOH-EXTREME: APCpp hint patch 6 does not match the pinned source; nothing was overwritten.")
        endif()
        string(REPLACE "${old}" "${new}" cpp "${cpp}")
    endif()
    set(old [==[                if (!map_server_data.count(itr)) continue;]==])
    set(new [==[                if (itr == sohHintKey) {
                    sohHints = root[i]["keys"][itr];
                    sohHintsLoaded = true;
                    sohPublishHints();
                    continue;
                }
                if (!map_server_data.count(itr)) continue;]==])
    string(FIND "${cpp}" "${new}" fixed)
    if(fixed EQUAL -1)
        string(FIND "${cpp}" "${old}" found)
        if(found EQUAL -1)
            message(FATAL_ERROR "SOH-EXTREME: APCpp hint patch 7 does not match the pinned source; nothing was overwritten.")
        endif()
        string(REPLACE "${old}" "${new}" cpp "${cpp}")
    endif()
    set(old [==[        } else if (cmd == "SetReply") {
]==])
    set(new [==[        } else if (cmd == "SetReply") {
            if (root[i]["key"].isString() && root[i]["key"].asString() == sohHintKey) {
                sohHints = root[i]["value"];
                sohHintsLoaded = true;
                sohPublishHints();
                continue;
            }
]==])
    string(FIND "${cpp}" "${new}" fixed)
    if(fixed EQUAL -1)
        string(FIND "${cpp}" "${old}" found)
        if(found EQUAL -1)
            message(FATAL_ERROR "SOH-EXTREME: APCpp hint patch 8 does not match the pinned source; nothing was overwritten.")
        endif()
        string(REPLACE "${old}" "${new}" cpp "${cpp}")
    endif()
    file(WRITE "${source_dir}/Archipelago.cpp" "${cpp}")
    file(WRITE "${source_dir}/Archipelago.h" "${header}")
endfunction()
soh_extreme_ap_hints("${apcpp_SOURCE_DIR}")
