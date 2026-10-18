#pragma once

#include "CustomMessageEncoding.h"
#include <algorithm>
#include <string>
#include <vector>

// Layout for the native PAL textbox, also used by translated custom messages.
// Keep a page below both the 200-byte decoded buffer and the 120 glyph textures
// refreshed by Message_Decode. Pixel width alone is insufficient for narrow text.
namespace CustomMessageFormatting {
constexpr size_t MaxPageDecodedBytes = 184;
constexpr size_t MaxPageGlyphs = 120;

struct Token {
    std::string text;
    size_t width = 0;
    size_t decoded = 0;
    size_t glyphs = 0;
    bool IsSpace() const { return text == " "; }
    bool BreakAfter() const { return text.size() == 1 && std::string(".,!?-").find(text[0]) != std::string::npos; }
};

template <typename WidthOf>
Token ReadToken(const std::string& text, size_t offset, WidthOf widthOf) {
    Token token{ text.substr(offset, CustomMessageEncoding::TokenLength(text, offset)) };
    const auto code = static_cast<unsigned char>(token.text[0]);
    token.decoded = token.text.size();
    if (code >= 0x20) {
        token.width = widthOf(token.text);
        token.glyphs = token.IsSpace() ? 0 : token.text.size();
    } else if (code == 0x0F) { // File name: up to eight glyphs, including native name-language controls.
        token.width = 96;
        token.decoded = 16;
        token.glyphs = 8;
    } else if (code == 0x06 && token.text.size() == 2) { // Horizontal shift.
        token.width = static_cast<unsigned char>(token.text[1]);
    } else if (code == 0x16 || code == 0x17 || code == 0x18 || code == 0x19 ||
               code == 0x1D || code == 0x1E || code == 0x1F) { // Runtime numbers/times.
        token.width = 48;
        token.decoded = 6;
        token.glyphs = 6;
    }
    return token;
}

template <typename WidthOf>
std::string Wrap(const std::string& text, WidthOf widthOf) {
    bool hasIcon = false;
    for (size_t pos = 0; pos < text.size(); pos += CustomMessageEncoding::TokenLength(text, pos)) {
        hasIcon |= static_cast<unsigned char>(text[pos]) == 0x13;
    }
    const size_t lineLimit = hasIcon ? 200 : 216;
    std::string output;
    output.reserve(text.size());
    std::vector<Token> line;
    size_t lineWidth = 0, lineDecoded = 0, lineGlyphs = 0;
    size_t pageDecoded = 0, pageGlyphs = 0, lineNumber = 1;
    std::string color, icon, speed;
    bool quick = false, unskippable = false;

    auto recountLine = [&]() {
        lineWidth = lineDecoded = lineGlyphs = 0;
        for (const auto& token : line) {
            lineWidth += token.width;
            lineDecoded += token.decoded;
            lineGlyphs += token.glyphs;
        }
    };
    auto commit = [&](size_t count) {
        for (size_t i = 0; i < count; ++i) {
            const auto& token = line[i];
            output += token.text;
            pageDecoded += token.decoded;
            pageGlyphs += token.glyphs;
            switch (static_cast<unsigned char>(token.text[0])) {
                case 0x05: color = token.text; break;
                case 0x13: icon = token.text; break;
                case 0x14: speed = token.text; break;
                case 0x08: quick = true; break;
                case 0x09: quick = false; break;
                case 0x1A: unskippable = true; break;
            }
        }
        line.erase(line.begin(), line.begin() + count);
        recountLine();
    };
    auto newPage = [&](const std::string& delimiter, bool automatic, bool nextHasIcon = false) {
        output += delimiter;
        pageDecoded = pageGlyphs = 0;
        lineNumber = 1;
        std::string prefix;
        if (automatic) {
            if (color.size() == 2 && (static_cast<unsigned char>(color[1]) & 0x0F) != 0) prefix += color;
            prefix += icon;
            prefix += speed;
            if (quick) prefix += '\x08';
            if (unskippable) prefix += '\x1A';
        } else {
            // Explicit pages reset native text styling. Item messages still need
            // their icon on each page; do not duplicate an already encoded icon.
            if (!nextHasIcon) prefix += icon;
            color.clear();
            speed.clear();
            quick = unskippable = false;
            if (nextHasIcon) icon.clear();
        }
        output += prefix;
        pageDecoded += prefix.size();
    };
    auto newLine = [&]() {
        if (lineNumber == 4 || pageDecoded + 1 >= MaxPageDecodedBytes) {
            newPage("\x04", true);
        } else {
            output += '\x01';
            ++pageDecoded;
            ++lineNumber;
        }
    };
    auto splitLine = [&](bool pageFull) {
        size_t count = line.size(), skip = 0;
        // Prefer whole words; keep punctuation and hard-wrap a single overwide
        // name only when no word boundary fits. Never index npos or split a token.
        for (size_t i = line.size(); i > 0; --i) {
            if (line[i - 1].IsSpace() && i > 1) {
                count = i - 1;
                skip = 1;
                break;
            }
            if (line[i - 1].BreakAfter()) {
                count = i;
                break;
            }
        }
        commit(count);
        if (skip != 0) {
            line.erase(line.begin());
            recountLine();
        }
        if (pageFull) newPage("\x04", true);
        else newLine();
    };

    bool ended = false;
    for (size_t pos = 0; pos < text.size();) {
        auto token = ReadToken(text, pos, widthOf);
        const auto code = static_cast<unsigned char>(token.text[0]);
        pos += token.text.size();
        if (code == 0x02 || code == 0x07 || code == 0x0B) {
            commit(line.size());
            output += token.text;
            // The original dialogue terminator belongs to the actor. Do not
            // substitute TEXTID, EVENT or END with a synthetic continuation.
            if (code != 0x02) output += '\x02';
            ended = true;
            break;
        }
        if (code == 0x01) {
            commit(line.size());
            newLine();
            continue;
        }
        if (CustomMessageEncoding::IsPageBreak(code)) {
            commit(line.size());
            bool nextHasIcon = false;
            for (size_t next = pos; next < text.size();) {
                const auto nextCode = static_cast<unsigned char>(text[next]);
                if (nextCode >= 0x20 || nextCode == 0x01 || CustomMessageEncoding::IsDecodeBoundary(nextCode)) break;
                nextHasIcon |= nextCode == 0x13;
                next += CustomMessageEncoding::TokenLength(text, next);
            }
            newPage(token.text, false, nextHasIcon);
            continue;
        }
        if (code == 0x1B || code == 0x1C) {
            const size_t choiceLine = code == 0x1B ? 3 : 2;
            size_t choiceDecoded = token.decoded, choiceGlyphs = 0;
            for (size_t next = pos; next < text.size();) {
                const auto choice = ReadToken(text, next, widthOf);
                if (CustomMessageEncoding::IsDecodeBoundary(static_cast<unsigned char>(choice.text[0]))) break;
                choiceDecoded += choice.decoded;
                choiceGlyphs += choice.glyphs;
                next += choice.text.size();
            }
            const bool hasPrompt = lineWidth != 0;
            commit(line.size());
            if (lineNumber > choiceLine || (lineNumber == choiceLine && hasPrompt) ||
                pageDecoded + choiceDecoded + 4 >= MaxPageDecodedBytes ||
                pageGlyphs + choiceGlyphs > MaxPageGlyphs) {
                newPage("\x04", true);
            }
            while (lineNumber < choiceLine) newLine();
        }
        while (true) {
            const bool pageFull = pageDecoded + lineDecoded + token.decoded > MaxPageDecodedBytes ||
                                  pageGlyphs + lineGlyphs + token.glyphs > MaxPageGlyphs;
            const bool lineFull = lineWidth + token.width > lineLimit && lineWidth != 0;
            if (!pageFull && !lineFull) break;
            if (line.empty()) {
                newPage("\x04", true);
            } else {
                splitLine(pageFull);
            }
        }
        // A space used as a wrap boundary has no visible content on the new line.
        if (token.IsSpace() && line.empty() && lineWidth == 0 && !output.empty() &&
            (output.back() == '\x01' || output.back() == '\x04')) continue;
        lineWidth += token.width;
        lineDecoded += token.decoded;
        lineGlyphs += token.glyphs;
        line.push_back(std::move(token));
    }
    if (!ended) {
        commit(line.size());
        output += '\x02';
    }
    return output;
}
} // namespace CustomMessageFormatting
