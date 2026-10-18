"""Compile real textbox formatting code with game-only declarations isolated.

The formatter/header and AutoFormatString body come directly from the source
under test. The adapter supplies only engine enum/constants unavailable in the
source-only snapshot, allowing ASan/UBSan validation without the Windows build.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[2]
    messages = source / "soh/Enhancements/custom-message"
    manager = messages / "CustomMessageManager.cpp"
    text = manager.read_text(encoding="utf-8")
    header = (messages / "CustomMessageManager.h").read_text(encoding="utf-8")
    tables = text[text.index("static const std::unordered_map<std::string, char> textBoxSpecialCharacters"):
                  text.index("CustomMessage::CustomMessage(")]
    method = text[text.index("void CustomMessage::AutoFormatString("):
                  text.index("void CustomMessage::InsertNumber(")]
    items = sorted(set(re.findall(r"\bITEM_[A-Z_]+\b", tables)))
    colors = header[header.index("#define QM_WHITE"):header.index("#define HS_HORSE_ARCHERY")]
    adapter = "\n".join([
        '#include "CustomMessageFormatter.h"',
        "#include <map>\n#include <unordered_map>\nusing namespace std::literals::string_literals;",
        "enum ItemID { " + ", ".join(items) + " };", colors, tables,
        r'''class CustomMessage {
public:
    std::vector<std::string> colors;
    static std::string COLOR(const std::string& c) { return "\x05"s + c; }
    static std::string ITEM_OBTAINED(unsigned char c) { return "\x13"s + static_cast<char>(c); }
    static std::string NEWLINE() { return "\x01"s; }
    static std::string WAIT_FOR_INPUT() { return "\x04"s; }
    static std::string PLAYER_NAME() { return "\x0F"s; }
    void AutoFormatString(std::string&) const;
};''', method])
    test = source / "tools/tests/custom_message_pagination_tests.cpp"
    with tempfile.TemporaryDirectory(prefix="soh-hint-pagination-") as scratch:
        build = Path(scratch)
        (build / "custom_message_test_adapter.h").write_text(adapter, encoding="utf-8")
        executable = build / "pagination_tests"
        command = ["g++", "-std=c++20", "-O1", "-g", "-Wall", "-Wextra", "-Werror",
                   "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-I", str(build),
                   "-I", str(messages), str(test), "-o", str(executable)]
        compile_result = subprocess.run(command, text=True, capture_output=True)
        if compile_result.returncode:
            raise RuntimeError(compile_result.stdout + compile_result.stderr)
        # LeakSanitizer cannot inspect /proc tasks in the managed runtime; the
        # requested buffer/undefined-behavior checks remain fully enabled.
        env = dict(os.environ, ASAN_OPTIONS="detect_leaks=0:halt_on_error=1", UBSAN_OPTIONS="halt_on_error=1")
        result = subprocess.run([str(executable)], text=True, capture_output=True, env=env)
        print(result.stdout, end="")
        if result.returncode:
            raise RuntimeError(result.stderr or f"Pagination test exited {result.returncode}")
        files = [manager, messages / "CustomMessageManager.h", messages / "CustomMessageEncoding.h",
                 messages / "CustomMessageFormatter.h", test, Path(__file__).resolve()]
        report = {"status": "passed", "scope": "native custom-message formatting and bounded page layout",
                  "full_native_game_build": False, "sanitizers": ["address", "undefined"],
                  "cases": [line[5:] for line in result.stdout.splitlines() if line.startswith("PASS ")],
                  "source_sha256": {str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
                  "stdout": result.stdout}
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
