#pragma once

#include "CustomMessageEncoding.h"

#include <cstdint>
#include <cstring>
#include <string>
#include <utility>

// Keep complete custom text outside the native 1280-byte Font buffer. The
// decoder consumes one page at a time; its cursor always remains local to that
// page, so neither the Font capacity nor the u16 cursor limits the whole hint.
class CustomMessagePageBuffer {
  public:
    void Clear() {
        std::string().swap(message);
        owner = nullptr;
        bufferCapacity = pageStart = pageEnd = boundary = 0;
        decoded = pageDrawn = false;
        previousPagesDrawn = true;
    }

    // The caller autoformats before loading, including the stricter 200-byte
    // decoded-page limit. Reject malformed controls/oversized encoded pages
    // instead of copying a truncated control or losing the rest of a hint.
    bool Load(std::string text, char* buffer, size_t capacity, uint32_t& length) {
        Clear();
        length = 0;
        if (buffer == nullptr || capacity < 2) {
            return false;
        }

        size_t start = 0;
        bool hasTerminal = false;
        for (size_t offset = 0; offset < text.size();) {
            const auto code = static_cast<unsigned char>(text[offset]);
            if (CustomMessageEncoding::ControlLength(code) > text.size() - offset) {
                return false;
            }
            offset += CustomMessageEncoding::TokenLength(text, offset);
            if (!CustomMessageEncoding::IsDecodeBoundary(code)) {
                continue;
            }
            if (offset - start >= capacity) {
                return false;
            }
            if (!CustomMessageEncoding::IsPageBreak(code)) {
                hasTerminal = true;
                break;
            }
            start = offset;
        }
        if (!hasTerminal) {
            // A literal/raw message may omit END, or finish with a page break.
            // Leave space for both END and the guard after the copied page.
            if (text.size() - start >= capacity - 1) {
                return false;
            }
            text.push_back('\x02');
        }

        message = std::move(text);
        owner = buffer;
        bufferCapacity = capacity;
        SelectPage(0);
        CopyPage(buffer, length);
        return true;
    }

    bool Prepare(char* buffer, size_t capacity, uint16_t& position, uint32_t& length) {
        if (owner == nullptr || owner != buffer || capacity != bufferCapacity) {
            return false;
        }
        if (!MatchesCurrentPage(buffer)) {
            // A direct debugger write or restored message buffer supersedes
            // this stream just as opening a new textbox does.
            Clear();
            return false;
        }

        const size_t pageLength = pageEnd - pageStart;
        const auto code = static_cast<unsigned char>(message[boundary]);
        if (position >= pageLength ||
            (!CustomMessageEncoding::IsPageBreak(code) && position > boundary - pageStart)) {
            if (CustomMessageEncoding::IsPageBreak(code)) {
                SelectPage(pageEnd);
            }
            // Language replay can request more pages than the new translation
            // contains. Safely repeat its last page instead of reading beyond
            // END/EVENT/TEXTID or treating their operands as another message.
            position = 0;
            CopyPage(buffer, length);
        } else {
            length = static_cast<uint32_t>(pageLength);
        }
        decoded = true;
        return true;
    }

    // Called from the native draw loop when it reaches a real page/end control.
    // Decoding a page (including language replay) does not count as reading it.
    bool MarkDrawn(char* buffer, size_t capacity, uint16_t drawn, uint16_t decodedLength) {
        if (owner == nullptr || owner != buffer || capacity != bufferCapacity || !decoded ||
            !MatchesCurrentPage(buffer)) {
            return false;
        }
        const auto code = static_cast<unsigned char>(message[boundary]);
        const size_t terminalLength = CustomMessageEncoding::ControlLength(code);
        if (static_cast<size_t>(decodedLength) + 1 < terminalLength ||
            drawn < static_cast<size_t>(decodedLength) + 1 - terminalLength) {
            return false;
        }
        pageDrawn = true;
        return previousPagesDrawn && !CustomMessageEncoding::IsPageBreak(code);
    }

  private:
    void SelectPage(size_t start) {
        if (pageEnd != 0 && start != pageStart) {
            previousPagesDrawn = previousPagesDrawn && pageDrawn;
        }
        decoded = pageDrawn = false;
        pageStart = start;
        for (size_t offset = start; offset < message.size();) {
            const size_t tokenStart = offset;
            const auto code = static_cast<unsigned char>(message[offset]);
            offset += CustomMessageEncoding::TokenLength(message, offset);
            if (CustomMessageEncoding::IsDecodeBoundary(code)) {
                boundary = tokenStart;
                pageEnd = offset;
                return;
            }
        }
    }

    void CopyPage(char* buffer, uint32_t& length) const {
        const size_t pageLength = pageEnd - pageStart;
        std::memset(buffer, 0, bufferCapacity);
        std::memcpy(buffer, message.data() + pageStart, pageLength);
        // Native credits can convert BOX_BREAK to its delayed two-byte form.
        // A safe following byte also protects boundary lookahead.
        buffer[pageLength] = '\x02';
        length = static_cast<uint32_t>(pageLength);
    }

    bool MatchesCurrentPage(const char* buffer) const {
        const size_t pageLength = pageEnd - pageStart;
        if (std::memcmp(buffer, message.data() + pageStart, pageLength) == 0) {
            return true;
        }
        // NoInputForCredits makes these two mutations while decoding. They
        // must not cancel the remaining pages of that same custom message.
        const size_t localBoundary = boundary - pageStart;
        const auto original = static_cast<unsigned char>(message[boundary]);
        const auto current = static_cast<unsigned char>(buffer[localBoundary]);
        return std::memcmp(buffer, message.data() + pageStart, localBoundary) == 0 &&
               ((original == 0x04 && current == 0x0C) || (original == 0x02 && current == 0x11));
    }

    std::string message;
    char* owner = nullptr;
    size_t bufferCapacity = 0;
    size_t pageStart = 0;
    size_t pageEnd = 0;
    size_t boundary = 0;
    bool decoded = false;
    bool pageDrawn = false;
    bool previousPagesDrawn = true;
};
