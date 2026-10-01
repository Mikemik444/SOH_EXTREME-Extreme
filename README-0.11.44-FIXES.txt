SOH-EXTREME 0.11.44 - Enemy logic, Market crash safeguard, and soul artwork

READY-TO-RUN DRAG/DROP UPDATE
1. Close SOH. Open the folder containing the soh.exe you actually launch
   (for your recent logs: E:\test\bb\x64\Release).
2. Extract soh.exe, APCpp.dll AND soh.o2r from the Windows x64 ZIP into that
   folder, replacing all three together. The new O2R contains the new soul art.
   Leave your ROM archives, save files and configuration in place.
3. Install the included soh_extreme.apworld into Archipelago's custom_worlds
   folder, replacing the old SOH-EXTREME APWorld. Restart the AP client and UT.
   Use Refresh AP checks / Restart AP Tracker if a tracker was already open.

SOURCE BUILD ALTERNATIVE
Extract the Source-Patch ZIP over your SOH_EXTREME-Extreme source root (the
folder containing build.cmd), then run build.cmd in a new command prompt.
The source overlay includes the PNG/SVG artwork, CMake dependency patches and
all earlier cumulative changes. It is based on commit
9bc10e7191b546754a50da6463e074276d33862f. A binary-capable cumulative Git patch
is also included as an alternative; do not apply both methods.
The source overlay does not contain the compiled EXE/DLL/O2R.

WHAT CHANGED
- Corrected 200 enemy placements' combat classifications. The rules distinguish
  damage from stun-only attacks for Tektites, Peahats, Shaboms, Biri/Bari,
  Tailpasarans, Stingers and Bubbles, plus specific rules for Armos, Dead Hand
  and its arms, Skull Kid, Freezard and Spike. Applicable souls and actual
  room routes remain required. Ordinary Skulltulas keep their separate soul.
- The eight Market Ruins Redeads require adult access. Having adult equipment
  while unable to become adult no longer qualifies them.
- Child Grab no longer bypasses the Dodongo's Cavern lobby-switch ledge and
  the earlier Lizalfos fight. Adult access and enabled tricks stay alternatives.
- The native finder now includes Peahat daytime activation and the missing
  Composer / Big Octo interaction gates, consistent with AP rules.
- Shared NPC regions no longer mark all Market checks as current Kakariko checks.
- Redesigned animal/category/bean/boss soul icons; clearer existing enemy
  portraits in the tracker; beveled pickup medallions with a smaller flame.
  The 47 existing enemy portraits are reused. Native texture tiles stay 32px;
  the larger artwork is only used in the GUI.

CRASH FINDING AND LIMIT
Both supplied .43 Market crashes jumped to 0x5AC4D9B0, the truncated low half
of that build's EnButte_Draw callback. The new safeguard restores only this
exact fault pattern for an initialized butterfly whose native update and
cleanup callbacks still match. It does not restore hidden/dying actors or
replace legitimate callbacks. A controlled injected-fault test reproduces the
execute violation and verifies this containment.
The write that damaged the pointer has NOT been identified. This is a safeguard
against the observed failure, not proof that every random/transition crash is
fixed. Crash reports now preserve real fault/caller addresses, module RVAs and
active actor details even without PDB files, to make further failures actionable.
The earlier bounded-TLUT renderer fix is retained.

VALIDATION
- Release x64 build succeeds; matching APCpp DLL loads and callback ABI passes.
- All 739 active enemy checks audited through AP and the real UT evaluator:
  fresh missing-soul/capability states, shared/individual/off souls, adult
  access, frozen day/night, Sun's Song alternative, and focused weapon cases.
- Native finder tests cover every catalogue row against all age/time masks,
  state restoration, room conditions and specific damage/activation cases.
- DC route, Market adult access, tracker grouping, soul rendering/resource
  bounds and Windows crash containment/diagnostics have targeted regressions.
- Fresh generation and independent progression replay of the saved supplied
  settings fixture reached the goal and all 3,311 network checks. No rejection
  by the additional source-derived interaction constraints.
- All 222 new textures checked against the final O2R; APWorld checked byte for
  byte against source; ZIP integrity and cumulative patch application checked.

These are source/rule tests and controlled native harnesses, not a complete
in-game playthrough of every location. They do not certify 100% of physical
routes, settings combinations or absence of future crashes.

EXISTING SEEDS
Existing saves and location/item IDs are preserved; the earlier retired checks
remain reserved. Your seed's item placements do not move when logic is fixed.
Install the matching APWorld for tracker rules. Generate a new seed with this
APWorld to use the corrected generation rules; no claim is made that an older
seed's placements become beatable automatically.

See VALIDATION-0.11.44-FIXES.json and TEST-EVIDENCE-0.11.44-FIXES.json for details.
