#include <iostream>
#include <unordered_map>
#include <string>
#include <cassert>
#include "EntranceRouting.h"
int main() {
    std::unordered_map<std::string,int> m;
    m["EntranceRandomizerRevision"]=1;
    m["EntranceRiverPathsRevision"]=1;
    for (const auto& row : SohExtreme::kEntranceEndpoints)
        m["EntranceMap."+std::to_string(row.id)]=row.id;
    m["EntranceMapRouteCount"]=721;
    m["EntranceMapFingerprint"]=1081211733;
    SohExtreme::EntranceRouting r;
    std::string error;
    if (!r.Configure(m,error)) {std::cerr << "identity map failed: " << error << "\n"; return 1;}
    if (r.Routes().size()!=721) return 2;
    // A missing entry must be detected rather than silently falling back to vanilla.
    m.erase("EntranceMap.99");
    error.clear();
    if (r.Configure(m,error)) {std::cerr<<"accepted truncated map\n";return 3;}
    if (error.find("source count")==std::string::npos) {std::cerr<<error;return 4;}
    m["EntranceMap.99"]=99;
    m["EntranceMapFingerprint"]=1081211732;
    error.clear();
    if (r.Configure(m,error)) {std::cerr<<"accepted altered hash\n";return 5;}
    if (error.find("checksum mismatch")==std::string::npos) {std::cerr<<error;return 6;}
    std::cout << "PASS native map count, checksum and 721 identity routes\n";
}
