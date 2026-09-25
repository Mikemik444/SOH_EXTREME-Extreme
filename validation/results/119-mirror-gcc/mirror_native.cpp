
#include <atomic>
#include <mutex>
#include <cstddef>
#include <cstdint>
#include <deque>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>
#include <random>
#include <chrono>
#include <fstream>
#include <iostream>
#include <functional>
#include "soh/Network/Archipelago/TrackerMirror.h"
#define private public
#include "soh/Network/Archipelago/ArchipelagoClient.h"
#undef private
bool authenticated=true;
struct AP_Bounce { std::vector<std::string>* tags=nullptr;std::string data; };
std::vector<std::string> requests;
int playerId=1;int AP_GetPlayerID(){return playerId;}
void AP_SendBounce(const AP_Bounce& b){requests.push_back(b.data);}
bool ArchipelagoClient::IsAuthenticated()const{return authenticated;}
ArchipelagoClient& ArchipelagoClient::GetInstance(){static ArchipelagoClient c;return c;}
struct ImVec2 {float x,y;ImVec2(float a,float b):x(a),y(b){}};
namespace ImGui {
std::vector<std::string> rendered;
void TextWrapped(const char*,...){};void Text(const char*,...){};
void TextUnformatted(const char* s){rendered.emplace_back(s);}
bool Button(const char*){return false;}void Separator(){};
bool BeginChild(const char*,ImVec2,bool){return true;}void EndChild(){};
bool IsItemHovered(){return false;}void BeginTooltip(){};void EndTooltip(){};
}
double FinderMirrorClock() {
    return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count();
}
void ArchipelagoClient::ResetFinderMirror() {
    // Not an authentication secret: a collision-resistant per-save/connection
    // token preventing accidental use of another slot's or an old save's data.
    static constexpr char hex[] = "0123456789abcdef";
    std::random_device random;
    std::string nonce(32, '0');
    for (auto& c : nonce) c = hex[random() & 15u];
    finderMirror.Reset(nonce);
    pendingFinderPayload.clear();
    finderMirrorError.clear();
    finderNextRequest = 0.0;
}
void ArchipelagoClient::RefreshFinderMirror() {
    // Called from the game UI; do not erase a valid snapshot just for a refresh.
    finderNextRequest = 0.0;
}
const SohExtreme::TrackerSnapshot* ArchipelagoClient::GetFinderSnapshot(std::string& status) {
    if (!currentSaveIsArchipelago || !IsAuthenticated()) {
        status = "Connect the game and SOH-EXTREME Universal Tracker to the same slot.";
        return nullptr;
    }
    if (!activeLocationsLoaded) {
        status = "Waiting for the server's active location manifest...";
        return nullptr;
    }
    std::string payload;
    uint64_t received = 0;
    std::set<int64_t> active;
    {
        std::scoped_lock lock(queueMutex);
        payload.swap(pendingFinderPayload);
        received = incomingItemOrdinal;
        active.insert(activeLocations.begin(), activeLocations.end());
    }
    const double now = FinderMirrorClock();
    const auto slot = static_cast<uint32_t>(AP_GetPlayerID());
    if (!payload.empty()) {
        try {
            finderMirror.Accept(SohExtreme::DecodeTrackerSnapshot(payload), slot, now, finderMirrorError);
        } catch (const std::exception& error) {
            finderMirrorError = std::string("Invalid tracker snapshot: ") + error.what();
        }
    }
    if (now >= finderNextRequest) {
        const uint64_t request = finderMirror.NextRequest();
        AP_Bounce bounce{};
        std::vector<std::string> tags{ "SOHExtremeUT" };
        bounce.tags = &tags;
        bounce.data = "{\"soh_extreme_tracker\":\"SOHExtremeFinder1\",\"kind\":\"request\",\"slot\":" +
            std::to_string(slot) + ",\"nonce\":\"" + finderMirror.Nonce() + "\",\"request\":" +
            std::to_string(request) + "}";
        AP_SendBounce(bounce);
        finderNextRequest = now + 2.0;
    }
    std::set<int64_t> checked;
    for (const auto id : reportedLocations) if (active.count(id)) checked.insert(id);
    const auto* result = finderMirror.Current(slot, received, active, checked, now, status);
    if (!result && !finderMirrorError.empty()) status += " " + finderMirrorError;
    return result;
}static void DrawUniversalFinderMirror() {
    auto& client = ArchipelagoClient::GetInstance();
    std::string status;
    const auto* snapshot = client.GetFinderSnapshot(status);
    ImGui::TextWrapped("%s", status.c_str());
    if (ImGui::Button("Refresh Universal Tracker")) client.RefreshFinderMirror();
    if (snapshot == nullptr) {
        ImGui::Separator();
        ImGui::TextWrapped("Open SOH-EXTREME Universal Tracker from Archipelago Launcher and connect it to this game's slot. "
                           "This view never falls back to approximate native availability.");
        return;
    }
    size_t normal = 0, glitched = 0;
    for (const auto& row : snapshot->rows) { if (row.state == 1) ++normal; else ++glitched; }
    ImGui::Text("In logic: %u   Glitched: %u   Checked: %u / %u",
        static_cast<unsigned>(normal), static_cast<unsigned>(glitched),
        static_cast<unsigned>(snapshot->checked.size()), static_cast<unsigned>(snapshot->active.size()));
    if (snapshot->manualCount || snapshot->ignoredCount) {
        ImGui::TextWrapped("UT overrides active: %u manually added items; %u ignored locations. These are mirrored too.",
            snapshot->manualCount, snapshot->ignoredCount);
    }
    if (snapshot->received > client.GetAppliedItemCount()) {
        ImGui::TextWrapped("AP has delivered %llu items; %llu are applied to this save. This list matches UT's received inventory.",
            static_cast<unsigned long long>(snapshot->received),
            static_cast<unsigned long long>(client.GetAppliedItemCount()));
    }
    ImGui::Separator();
    if (ImGui::BeginChild("SOHExtremeUTRows", ImVec2(0, 0), false)) {
        if (snapshot->rows.empty()) ImGui::TextUnformatted("Universal Tracker has no remaining in-logic checks.");
        for (const auto& row : snapshot->rows) {
            // Never interpret network labels as printf formats or ImGui IDs.
            const std::string line = (row.state == 2 ? "[Glitched] " : "") + row.region + " | " + row.name;
            ImGui::TextUnformatted(line.c_str());
            if (ImGui::IsItemHovered()) {
                ImGui::BeginTooltip();
                ImGui::Text("AP location ID: %lld", static_cast<long long>(row.id));
                ImGui::EndTooltip();
            }
        }
    }
    ImGui::EndChild();
}
int checks=0;
void ck(bool value,const char* name){++checks;if(!value){std::cerr<<"FAIL "<<name<<"\n";std::exit(1);}}
int main(int argc,char** argv){
 if(argc!=2)return 2;
 std::ifstream input(argv[1]);std::string payload((std::istreambuf_iterator<char>(input)),{});
 auto snapshot=SohExtreme::DecodeTrackerSnapshot(payload);
 using namespace SohExtreme;
 TrackerMirrorState store;store.Reset(snapshot.nonce);store.NextRequest();std::string status;
 auto valid=snapshot;valid.request=1;valid.revision=1;
 ck(store.Accept(valid,valid.slot,100,status),"initial snapshot");
 ck(store.Current(valid.slot,valid.received,valid.active,valid.checked,100,status)!=nullptr,"ready exact snapshot");
 ck(store.Current(valid.slot,valid.received+1,valid.active,valid.checked,100,status)==nullptr,"pending receipt rejected");
 auto extra=valid.active;extra.insert(999999999);
 ck(store.Current(valid.slot,valid.received,extra,valid.checked,100,status)==nullptr,"different active set rejected");
 extra=valid.checked;extra.insert(999999999);
 ck(store.Current(valid.slot,valid.received,valid.active,extra,100,status)==nullptr,"different checked set rejected");
 ck(store.Current(valid.slot,valid.received,valid.active,valid.checked,111,status)==nullptr,"expired snapshot hidden");
 ck(!store.Accept(valid,valid.slot,101,status),"duplicate revision rejected");
 auto bad=valid;bad.revision=2;bad.version="0.11.18";
 ck(!store.Accept(bad,valid.slot,101,status),"version mismatch rejected");
 bad=valid;bad.revision=2;bad.nonce=std::string(32,'e');
 ck(!store.Accept(bad,valid.slot,101,status),"nonce mismatch rejected");
 bad=valid;bad.revision=2;bad.slot++;
 ck(!store.Accept(bad,valid.slot,101,status),"slot mismatch rejected");
 bad=valid;bad.revision=2;bad.request=9;
 ck(!store.Accept(bad,valid.slot,101,status),"unsent request rejected");
 bad=valid;bad.revision=2;bad.producer="other";
 ck(!store.Accept(bad,valid.slot,101,status),"second producer pinned out");
 ck(store.Accept(bad,valid.slot,112,status),"tracker restart can recover after expiry");
 store.Reset(std::string(32,'d'));
 ck(store.Current(valid.slot,valid.received,valid.active,valid.checked,112,status)==nullptr,"save reset discards data");
 ck(!store.Accept(valid,valid.slot,112,status),"old save response rejected");
 for(const std::string invalid:{"", "=AAA", "A===", "AA=A", "AAAA=", "!!!!", "AB==", "AAB="}){
  bool failed=false;try{DecodeTrackerSnapshot(invalid);}catch(const std::exception&){failed=true;}
  ck(failed,"malformed payload rejected");
 }
 auto& client=ArchipelagoClient::GetInstance();client.ResetFinderMirror();
 client.finderMirror.Reset(snapshot.nonce);client.finderMirror.NextRequest();
 playerId=static_cast<int>(snapshot.slot);client.currentSaveIsArchipelago=true;client.activeLocationsLoaded=true;
 client.activeLocations.insert(snapshot.active.begin(),snapshot.active.end());
 client.reportedLocations.insert(snapshot.checked.begin(),snapshot.checked.end());
 client.incomingItemOrdinal=snapshot.received;client.appliedItemCount=snapshot.received;
 client.pendingFinderPayload=payload;
 ck(client.GetFinderSnapshot(status)!=nullptr,"actual client accepts matching payload");
 ck(!requests.empty()&&requests.back().find("SOHExtremeFinder1")!=std::string::npos,"actual client sends request");
 DrawUniversalFinderMirror();
 ck(ImGui::rendered.size()==snapshot.rows.size()||snapshot.rows.empty(),"actual view draws full list");
 if(!snapshot.rows.empty())for(size_t i=0;i<snapshot.rows.size();++i){
  const auto& row=snapshot.rows[i];
  const std::string expected=(row.state==2?"[Glitched] ":"")+row.region+" | "+row.name;
  ck(ImGui::rendered[i]==expected,"actual view matches received labels/state");
 }
 authenticated=false;ck(client.GetFinderSnapshot(status)==nullptr,"disconnected hides availability");
 std::cout<<"CHECKS\t"<<checks<<"\n";
 for(const auto& row:snapshot.rows)std::cout<<row.id<<"\t"<<unsigned(row.state)<<"\t"<<row.region<<" | "<<row.name<<"\n";
 return 0;
}
