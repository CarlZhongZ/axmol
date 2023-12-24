


if(BUILD_SHARED_LIBS)
  cmake_policy(SET CMP0079 NEW)
endif()

function(setup_ax_extension_config target_name)
  set(options DNTLINK opt_DNTLINK)
  set(options LINK_SCOPE opt_LINK_SCOPE)
  cmake_parse_arguments(opt "" "${options}" ""
                          "" ${ARGN} )

  target_link_libraries(${target_name} ${opt_LINK_SCOPE} ${_AX_CORE_LIB})

  if(BUILD_SHARED_LIBS)
    target_compile_definitions(${target_name} PRIVATE _USREXDLL=1)
  endif()

  set_target_properties(${target_name}
      PROPERTIES
      ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/lib"
      LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/lib"
      RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
      FOLDER "Extensions"
  )

  if (WINRT)
    set_property(TARGET ${target_name} PROPERTY VS_PROJECT_IMPORT ${CMAKE_BINARY_DIR}/packages/Microsoft.Windows.CppWinRT/build/native/Microsoft.Windows.CppWinRT.props)
  endif()

  if(NOT opt_DNTLINK)
      set(_AX_EXTENSION_LIBS "${target_name};${_AX_EXTENSION_LIBS}" CACHE INTERNAL "extensions for auto link to target application")
  endif()

  if(XCODE OR VS)
    ax_mark_code_files("${target_name}")
  endif()

endfunction()

if(AX_ENABLE_EXT_GUI)
  add_subdirectory(GUI)
endif()

if(AX_ENABLE_EXT_PARTICLE3D)
  add_subdirectory(Particle3D)
endif()

if(AX_ENABLE_EXT_PHYSICS_NODE)
  add_subdirectory(physics-nodes)
endif()

if(AX_ENABLE_EXT_SPINE)
  add_subdirectory(spine)
endif()

if(AX_ENABLE_EXT_DRAGONBONES)
  add_subdirectory(DragonBones)
endif()

if(AX_ENABLE_EXT_LIVE2D)
  add_subdirectory(Live2D)
endif()

if (AX_ENABLE_EXT_EFFEKSEER)
  add_subdirectory(Effekseer)
endif()

if(AX_ENABLE_EXT_LUA)
  add_subdirectory(scripting/lua-bindings)
endif()

if(AX_ENABLE_EXT_JSONDEFAULT)
  add_subdirectory(JSONDefault)
endif()

message(STATUS "Enabled ${_AX_CORE_LIB} extensions:${_AX_EXTENSION_LIBS}")
