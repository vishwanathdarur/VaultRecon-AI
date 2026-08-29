cmake_minimum_required(VERSION 3.14)
project(VaultReconAI VERSION 1.0.0 LANGUAGES CXX C)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

include_directories(
    ${CMAKE_CURRENT_SOURCE_DIR}/MiniVaultDB/include
)

file(GLOB_RECURSE MINIVAULTDB_SRCS
    ${CMAKE_CURRENT_SOURCE_DIR}/MiniVaultDB/src/*.cpp
)

add_library(minivaultdb SHARED ${MINIVAULTDB_SRCS})
set_target_properties(minivaultdb PROPERTIES OUTPUT_NAME "minivaultdb")

add_library(minivaultdb_static STATIC ${MINIVAULTDB_SRCS})
set_target_properties(minivaultdb_static PROPERTIES OUTPUT_NAME "minivaultdb")

# Optional Pybind11 / Executable targets if desired
enable_testing()

