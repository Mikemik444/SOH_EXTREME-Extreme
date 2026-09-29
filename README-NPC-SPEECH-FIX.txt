SOH-EXTREME NPC Speech Sanity repair - 2026-09-29
Version 0.11.29; cumulative Windows x64 Release
Repository: https://github.com/Mikemik444/SOH_EXTREME-Extreme
Source base: 9bc10e7191b546754a50da6463e074276d33862f

WHY NO KOKIRI CHECKS WERE SENT
The supplied seed had NPC Speech Sanity enabled in the AP options and native
settings. The log also showed receipt of Speak Kokiri and NPC Soul. The old
114-entry speech catalogue used reward locations and shop shelves; it omitted
ordinary Kokiri conversations. The generic fallback had no server locations.
The setting was linked correctly. The previous audit missed this coverage gap.

WHAT THIS FIX DOES
- Adds a catalogue of 181 first-conversation identities, including all thirteen
  Kokiri children, Mido, Saria and the Kokiri shopkeeper. A moving character or
  character with child/adult models shares one identity. Shopkeepers have one
  speech check, separate from their shop shelves.
- The first eligible manual conversation sends its check. Following conversations
  run normally, even while the first check awaits server acknowledgment. Scripted
  introductions keep running and are also recognized. Pending checks retry using
  the existing saved outbox after a disconnect.
- Uses the NPC selected for talking, including C-Up, and excludes Navi's enemy
  descriptions. Scripted dialogue checks reject stale actor pointers.
- Adds conversation rules and finder rows. NPC Soul and the correct language are
  required when shuffled, together with the route's age/time/access requirements.
  No purchase or normal reward is required just to talk to an accessible NPC.
- Keeps Sheik's normal conversation and the Mask Shop guest available until their
  new speech check is collected. Old seeds retain their original location IDs.
- Includes the previous cumulative repairs from this chat: all-abilities logic,
  souls, Mido, Zora River, grass strength, crates, frozen time, scrub prices,
  fishing, AP hints and pickup text, hold-up animation, heart healing, full wallets,
  Triforce completion, build/source parity and network safety changes.

NEW SEED REQUIRED FOR THESE NPC CHECKS
Your current AP_32037442678715337267 multiworld does not contain the new Kokiri
locations. Replacing the executable cannot add them to its server. Install the
matching APWorld, generate a NEW multiworld with npc_speech_sanity enabled and
start a save for that new seed. Reconnect other players to the new room as needed.
Existing saves and server placements have not been modified by this repair.

READY-BUILT WINDOWS REPLACEMENT (NO BUILD REQUIRED)
1. Close SOH and Archipelago/Universal Tracker. Keep a copy of the old files.
2. Extract SOH-EXTREME-NPC-Speech-Fix-Windows-x64.zip. Copy soh.exe and APCpp.dll
   into your existing game folder beside its current soh.exe, replacing both.
   Keep the existing assets, soh.o2r, configuration and saves.
3. Install the included soh_extreme.apworld with Archipelago's Install APWorld
   action. Restart Archipelago/Universal Tracker so it loads version 0.11.29.
4. Generate a new multiworld and start a new seed/save, as described above.

SOURCE OVERLAY ALTERNATIVE
1. Close SOH and AP/Universal Tracker.
2. Extract the CONTENTS of SOH-EXTREME-NPC-Speech-Fix-Source-Patch.zip into your
   source root beside build.cmd and CMakeLists.txt. Merge folders and replace files.
3. Open a FRESH Command Prompt in that folder and run build.cmd.
4. Wait for BUILD COMPLETE. The build packages/verifies and installs its matching
   APWorld and copies the runtime to the source root. Restart AP/Universal Tracker.
5. Generate a new multiworld and start a new seed/save.
The included .patch is for Git/review; do not apply it again after copying files.

VALIDATION PERFORMED FOR THIS RELEASE
- 127 AP/Universal Tracker/old-and-new-slot assertions and 215 compiled C++
  first-talk, identity, language, pending/outbox and dialogue assertions passed.
- 181 fresh-inventory scenarios covered all 3,325 configured final AP checks:
  601,825 AP/Universal Tracker comparisons with no failures.
- Explicit day-start and frozen-night seed generation each filled successfully;
  independent collection replay reached the goal and every final AP check.
- MSVC Windows x64 Release build completed. The 102-file APWorld was verified
  byte-for-byte against tested source. DLL loading, forward/reverse cumulative
  patch application and every ZIP entry were checked.

LIMITS
There has been no connected in-game playthrough of this release. The 181-entry
catalogue is finite, not every possible dialogue actor: cinematic scenery,
capturing Gerudo sentries (including their later dialogue) and the transient
membership-card giver are excluded. Certain moving/story NPC routes deliberately
use conservative guaranteed access rules.
The source audit retains physical region/encounter review gaps. Agreement between
AP and UT does not prove every physical obstacle or every setting combination.
Earlier suites not rerun are identified as historical evidence in the JSON report.

FILES
README-NPC-SPEECH-FIX.txt: installation, behavior and scope
VALIDATION-NPC-SPEECH-FIX.json: results, hashes and limitations
CHECK-AUDIT-NPC-SPEECH.json: source coverage and fresh-inventory evidence
SOH_AP_FIX_HISTORY.txt: cumulative reports and decisions from this chat
SHA256SUMS-NPC-SPEECH-FIX.txt: checksums of the contents of each ZIP
