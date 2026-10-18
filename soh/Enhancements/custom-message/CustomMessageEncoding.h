#pragma once

#include <cstddef>
#include <string>

// PAL message bytecode. Custom messages use this encoding in every language,
// including the English fallback when the game language is Japanese.
namespace CustomMessageEncoding {

constexpr size_t ControlLength(unsigned char code) {
    switch (code) {
        case 0x05: // COLOR
        case 0x06: // SHIFT
        case 0x0C: // BOX_BREAK_DELAYED
        case 0x0E: // FADE
        case 0x13: // ITEM_ICON
        case 0x14: // TEXT_SPEED
        case 0x1E: // HIGHSCORE
            return 2;
        case 0x07: // TEXTID
        case 0x11: // FADE2
        case 0x12: // SFX
            return 3;
        case 0x15: // BACKGROUND
            return 4;
        default:
            return 1;
    }
}

// Return an entire control plus its operands, or one entire UTF-8 character
// before it is converted to the native font. Invalid/truncated input always
// advances within the supplied string; operand bytes are never new controls.
inline size_t TokenLength(const std::string& text, size_t offset) {
    if (offset >= text.size()) {
        return 0;
    }
    const auto first = static_cast<unsigned char>(text[offset]);
    const size_t controlLength = ControlLength(first);
    if (controlLength > 1) {
        const size_t remaining = text.size() - offset;
        return controlLength < remaining ? controlLength : remaining;
    }
    size_t length = 1;
    if (first >= 0xC2 && first <= 0xDF) {
        length = 2;
    } else if (first >= 0xE0 && first <= 0xEF) {
        length = 3;
    } else if (first >= 0xF0 && first <= 0xF4) {
        length = 4;
    }
    if (length > text.size() - offset) {
        return 1;
    }
    for (size_t index = 1; index < length; ++index) {
        const auto continuation = static_cast<unsigned char>(text[offset + index]);
        if ((continuation & 0xC0) != 0x80) {
            return 1;
        }
    }
    return length;
}

constexpr bool IsPageBreak(unsigned char code) {
    return code == 0x04 || code == 0x0C;
}

constexpr bool IsDecodeBoundary(unsigned char code) {
    return IsPageBreak(code) || code == 0x02 || code == 0x07 || code == 0x0B;
}

} // namespace CustomMessageEncoding
