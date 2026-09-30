// Exercises the built APCpp DLL parser/callback ABI without opening a socket.
#include "Archipelago.h"
#include <cassert>
#include <iostream>
#include <string>
#include <vector>
bool parse_response(std::string message, std::string& request);
void packet(const std::string& json) { std::string reply; parse_response(json, reply); }
int main() {
    AP_SetLoggingCallback([](std::string) {});
    AP_Init("localhost:1", "SOH-EXTREME", "Tester", "");
    AP_SetItemClearCallback([]() {});
    AP_SetItemRecvCallback([](int64_t, bool) {});
    AP_SetLocationCheckedCallback([](int64_t) {});
    std::vector<AP_NetworkItem> scouts;
    AP_SetLocationInfoCallback([&](std::vector<AP_NetworkItem> items) { scouts = std::move(items); });
    packet(R"([{"cmd":"RoomInfo","version":{"major":0,"minor":6,"build":7},"tags":[],"password":false,"permissions":{},"hint_cost":10,"location_check_points":1,"datapackage_checksums":{"SOH-EXTREME":"enemy-model-local","OtherGame":"enemy-model-other"},"seed_name":"test","time":0}])");
    packet(R"([{"cmd":"Connected","team":0,"slot":1,"checked_locations":[],"players":[{"team":0,"slot":1,"name":"Tester","alias":"Tester"},{"team":0,"slot":2,"name":"Same","alias":"Same"},{"team":0,"slot":3,"name":"Other","alias":"Other"}],"slot_info":{"1":{"game":"SOH-EXTREME"},"2":{"game":"SOH-EXTREME"},"3":{"game":"OtherGame"}},"slot_data":{}}])");
    packet(R"([{"cmd":"DataPackage","data":{"games":{"SOH-EXTREME":{"checksum":"enemy-model-local","item_name_to_id":{"Kokiri Sword":1},"location_name_to_id":{"Enemy":9800001}},"OtherGame":{"checksum":"enemy-model-other","item_name_to_id":{"Kokiri Sword":1},"location_name_to_id":{}}}}}])");
    packet(R"([{"cmd":"LocationInfo","locations":[{"item":1,"location":9800001,"player":1,"flags":1},{"item":1,"location":9800002,"player":2,"flags":1},{"item":1,"location":9800003,"player":3,"flags":1},{"item":1,"location":9800004,"player":99,"flags":1}]}])");
    assert(scouts.size() == 4);
    assert(scouts[0].itemGame == "SOH-EXTREME" && scouts[0].player == 1);
    assert(scouts[1].itemGame == "SOH-EXTREME" && scouts[1].player == 2);
    assert(scouts[2].itemGame == "OtherGame" && scouts[2].player == 3);
    assert(scouts[3].itemGame.empty());
    assert(scouts[0].itemName == "Kokiri Sword" && scouts[2].itemName == scouts[0].itemName);
    assert(scouts[0].item == scouts[2].item && scouts[2].flags == 1);
    // Aliases and name/ID collisions do not change the recipient game.
    packet(R"([{"cmd":"RoomUpdate","players":[{"team":0,"slot":3,"alias":"Same"}]}])");
    packet(R"([{"cmd":"LocationInfo","locations":[{"item":1,"location":9800003,"player":3,"flags":2}]}])");
    assert(scouts.size() == 1 && scouts[0].playerName == "Same");
    assert(scouts[0].itemGame == "OtherGame" && scouts[0].flags == 2);
    AP_Shutdown();
    std::cout << "PASS LocationInfo game identity and callback ABI\n";
}
