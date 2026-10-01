SOH-EXTREME 0.11.42 - Boulder cleanup and delayed item presentations
Repository: https://github.com/Mikemik444/SOH_EXTREME-Extreme

WHAT CHANGED
Collected randomized boulders stop displaying reward halos and follow their
normal destruction flags. Silver boulders record the normal removal switch
when thrown. An uncollected randomized reward can still be recovered after
leaving and returning; collecting it ends that exception. Small rocks retain
their original respawn behavior. Existing soul/strength requirements remain.
An older save may need one more normal destruction if its removal switch was
previously suppressed. Reload the area for saved removal flags to take effect.

Corrected an interrupted-item offer that could block the AP receive queue.
The player update clears the offer's interaction pointer while retaining its
item fields. The retry now recognizes that exact pending AP item and offers
it again on the next safe update, instead of waiting for the long timeout.
Real NPC/chest offers and mismatched items are protected. Important items
still use hold-up animations; actual receipt commits each item exactly once.
Transition, cutscene, water, death and other safety checks remain in place.

Rock drops explicitly carry their check identity for the existing AP pickup
handler. Collectible allocation failure is handled without a null dereference
or consuming an uncollected check.

The inspected .41 log sent DMT rock checks within 0-1 ms, with received-item
messages around 50 ms later. The Slingshot hold-up waited over 7 seconds while
later items queued behind it. This is evidence of a presentation queue stall;
it does not prove accumulated item history itself increases network latency.
Normal network travel and time spent in animations/unsafe states still apply.

KEEP YOUR SEED AND SAVE
There are no changes to placements, location IDs, item IDs or logic from .41.
The APWorld update is version-only, matching the game's tracker version.
Keep your current server/multidata and save. Do not regenerate for this fix.
Earlier cumulative logic/catalog updates retain their documented caveats.

WINDOWS DRAG-AND-DROP
1. Close SOH. Extract the Windows ZIP into the folder containing the soh.exe
   you actually launch (E:\test\bb\x64\Release in the inspected installation).
   Replace both soh.exe and APCpp.dll. Keep your existing assets and saves.
2. Install the included soh_extreme.apworld with Archipelago's installer, or
   replace its existing copy in custom_worlds. Restart Archipelago/Universal
   Tracker and the in-game AP tracker to load the matching .42 version.
3. Reconnect to the existing seed. Re-enter the area to refresh boulders.
   The startup log should say SOH-EXTREME runtime 0.11.42 loaded.

SOURCE DRAG-AND-DROP
Extract the Source-Patch ZIP into the source root beside build.cmd, replacing
the included files. Run build.cmd in a fresh Command Prompt. Wait for BUILD
SUCCESS, then use the generated runtime and install the matching .42 APWorld.
This cumulative overlay targets commit 9bc10e7191b546754a50da6463e074276d33862f.
Preserve unrelated local edits. The Windows ZIP does not require a build.

VALIDATION
Windows Release build passed. Compiled production-function harnesses passed
493 boulder lifecycle assertions and 18044 receipt assertions, including 4000
consecutive interrupted offers. The targeted new tests fail against .41's
production functions. Five delivery/save regression groups and the rebuilt
DLL callback ABI test passed. APWorld matches all 104 source files, differs
from .41 only in version strings, and ZIP/patch integrity checks passed.

The harnesses substitute rendering/allocation/network services. No connected
game latency measurement or rendered boulder playtest was performed here.
Earlier crash guards and .41 legacy enemy-check compatibility are retained.
See VALIDATION-0.11.42-FIXES.json, TEST-EVIDENCE-0.11.42-FIXES.json and
SOH_AP_FIX_HISTORY.txt for evidence and earlier limitations.
