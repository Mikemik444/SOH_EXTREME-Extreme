# Publish server-authenticated room identity on the network thread, before slot
# data. This avoids reading mutable APCpp strings from the gameplay thread.
include_guard(GLOBAL)
function(soh_extreme_ap_identity source_dir)
    file(LOCK "${source_dir}/.soh-extreme-identity.lock" GUARD FUNCTION TIMEOUT 120)
    file(READ "${source_dir}/Archipelago.cpp" cpp)
    string(REPLACE "\r\n" "\n" cpp "${cpp}")
    # Keep the hints patch's four-line anchor contiguous so both dependency
    # patches remain idempotent when the entire configure sequence runs again.
    set(old [=[            ap_player_team = root[i]["team"].asInt();
            sohHintKey = "_read_hints_" + std::to_string(ap_player_team) + "_" + std::to_string(ap_player_id);
            sohHints = Json::nullValue;
            sohHintsLoaded = false;]=])
    set(new [=[            ap_player_team = root[i]["team"].asInt();
            sohHintKey = "_read_hints_" + std::to_string(ap_player_team) + "_" + std::to_string(ap_player_id);
            sohHints = Json::nullValue;
            sohHintsLoaded = false;
            // SOH-EXTREME connection identity 0.11.61: this is local metadata,
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
    set(old_key [=[                std::string key = slot_itr.key().asString();]=])
    set(new_key [=[                std::string key = slot_itr.key().asString();
                if (key == "_soh_connection_identity") continue; // local-only callback]=])
    # Upgrade the exact 0.11.61 layout, including a hints pass that has already
    # reinserted its setup before the old callback. Keep unknown edits untouched.
    set(hints [=[            sohHintKey = "_read_hints_" + std::to_string(ap_player_team) + "_" + std::to_string(ap_player_id);
            sohHints = Json::nullValue;
            sohHintsLoaded = false;]=])
    string(REPLACE "${hints}\n" "" legacy "${new}")
    foreach(previous IN ITEMS "${legacy}\n${hints}" "${new}\n${hints}")
        string(FIND "${cpp}" "${previous}" found)
        if(NOT found EQUAL -1)
            string(REPLACE "${previous}" "" stripped "${cpp}")
            string(LENGTH "${cpp}" full_len)
            string(LENGTH "${stripped}" stripped_len)
            string(LENGTH "${previous}" anchor_len)
            math(EXPR removed "${full_len} - ${stripped_len}")
            if(NOT removed EQUAL anchor_len)
                message(FATAL_ERROR "SOH-EXTREME: duplicate legacy APCpp identity; nothing overwritten.")
            endif()
            string(REPLACE "${previous}" "${new}" cpp "${cpp}")
        endif()
    endforeach()
    foreach(pair IN ITEMS identity key)
        if(pair STREQUAL "identity")
            set(before "${old}")
            set(after "${new}")
        else()
            set(before "${old_key}")
            set(after "${new_key}")
        endif()
        string(FIND "${cpp}" "${after}" fixed)
        if(fixed EQUAL -1)
            string(FIND "${cpp}" "SOH-EXTREME connection identity 0.11.61" marker)
            if(pair STREQUAL "identity" AND NOT marker EQUAL -1)
                message(FATAL_ERROR "SOH-EXTREME: changed APCpp identity patch; nothing overwritten.")
            endif()
            string(FIND "${cpp}" "${before}" found)
            if(found EQUAL -1)
                message(FATAL_ERROR "SOH-EXTREME: APCpp identity anchor missing; nothing overwritten.")
            endif()
            string(REPLACE "${before}" "" stripped "${cpp}")
            string(LENGTH "${cpp}" full_len)
            string(LENGTH "${stripped}" stripped_len)
            string(LENGTH "${before}" anchor_len)
            math(EXPR removed "${full_len} - ${stripped_len}")
            if(NOT removed EQUAL anchor_len)
                message(FATAL_ERROR "SOH-EXTREME: duplicate APCpp identity anchor; nothing overwritten.")
            endif()
            string(REPLACE "${before}" "${after}" cpp "${cpp}")
        endif()
    endforeach()
    file(WRITE "${source_dir}/Archipelago.cpp" "${cpp}")
endfunction()
soh_extreme_ap_identity("${apcpp_SOURCE_DIR}")
