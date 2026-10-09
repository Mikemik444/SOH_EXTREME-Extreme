# Populate local builds as well as CI builds, without changing save/asset versions.
find_package(Git QUIET)
if(GIT_FOUND)
    execute_process(COMMAND "${GIT_EXECUTABLE}" rev-parse --show-toplevel
        WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}"
        OUTPUT_VARIABLE _soh_git_root OUTPUT_STRIP_TRAILING_WHITESPACE ERROR_QUIET)
    cmake_path(NORMAL_PATH _soh_git_root)
    cmake_path(NORMAL_PATH CMAKE_CURRENT_SOURCE_DIR OUTPUT_VARIABLE _soh_source_root)
    # A source archive inside some other repository must not inherit its metadata.
    if(_soh_git_root STREQUAL _soh_source_root)
        foreach(_soh_field IN ITEMS BRANCH COMMIT_HASH COMMIT_TAG)
            if(NOT CMAKE_PROJECT_GIT_${_soh_field})
                if(_soh_field STREQUAL "BRANCH")
                    set(_soh_args rev-parse --abbrev-ref HEAD)
                elseif(_soh_field STREQUAL "COMMIT_HASH")
                    set(_soh_args rev-parse --short=12 HEAD)
                else()
                    set(_soh_args describe --tags --exact-match HEAD)
                endif()
                execute_process(COMMAND "${GIT_EXECUTABLE}" ${_soh_args}
                    WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}"
                    OUTPUT_VARIABLE CMAKE_PROJECT_GIT_${_soh_field}
                    OUTPUT_STRIP_TRAILING_WHITESPACE ERROR_QUIET)
                if(_soh_field STREQUAL "COMMIT_HASH" AND CMAKE_PROJECT_GIT_COMMIT_HASH)
                    execute_process(COMMAND "${GIT_EXECUTABLE}" status --porcelain --untracked-files=normal
                        WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}"
                        OUTPUT_VARIABLE _soh_changes ERROR_QUIET)
                    if(_soh_changes)
                        string(APPEND CMAKE_PROJECT_GIT_COMMIT_HASH " (modified)")
                    endif()
                endif()
            endif()
        endforeach()
    endif()
endif()
if(NOT CMAKE_PROJECT_GIT_BRANCH)
    set(CMAKE_PROJECT_GIT_BRANCH "Source archive")
endif()
if(NOT CMAKE_PROJECT_GIT_COMMIT_HASH)
    set(CMAKE_PROJECT_GIT_COMMIT_HASH "Not recorded")
endif()
# Escape metadata before it is substituted into C string literals.
foreach(_soh_field IN ITEMS BRANCH COMMIT_HASH COMMIT_TAG)
    string(REPLACE "\\" "\\\\" CMAKE_PROJECT_GIT_${_soh_field} "${CMAKE_PROJECT_GIT_${_soh_field}}")
    string(REPLACE "\"" "\\\"" CMAKE_PROJECT_GIT_${_soh_field} "${CMAKE_PROJECT_GIT_${_soh_field}}")
    string(REPLACE "\n" "\\n" CMAKE_PROJECT_GIT_${_soh_field} "${CMAKE_PROJECT_GIT_${_soh_field}}")
    string(REPLACE "\r" "\\r" CMAKE_PROJECT_GIT_${_soh_field} "${CMAKE_PROJECT_GIT_${_soh_field}}")
endforeach()
