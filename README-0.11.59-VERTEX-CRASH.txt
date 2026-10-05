SOH-EXTREME 0.11.59 - Renderer vertex bounds and malformed-frame protection

The supplied October 2 log contains a 17:11 Jabu-Jabu crash on runtime .55,
after 611 received items. Saved .55 debug symbols resolve the access violation
to GfxSpModifyVertex. The vertex index in the registers is 0x4DFF (19,967),
outside the normal 64-slot vertex buffer. An unknown graphics opcode appeared
immediately beforehand. The log does not establish an out-of-memory condition
or a leak caused by item collection.

This update validates vertex loads, vertex modifications, triangle references,
and branch vertex references before using them. Unsigned range overflow and
underflow are rejected. Rectangle rendering retains its four scratch vertices.
Unknown opcodes, invalid microcode, and invalid vertex commands stop the rest
of that graphics frame. Valid queued geometry is flushed before restoring the
normal framebuffer. Command/caller state is cleared for the next frame.

Raw command words, microcode, and caller addresses are logged without reading
untrusted embedded filenames. Repeated errors are rate limited. This handles
the demonstrated failure path; it does not prove which code originally produced
the malformed display list, nor does it guarantee every possible crash is fixed.
A rejected frame can be visibly incomplete. Unrelated engine exceptions remain
visible instead of being swallowed.

Install:
Close SOH, extract the Windows package into your game folder, and replace the
matching files. Install the included soh_extreme.apworld into Archipelago's
custom_worlds folder and restart the AP client/tracker for matching .59 versions.
Keep your saves and oot.o2r. No seed regeneration is needed for this renderer
change. Existing placements and location IDs are unchanged. Includes all prior
.58 fixes and the ROM extraction assets; no ROM or generated oot.o2r is included.

Source:
The source ZIP contains the cumulative overlay and a patch against commit
9bc10e7191b546754a50da6463e074276d33862f. Its CMake integration applies the
renderer changes to the libultraship dependency during configuration. Keep
Cmake/SohExtremeVertexSafety.cmake, SohExtremeVertexEdits.json, and the two
new .cpp.inc fragments together. Unrecognized affected source is rejected
without partially overwriting the dependency.

Validation:
A protected-page harness using the actual old MODIFYVTX function reproduces
access violation 0xC0000005 for the logged index. The new native harness passes
185,922 assertions, including every uint16 vertex modification index, range
overflow/underflow, all triangle index bytes, all 12-bit branch indices, stopping
bad command streams, valid next frames, framebuffer recovery, nested callers,
10,000 rejected frames with bounded logging, and unrelated exception propagation.
Actual command dispatch and frame execution are compiled; vertex load/triangle
shader bodies are replaced by test sentinels after their production guards.
This is not a live GPU or game playtest.

Five CMake patch cases pass, covering baseline application, idempotence, and
atomic rejection of missing, ambiguous, or altered patch targets. Production
renderer source matches the tested fixture. The Windows Release build, APWorld
parity, source patch application, and archive integrity are checked separately.
