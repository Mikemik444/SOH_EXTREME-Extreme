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
