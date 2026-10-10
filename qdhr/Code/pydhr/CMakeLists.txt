# include paths for qdhr, the internal dhr API, and Python
set(MODULE_INCLUDES
    PRIVATE ${CMAKE_SOURCE_DIR}/qdhr
    PRIVATE ${CMAKE_SOURCE_DIR}/dhr/api/replay
    PRIVATE ${PYTHON_INCLUDE_DIR})
  
# preprocessor definitions for compiling
set(MODULE_DEFINES
    PRIVATE -DDHR_PLATFORM_LINUX)

if(CMAKE_CXX_COMPILER_ID MATCHES "Clang")
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wno-unknown-warning-option -Wno-unused-private-field -Wno-shadow -Wno-shorten-64-to-32")

    if(CMAKE_CXX_COMPILER_VERSION VERSION_GREATER 19)
        set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wno-cast-function-type")
    endif()
endif()

if(CMAKE_COMPILER_IS_GNUCXX)
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wno-cast-function-type -Wno-stringop-truncation")
endif()

set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wno-deprecated-declarations")

# Set up rpath to find libdhr.so
set(CMAKE_SKIP_BUILD_RPATH TRUE)
set(CMAKE_BUILD_WITH_INSTALL_RPATH TRUE)
if (APPLE)
    set(CMAKE_MACOSX_RPATH TRUE)
    set(CMAKE_INSTALL_RPATH "@loader_path/../lib")
    set(CMAKE_BUILD_WITH_INSTALL_NAME_DIR TRUE)
else()
    set(CMAKE_INSTALL_RPATH "$ORIGIN/:$ORIGIN/../lib${LIB_SUFFIX}/${LIB_SUBFOLDER_TRAIL_SLASH}")
endif()

# Add python library
set (CMAKE_SHARED_LINKER_FLAGS "${PYTHON_LIBRARY} ${CMAKE_SHARED_LINKER_FLAGS}")

add_library(_dhr SHARED
    ${CMAKE_BINARY_DIR}/qdhr/dhr_python.cxx
    pydhr_stub.cpp)

set_source_files_properties(${CMAKE_BINARY_DIR}/qdhr/dhr_python.cxx
                            PROPERTIES GENERATED TRUE)

target_compile_definitions(_dhr ${MODULE_DEFINES})
target_include_directories(_dhr ${MODULE_INCLUDES})
target_link_libraries(_dhr PRIVATE dhr)

add_library(_qdhr SHARED
    ${CMAKE_BINARY_DIR}/qdhr/dhr_python.cxx
    ${CMAKE_BINARY_DIR}/qdhr/qdhr_python.cxx
    pydhr_stub.cpp
    qdhr_stub.cpp)

set_source_files_properties(${CMAKE_BINARY_DIR}/qdhr/qdhr_python.cxx
                            PROPERTIES GENERATED TRUE)

target_compile_definitions(_qdhr ${MODULE_DEFINES})
target_include_directories(_qdhr ${MODULE_INCLUDES})
target_link_libraries(_qdhr PRIVATE dhr)

# Python expects .so extension when importing shared libraries on non-Windows platform
if(APPLE)
    set_target_properties(_dhr PROPERTIES SUFFIX ".so")
    set_target_properties(_qdhr PROPERTIES SUFFIX ".so")
endif()

# Don't prefix with lib, python expects a bare .so.
# Also rename to non-underscore due to this (We couldn't call the
# python library 'dhr' since that would clash with the
# prefixed target)
set_target_properties(_dhr PROPERTIES PREFIX "")
set_target_properties(_qdhr PROPERTIES PREFIX "")
set_target_properties(_dhr PROPERTIES OUTPUT_NAME "dhr")
set_target_properties(_qdhr PROPERTIES OUTPUT_NAME "qdhr")

# Make sure we build after the wrappers are generated
add_dependencies(_dhr swig-bindings)
add_dependencies(_qdhr swig-bindings)
