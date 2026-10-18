#pragma once

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif
const char* Interface_ReplaceSpecialCharacters(char text[]);
void CustomMessage_ResetTextBuffer(void);
int CustomMessage_PrepareTextBuffer(char* buffer, size_t capacity, uint16_t* position, uint32_t* length);
void CustomMessage_RecordDrawnPage(char* buffer, size_t capacity, uint16_t drawn, uint16_t decodedLength);
#ifdef __cplusplus
};
#endif
