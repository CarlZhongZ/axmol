set(ax_root ${_AX_ROOT})

set(lua_bindings_files
    manual/Lua-BindingsExport.h

    manual/LuaEngine.h
    manual/LuaEngine.cpp
    manual/LuaStack.h
    manual/LuaStack.cpp
    manual/LuaBridge.h
    manual/LuaBridge.cpp
    manual/LuaValue.h
    manual/LuaValue.cpp
    manual/AxluaLoader.h
    manual/AxluaLoader.cpp
    manual/lua_module_register.h
    manual/lua_module_register.cpp
    manual/Tolua.h
    manual/Tolua.cpp
    manual/tolua_manual_convert.h
    auto/lua_auto_gen_codes.cpp
    auto/tolua_auto_convert.h
    )

if(APPLE)
    # CCLuaObjcBridge.mm needed by ios and mac
    set(lua_bindings_files
        ${lua_bindings_files}
        manual/platform/ios/LuaObjcBridge.h
        manual/platform/ios/LuaObjcBridge.mm
        )
endif()

set(_AX_LUA_LIB axlua CACHE INTERNAL "The axmol lua bindings lib name" )

add_library(${_AX_LUA_LIB} STATIC ${lua_bindings_files})
target_link_libraries(${_AX_LUA_LIB} ${_AX_CORE_LIB})
add_dependencies(${_AX_LUA_LIB} ${_AX_CORE_LIB})

if(MSVC)
    target_compile_options(${_AX_LUA_LIB} PRIVATE /bigobj)
endif()

get_target_property(lua_ext_depend thirdparty AX_LUA_DEPEND)
target_link_libraries(${_AX_LUA_LIB} ${lua_ext_depend})

target_include_directories(${_AX_LUA_LIB}
    PUBLIC ${ax_root}/thirdparty/lua
    PRIVATE manual/platform/android
    PRIVATE manual/platform/android/jni
    PRIVATE ${ax_root}/extensions/spine/runtime/include
    INTERFACE ${ax_root}/extensions/scripting/lua-bindings/manual
    PRIVATE ${ax_root}/extensions/spine/runtime/include
)

if(WINDOWS)
    target_compile_definitions(${_AX_LUA_LIB} PUBLIC _USRLUASTATIC)
    if (WINRT)
        target_compile_options(${_AX_LUA_LIB} PUBLIC /wd4700)
    endif()
endif()

set_target_properties(${_AX_LUA_LIB}
                      PROPERTIES
                      ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/lib"
                      LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/lib"
                      FOLDER "Extensions"
                      )

if(XCODE OR VS)
    ax_mark_code_files("${_AX_LUA_LIB}")
endif()

