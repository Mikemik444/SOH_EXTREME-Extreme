// Exercise the production APCpp packet parser without opening a network socket.
#include "Archipelago.h"
#include <cassert>
#include <iostream>
#include <string>
#include <vector>
bool parse_response(std::string message, std::string& request);
std::string request;
void packet(const std::string& json) { request.clear(); parse_response(json, request); }
int main() {
    AP_SetLoggingCallback([](std::string) {});
    AP_Init("localhost:1", "SOH-EXTREME", "Player", "");
    AP_SetItemClearCallback([]() {});
    AP_SetItemRecvCallback([](int64_t, bool) {});
    AP_SetLocationCheckedCallback([](int64_t) {});
    std::vector<std::string> events;
    AP_RegisterSlotDataRawCallback("_soh_connection_identity", [&](std::string raw) {events.push_back(raw);});
    AP_RegisterSlotDataRawCallback("extreme_soh_cvars", [&](std::string) {events.push_back("settings");});
    packet(R"([{"cmd":"RoomInfo","version":{"major":0,"minor":6,"build":8},"tags":[],"password":false,"permissions":{},"hint_cost":10,"location_check_points":1,"datapackage_checksums":{},"seed_name":"original-seed","time":0}])");
    assert(events.empty()); // A RoomInfo alone is not an authenticated slot.
    packet(R"([{"cmd":"ConnectionRefused","errors":["InvalidPassword"]}])");
    assert(events.empty());
    const std::string connected=R"([{"cmd":"Connected","team":2,"slot":3,"checked_locations":[],"players":[{"team":2,"slot":3,"name":"Player","alias":"Alias"}],"slot_info":{"3":{"game":"SOH-EXTREME"}},"slot_data":{"_soh_connection_identity":{"seed":"forged"},"extreme_soh_cvars":{"Climb":1}}}])";
    packet(connected);
    assert(events.size()==2 && events[1]=="settings");
    assert(events[0].find("original-seed")!=std::string::npos);
    assert(events[0].find("Player")!=std::string::npos && events[0].find("Alias")==std::string::npos);
    assert(events[0].find("forged")==std::string::npos);
    assert(events[0].find("\"team\":2")!=std::string::npos);
    assert(events[0].find("\"slot\":3")!=std::string::npos);
    events.clear();packet(connected);assert(events.size()==2); // Reconnection republishes ownership first.
    AP_Shutdown();
    std::cout<<"PASS APCpp identity: RoomInfo/refusal gating, stable player name, team/slot, callback ordering, spoofed slot_data exclusion, reconnect\n";
}
