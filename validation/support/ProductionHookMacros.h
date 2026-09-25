#pragma once
#define REGISTER_VB_SHOULD(flag, body)                                                  \
    GameInteractor::Instance->RegisterGameHookForID<GameInteractor::OnVanillaBehavior>( \
        flag, [](GIVanillaBehavior _, bool* should, va_list _originalArgs) {            \
            va_list args;                                                               \
            va_copy(args, _originalArgs);                                               \
            body;                                                                       \
            va_end(args);                                                               \
        })

#define COND_HOOK(hookType, condition, body)                                                     \
    {                                                                                            \
        static HOOK_ID hookId = 0;                                                               \
        GameInteractor::Instance->UnregisterGameHook<GameInteractor::hookType>(hookId);          \
        hookId = 0;                                                                              \
        if (condition) {                                                                         \
            hookId = GameInteractor::Instance->RegisterGameHook<GameInteractor::hookType>(body); \
        }                                                                                        \
    }
#define COND_ID_HOOK(hookType, id, condition, body)                                                       \
    {                                                                                                     \
        static HOOK_ID hookId = 0;                                                                        \
        GameInteractor::Instance->UnregisterGameHookForID<GameInteractor::hookType>(hookId);              \
        hookId = 0;                                                                                       \
        if (condition) {                                                                                  \
            hookId = GameInteractor::Instance->RegisterGameHookForID<GameInteractor::hookType>(id, body); \
        }                                                                                                 \
    }
#define COND_VB_SHOULD(id, condition, body)                                                           \
    {                                                                                                 \
        static HOOK_ID hookId = 0;                                                                    \
        GameInteractor::Instance->UnregisterGameHookForID<GameInteractor::OnVanillaBehavior>(hookId); \
        hookId = 0;                                                                                   \
        if (condition) {                                                                              \
            hookId = REGISTER_VB_SHOULD(id, body);                                                    \
        }                                                                                             \
    }
