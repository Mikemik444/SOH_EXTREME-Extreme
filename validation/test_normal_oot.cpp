#include "soh/Extractor/NormalOot.h"
#include <iostream>
#ifdef TEST_TORCH
#include "soh/Extractor/TorchExtract.h"
#endif

int main(int argc, char** argv) {
    if (argc != 5) return 2;
    const std::string command = argv[1];
#ifdef TEST_TORCH
    if (command == "extract") {
        std::filesystem::create_directories(argv[4]);
        std::atomic<size_t> progress = 0;
        auto name = SohTorch::Extract(argv[2], argv[3], argv[4], "9.1.3", &progress);
        std::cout << name << " " << progress << '\n';
        return name == "oot.o2r" ? 0 : 1;
    }
#endif
    std::vector<uint8_t> source, patch, output{17, 42, 99};
    std::string error;
    bool ok = SohRom::ReadFile(argv[2], source, 64 * 1024 * 1024, error);
    if (ok && command == "apply") {
        ok = SohRom::ReadFile(argv[3], patch, 64 * 1024 * 1024, error) &&
             SohRom::ApplyBps(source, patch, output, error);
    } else if (ok && command == "convert") {
        ok = SohRom::NormalizeRom(source, error) && SohRom::ConvertMasterQuest(source, argv[3], output, error);
    } else if (ok && command == "normalize") {
        ok = SohRom::NormalizeRom(source, error);
        if (ok) output = source;
    } else if (ok) {
        return 2;
    }
    if (!ok) {
        if (output != std::vector<uint8_t>{17, 42, 99}) return 3;
        std::cerr << error << '\n';
        return 1;
    }
    std::ofstream file(argv[4], std::ios::binary);
    file.write(reinterpret_cast<const char*>(output.data()), output.size());
    return file ? 0 : 4;
}
