# Test scope

These are isolated production-code tests, not a complete game build. The runner
reads the delivered ExtraTraps.cpp, removes only its include directives, and
compiles its entire remaining implementation against controlled engine services.
It also compiles the delivered ApplySlotSettings method and the exact delivered
Additional Traps menu block. Production hook macros, the OptionValue declaration,
trap-mode enums, setting enums and entrance enum table are supplied under support/.
OptionValue method definitions and engine, UI, persistence and settings services
are controlled test substitutes. Tests do not link libultraship, APCpp, or a game
executable. A before-version method reproduces the actual overwritten preferences.
The support entrance table is from the supplied Shipwright source archive.

The tests cover selector equivalence, preference preservation, simulated config
save/reload, menu visibility, save-switch lifecycle, pending count preservation,
timer expiry, repeated registration and callbacks. There is no AP seed generation,
network test, full Windows/MSVC build, or live menu/gameplay test here.
