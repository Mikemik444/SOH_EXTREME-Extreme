#include "CustomMessageManager.h"
#include "CustomMessageFormatter.h"
#include "CustomMessageInterfaceAddon.h"
#include "CustomMessagePageBuffer.h"
#include <algorithm>
#include <stdint.h>
#include <cstring>
#include <map>
#include <spdlog/spdlog.h>
#include <variables.h>
#include <soh/Enhancements/gameconsole.h>
#include <soh/util.h>

using namespace std::literals::string_literals;

static const std::unordered_map<std::string, char> textBoxSpecialCharacters = {
    { "À", 0x80 }, { "î", 0x81 }, { "Â", 0x82 }, { "Ä", 0x83 }, { "Ç", 0x84 }, { "È", 0x85 }, { "É", 0x86 },
    { "Ê", 0x87 }, { "Ë", 0x88 }, { "Ï", 0x89 }, { "Ô", 0x8A }, { "Ö", 0x8B }, { "Ù", 0x8C }, { "Û", 0x8D },
    { "Ü", 0x8E }, { "ß", 0x8F }, { "à", 0x90 }, { "á", 0x91 }, { "â", 0x92 }, { "ä", 0x93 }, { "ç", 0x94 },
    { "è", 0x95 }, { "é", 0x96 }, { "ê", 0x97 }, { "ë", 0x98 }, { "ï", 0x99 }, { "ô", 0x9A }, { "ö", 0x9B },
    { "ù", 0x9C }, { "û", 0x9D }, { "ü", 0x9E }
};
static const std::unordered_map<std::string, std::string> percentColors = {
    { "w", QM_WHITE }, { "r", QM_RED },  { "g", QM_GREEN },  { "b", QM_BLUE },
    { "c", QM_LBLUE }, { "p", QM_PINK }, { "y", QM_YELLOW }, { "B", QM_BLACK },
};

static const std::unordered_map<std::string, std::string> colorToPercent = {
    { QM_WHITE, "%w" }, { QM_RED, "%r" },  { QM_GREEN, "%g" },  { QM_BLUE, "%b" },
    { QM_LBLUE, "%c" }, { QM_PINK, "%p" }, { QM_YELLOW, "%y" }, { QM_BLACK, "%B" },
};

static const std::unordered_map<std::string, ItemID> altarIcons = {
    { "0", ITEM_KOKIRI_EMERALD },  { "1", ITEM_GORON_RUBY },       { "2", ITEM_ZORA_SAPPHIRE },
    { "8", ITEM_MEDALLION_LIGHT }, { "3", ITEM_MEDALLION_FOREST }, { "4", ITEM_MEDALLION_FIRE },
    { "5", ITEM_MEDALLION_WATER }, { "6", ITEM_MEDALLION_SPIRIT }, { "7", ITEM_MEDALLION_SHADOW },
    { "l", ITEM_ARROW_LIGHT },     { "b", ITEM_KEY_BOSS },         { "o", ITEM_SWORD_MASTER },
    { "c", ITEM_OCARINA_FAIRY },   { "i", ITEM_OCARINA_TIME },     { "L", ITEM_BOW_ARROW_LIGHT },
    { "k", ITEM_TUNIC_KOKIRI },    { "m", ITEM_DUNGEON_MAP },      { "C", ITEM_COMPASS },
    { "s", ITEM_SKULL_TOKEN },     { "g", ITEM_MASK_GORON },       { "w", ITEM_CUSTOM },
};

static std::map<std::string, int> pixelWidthTable = {
    { " ", 6 },  { "!", 6 },  { "\"", 5 },     { "#", 7 },  { "$", 7 },  { "%", 11 }, { "&", 9 },  { "\'", 3 },
    { "(", 6 },  { ")", 6 },  { "*", 6 },      { "+", 7 },  { ",", 3 },  { "-", 5 },  { ".", 3 },  { "/", 7 },
    { "0", 8 },  { "1", 4 },  { "2", 7 },      { "3", 7 },  { "4", 8 },  { "5", 7 },  { "6", 7 },  { "7", 7 },
    { "8", 7 },  { "9", 7 },  { ":", 5 },      { ";", 5 },  { "<", 7 },  { "=", 9 },  { ">", 7 },  { "?", 9 },
    { "@", 10 }, { "A", 9 },  { "B", 7 },      { "C", 9 },  { "D", 9 },  { "E", 6 },  { "F", 6 },  { "G", 9 },
    { "H", 8 },  { "I", 3 },  { "J", 6 },      { "K", 8 },  { "L", 6 },  { "M", 10 }, { "N", 9 },  { "O", 10 },
    { "P", 7 },  { "Q", 10 }, { "R", 8 },      { "S", 8 },  { "T", 7 },  { "U", 8 },  { "V", 9 },  { "W", 12 },
    { "X", 9 },  { "Y", 8 },  { "Z", 8 },      { "[", 6 },  { "\\", 8 }, { "]", 6 },  { "^", 8 },  { "_", 7 },
    { "`", 4 },  { "a", 6 },  { "b", 7 },      { "c", 6 },  { "d", 7 },  { "e", 7 },  { "f", 5 },  { "g", 7 },
    { "h", 6 },  { "i", 3 },  { "j", 5 },      { "k", 6 },  { "l", 3 },  { "m", 9 },  { "n", 7 },  { "o", 7 },
    { "p", 7 },  { "q", 7 },  { "r", 6 },      { "s", 6 },  { "t", 6 },  { "u", 6 },  { "v", 7 },  { "w", 9 },
    { "x", 6 },  { "y", 7 },  { "z", 6 },      { "{", 6 },  { "¦", 4 },  { "}", 6 },  { "¡", 5 },  { "¢", 7 },
    { "£", 8 },  { "¤", 7 },  { "¥", 8 },      { "|", 4 },  { "§", 12 }, { "¨", 12 }, { "©", 10 }, { "ª", 5 },
    { "«", 8 },  { "¬", 7 },  { "\u00AD", 6 }, { "®", 10 }, { "¯", 8 },  { "°", 12 }, { "±", 12 }, { "²", 5 },
    { "³", 5 },  { "µ", 6 },  { "¶", 8 },      { "·", 4 },  { "¹", 4 },  { "º", 5 },  { "»", 9 },  { "¼", 9 },
    { "½", 9 },  { "¾", 10 }, { "¿", 7 },      { "À", 11 }, { "Á", 9 },  { "Â", 9 },  { "Ã", 9 },  { "Ä", 9 },
    { "Å", 9 },  { "Æ", 12 }, { "Ç", 9 },      { "È", 6 },  { "É", 6 },  { "Ê", 6 },  { "Ë", 6 },  { "Ì", 5 },
    { "Í", 5 },  { "Î", 5 },  { "Ï", 5 },      { "Ð", 10 }, { "Ñ", 9 },  { "Ò", 10 }, { "Ó", 10 }, { "Ô", 10 },
    { "Õ", 10 }, { "Ö", 10 }, { "×", 9 },      { "Ø", 10 }, { "Ù", 8 },  { "Ú", 8 },  { "Û", 8 },  { "Ü", 8 },
    { "Ý", 10 }, { "Þ", 8 },  { "ß", 7 },      { "à", 6 },  { "á", 6 },  { "â", 6 },  { "ã", 6 },  { "ä", 6 },
    { "å", 6 },  { "æ", 11 }, { "ç", 6 },      { "è", 7 },  { "é", 7 },  { "ê", 7 },  { "ë", 7 },  { "ì", 5 },
    { "í", 5 },  { "î", 5 },  { "ï", 5 },      { "ð", 7 },  { "ñ", 7 },  { "ò", 7 },  { "ó", 7 },  { "ô", 7 },
    { "õ", 7 },  { "ö", 7 },  { "÷", 11 },     { "ø", 9 },  { "ù", 7 },  { "ú", 7 },  { "û", 7 },  { "ü", 7 },
    { "ý", 8 },  { "þ", 8 },  { "ÿ", 8 },      { "Œ", 11 }, { "œ", 11 }, { "„", 5 },  { "”", 5 },  { "€", 10 },
    { "Ÿ", 10 }, { "~", 8 },
};

CustomMessage::CustomMessage(std::string english_, std::string german_, std::string french_, TextBoxType type_,
                             TextBoxPosition position_)
    : type(type_), position(position_) {
    messages[LANGUAGE_ENG] = std::move(english_);
    messages[LANGUAGE_GER] = std::move(german_);
    messages[LANGUAGE_FRA] = std::move(french_);
}

CustomMessage::CustomMessage(std::string english_, std::string german_, std::string french_,
                             std::vector<std::string> colors_, std::vector<bool> capital_, TextBoxType type_,
                             TextBoxPosition position_) {
    messages[LANGUAGE_ENG] = std::move(english_);
    messages[LANGUAGE_GER] = std::move(german_);
    messages[LANGUAGE_FRA] = std::move(french_);
    colors = std::move(colors_);
    capital = std::move(capital_);
    type = type_;
    position = position_;
}

CustomMessage::CustomMessage(std::string english_, TextBoxType type_, TextBoxPosition position_)
    : type(type_), position(position_) {
    messages[LANGUAGE_ENG] = std::move(english_);
}

CustomMessage::CustomMessage(std::string english_, std::vector<std::string> colors_, std::vector<bool> capital_,
                             TextBoxType type_, TextBoxPosition position_) {
    messages[LANGUAGE_ENG] = std::move(english_);
    colors = std::move(colors_);
    capital = std::move(capital_);
    type = type_;
    position = position_;
}

CustomMessage::CustomMessage(Text text, TextBoxType type_, TextBoxPosition position_)
    : type(type_), position(position_) {
    messages[LANGUAGE_ENG] = text.GetEnglish();
    messages[LANGUAGE_GER] = text.GetGerman();
    messages[LANGUAGE_FRA] = text.GetFrench();
}

typedef struct {
    u16 textId;
    u8 typePos;
    const char* segment;
    u32 msgSize;
} MessageTableEntry;

extern "C" MessageTableEntry* sNesMessageEntryTablePtr;
extern "C" MessageTableEntry* sGerMessageEntryTablePtr;
extern "C" MessageTableEntry* sFraMessageEntryTablePtr;

CustomMessage CustomMessage::LoadVanillaMessageTableEntry(uint16_t textId) {
    MessageTableEntry* msgEntry = sNesMessageEntryTablePtr;
    u16 bufferId = textId;
    CustomMessage msg;
    if (gSaveContext.language == LANGUAGE_GER) {
        msgEntry = sGerMessageEntryTablePtr;
    } else if (gSaveContext.language == LANGUAGE_FRA) {
        msgEntry = sFraMessageEntryTablePtr;
    }
    while (msgEntry->textId != 0xFFFF) {
        if (msgEntry->textId == bufferId) {
            TextBoxPosition position = static_cast<TextBoxPosition>(msgEntry->typePos & 0xF);
            TextBoxType type = static_cast<TextBoxType>(msgEntry->typePos >> 4);
            // uint8_t icon = msgEntry->segment[1];
            std::string message = std::string(msgEntry->segment, msgEntry->msgSize);
            msg = CustomMessage(message, type, position);
            // msg.Format(static_cast<ItemID>(icon));
            return msg;
        }
        msgEntry++;
    }
    return CustomMessage();
}

const std::string CustomMessage::GetEnglish(MessageFormat format) const {
    return GetForLanguage(LANGUAGE_ENG, format);
}

const std::string CustomMessage::GetGerman(MessageFormat format) const {
    return GetForLanguage(LANGUAGE_GER, format);
}

const std::string CustomMessage::GetFrench(MessageFormat format) const {
    return GetForLanguage(LANGUAGE_FRA, format);
}

const std::string CustomMessage::GetForCurrentLanguage(MessageFormat format) const {
    return GetForLanguage(
        ((Language)gSaveContext.language == LANGUAGE_JPN) ? LANGUAGE_ENG : (Language)gSaveContext.language, format);
}

const std::string CustomMessage::GetForLanguage(uint8_t language, MessageFormat format) const {
    std::string output = !messages[language].starts_with(TODO_TRANSLATE) ? messages[language] : messages[LANGUAGE_ENG];
    ProcessMessageFormat(output, format);
    return output;
}

const std::vector<std::string> CustomMessage::GetAllMessages(MessageFormat format) const {
    std::vector<std::string> output = messages;
    for (auto& str : output) {
        ProcessMessageFormat(str, format);
    }
    return output;
}

void CustomMessage::ProcessMessageFormat(std::string& str, MessageFormat format) const {
    if (format == MF_FORMATTED) {
        FormatString(str);
    } else if (format == MF_CLEAN) {
        CleanString(str);
    } else if (format == MF_AUTO_FORMAT) {
        AutoFormatString(str);
    } else if (format == MF_ENCODE) {
        EncodeColors(str);
    }
}

const std::vector<bool>& CustomMessage::GetCapital() const {
    return capital;
}

void CustomMessage::SetCapital(std::vector<bool> capital_) {
    capital = std::move(capital_);
}
const std::vector<std::string>& CustomMessage::GetColors() const {
    return colors;
}

void CustomMessage::SetColors(std::vector<std::string> colors_) {
    colors = std::move(colors_);
}

const TextBoxType& CustomMessage::GetTextBoxType() const {
    return type;
}

void CustomMessage::SetTextBoxType(TextBoxType boxType) {
    type = boxType;
}

const TextBoxPosition& CustomMessage::GetTextBoxPosition() const {
    return position;
}

void CustomMessage::SetTextBoxPosition(TextBoxPosition boxPos) {
    position = boxPos;
}

static bool MessageHasTerminalBefore(const std::string& text, size_t limit = std::string::npos) {
    for (size_t pos = 0; pos < text.size() && pos < limit;) {
        const auto code = static_cast<unsigned char>(text[pos]);
        if (code == 0x02 || code == 0x07 || code == 0x0B) return true;
        pos += CustomMessageEncoding::TokenLength(text, pos);
    }
    return false;
}

CustomMessage CustomMessage::operator+(const CustomMessage& right) const {
    std::vector<std::string> newColors = colors;
    SohUtils::AppendVector(newColors, right.GetColors());
    std::vector<bool> newCapital = capital;
    SohUtils::AppendVector(newCapital, right.GetCapital());
    CustomMessage result(messages[LANGUAGE_ENG] + right.GetEnglish(MF_RAW),
                         messages[LANGUAGE_GER] + right.GetGerman(MF_RAW),
                         messages[LANGUAGE_FRA] + right.GetFrench(MF_RAW), newColors, newCapital, type, position);
    result.AddHintTargets(hintedItemTargets);
    if (!MessageHasTerminalBefore(GetForCurrentLanguage(MF_RAW))) result.AddHintTargets(right.GetHintTargets());
    return result;
}

CustomMessage CustomMessage::operator+(const std::string& right) const {
    CustomMessage result(messages[LANGUAGE_ENG] + right, messages[LANGUAGE_GER] + right,
                         messages[LANGUAGE_FRA] + right);
    result.AddHintTargets(hintedItemTargets);
    return result;
}

void CustomMessage::operator+=(const CustomMessage& right) {
    const bool visible = !MessageHasTerminalBefore(GetForCurrentLanguage(MF_RAW));
    messages[LANGUAGE_ENG] += right.GetEnglish(MF_RAW);
    messages[LANGUAGE_GER] += right.GetGerman(MF_RAW);
    messages[LANGUAGE_FRA] += right.GetFrench(MF_RAW);
    SohUtils::AppendVector(colors, right.GetColors());
    SohUtils::AppendVector(capital, right.GetCapital());
    if (visible) AddHintTargets(right.GetHintTargets());
}

void CustomMessage::operator+=(const std::string& right) {
    messages[LANGUAGE_ENG] += right;
    messages[LANGUAGE_GER] += right;
    messages[LANGUAGE_FRA] += right;
}

bool CustomMessage::operator==(const CustomMessage& operand) const {
    return messages[LANGUAGE_ENG] == operand.messages[LANGUAGE_ENG];
}

bool CustomMessage::operator==(const std::string& operand) const {
    for (const auto& str : messages) {
        if (str == operand) {
            return true;
        }
    }
    return false;
}

bool CustomMessage::operator!=(const CustomMessage& operand) const {
    return !operator==(operand);
}

namespace {
CustomMessagePageBuffer sCustomMessagePageBuffer;
std::vector<SohExtreme::HintTarget> sPendingHintTargets;
}

void CustomMessage_ResetTextBuffer() {
    sCustomMessagePageBuffer.Clear();
    sPendingHintTargets.clear();
}

int CustomMessage_PrepareTextBuffer(char* buffer, size_t capacity, uint16_t* position, uint32_t* length) {
    if (position == nullptr || length == nullptr) {
        return false;
    }
    return sCustomMessagePageBuffer.Prepare(buffer, capacity, *position, *length);
}

void CustomMessage_RecordDrawnPage(char* buffer, size_t capacity, uint16_t drawn, uint16_t decodedLength) {
    if (sPendingHintTargets.empty() ||
        !sCustomMessagePageBuffer.MarkDrawn(buffer, capacity, drawn, decodedLength)) {
        return;
    }
    // Clear before the client callback: reentrant dialogue cannot reuse this
    // message's targets, and subsequent draw frames cannot publish it twice.
    auto revealed = std::move(sPendingHintTargets);
    sPendingHintTargets.clear();
    SohExtreme::RecordRevealedHintTargets(revealed);
}

void CustomMessage::LoadIntoFont() {
    MessageContext* msgCtx = &gPlayState->msgCtx;
    Font* font = &msgCtx->font;
    uint32_t pageLength = 0;
    sPendingHintTargets.clear();
    // Reformat the selected language after all dynamic hint/item replacements.
    // Already encoded messages keep their native controls and page boundaries.
    if (!sCustomMessagePageBuffer.Load(GetForCurrentLanguage(MF_AUTO_FORMAT), font->msgBuf, sizeof(font->msgBuf),
                                       pageLength)) {
        SPDLOG_ERROR("Custom message has an invalid control or an oversized encoded page");
        sCustomMessagePageBuffer.Load("This message could not be displayed.\x02", font->msgBuf,
                                      sizeof(font->msgBuf), pageLength);
    } else {
        sPendingHintTargets = hintedItemTargets;
    }
    font->charTexBuf[0] = (type << 4) | position;
    msgCtx->msgLength = font->msgLength = pageLength;
}

void CustomMessage::Replace(std::string&& oldStr, std::string&& newStr) {
    if (oldStr != newStr && GetForCurrentLanguage(MF_RAW).find(oldStr) != std::string::npos) {
        // An arbitrary edit may remove the disclosed item. Builders attach
        // provenance after substitutions, or explicitly retain cosmetic edits.
        hintedItemTargets.clear();
    }
    for (std::string& str : messages) {
        size_t position = str.find(oldStr);
        while (position != std::string::npos) {
            str.replace(position, oldStr.length(), newStr);
            position = str.find(oldStr, position + 1);
        }
    }
}

void CustomMessage::Replace(std::string&& oldStr, CustomMessage newMessage) {
    const auto current = GetForCurrentLanguage(MF_RAW);
    const size_t replaced = current.find(oldStr);
    const bool visible = replaced != std::string::npos && !MessageHasTerminalBefore(current, replaced);
    if (replaced != std::string::npos) hintedItemTargets.clear();
    for (uint8_t language = 0; language < LANGUAGE_MAX - 1; language++) {
        size_t position = messages[language].find(oldStr);
        std::string newMsg = newMessage.messages[language];
        if (language != LANGUAGE_ENG && newMsg == TODO_TRANSLATE) {
            newMsg = newMessage.messages[LANGUAGE_ENG];
        }
        while (position != std::string::npos) {
            messages[language].replace(position, oldStr.length(), newMsg);
            position = messages[language].find(oldStr);
        }
    }
    if (visible) AddHintTargets(newMessage.GetHintTargets());
}

void CustomMessage::Format(ItemID iid) {
    for (std::string& str : messages) {
        str.insert(0, ITEM_OBTAINED(iid));
        size_t start_pos = 0;
        std::replace(str.begin(), str.end(), '&', NEWLINE()[0]);
        while ((start_pos = str.find('^', start_pos)) != std::string::npos) {
            str.replace(start_pos, 1, WAIT_FOR_INPUT() + ITEM_OBTAINED(iid));
            start_pos += 3;
        }
        std::replace(str.begin(), str.end(), '@', PLAYER_NAME()[0]);
        ReplaceSpecialCharacters(str);
        ReplaceColors(str);
        ReplaceAltarIcons(str);
    }
    *this += MESSAGE_END();
}

void CustomMessage::Format() {
    for (std::string& str : messages) {
        FormatString(str);
    }
}

void CustomMessage::AutoFormat() {
    for (std::string& str : messages) {
        AutoFormatString(str);
    }
}

void CustomMessage::AutoFormat(ItemID iid) {
    for (std::string& str : messages) {
        str.insert(0, ITEM_OBTAINED(iid));
    }
    AutoFormat();
}

void CustomMessage::Clean() {
    for (std::string& str : messages) {
        CleanString(str);
    }
}

void CustomMessage::Encode() {
    for (std::string& str : messages) {
        EncodeColors(str);
    }
}

void CustomMessage::FormatString(std::string& str) const {
    std::replace(str.begin(), str.end(), '&', NEWLINE()[0]);
    std::replace(str.begin(), str.end(), '^', WAIT_FOR_INPUT()[0]);
    std::replace(str.begin(), str.end(), '@', PLAYER_NAME()[0]);
    ReplaceSpecialCharacters(str);
    ReplaceColors(str);
    ReplaceAltarIcons(str);
    str += MESSAGE_END();
}

void DeleteControlCode(std::string& str, std::string code) {
    size_t start_pos = 0;
    while ((start_pos = str.find(code, start_pos)) != std::string::npos) {
        str.replace(start_pos, code.length(), "");
        start_pos += code.length();
    }
}

void CustomMessage::CleanString(std::string& str) const {
    std::replace(str.begin(), str.end(), '&', "\n"[0]);
    std::replace(str.begin(), str.end(), '^', " "[0]);
    for (const auto& colorPair : percentColors) {
        DeleteControlCode(str, "%" + colorPair.first);
    }
    std::erase(str, '#');
    for (const auto& iconPair : altarIcons) {
        DeleteControlCode(str, "$" + iconPair.first);
    }
}

void CustomMessage::AutoFormatString(std::string& str) const {
    // Encode one complete token at a time. A byte such as '&', '^', or '@'
    // inside a color, item, SFX or TEXTID operand is data, never a directive.
    std::string encoded;
    encoded.reserve(str.size());
    size_t colorIndex = 0;
    bool colorOpen = false;
    for (size_t pos = 0; pos < str.size();) {
        const auto code = static_cast<unsigned char>(str[pos]);
        const size_t length = CustomMessageEncoding::TokenLength(str, pos);
        std::string token = str.substr(pos, length);
        pos += length;
        if (code < 0x20) {
            encoded += token;
            const size_t expected = CustomMessageEncoding::ControlLength(code);
            if (length < expected) encoded.append(expected - length, '\0');
            continue;
        }
        if (token == "#") {
            if (colorOpen) {
                encoded += COLOR(QM_WHITE);
                colorOpen = false;
            } else if (colorIndex < colors.size()) {
                encoded += COLOR(colors[colorIndex++]);
                colorOpen = true;
            }
            continue;
        }
        if (token == "%" && pos < str.size()) {
            const auto color = percentColors.find(str.substr(pos, 1));
            if (color != percentColors.end()) {
                encoded += COLOR(color->second);
                ++pos;
                continue;
            }
        }
        if (token == "$" && pos < str.size()) {
            const auto icon = altarIcons.find(str.substr(pos, 1));
            if (icon != altarIcons.end()) {
                encoded += ITEM_OBTAINED(icon->second);
                ++pos;
                continue;
            }
        }
        if (token == "&") encoded += NEWLINE();
        else if (token == "^") encoded += WAIT_FOR_INPUT();
        else if (token == "@") encoded += PLAYER_NAME();
        else if (token == "_") encoded += ' ';
        else if (const auto special = textBoxSpecialCharacters.find(token); special != textBoxSpecialCharacters.end()) {
            encoded += special->second;
        } else {
            encoded += token;
        }
    }
    auto widthOf = [](const std::string& token) -> size_t {
        if (const auto width = pixelWidthTable.find(token); width != pixelWidthTable.end()) return width->second;
        // Already encoded accented glyphs must measure the same way when a hint
        // is formatted again while composing NPC dialogue or loading the font.
        if (token.size() == 1) {
            for (const auto& special : textBoxSpecialCharacters) {
                if (token[0] == special.second) return pixelWidthTable.at(special.first);
            }
        }
        // Unknown glyphs still consume native decoder/texture slots. Count them
        // conservatively instead of allowing an arbitrarily long zero-width word.
        return 12 * token.size();
    };
    str = CustomMessageFormatting::Wrap(encoded, widthOf);
}

void CustomMessage::InsertNumber(uint8_t num) {
    for (std::string& str : messages) {
        size_t firstBar = str.find('|');
        if (firstBar != std::string::npos) {
            size_t secondBar = str.find('|', firstBar + 1);
            if (secondBar != std::string::npos) {
                size_t thirdBar = str.find('|', secondBar + 1);
                if (thirdBar != std::string::npos) {
                    if (num == 1) {
                        str.erase(secondBar, thirdBar - secondBar);
                    } else {
                        str.erase(firstBar, secondBar - firstBar);
                    }
                }
            }
        }
    }
    // remove the remaining bar
    Replace("|", "");
    Replace("[[d]]", std::to_string(num));
}

void CustomMessage::SetSingularPlural() {
    for (std::string& str : messages) {
        size_t firstBar = str.find('|');
        if (firstBar != std::string::npos) {
            size_t euroSign = str.find("€");
            size_t secondBar = str.find('|', firstBar + 1);
            if (secondBar != std::string::npos) {
                size_t thirdBar = str.find('|', secondBar + 1);
                if (thirdBar != std::string::npos) {
                    if (euroSign == std::string::npos) {
                        str.erase(secondBar, thirdBar - secondBar);
                    } else {
                        str.erase(firstBar, secondBar - firstBar);
                    }
                }
            }
        }
    }
    // remove the remaining bar
    Replace("|", "");
    Replace("€", "");
}

void CustomMessage::Capitalize() {
    for (std::string& str : messages) {
        if (!str.empty()) {
            str[0] = std::toupper(str[0]);
        }
    }
}

void CustomMessage::ReplaceSpecialCharacters(std::string& str) const {
    // add special characters
    for (const auto& specialCharacterPair : textBoxSpecialCharacters) {
        size_t start_pos = 0;
        std::string textBoxSpecialCharacterString = ""s;
        textBoxSpecialCharacterString += specialCharacterPair.second;
        while ((start_pos = str.find(specialCharacterPair.first, start_pos)) != std::string::npos) {
            str.replace(start_pos, specialCharacterPair.first.length(), textBoxSpecialCharacterString);
            start_pos += textBoxSpecialCharacterString.length();
        }
    }
}

const char* Interface_ReplaceSpecialCharacters(char text[]) {
    std::string textString(text);

    for (const auto& specialCharacterPair : textBoxSpecialCharacters) {
        size_t start_pos = 0;
        std::string textBoxSpecialCharacterString = ""s;
        textBoxSpecialCharacterString += specialCharacterPair.second;
        while ((start_pos = textString.find(specialCharacterPair.first, start_pos)) != std::string::npos) {
            textString.replace(start_pos, specialCharacterPair.first.length(), textBoxSpecialCharacterString);
            start_pos += textBoxSpecialCharacterString.length();
        }
    }

    char* textChar = new char[textString.length() + 1];
    strcpy(textChar, textString.c_str());
    return textChar;
}

void CustomMessage::EncodeColors(std::string& str) const {
    for (const std::string& color : colors) {
        if (const size_t firstHashtag = str.find('#'); firstHashtag != std::string::npos) {
            str.replace(firstHashtag, 1, colorToPercent.at(color));
            if (const size_t secondHashtag = str.find('#', firstHashtag + 1); secondHashtag != std::string::npos) {
                str.replace(secondHashtag, 1, "%w");
            } else {
                SPDLOG_DEBUG("non-matching hashtags in string: \"{}\"", str);
            }
        }
    }
    // Remove any remaining '#' characters.
    std::erase(str, '#');
}

void CustomMessage::ReplaceColors(std::string& str) const {
    EncodeColors(str);
    for (const auto& colorPair : percentColors) {
        std::string textToReplace = "%";
        textToReplace += colorPair.first;
        size_t start_pos = 0;
        while ((start_pos = str.find(textToReplace, start_pos)) != std::string::npos) {
            str.replace(start_pos, textToReplace.length(), COLOR(colorPair.second));
            start_pos += textToReplace.length();
        }
    }
}

void CustomMessage::ReplaceAltarIcons(std::string& str) const {
    for (const auto& iconPair : altarIcons) {
        std::string textToReplace = "$";
        textToReplace += iconPair.first;
        size_t start_pos = 0;
        while ((start_pos = str.find(textToReplace, start_pos)) != std::string::npos) {
            str.replace(start_pos, textToReplace.length(), ITEM_OBTAINED(iconPair.second));
            start_pos += textToReplace.length();
        }
    }
}

void CustomMessage::InsertNames(std::vector<CustomMessage> toInsert) {
    for (uint8_t a = 0; a < toInsert.size(); a++) {
        CustomMessage temp = toInsert[a];
        if (capital.size() > a && capital[a]) {
            temp.Capitalize();
        }
        Replace("[[" + std::to_string(a + 1) + "]]", temp);
    }
}

std::string CustomMessage::MESSAGE_END() {
    return "\x02"s;
}

std::string CustomMessage::ITEM_OBTAINED(uint8_t x) {
    return "\x13"s + char(x);
}

std::string CustomMessage::NEWLINE() {
    return "\x01"s;
}

std::string CustomMessage::COLOR(std::string x) {
    return "\x05"s + x;
}

std::string CustomMessage::POINTS(std::string x) {
    return "\x1E"s + x;
}

std::string CustomMessage::WAIT_FOR_INPUT() {
    return "\x04"s;
}

std::string CustomMessage::PLAYER_NAME() {
    return "\x0F"s;
}

std::string CustomMessage::TWO_WAY_CHOICE() {
    return "\x1B"s;
}

std::string CustomMessage::THREE_WAY_CHOICE() {
    return "\x1C"s;
}

bool CustomMessageManager::InsertCustomMessage(const std::string& tableID, uint16_t textID, CustomMessage messages) {
    auto foundMessageTable = messageTables.find(tableID);
    if (foundMessageTable == messageTables.end()) {
        return false;
    }
    auto& messageTable = foundMessageTable->second;
    auto messageInsertResult = messageTable.emplace(textID, std::move(messages));
    return messageInsertResult.second;
}

bool CustomMessageManager::CreateGetItemMessage(const std::string& tableID, uint16_t giid, ItemID iid,
                                                CustomMessage messageEntry) {
    messageEntry.Format(iid);
    const uint16_t textID = giid;
    return InsertCustomMessage(tableID, textID, std::move(messageEntry));
}

bool CustomMessageManager::CreateMessage(const std::string& tableID, uint16_t textID, CustomMessage messageEntry) {
    return InsertCustomMessage(tableID, textID, std::move(messageEntry));
}

CustomMessage CustomMessageManager::RetrieveMessage(const std::string& tableID, uint16_t textID, MessageFormat format) {
    std::unordered_map<std::string, CustomMessageTable>::const_iterator foundMessageTable = messageTables.find(tableID);
    if (foundMessageTable == messageTables.end()) {
        throw(MessageNotFoundException(tableID, textID));
    }
    const CustomMessageTable& messageTable = foundMessageTable->second;
    std::unordered_map<uint16_t, CustomMessage>::const_iterator foundMessage = messageTable.find(textID);
    if (foundMessage == messageTable.end()) {
        throw(MessageNotFoundException(tableID, textID));
    }
    CustomMessage message = foundMessage->second;

    if (format == MF_FORMATTED) {
        message.Format();
    } else if (format == MF_AUTO_FORMAT) {
        message.AutoFormat();
    } else if (format == MF_CLEAN) {
        message.Clean();
    } else if (format == MF_ENCODE) {
        message.Encode();
    }

    return message;
}

bool CustomMessageManager::ClearMessageTable(const std::string& tableID) {
    auto foundMessageTable = messageTables.find(tableID);
    if (foundMessageTable == messageTables.end()) {
        return false;
    }
    auto& messageTable = foundMessageTable->second;
    messageTable.clear();
    return true;
}

bool CustomMessageManager::AddCustomMessageTable(const std::string& tableID) {
    return messageTables.try_emplace(tableID).second;
}
