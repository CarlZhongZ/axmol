/****************************************************************************
 Copyright (c) 2017-2018 Xiamen Yaji Software Co., Ltd.
 Copyright (c) 2019-present Axmol Engine contributors (see AUTHORS.md).

 https://axmolengine.github.io/

 Permission is hereby granted, free of charge, to any person obtaining a copy
 of this software and associated documentation files (the "Software"), to deal
 in the Software without restriction, including without limitation the rights
 to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 copies of the Software, and to permit persons to whom the Software is
 furnished to do so, subject to the following conditions:

 The above copyright notice and this permission notice shall be included in
 all copies or substantial portions of the Software.

 THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 THE SOFTWARE.
 ****************************************************************************/
#include "scripting/lua-bindings/manual/lua_module_register.h"
#include "axmol.h"
#include "lua.hpp"

#if (AX_TARGET_PLATFORM == AX_PLATFORM_IOS || AX_TARGET_PLATFORM == AX_PLATFORM_MAC)
#    include "scripting/lua-bindings/manual/platform/ios/LuaObjcBridge.h"
#endif

#if (AX_TARGET_PLATFORM == AX_PLATFORM_ANDROID)
#    include "scripting/lua-bindings/manual/platform/android/LuaJavaBridge.h"
#endif

#include "lua_cjson.h"
#include "yasio/bindings/yasio_axlua.hpp"

static int get_string_for_print(lua_State* L, std::string* out)
{
    int n = lua_gettop(L); /* number of arguments */
    for (int i = 1; i <= n; i++)
    {
        size_t sz;
        const char* s = lua_tolstring(L, -1, &sz); /* get result */
        if (s)
        {
            if (i > 1)
                out->append("\t");
            out->append(s, sz);
        }
    }
    return 0;
}

static int lua_release_print(lua_State* L)
{
    std::string t;
    get_string_for_print(L, &t);
    ax::print("[LUA-print] %s", t.c_str());

    return 0;
}

static void lua_register_extensions(lua_State* L)
{

    static luaL_Reg lua_exts[] = {{"yasio", luaopen_yasio_axlua}, {"cjson", luaopen_cjson}, {NULL, NULL}};

    lua_getglobal(L, "package");
    lua_getfield(L, -1, "preload");
    auto lib = lua_exts;
    for (; lib->func; ++lib)
    {
        lua_pushcfunction(L, lib->func);
        lua_setfield(L, -2, lib->name);
    }
    lua_pop(L, 2);
}

int lua_module_register(lua_State* L)
{
    lua_register(L, "print", lua_release_print);
    lua_register(L, "release_print", lua_release_print);

#if (AX_TARGET_PLATFORM == AX_PLATFORM_IOS || AX_TARGET_PLATFORM == AX_PLATFORM_MAC)
    LuaObjcBridge::luaopen_luaoc(L);
#endif

#if (AX_TARGET_PLATFORM == AX_PLATFORM_ANDROID)
    LuaJavaBridge::luaopen_luaj(L);
#endif

    // register extensions: yaiso, lua-cjson
    lua_register_extensions(L);
    return 1;
}
