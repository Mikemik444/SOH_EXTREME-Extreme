// Exercises the built APCpp DLL's actual packet parser without opening a socket.
#include "Archipelago.h"
#include <cassert>
#include <iostream>
#include <string>
bool parse_response(std::string message, std::string& request);
std::string request;
void packet(const std::string& json) { request.clear(); parse_response(json, request); }
AP_HintListMessage* hints() {
    while (AP_IsMessagePending()) {
        auto* message = AP_GetLatestMessage();
        if (message && message->type == AP_MessageType::HintList) return static_cast<AP_HintListMessage*>(message);
        AP_ClearLatestMessage();
    }
    return nullptr;
}
int main() {
    AP_SetLoggingCallback([](std::string) {});
    AP_Init("localhost:1", "HintTestGame", "Tester", "");
    AP_SetItemClearCallback([]() {});
    AP_SetItemRecvCallback([](int64_t, bool) {});
    AP_SetLocationCheckedCallback([](int64_t) {});
    packet(R"([{"cmd":"RoomInfo","version":{"major":0,"minor":6,"build":7},"tags":[],"password":false,"permissions":{},"hint_cost":10,"location_check_points":1,"datapackage_checksums":{"HintTestGame":"hint-protocol-20260929a","OtherGame":"hint-protocol-20260929b"},"seed_name":"test","time":0}])");
    packet(R"([{"cmd":"Connected","team":2,"slot":1,"checked_locations":[],"players":[{"team":2,"slot":1,"name":"Tester","alias":"Tester"},{"team":2,"slot":2,"name":"Friend","alias":"Friend"}],"slot_info":{"1":{"game":"HintTestGame"},"2":{"game":"OtherGame"}},"slot_data":{}}])");
    assert(request.find("_read_hints_2_1") != std::string::npos);
    assert(request.find("SetNotify") != std::string::npos && request.find("\"Get\"") != std::string::npos);
    packet(R"([{"cmd":"Retrieved","keys":{"_read_hints_2_1":[{"finding_player":1,"receiving_player":2,"item":123,"location":456,"found":false,"entrance":"Forest"}]}}])");
    // Cached packages are allowed; the final result must also resolve after refresh.
    while (AP_IsMessagePending()) AP_ClearLatestMessage();
    packet(R"([{"cmd":"DataPackage","data":{"games":{"HintTestGame":{"checksum":"hint-protocol-20260929a","item_name_to_id":{},"location_name_to_id":{"Deku Scrub":456}},"OtherGame":{"checksum":"hint-protocol-20260929b","item_name_to_id":{"Important Sword":123},"location_name_to_id":{}}}}}])");
    auto* snapshot = hints();
    assert(snapshot && snapshot->hints.size() == 1);
    assert(snapshot->hints[0].item == "Important Sword");
    assert(snapshot->hints[0].location == "Deku Scrub");
    assert(snapshot->hints[0].finder == "Tester" && snapshot->hints[0].recipient == "Friend");
    assert(snapshot->hints[0].entrance == "Forest" && !snapshot->hints[0].found);
    AP_ClearLatestMessage();
    packet(R"([{"cmd":"SetReply","key":"_read_hints_2_1","value":[{"finding_player":1,"receiving_player":2,"item":123,"location":456,"found":true}]}])");
    snapshot = hints(); assert(snapshot && snapshot->hints.size() == 1 && snapshot->hints[0].found);
    AP_ClearLatestMessage();
    packet(R"([{"cmd":"Retrieved","keys":{"_read_hints_2_1":[null,{"finding_player":"invalid"},{"finding_player":1,"receiving_player":2,"item":123,"location":456,"found":false}]}}])");
    snapshot = hints(); assert(snapshot && snapshot->hints.size() == 1); AP_ClearLatestMessage();
    packet(R"([{"cmd":"Retrieved","keys":{"_read_hints_2_1":[]}}])");
    snapshot = hints(); assert(snapshot && snapshot->hints.empty()); AP_ClearLatestMessage();
    packet(R"([{"cmd":"PrintJSON","data":[{"type":"player_id","text":"2"},{"text":" joined"}]}])");
    assert(AP_IsMessagePending() && AP_GetLatestMessage()->text == "Friend joined"); AP_ClearLatestMessage();
    packet(R"([{"cmd":"PrintJSON","data":[{"type":"player_id","text":"not-a-slot"}]}])");
    assert(AP_IsMessagePending() && AP_GetLatestMessage()->text == "not-a-slot"); AP_ClearLatestMessage();
    AP_Shutdown();
    std::cout << "PASS built DLL: subscription, nonzero team, cross-game names, delayed data package, found updates, malformed rows, empty hints\n";
}
