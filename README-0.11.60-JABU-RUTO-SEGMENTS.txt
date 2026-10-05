SOH-EXTREME 0.11.60 - Jabu-Jabu Ruto logic and graphics segment protection

Jabu-Jabu:
The AP Ruto-rescued event now requires Grab / Power Bracelet and being able to
interact with Ruto: NPC Soul and shared Speak or Speak Zora when those are
shuffled. The Boomerang chest, tentacle sequence, Big Octo route and subsequent
checks inherit that event. Previously, AP could grant the rescue event based
only on age/swimming access. Native room logic already checked carrying Ruto.
The final weighted-switch door also explicitly requires Grab, including the
hover shortcut, matching native logic. Initial rooms remain accessible normally.
Unshuffled capabilities remain innate. Physical Strength Upgrade #1 continues
to grant Grab when Grab is shuffled; it is included in the regression coverage.

New crash:
The supplied log confirms a crash on .59 at 14:20 on October 3, in Jabu-Jabu
room 10. Saved .59 symbols resolve it to Interpreter::SegAddr, before vertex
loading. The graphics address 0xFECD00000241FFD7 led to an out-of-range read from
the 16-entry segment table. Both segment-table reads and writes now validate
indices before access. Reads also reject unbound segments and address addition
overflow; writes reject misaligned offsets. Aligned native pointers and valid
interpolation slots preserve their previous behavior.

These errors use .59's frame rejection and rate-limited diagnostics. The
malformed command's original producer is still unidentified. This protects
the demonstrated additional failure path; it is not a guarantee against all
crashes or proof of a memory leak. No live gameplay test was performed.

Install:
Close SOH and extract the Windows package into the game directory, replacing
the matching files. Install the included soh_extreme.apworld into Archipelago's
custom_worlds folder and restart the AP client/tracker. Use matching .60 files.
Keep your saves and oot.o2r. Existing checks and item placements are preserved.
The updated tracker uses corrected requirements for existing seeds, but updates
do not move items already placed behind those requirements. Newly generated
seeds use the corrected Ruto rule during placement.

The package includes all .59 fixes and 20,353 ROM extraction assets. No ROM or
generated oot.o2r is included. The source ZIP contains a cumulative overlay and
verified patch against commit 9bc10e7191b546754a50da6463e074276d33862f. Renderer
fragments are applied to libultraship by CMake, including upgrades from .59.

Validation:
The actual previous SegAddr function reproduces a protected-page access
violation. The new segment harness passes 263,050 assertions covering every
16-bit segment-write offset for both microcodes, valid/invalid segment reads,
unbound and overflowing addresses, the logged malformed address, interpolation,
and recovery through the production vertex handler and rejected-frame wrapper.
All 185,922 earlier vertex/frame assertions pass again. Seven build-patch cases
pass, including clean application, .59 upgrade, idempotence, and atomic rejection
of incompatible source. The production renderer matches the tested fixture.

AP/Universal Tracker tests use real received-item inventories and event sweeps,
without injecting reachability. Coverage includes missing Grab/NPC Soul/speech,
shared and individual speech, disabled shuffles, restored slot settings, no
private enemy graph, child/adult access, early accessible checks, dependent
checks, and physical Strength Upgrade behavior. The release validation report
records the exact old/new results, build result, hashes and archive integrity.
All 1,682 AP/UT assertions pass; old .59 fails 104 of those same assertions.
