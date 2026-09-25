#pragma once
#include <cstdint>
#include <stdexcept>
#include <string>

namespace SohExtreme {
inline std::string TrackerJsonString(const std::string& value) {
    std::string out = "\"";
    const char* hex = "0123456789abcdef";
    for (const unsigned char c : value) {
        if (c == '"' || c == '\\') { out += '\\'; out += static_cast<char>(c); }
        else if (c < 32) { out += "\\u00"; out += hex[c >> 4]; out += hex[c & 15]; }
        else out += static_cast<char>(c);
    }
    return out + "\"";
}
inline std::string MakeTrackerWorkerBootstrap(const std::string& server, const std::string& name,
                                               const std::string& password, uint32_t slot,
                                               const std::string& nonce) {
    if (server.empty() || server.size() > 4096 || name.empty() || name.size() > 512 ||
        password.size() > 8192 || nonce.size() != 32 || slot == 0 || slot > 65535)
        throw std::invalid_argument("Invalid AP tracker startup fields");
    std::string result = "{\"server\":" + TrackerJsonString(server) + ",\"slot_name\":" + TrackerJsonString(name) +
        ",\"password\":" + TrackerJsonString(password) + ",\"slot\":" + std::to_string(slot) +
        ",\"nonce\":" + TrackerJsonString(nonce) + "}";
    if (result.size() > 16000) throw std::invalid_argument("AP tracker startup configuration is too large");
    return result;
}
} // namespace SohExtreme
