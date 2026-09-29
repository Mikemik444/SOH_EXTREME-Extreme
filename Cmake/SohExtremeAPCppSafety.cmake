# SOH-EXTREME 0.11.21a -- narrow repairs to the fetched APCpp revision.
# Included immediately after FetchContent_MakeAvailable(apcpp). Do not replace
# APCpp with a different revision or change any of its dependency/toolchain flags.
include_guard(GLOBAL)

function(soh_extreme_repair_apcpp source_dir)
    if(NOT EXISTS "${source_dir}/Archipelago.cpp")
        message(FATAL_ERROR "SOH-EXTREME: APCpp's Archipelago.cpp was not found in ${source_dir}")
    endif()
    file(LOCK "${source_dir}/.soh-extreme-safety.lock" GUARD FUNCTION TIMEOUT 120)
    set(marker "SOH-EXTREME APCpp safety hotfix 0.11.21a active")
    set(old_cleanup [=[for (std::pair<std::string,AP_GetServerDataRequest*> itr : map_server_data) {
                    itr.second->status = AP_RequestStatus::Error;
                    map_server_data.erase(itr.first);
                }]=])
    set(new_cleanup [=[// SOH-EXTREME 0.11.21a: erase returns the next valid iterator.
                // The old range-for incremented an iterator to an erased node.
                for (auto pending = map_server_data.begin(); pending != map_server_data.end();) {
                    AP_GetServerDataRequest* failed = pending->second;
                    pending = map_server_data.erase(pending);
                    if (failed != nullptr) failed->status = AP_RequestStatus::Error;
                }]=])
    file(READ "${source_dir}/Archipelago.cpp" main)
    string(REPLACE "\r\n" "\n" main "${main}")
    string(FIND "${main}" "${marker}" fixed)
    if(fixed EQUAL -1)
        string(FIND "${main}" "${old_cleanup}" found)
        if(found EQUAL -1)
            message(FATAL_ERROR "SOH-EXTREME: this APCpp revision does not match the reviewed cleanup block. Nothing was overwritten. Supply its Archipelago.cpp for review.")
        endif()
        string(REPLACE "${old_cleanup}" "${new_cleanup}" main "${main}")
        set(init_anchor "void AP_Start() {")
        string(FIND "${main}" "${init_anchor}" found)
        if(found EQUAL -1)
            message(FATAL_ERROR "SOH-EXTREME: APCpp start signature changed. Nothing was overwritten.")
        endif()
        string(REPLACE "${init_anchor}" "${init_anchor}\n    logfunc(\"AP: ${marker}\");" main "${main}")
    else()
        string(FIND "${main}" "${new_cleanup}" found)
        if(found EQUAL -1)
            message(FATAL_ERROR "SOH-EXTREME: APCpp hotfix marker exists but its cleanup differs. Nothing was overwritten.")
        endif()
    endif()

    # One websocket producer and one game-thread consumer share messageQueue.
    # Even push_back vs pop_front/empty is undefined without synchronization.
    set(queue_marker "SOH-EXTREME synchronized AP message queue")
    string(FIND "${main}" "${queue_marker}" queue_fixed)
    if(queue_fixed EQUAL -1)
        set(old_queue [=[bool AP_IsMessagePending() {
    return !messageQueue.empty();
}

AP_Message* AP_GetLatestMessage() {
    return messageQueue.front();
}

void AP_ClearLatestMessage() {
    if (AP_IsMessagePending()) {
        delete messageQueue.front();
        messageQueue.pop_front();
    }
}]=])
        set(new_queue [=[bool AP_IsMessagePending() {
    std::lock_guard<std::mutex> lock(messageQueueMutex);
    return !messageQueue.empty();
}

AP_Message* AP_GetLatestMessage() {
    std::lock_guard<std::mutex> lock(messageQueueMutex);
    // Single consumer: the pointer stays valid until it calls ClearLatestMessage.
    return messageQueue.empty() ? nullptr : messageQueue.front();
}

void AP_ClearLatestMessage() {
    std::lock_guard<std::mutex> lock(messageQueueMutex);
    if (!messageQueue.empty()) {
        delete messageQueue.front();
        messageQueue.pop_front();
    }
}]=])
        string(FIND "${main}" "${old_queue}" queue_found)
        string(FIND "${main}" "std::deque<AP_Message*> messageQueue;" queue_decl)
        if(queue_found EQUAL -1 OR queue_decl EQUAL -1)
            message(FATAL_ERROR "SOH-EXTREME: APCpp message queue differs from the reviewed revision. Nothing was overwritten.")
        endif()
        string(REPLACE "${old_queue}" "${new_queue}" main "${main}")
        string(REPLACE "messageQueue.push_back(msg);" "AP_QueueMessage(msg);" main "${main}")
        string(REPLACE "std::deque<AP_Message*> messageQueue;" [=[// SOH-EXTREME synchronized AP message queue
std::deque<AP_Message*> messageQueue;
std::mutex messageQueueMutex;
static void AP_QueueMessage(AP_Message* message) {
    std::lock_guard<std::mutex> lock(messageQueueMutex);
    messageQueue.push_back(message);
}]=] main "${main}")
        string(PREPEND main "#include <mutex>\n")
    endif()

    # PrintJSON text is a string in the AP protocol, including player_id parts.
    # JsonCpp asInt() on that string throws on the websocket thread.
    set(old_player_text "msg->text += getPlayer(0, itr[\"text\"].asInt()).alias;")
    set(new_player_text [=[// SOH-EXTREME: parse string-valued PrintJSON player IDs.
                        const auto& part = itr["text"];
                        if (!part.isString() && !part.isInt()) continue;
                        const std::string value = part.asString();
                        try {
                            size_t consumed = 0;
                            const int slot = std::stoi(value, &consumed);
                            if (consumed == value.size() && map_players.count(slot))
                                msg->text += getPlayer(ap_player_team, slot).alias;
                            else msg->text += value;
                        } catch (const std::exception&) {
                            msg->text += value;
                        }]=])
    string(FIND "${main}" "${new_player_text}" player_fixed)
    if(player_fixed EQUAL -1)
        string(FIND "${main}" "${old_player_text}" player_found)
        if(player_found EQUAL -1)
            message(FATAL_ERROR "SOH-EXTREME: APCpp PrintJSON player text differs; nothing was overwritten.")
        endif()
        string(REPLACE "${old_player_text}" "${new_player_text}" main "${main}")
    endif()

    # Reader/FastWriter mutate their own parse/output buffers. Tracker Bounce
    # messages are sent on the game thread while the websocket thread parses
    # Received/Retrieved packets. Give each thread its own codec instances.
    # All extern declarations (including gifting/offline helpers) must agree.
    file(GLOB files "${source_dir}/Archipelago*.cpp" "${source_dir}/Archipelago*.h")
    set(def_reader 0)
    set(def_writer 0)
    set(index 0)
    foreach(path IN LISTS files)
        file(READ "${path}" before)
        string(REPLACE "\r\n" "\n" text "${before}")
        if(path STREQUAL "${source_dir}/Archipelago.cpp")
            set(text "${main}")
        endif()
        foreach(pair "Reader;reader" "FastWriter;writer")
            list(GET pair 0 type)
            list(GET pair 1 name)
            string(REGEX MATCHALL "(^|\n)[ \t]*(thread_local[ \t]+)?Json::${type}[ \t]+${name}[ \t]*" definitions "${text}")
            list(LENGTH definitions count)
            math(EXPR def_${name} "${def_${name}} + ${count}")
            # Separate replacements: CMake rejects a replacement backreference
            # to an optional group that did not participate in a match.
            string(REGEX REPLACE "(^|\n)([ \t]*)extern[ \t]+(thread_local[ \t]+)?Json::${type}[ \t]+${name}[ \t]*;"
                "\\1\\2extern thread_local Json::${type} ${name};" text "${text}")
            string(REGEX REPLACE "(^|\n)([ \t]*)(thread_local[ \t]+)?Json::${type}[ \t]+${name}[ \t]*;"
                "\\1\\2thread_local Json::${type} ${name};" text "${text}")
        endforeach()
        # Validate everything before writing the first file; no half-applied set.
        set(path_${index} "${path}")
        set(before_${index} "${before}")
        set(after_${index} "${text}")
        math(EXPR index "${index} + 1")
    endforeach()
    if(NOT def_reader EQUAL 1 OR NOT def_writer EQUAL 1)
        message(FATAL_ERROR "SOH-EXTREME: expected one APCpp Reader and one FastWriter definition; found ${def_reader}/${def_writer}. Nothing was overwritten.")
    endif()
    math(EXPR last "${index} - 1")
    foreach(i RANGE ${last})
        if(NOT "${before_${i}}" STREQUAL "${after_${i}}")
            if(NOT EXISTS "${path_${i}}.before-soh-0.11.21a")
                configure_file("${path_${i}}" "${path_${i}}.before-soh-0.11.21a" COPYONLY)
            endif()
            file(WRITE "${path_${i}}.soh-safety.tmp" "${after_${i}}")
            file(RENAME "${path_${i}}.soh-safety.tmp" "${path_${i}}")
        endif()
    endforeach()
    message(STATUS "SOH-EXTREME: APCpp cleanup and per-thread JSON safety fixes verified")
endfunction()

if(NOT DEFINED apcpp_SOURCE_DIR OR apcpp_SOURCE_DIR STREQUAL "")
    message(FATAL_ERROR "Include SohExtremeAPCppSafety.cmake after FetchContent_MakeAvailable(apcpp).")
endif()
soh_extreme_repair_apcpp("${apcpp_SOURCE_DIR}")

# Exact target outputs, not the newest EXE/DLL found by a directory scan.
if(TARGET soh AND TARGET APCpp)
    file(GENERATE OUTPUT "${CMAKE_BINARY_DIR}/soh-extreme-runtime-$<CONFIG>.txt"
        CONTENT "$<TARGET_FILE:soh>\n$<TARGET_FILE:APCpp>\n")
endif()
