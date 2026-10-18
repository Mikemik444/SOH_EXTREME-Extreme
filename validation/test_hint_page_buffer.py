#!/usr/bin/env python3
"""Compile actual streaming code and native integration fragments with ASan/UBSan.

The uploaded source omits the root build and native headers/assets. This harness
uses a minimal engine-state fixture, not a full native game build or gameplay.
Formatter text layout has its own full normalization/glyph-width regression test.
"""

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source"
CUSTOM = SOURCE / "soh/Enhancements/custom-message"
BUILD = ROOT / "tests/hint_page_buffer_build"
BUILD.mkdir(exist_ok=True)


def between(text, begin, end):
    start = text.index(begin)
    return text[start:text.index(end, start)]


def main():
    manager = (CUSTOM / "CustomMessageManager.cpp").read_text()
    native = (SOURCE / "src/code/z_message_PAL.c").read_text()
    fixture = (ROOT / "tests/hint_page_buffer_fixture.cpp.in").read_text()
    fragments = {
        "MANAGER_STREAM": between(manager, "namespace {\nCustomMessagePageBuffer", "\nvoid CustomMessage::Replace("),
        "OPEN_RESET": between(native[native.index("void Message_OpenText("):], "    bool loadFromMessageTable = true;", "\n    sDisplayNextMessageAsEnglish = false;"),
        "DECODE_REFILL": between(native[native.index("void Message_Decode("):], "    u32 customPageLength;", "\n    // #region SOH [NTSC]"),
        "DRAW_BOX_BREAK": between(native[native.index("void Message_DrawText("):], "            case MESSAGE_BOX_BREAK:", "            case MESSAGE_SHIFT:"),
        "UPDATE_DELAYED": between(native[native.index("void Message_Update("):], "        case MSGMODE_TEXT_DELAYED_BREAK:", "        case MSGMODE_TEXT_AWAIT_NEXT:"),
        "UPDATE_AWAIT_NEXT": between(native[native.index("void Message_Update("):], "        case MSGMODE_TEXT_AWAIT_NEXT:", "        case MSGMODE_TEXT_DONE:"),
        "CLOSE_TEXTBOX": between(native, "void Message_CloseTextbox(PlayState* play) {", "\nvoid Message_HandleChoiceSelection("),
    }
    for name, code in fragments.items():
        fixture = fixture.replace(f"@{name}@", code)
    assert not re.search(r"@[A-Z_]+@", fixture)
    (BUILD / "fixture.cpp").write_text(fixture)
    (BUILD / "c_api.c").write_text(
        '#include "CustomMessageInterfaceAddon.h"\n'
        'int CallPrepareFromC(char* b, size_t n, uint16_t* p, uint32_t* l) {\n'
        '    return CustomMessage_PrepareTextBuffer(b, n, p, l);\n}\n'
    )
    flags = ["-Wall", "-Wextra", "-Werror", "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-g", "-O1"]
    subprocess.run(["gcc", "-std=c11", *flags, "-I", str(CUSTOM), "-c", str(BUILD / "c_api.c"), "-o", str(BUILD / "c_api.o")], check=True)
    subprocess.run(["g++", "-std=c++20", *flags, "-I", str(CUSTOM), str(BUILD / "fixture.cpp"), str(BUILD / "c_api.o"), "-o", str(BUILD / "fixture")], check=True)
    env = {**os.environ, "ASAN_OPTIONS": "detect_leaks=0:halt_on_error=1", "UBSAN_OPTIONS": "halt_on_error=1:print_stacktrace=1"}
    result = subprocess.run([str(BUILD / "fixture")], check=True, text=True, capture_output=True, env=env)
    print(result.stdout, end="")
    match = re.search(r"RESULT cases=(\d+) assertions=(\d+)", result.stdout)
    assert match
    paths = [CUSTOM / name for name in ["CustomMessageEncoding.h", "CustomMessageFormatter.h", "CustomMessagePageBuffer.h", "CustomMessageInterfaceAddon.h", "CustomMessageManager.cpp"]]
    paths.append(SOURCE / "src/code/z_message_PAL.c")
    report = {
        "status": "passed",
        "cases": int(match[1]),
        "assertions": int(match[2]),
        "instrumentation": ["AddressSanitizer", "UndefinedBehaviorSanitizer", "C11/C++20 ABI link", "font buffer canaries"],
        "scope": "Actual formatter/streaming headers, C wrappers, LoadIntoFont, and extracted native open/reset, draw-box-break, A/delayed update, decode-refill, close fragments with minimal engine state; not a full game build or gameplay test.",
        "full_message_regression": "5000 pages and more than 65535 encoded bytes reconstructed exactly through native A/refill flow",
        "native_font_capacity": 1280,
        "native_decoded_capacity": 200,
        "sources": {str(path.relative_to(SOURCE)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths},
        "fragments": {name: hashlib.sha256(code.encode()).hexdigest() for name, code in fragments.items()},
        "output": result.stdout.splitlines(),
    }
    (ROOT / "tests/hint_page_buffer_validation.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
