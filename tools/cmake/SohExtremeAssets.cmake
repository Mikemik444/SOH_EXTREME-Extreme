# SOH-EXTREME asset build, shared by both historical checkout layouts.
# Tool source discovery is deliberately independent of assets/custom: that
# directory can exist with only the few resources installed by a patch.
set(_soh_extreme_root "${CMAKE_CURRENT_SOURCE_DIR}")
set(_soh_packer_dir "")
foreach(_candidate IN ITEMS
        "${_soh_extreme_root}/soh/assets/tools/soh-o2r-packer"
        "${_soh_extreme_root}/assets/tools/soh-o2r-packer")
    if(EXISTS "${_candidate}/main.cpp" AND
       EXISTS "${_candidate}/PngTexture.cpp" AND
       EXISTS "${_candidate}/PngTexture.h")
        set(_soh_packer_dir "${_candidate}")
        break()
    endif()
endforeach()
if(NOT _soh_packer_dir)
    message(FATAL_ERROR
        "soh-o2r-packer sources are missing from both soh/assets/tools and assets/tools. "
        "Restore main.cpp, PngTexture.cpp and PngTexture.h; do not delete build-vs.")
endif()
if(NOT TARGET torch)
    message(FATAL_ERROR "Include SohExtremeAssets.cmake after add_subdirectory(Torch).")
endif()

message(STATUS "SOH-EXTREME packer source: ${_soh_packer_dir}")
add_executable(soh-o2r-packer EXCLUDE_FROM_ALL
    "${_soh_packer_dir}/main.cpp"
    "${_soh_packer_dir}/PngTexture.cpp"
)
target_include_directories(soh-o2r-packer PRIVATE
    "${_soh_extreme_root}/Torch/src"
    "${_soh_packer_dir}"
)
target_compile_features(soh-o2r-packer PRIVATE cxx_std_17)
target_link_libraries(soh-o2r-packer PRIVATE torch)
if(MSVC)
    set_property(TARGET soh-o2r-packer PROPERTY
        MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")
    target_compile_options(soh-o2r-packer PRIVATE /EHsc /FS /MP1)
endif()

# Follow the library actually selected by this build when available.
set(_soh_shader_dir "${_soh_extreme_root}/../libultraship/src/fast/shaders")
if(TARGET libultraship)
    get_target_property(_soh_lus_dir libultraship SOURCE_DIR)
    if(_soh_lus_dir AND EXISTS "${_soh_lus_dir}/src/fast/shaders")
        set(_soh_shader_dir "${_soh_lus_dir}/src/fast/shaders")
    endif()
endif()

# Staging and packing share a lock. A failed pack never replaces a valid output.
# Neither source asset tree is removed or overwritten during this operation.
add_custom_target(GenerateSohOtr
    COMMAND "${CMAKE_COMMAND}"
        "-DSOH_SOURCE_ROOT:PATH=${_soh_extreme_root}"
        "-DSOH_BUILD_ROOT:PATH=${CMAKE_BINARY_DIR}"
        "-DSOH_SHADER_DIR:PATH=${_soh_shader_dir}"
        "-DSOH_PACKER:FILEPATH=$<TARGET_FILE:soh-o2r-packer>"
        "-DSOH_PORT_VERSION:STRING=${CMAKE_PROJECT_VERSION}"
        -P "${CMAKE_CURRENT_LIST_DIR}/PackSohExtremeAssets.cmake"
    DEPENDS soh-o2r-packer
    BYPRODUCTS "${CMAKE_BINARY_DIR}/soh/soh.o2r"
    COMMENT "Generating soh.o2r from the complete asset tree and local overlays..."
    VERBATIM
)

# BEGIN SOH-EXTREME ASSET HEADER SEARCH PATH FIX
# Packing soh.o2r and compiling the game are separate operations. The packer
# above already supports both layouts, but soh.exe also needs the directories
# containing the resource-name headers (not assets/custom or the staging tree).
if(NOT TARGET soh)
    message(FATAL_ERROR
        "Include SohExtremeAssets.cmake after the soh executable target is created.")
endif()
set(_soh_asset_header_dirs "")
foreach(_soh_header_root IN ITEMS
        "${_soh_extreme_root}/assets"
        "${_soh_extreme_root}/soh/assets")
    if(IS_DIRECTORY "${_soh_header_root}")
        list(APPEND _soh_asset_header_dirs "${_soh_header_root}")
    endif()
endforeach()

# Check actual headers, not just the existence of assets/. Previous texture
# patches may have created a root assets/custom/ overlay without these headers.
foreach(_soh_required_header IN ITEMS
        "soh_assets.h"
        "textures/icon_item_static/icon_item_static.h")
    set(_soh_header_found FALSE)
    foreach(_soh_header_root IN LISTS _soh_asset_header_dirs)
        if(EXISTS "${_soh_header_root}/${_soh_required_header}" AND
           NOT IS_DIRECTORY "${_soh_header_root}/${_soh_required_header}")
            set(_soh_header_found TRUE)
            break()
        endif()
    endforeach()
    if(NOT _soh_header_found)
        message(FATAL_ERROR
            "Missing asset header: ${_soh_required_header}. "
            "Checked ${_soh_extreme_root}/assets and ${_soh_extreme_root}/soh/assets. "
            "Restore the matching header from your source checkout; rebuilding "
            "soh.o2r does not create it. Keep build-vs and your existing build.cmd.")
    endif()
endforeach()

# SOH-EXTREME asset header fix v2: support BOTH include spellings used by
# the game. Bare "soh_assets.h" and "textures/..." need the assets directory;
# "assets/soh_assets.h" (ImGuiUtils.cpp) needs its PARENT directory instead.
# In the nested checkout these are <root>/soh/assets and <root>/soh.
# Do not copy headers: both spellings must resolve to the same physical file.
set(_soh_asset_include_dirs ${_soh_asset_header_dirs})
foreach(_soh_header_root IN LISTS _soh_asset_header_dirs)
    get_filename_component(_soh_header_parent "${_soh_header_root}" DIRECTORY)
    list(APPEND _soh_asset_include_dirs "${_soh_header_parent}")
endforeach()
list(REMOVE_DUPLICATES _soh_asset_include_dirs)

# Append, never replace, the target's existing include directories. Keep the
# legacy root assets before nested assets so local overrides retain precedence.
# PRIVATE confines this repair to the game; dependency targets are unchanged.
target_include_directories(soh AFTER PRIVATE ${_soh_asset_include_dirs})
message(STATUS "SOH-EXTREME game asset header paths (v2): ${_soh_asset_include_dirs}")
unset(_soh_asset_include_dirs)
unset(_soh_asset_header_dirs)
unset(_soh_header_root)
unset(_soh_header_parent)
unset(_soh_required_header)
unset(_soh_header_found)
# END SOH-EXTREME ASSET HEADER SEARCH PATH FIX
