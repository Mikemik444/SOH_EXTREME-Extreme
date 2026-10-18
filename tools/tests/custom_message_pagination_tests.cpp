#include "custom_message_test_adapter.h"
#include <iostream>
#include <random>
#include <stdexcept>

static void Require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}

struct Layout {
    size_t pages = 1;
    size_t maxDecoded = 0;
    size_t maxGlyphs = 0;
    std::vector<size_t> choiceLines;
    std::string visible;
};

static Layout Inspect(const std::string& text) {
    Layout result;
    size_t decoded = 0, glyphs = 0, line = 1, width = 0;
    bool icon = false;
    for (size_t pos = 0; pos < text.size();) {
        const auto code = static_cast<unsigned char>(text[pos]);
        const auto length = CustomMessageEncoding::TokenLength(text, pos);
        Require(length >= CustomMessageEncoding::ControlLength(code), "Truncated control operand");
        const auto token = text.substr(pos, length);
        pos += length;
        decoded += length;
        if (code >= 0x20) {
            if (code != ' ') {
                glyphs += length;
                result.visible += token;
            }
            const auto found = pixelWidthTable.find(token);
            if (found != pixelWidthTable.end()) width += found->second;
            else {
                bool specialFound = false;
                for (const auto& special : textBoxSpecialCharacters) {
                    if (length == 1 && token[0] == special.second) {
                        width += pixelWidthTable.at(special.first);
                        specialFound = true;
                    }
                }
                if (!specialFound) width += 12 * length;
            }
        } else if (code == 0x0F) {
            decoded += 15;
            glyphs += 8;
            width += 96;
        } else if (code == 0x16 || code == 0x17 || code == 0x18 || code == 0x19 ||
                   code == 0x1D || code == 0x1E || code == 0x1F) {
            decoded += 6 - length;
            glyphs += 6;
            width += 48;
        } else if (code == 0x06) {
            width += static_cast<unsigned char>(token[1]);
        } else if (code == 0x13) {
            icon = true;
        } else if (code == 0x1B || code == 0x1C) {
            result.choiceLines.push_back(line);
        }
        Require(width <= (icon ? 200u : 216u), "Text exceeds the native line width");
        if (code == 0x01) {
            ++line;
            width = 0;
        }
        Require(line <= 4, "More than four lines on a native page");
        Require(decoded < 200, "Native decoded message buffer overflow");
        Require(glyphs <= 120, "Unrefreshed native glyph texture slot");
        result.maxDecoded = std::max(result.maxDecoded, decoded);
        result.maxGlyphs = std::max(result.maxGlyphs, glyphs);
        if (CustomMessageEncoding::IsPageBreak(code)) {
            ++result.pages;
            decoded = glyphs = width = 0;
            line = 1;
            icon = false;
        }
        if (code == 0x02 || code == 0x0B || code == 0x07) break;
    }
    return result;
}

static std::string Format(const std::string& text, std::vector<std::string> colors = {}) {
    CustomMessage message;
    message.colors = std::move(colors);
    std::string formatted = text;
    message.AutoFormatString(formatted);
    Inspect(formatted);
    auto repeated = formatted;
    message.AutoFormatString(repeated);
    if (repeated != formatted) {
        std::cerr << "Idempotence input bytes " << text.size() << ", first " << formatted.size()
                  << ", repeated " << repeated.size() << '\n';
        throw std::runtime_error("Reformatting an encoded message changed its pages");
    }
    return formatted;
}

int main() {
    std::cout << std::unitbuf;
    size_t cases = 0, largestPages = 0;
    auto run = [&](const char* name, auto test) {
        test();
        ++cases;
        std::cout << "PASS " << name << '\n';
    };
    run("unbroken wide name preserves every character", [&]() {
        const auto text = Format(std::string(1500, 'W'));
        const auto layout = Inspect(text);
        Require(layout.visible == std::string(1500, 'W'), "Wide name was shortened");
        Require(layout.pages > 1, "Long name was not paginated");
        largestPages = std::max(largestPages, layout.pages);
    });
    run("narrow glyphs respect native decoder and texture capacity", [&]() {
        const auto layout = Inspect(Format(std::string(3000, 'i')));
        Require(layout.visible == std::string(3000, 'i'), "Narrow name was shortened");
        Require(layout.pages >= 25, "Narrow text was not split at the glyph capacity");
    });
    run("long prose preserves names and suffixes beyond the old font buffer", [&]() {
        std::string input;
        for (size_t i = 0; i < 100; ++i) input += "Progressive equipment for Player LongLocation DistinguishingSuffix. ";
        const auto layout = Inspect(Format(input));
        std::erase(input, ' ');
        Require(layout.visible == input, "Long hint lost content");
        largestPages = std::max(largestPages, layout.pages);
    });
    run("explicit and encoded line and page boundaries", [&]() {
        const auto raw = Format("one&two&three&four&five^six&seven");
        const auto native = Format(std::string("one\x01two\x01three\x01") + "four\x01" + "five\x04six\x01seven");
        Require(raw == native, "Encoded boundaries differ from authored boundaries");
        Require(Inspect(raw).pages == 3, "Fourth-line continuation is missing");
    });
    run("colors icons text speed and quick text survive automatic pages", [&]() {
        const auto text = Format(std::string("\x13\x40\x08\x14\x02\x1A") + "%r" + std::string(600, 'W') + "%w\x09");
        for (size_t pos = 0; pos < text.size(); pos += CustomMessageEncoding::TokenLength(text, pos)) {
            if (text[pos] == '\x04') Require(text.substr(pos + 1, 2) == "\x05\x41", "Continued color was lost");
        }
        Require(Inspect(text).visible == std::string(600, 'W'), "Colored name was shortened");
    });
    run("operand bytes are never interpreted as markup or page controls", [&]() {
        const std::string prefix = std::string("\x12") + "^&" + "\x05\x40" + "\x13\x23";
        const auto text = Format(prefix + "Text");
        Require(text.starts_with(prefix), "Native command operand was rewritten");
        const auto terminator = std::string("\x07") + "^@";
        Require(Format("Text" + terminator).ends_with(terminator + '\x02'), "TEXTID operand was rewritten");
        const auto withOperandBreak = Format(std::string("\x12\x04\x01") + "Text");
        Require(Inspect(withOperandBreak).pages == 1, "SFX data created a false page");
    });
    run("native accented text survives repeated formatting", [&]() {
        std::string input;
        for (size_t i = 0; i < 140; ++i) input += "ÉléphantÖ ";
        const auto layout = Inspect(Format(input));
        std::string expected;
        for (size_t i = 0; i < 140; ++i) expected += std::string("\x86l\x96phant\x8B");
        Require(layout.visible == expected, "Accented name changed or lost content");
    });
    run("runtime file names and scores reserve their expanded size", [&]() {
        std::string input;
        for (size_t i = 0; i < 80; ++i) input += "@ " + std::string("\x1E\x01") + " WWW ";
        Require(Inspect(Format(input)).pages >= 20, "Runtime expansions were not included in page limits");
    });
    run("two-choice prompt remains on the final page at line three", [&]() {
        const auto text = Format(std::string(800, 'W') + "?\x1B%gYes&No%w");
        const auto layout = Inspect(text);
        Require(layout.choiceLines == std::vector<size_t>{3}, "Two-choice cursor rows changed");
        Require(text.ends_with(std::string("Yes\x01No\x05\x00\x02", 9)), "Choice ending changed");
    });
    run("three-choice prompt remains on line two", [&]() {
        const auto layout = Inspect(Format(std::string(400, 'W') + "?\x1C%gOne&Two&Three%w"));
        Require(layout.choiceLines == std::vector<size_t>{2}, "Three-choice cursor rows changed");
    });
    run("actor event and existing terminators remain intact", [&]() {
        Require(Format(std::string(500, 'W') + "\x0B\x02").ends_with("\x0B\x02"), "EVENT changed to another dialogue state");
        Require(Format("Small\x02\x02") == "Small\x02", "Repeated formatting added END commands");
        const auto timed = Format("First" + std::string("\x0C\x04") + "Second" + std::string("\x11\x01\x04\x02"));
        Require(Inspect(timed).pages == 2, "Delayed page controls changed");
    });
    run("colored placeholders and trailing punctuation", [&]() {
        const auto text = Format("#" + std::string(300, 'W') + "#.", { QM_GREEN });
        Require(text.starts_with("\x05\x42"), "Stored color was not encoded");
        Require(Inspect(text).visible == std::string(300, 'W') + '.', "Final punctuation was lost");
        Format("word ");
        Format("");
    });
    run("deterministic mixed markup and repeat-format regression corpus", [&]() {
        const std::vector<std::string> pieces = { "WWWWWWWWW", "iii", " word ", "Été", "&", "^", "%r", "%w", "@", "!" };
        std::mt19937 rng(184185);
        for (size_t trial = 0; trial < 200; ++trial) {
            std::string input;
            for (size_t i = 0; i < 150; ++i) input += pieces[rng() % pieces.size()];
            Format(input);
        }
    });
    std::cout << "RESULT cases=" << cases << " largest_pages=" << largestPages << '\n';
}
