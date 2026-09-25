SOH-EXTREME 0.11.22 - Soul texture metadata linker fix
=====================================================

Purpose
-------
Fix EnemySoulDraw.obj unresolved externals for:
  ResourceMgr_LoadTexWidthByName
  ResourceMgr_LoadTexHeightByName

Install
-------
1. Close the game and stop any running build.
2. Back up soh/Enhancements/randomizer/EnemySoulDraw.cpp OUTSIDE the soh/
   source tree (for example in patch-backups/texture-link-fix/). Do not leave
   an extra .cpp backup under soh/, since the build uses a recursive glob.
3. Extract this ZIP into E:\test\bb, merge the soh/ folders, and replace
   soh/Enhancements/randomizer/EnemySoulDraw.cpp.
4. Run your existing build.cmd. Do not delete build-vs.

There is no installer, no CMake change, and no replacement build.cmd.
Keep EnemySoulIcons.h, SoulPortraitHQ.h, and the 0.11.22 portrait assets.

What changed
------------
The 0.11.22 renderer called two legacy texture-size functions declared in
ResourceManagerHelpers.h but unresolved by the user's actual game link.
It now loads the resource via the already-implemented
ResourceMgr_GetResourceByNameHandlingMQ, verifies that its registered type
is Fast::ResourceType::Texture, and reads Fast::Texture::Width and Height.
Null resources, absent metadata, non-texture resources, and dimensions
other than 128x128 fail the HQ check and use the existing fallback path.
No fake implementations of the missing functions were added. The type
check precedes a static_pointer_cast; no new RTTI dependency is needed.

All drawing commands, vertex arrays, portrait mappings, billboard size,
128x128 texture tiles, flame/skull/bean/boss drawing, receipt handling,
and C-linkage interpolation declarations remain as in the 0.11.22 renderer.
The resource-name token is still passed to the graphics commands, not a
raw pixel pointer.

Scope
-----
Only EnemySoulDraw.cpp is replaced. No files in arvhipelago, no APWorld,
no version/seed/save changes, no build helpers, and no textures are included.
You do not need to repackage your APWorld for this fix.

Validation performed
--------------------
Using the actual 0.11.22 renderer and its existing soul/HQ mapping headers,
with a mock engine/resource layer:
- The original source fails to link on the two reported function names.
- The replacement compiles, links, and runs with GCC and Clang.
- Both runs use -fno-rtti and AddressSanitizer/UndefinedBehaviorSanitizer.
- Each run checks all 47 HQ mappings, 12 resource/dimension safety cases,
  and the routing/state balance for all 84 soul entries.
- The mock layer deliberately DOES NOT implement either missing wrapper.

These are focused mock-engine tests, not a complete Windows/MSVC game
build, a link against the user's actual libultraship.lib, or a visual test.
The production API names/types were checked against the repository's
resource helpers and texture factory registrations, plus libultraship's
published Fast::Texture header.

Base
----
EnemySoulDraw.cpp from the previously supplied
SOH_EXTREME_0.11.22_Soul_Clarity_Grab_Fix.zip.
Base SHA-256:
290b34d70bea2615a6e37857b6aee5179cd9df455f1e987465e2ed74f98b800e
Replacement SHA-256:
dfe073a76ba038dbc314e46d195a13f9e3d454abcc382d3f6a84fa6b9da48bcc

Source references
-----------------
https://github.com/Mikemik444/SOH_EXTREME-Extreme/blob/main/soh/ResourceManagerHelpers.h
https://github.com/Mikemik444/SOH_EXTREME-Extreme/blob/main/soh/ResourceManagerHelpers.cpp
https://github.com/Mikemik444/SOH_EXTREME-Extreme/blob/main/soh/OTRGlobals.cpp
https://libultraship.com/api/Texture_8h_source.html
