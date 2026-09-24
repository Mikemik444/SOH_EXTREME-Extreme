#pragma once
// The game owns a windowless UT host. It is a read-only Tracker client, never
// a second game/item consumer. No Windows types leak into game headers.
#include <memory>
#include <string>

namespace SohExtreme {
class TrackerWorker {
  public:
    TrackerWorker();
    ~TrackerWorker();
    TrackerWorker(const TrackerWorker&) = delete;
    TrackerWorker& operator=(const TrackerWorker&) = delete;
    bool Start(const std::string& runtimeHint, const std::string& bootstrapJson, std::string& error);
    bool IsRunning(std::string& error);
    void Stop();
    const std::string& RuntimePath() const;
  private:
    struct Impl;
    std::unique_ptr<Impl> impl;
};
} // namespace SohExtreme
