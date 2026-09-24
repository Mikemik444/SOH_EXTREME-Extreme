#include "TrackerWorker.h"
#include <algorithm>
#include <cwchar>
#include <cwctype>
#include <filesystem>
#include <fstream>
#include <string>
#include <vector>

#if defined(_WIN32)
#ifndef NOMINMAX
#define NOMINMAX
#endif
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>
#if defined(_MSC_VER)
#pragma comment(lib, "Advapi32.lib")
#endif
#endif

namespace SohExtreme {
struct TrackerWorker::Impl {
    std::string runtime;
#if defined(_WIN32)
    HANDLE process = nullptr;
    HANDLE job = nullptr;
#endif
};
TrackerWorker::TrackerWorker() : impl(std::make_unique<Impl>()) {}
TrackerWorker::~TrackerWorker() { Stop(); }
const std::string& TrackerWorker::RuntimePath() const { return impl->runtime; }

#if defined(_WIN32)
namespace {
struct Handle {
    HANDLE value = nullptr;
    explicit Handle(HANDLE h = nullptr) : value(h) {}
    ~Handle() { if (value && value != INVALID_HANDLE_VALUE) CloseHandle(value); }
    Handle(const Handle&) = delete;
    Handle& operator=(const Handle&) = delete;
    HANDLE Release() { HANDLE h = value; value = nullptr; return h; }
    bool Valid() const { return value && value != INVALID_HANDLE_VALUE; }
};
std::wstring Wide(const std::string& s) {
    if (s.empty()) return {};
    const int n = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, s.data(), static_cast<int>(s.size()), nullptr, 0);
    if (!n) return {};
    std::wstring out(n, L'\0');
    MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, s.data(), static_cast<int>(s.size()), out.data(), n);
    return out;
}
std::string Utf8(const std::wstring& s) {
    if (s.empty()) return {};
    const int n = WideCharToMultiByte(CP_UTF8, 0, s.data(), static_cast<int>(s.size()), nullptr, 0, nullptr, nullptr);
    std::string out(n, '\0');
    WideCharToMultiByte(CP_UTF8, 0, s.data(), static_cast<int>(s.size()), out.data(), n, nullptr, nullptr);
    return out;
}
std::wstring Env(const wchar_t* name) {
    const DWORD n = GetEnvironmentVariableW(name, nullptr, 0);
    if (!n || n > 32768) return {};
    std::wstring out(n, L'\0');
    const DWORD read = GetEnvironmentVariableW(name, out.data(), n);
    if (!read || read >= n) return {};
    out.resize(read);
    return out;
}
std::wstring RegistryString(HKEY root, const std::wstring& key, const wchar_t* value, REGSAM view) {
    HKEY handle = nullptr;
    if (RegOpenKeyExW(root, key.c_str(), 0, KEY_READ | view, &handle) != ERROR_SUCCESS) return {};
    DWORD bytes = 0, type = 0;
    LSTATUS status = RegQueryValueExW(handle, value, nullptr, &type, nullptr, &bytes);
    std::wstring out;
    if (status == ERROR_SUCCESS && (type == REG_SZ || type == REG_EXPAND_SZ) && bytes <= 65536) {
        out.resize(bytes / sizeof(wchar_t) + 1, L'\0');
        if (RegQueryValueExW(handle, value, nullptr, &type, reinterpret_cast<BYTE*>(out.data()), &bytes) != ERROR_SUCCESS)
            out.clear();
        if (!out.empty()) out.resize(wcsnlen(out.c_str(), out.size()));
    }
    RegCloseKey(handle);
    if (!out.empty() && type == REG_EXPAND_SZ) {
        const DWORD n = ExpandEnvironmentStringsW(out.c_str(), nullptr, 0);
        if (n && n <= 32768) {
            std::wstring expanded(n, L'\0');
            if (ExpandEnvironmentStringsW(out.c_str(), expanded.data(), n) == n) {
                expanded.resize(n - 1); out = std::move(expanded);
            }
        }
    }
    return out;
}
std::wstring ExeInCommand(std::wstring command) {
    const auto first = command.find_first_not_of(L" \t");
    if (first == std::wstring::npos) return {};
    command.erase(0, first);
    if (command.front() == L'"') {
        const auto end = command.find(L'"', 1);
        return end == std::wstring::npos ? L"" : command.substr(1, end - 1);
    }
    std::wstring lower = command;
    std::transform(lower.begin(), lower.end(), lower.begin(), ::towlower);
    const auto end = lower.find(L".exe");
    return end == std::wstring::npos ? L"" : command.substr(0, end + 4);
}
void AddCandidate(std::vector<std::filesystem::path>& out, const std::wstring& path) {
    if (path.empty()) return;
    std::filesystem::path p(path);
    // Only known AP launchers are executable candidates. An installer DisplayIcon
    // or URL association may name another AP component; use its directory only.
    std::wstring name = p.filename().wstring();
    std::transform(name.begin(), name.end(), name.begin(), ::towlower);
    if (name == L"archipelagolauncherdebug.exe" || name == L"archipelagolauncher.exe") out.push_back(p);
    if (name.size() >= 4 && name.substr(name.size() - 4) == L".exe") p = p.parent_path();
    out.push_back(p / L"ArchipelagoLauncherDebug.exe");
    out.push_back(p / L"ArchipelagoLauncher.exe");
}
bool HasManagedWorld(const std::filesystem::path& directory) {
    // A missing/old world must not fall through the AP Launcher to its GUI.
    // ZIP central-directory filenames are uncompressed, so presence of the
    // worker module can be checked without another ZIP/runtime dependency.
    for (const auto* folder : {L"custom_worlds", L"worlds"}) {
        const auto base = directory / folder;
        std::error_code error;
        if (std::filesystem::is_regular_file(base / L"soh_extreme" / L"TrackerWorker.py", error)) return true;
        std::filesystem::directory_iterator it(base, error), end;
        for (; !error && it != end; it.increment(error)) {
            const auto path = it->path();
            if (path.extension() != L".apworld" || path.filename().wstring().find(L"soh_extreme") == std::wstring::npos) continue;
            std::ifstream file(path, std::ios::binary);
            if (!file) continue;
            file.seekg(0, std::ios::end);
            const auto length = file.tellg();
            if (length <= 0 || length > 33554432) continue;
            const auto tailSize = static_cast<std::streamoff>(std::min<std::streamoff>(length, 1048576));
            file.seekg(-tailSize, std::ios::end);
            std::string tail(static_cast<size_t>(tailSize), '\0');
            if (file.read(tail.data(), static_cast<std::streamsize>(tail.size())) &&
                tail.find("soh_extreme/TrackerWorker.py") != std::string::npos) return true;
        }
    }
    return false;
}
std::filesystem::path FindRuntime(const std::string& hint) {
    std::vector<std::filesystem::path> candidates;
    AddCandidate(candidates, Wide(hint));
    // An explicitly selected path takes priority and never silently selects a
    // different installation when invalid (a version mix-up is worse than an error).
    if (hint.empty()) {
        AddCandidate(candidates, Env(L"SOH_EXTREME_AP_PATH"));
        for (const HKEY root : {HKEY_CURRENT_USER, HKEY_LOCAL_MACHINE}) {
            for (const REGSAM view : {KEY_WOW64_64KEY, KEY_WOW64_32KEY}) {
                AddCandidate(candidates, RegistryString(root,
                    L"Software\\Microsoft\\Windows\\CurrentVersion\\App Paths\\ArchipelagoLauncher.exe", nullptr, view));
                AddCandidate(candidates, ExeInCommand(RegistryString(root,
                    L"Software\\Classes\\archipelago\\shell\\open\\command", nullptr, view)));
                const std::wstring uninstall = L"Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall";
                HKEY parent = nullptr;
                if (RegOpenKeyExW(root, uninstall.c_str(), 0, KEY_READ | view, &parent) == ERROR_SUCCESS) {
                    for (DWORD i = 0; i < 4096; ++i) {
                        wchar_t name[256]; DWORD count = 256;
                        const LSTATUS status = RegEnumKeyExW(parent, i, name, &count, nullptr, nullptr, nullptr, nullptr);
                        if (status == ERROR_NO_MORE_ITEMS) break;
                        if (status != ERROR_SUCCESS) continue;
                        const std::wstring key = uninstall + L"\\" + std::wstring(name, count);
                        const auto display = RegistryString(root, key, L"DisplayName", view);
                        if (display.rfind(L"Archipelago", 0) != 0) continue;
                        AddCandidate(candidates, RegistryString(root, key, L"InstallLocation", view));
                        AddCandidate(candidates, ExeInCommand(RegistryString(root, key, L"DisplayIcon", view)));
                    }
                    RegCloseKey(parent);
                }
            }
        }
        for (const wchar_t* variable : {L"ProgramData", L"ProgramFiles", L"ProgramFiles(x86)"}) {
            const auto path = Env(variable);
            if (!path.empty()) AddCandidate(candidates, (std::filesystem::path(path) / L"Archipelago").wstring());
        }
        const auto local = Env(L"LOCALAPPDATA");
        if (!local.empty()) {
            AddCandidate(candidates, (std::filesystem::path(local) / L"Programs" / L"Archipelago").wstring());
            AddCandidate(candidates, (std::filesystem::path(local) / L"Archipelago").wstring());
        }
        std::wstring exe(32768, L'\0');
        const DWORD len = GetModuleFileNameW(nullptr, exe.data(), static_cast<DWORD>(exe.size()));
        if (len && len < exe.size()) {
            exe.resize(len); AddCandidate(candidates, std::filesystem::path(exe).parent_path().wstring());
        }
    }
    std::filesystem::path firstInstalled;
    for (const auto& candidate : candidates) {
        std::error_code error;
        if (!candidate.is_absolute() || !std::filesystem::is_regular_file(candidate, error)) continue;
        if (firstInstalled.empty()) firstInstalled = candidate;
        if (HasManagedWorld(candidate.parent_path())) return candidate;
    }
    return firstInstalled;
}
std::string WinError(const char* step) {
    return std::string(step) + " (Windows error " + std::to_string(GetLastError()) + ").";
}
} // namespace
#endif

bool TrackerWorker::Start(const std::string& runtimeHint, const std::string& bootstrapJson, std::string& error) {
    Stop();
    if (bootstrapJson.empty() || bootstrapJson.size() > 16000 || bootstrapJson.find('\n') != std::string::npos) {
        error = "Invalid AP tracker startup configuration."; return false;
    }
#if defined(_WIN32)
    try {
        const auto runtime = FindRuntime(runtimeHint);
        if (runtime.empty()) {
            error = "Archipelago runtime not found. Set its installation folder below, then restart the AP tracker.";
            return false;
        }
        if (!HasManagedWorld(runtime.parent_path())) {
            error = "Install soh_extreme.apworld 0.11.21 in this Archipelago installation before starting the AP tracker.";
            return false;
        }
        SECURITY_ATTRIBUTES sa{sizeof(SECURITY_ATTRIBUTES), nullptr, TRUE};
        HANDLE readRaw = nullptr, writeRaw = nullptr;
        if (!CreatePipe(&readRaw, &writeRaw, &sa, 65536)) { error = WinError("Create tracker input pipe"); return false; }
        Handle read(readRaw), write(writeRaw);
        if (!SetHandleInformation(write.value, HANDLE_FLAG_INHERIT, 0)) { error = WinError("Protect tracker input"); return false; }
        Handle nullOut(CreateFileW(L"NUL", GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE, &sa, OPEN_EXISTING, 0, nullptr));
        if (!nullOut.Valid()) { error = WinError("Open tracker output sink"); return false; }
        Handle job(CreateJobObjectW(nullptr, nullptr));
        if (!job.Valid()) { error = WinError("Create tracker job"); return false; }
        JOBOBJECT_EXTENDED_LIMIT_INFORMATION limit{};
        limit.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
        if (!SetInformationJobObject(job.value, JobObjectExtendedLimitInformation, &limit, sizeof(limit))) {
            error = WinError("Set tracker lifetime"); return false;
        }
        SIZE_T bytes = 0;
        InitializeProcThreadAttributeList(nullptr, 1, 0, &bytes);
        if (!bytes) { error = WinError("Measure tracker handle list"); return false; }
        std::vector<unsigned char> storage(bytes);
        auto attrs = reinterpret_cast<LPPROC_THREAD_ATTRIBUTE_LIST>(storage.data());
        if (!InitializeProcThreadAttributeList(attrs, 1, 0, &bytes)) { error = WinError("Initialize tracker handle list"); return false; }
        struct AttributeCleanup { LPPROC_THREAD_ATTRIBUTE_LIST p; ~AttributeCleanup() { DeleteProcThreadAttributeList(p); } } cleanup{attrs};
        HANDLE inherited[] = {read.value, nullOut.value};
        if (!UpdateProcThreadAttribute(attrs, 0, PROC_THREAD_ATTRIBUTE_HANDLE_LIST, inherited, sizeof(inherited), nullptr, nullptr)) {
            error = WinError("Restrict tracker inherited handles"); return false;
        }
        STARTUPINFOEXW startup{};
        startup.StartupInfo.cb = sizeof(startup);
        startup.StartupInfo.dwFlags = STARTF_USESTDHANDLES | STARTF_USESHOWWINDOW;
        startup.StartupInfo.wShowWindow = SW_HIDE;
        startup.StartupInfo.hStdInput = read.value;
        startup.StartupInfo.hStdOutput = startup.StartupInfo.hStdError = nullOut.value;
        startup.lpAttributeList = attrs;
        const auto executable = runtime.wstring();
        std::wstring command = L"\"" + executable + L"\" \"SOH-EXTREME Universal Tracker\" -- --game-owned --nogui";
        PROCESS_INFORMATION process{};
        // Never invoke cmd.exe/ShellExecute or expose password/server/slot in the
        // command line. Only the private inherited pipe carries credentials.
        if (!CreateProcessW(executable.c_str(), command.data(), nullptr, nullptr, TRUE,
                            CREATE_NO_WINDOW | CREATE_SUSPENDED | EXTENDED_STARTUPINFO_PRESENT,
                            nullptr, runtime.parent_path().wstring().c_str(), &startup.StartupInfo, &process)) {
            error = WinError("Start Archipelago tracker runtime"); return false;
        }
        Handle child(process.hProcess), thread(process.hThread);
        if (!AssignProcessToJobObject(job.value, child.value)) {
            error = WinError("Attach tracker to game lifetime"); TerminateProcess(child.value, 1); return false;
        }
        // Configuration is smaller than the dedicated pipe buffer: no game-thread
        // wait for the Python interpreter to start or evaluate any rules.
        const std::string message = bootstrapJson + "\n";
        DWORD written = 0;
        if (!WriteFile(write.value, message.data(), static_cast<DWORD>(message.size()), &written, nullptr) || written != message.size()) {
            error = WinError("Send tracker startup configuration"); return false;
        }
        if (ResumeThread(thread.value) == static_cast<DWORD>(-1)) { error = WinError("Resume tracker runtime"); return false; }
        impl->process = child.Release(); impl->job = job.Release(); impl->runtime = Utf8(executable);
        error.clear(); return true;
    } catch (const std::exception&) {
        error = "Unable to resolve the Archipelago runtime path."; return false;
    }
#else
    (void)runtimeHint;
    error = "Automatic Universal Tracker hosting is currently available in Windows builds.";
    return false;
#endif
}

bool TrackerWorker::IsRunning(std::string& error) {
#if defined(_WIN32)
    if (!impl->process) return false;
    DWORD code = 0;
    if (!GetExitCodeProcess(impl->process, &code)) { error = WinError("Read tracker process state"); Stop(); return false; }
    if (code == STILL_ACTIVE) return true;
    switch (code) {
        case 20: error = "AP tracker startup data was invalid."; break;
        case 21: error = "Install tracker.apworld alongside the updated soh_extreme.apworld in the detected Archipelago installation."; break;
        case 22: error = "The AP tracker could not authenticate. Check the game's server, slot and password."; break;
        case 23: error = "Universal Tracker could not reconstruct this slot. See Archipelago's SOH-EXTREME-InGameTracker log."; break;
        default: error = "The AP tracker stopped (exit " + std::to_string(code) + "). Check the installed AP world and tracker versions."; break;
    }
    Stop();
#else
    (void)error;
#endif
    return false;
}
void TrackerWorker::Stop() {
#if defined(_WIN32)
    // The job contains only our child process tree. Closing it cannot close the
    // user's Launcher/UT windows or another game instance's worker.
    if (impl->job) { CloseHandle(impl->job); impl->job = nullptr; }
    if (impl->process) { CloseHandle(impl->process); impl->process = nullptr; }
#endif
}
} // namespace SohExtreme
