# Copy the recipient's game into LocationInfo on the network thread. Ship the
# rebuilt APCpp.dll together with soh.exe because AP_NetworkItem gains a field.
include_guard(GLOBAL)
function(soh_extreme_ap_models source_dir)
    file(LOCK "${source_dir}/.soh-extreme-models.lock" GUARD FUNCTION TIMEOUT 120)
    file(READ "${source_dir}/Archipelago.cpp" cpp)
    file(READ "${source_dir}/Archipelago.h" header)
    string(REPLACE "\r\n" "\n" cpp "${cpp}")
    string(REPLACE "\r\n" "\n" header "${header}")
    set(old [==[    std::string playerName;
};]==])
    set(new [==[    std::string playerName;
    // SOH-EXTREME: authoritative recipient game, copied with the scout.
    std::string itemGame;
};]==])
    string(FIND "${header}" "${new}" fixed)
    if(fixed EQUAL -1)
        string(FIND "${header}" "${old}" found)
        if(found EQUAL -1)
            message(FATAL_ERROR "SOH-EXTREME: APCpp model header does not match the pinned source; nothing was overwritten.")
        endif()
        string(REPLACE "${old}" "${new}" header "${header}")
    endif()
    set(old [==[                item.itemName = getItemName(player.game, item.item);]==])
    set(new [==[                item.itemGame = player.game;
                item.itemName = getItemName(player.game, item.item);]==])
    string(FIND "${cpp}" "${new}" fixed)
    if(fixed EQUAL -1)
        string(FIND "${cpp}" "${old}" found)
        if(found EQUAL -1)
            message(FATAL_ERROR "SOH-EXTREME: APCpp model callback does not match the pinned source; nothing was overwritten.")
        endif()
        string(REPLACE "${old}" "${new}" cpp "${cpp}")
    endif()
    file(WRITE "${source_dir}/Archipelago.cpp" "${cpp}")
    file(WRITE "${source_dir}/Archipelago.h" "${header}")
endfunction()
soh_extreme_ap_models("${apcpp_SOURCE_DIR}")
