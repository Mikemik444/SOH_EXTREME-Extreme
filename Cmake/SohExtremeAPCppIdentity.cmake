# Publish server-authenticated room identity on the network thread, before slot
# data. This avoids reading mutable APCpp strings from the gameplay thread.
include_guard(GLOBAL)
function(soh_extreme_ap_identity source_dir)
    file(LOCK "${source_dir}/.soh-extreme-identity.lock" GUARD FUNCTION TIMEOUT 120)
    file(READ "${source_dir}/Archipelago.cpp" original)
    string(REPLACE "\r\n" "\n" cpp "${original}")
    set(team [=[            ap_player_team = root[i]["team"].asInt();]=])
    set(hints [=[            sohHintKey = "_read_hints_" + std::to_string(ap_player_team) + "_" + std::to_string(ap_player_id);
            sohHints = Json::nullValue;
            sohHintsLoaded = false;]=])
    set(seed_hints [=[            sohLegacySeedHints = root[i]["slot_data"]["static_hints"];
            sohRichSeedHints = root[i]["slot_data"]["extreme_hint_data"];
            sohPublishedSeedHints.clear();]=])
    set(callback [=[            // SOH-EXTREME connection identity 0.11.61: this is local metadata,
            // derived from RoomInfo/Connected, never a supplied slot_data value.
            const auto identityCallback = map_slotdata_callback_raw.find("_soh_connection_identity");
            if (identityCallback != map_slotdata_callback_raw.end()) {
                Json::Value identity;
                identity["seed"] = lib_room_info.seed_name;
                identity["team"] = ap_player_team;
                identity["slot"] = ap_player_id;
                identity["name"] = ap_player_name;
                identityCallback->second(writer.write(identity));
            }]=])

    # The old identity patch split the new hint setup. The next configure could
    # then insert a second hint setup before rejecting the identity layout.
    # Normalize only this bounded Connected setup, accepting exact known blocks
    # in their historical orders. Unknown edits remain a hard error, not a reason
    # to replace the whole dependency. Keep the complete hint anchor contiguous.
    string(REPLACE "${team}" "" stripped "${cpp}")
    string(LENGTH "${cpp}" full_len)
    string(LENGTH "${stripped}" stripped_len)
    string(LENGTH "${team}" anchor_len)
    math(EXPR removed "${full_len} - ${stripped_len}")
    if(NOT removed EQUAL anchor_len)
        message(FATAL_ERROR "SOH-EXTREME: missing or duplicate APCpp identity anchor; nothing overwritten.")
    endif()
    string(FIND "${cpp}" "${team}" start)
    string(SUBSTRING "${cpp}" ${start} -1 tail)
    string(FIND "${tail}" "            resetItemValues();" stop)
    if(stop EQUAL -1)
        message(FATAL_ERROR "SOH-EXTREME: APCpp Connected setup boundary missing; nothing overwritten.")
    endif()
    string(SUBSTRING "${tail}" 0 ${stop} setup)
    set(remainder "${setup}")
    foreach(part IN ITEMS hints seed_hints callback)
        set(block "${${part}}\n")
        string(REPLACE "${block}" "" stripped "${remainder}")
        string(LENGTH "${remainder}" full_len)
        string(LENGTH "${stripped}" stripped_len)
        string(LENGTH "${block}" block_len)
        math(EXPR count_${part} "(${full_len} - ${stripped_len}) / ${block_len}")
        set(remainder "${stripped}")
    endforeach()
    if(NOT remainder STREQUAL "${team}\n" OR
       count_hints LESS 1 OR count_hints GREATER 2 OR
       count_seed_hints GREATER 2 OR count_callback GREATER 1)
        message(FATAL_ERROR "SOH-EXTREME: changed APCpp identity setup; nothing overwritten.")
    endif()
    set(fixed "${team}\n${hints}\n")
    if(count_seed_hints GREATER 0)
        string(APPEND fixed "${seed_hints}\n")
    endif()
    string(APPEND fixed "${callback}\n")
    string(REPLACE "${setup}" "${fixed}" cpp "${cpp}")

    # Server-supplied slot data must never impersonate this local callback.
    set(old_key [=[                std::string key = slot_itr.key().asString();]=])
    set(new_key [=[                std::string key = slot_itr.key().asString();
                if (key == "_soh_connection_identity") continue; // local-only callback]=])
    string(FIND "${cpp}" "${new_key}" guarded)
    if(guarded EQUAL -1)
        string(REPLACE "${old_key}" "" stripped "${cpp}")
        string(LENGTH "${cpp}" full_len)
        string(LENGTH "${stripped}" stripped_len)
        string(LENGTH "${old_key}" anchor_len)
        math(EXPR removed "${full_len} - ${stripped_len}")
        if(NOT removed EQUAL anchor_len)
            message(FATAL_ERROR "SOH-EXTREME: missing or duplicate APCpp identity key anchor; nothing overwritten.")
        endif()
        string(REPLACE "${old_key}" "${new_key}" cpp "${cpp}")
    endif()
    if(NOT cpp STREQUAL original)
        file(WRITE "${source_dir}/Archipelago.cpp" "${cpp}")
    endif()
endfunction()
soh_extreme_ap_identity("${apcpp_SOURCE_DIR}")
