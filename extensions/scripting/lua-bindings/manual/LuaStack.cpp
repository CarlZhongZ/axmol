/****************************************************************************
 Copyright (c) 2011-2012 cocos2d-x.org
 Copyright (c) 2013-2016 Chukong Technologies Inc.
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

#include "scripting/lua-bindings/manual/LuaStack.h"
#include <string.h>
extern "C" {
#include "lua.h"
#include "lualib.h"
#include "lauxlib.h"
}


#if (AX_TARGET_PLATFORM == AX_PLATFORM_IOS || AX_TARGET_PLATFORM == AX_PLATFORM_MAC)
#    include "scripting/lua-bindings/manual/platform/ios/LuaObjcBridge.h"
#endif

#if (AX_TARGET_PLATFORM == AX_PLATFORM_ANDROID)
#    include "scripting/lua-bindings/manual/platform/android/LuaJavaBridge.h"
#endif

#include "scripting/lua-bindings/manual/Tolua.h"
#include "base/ZipUtils.h"
#include "platform/FileUtils.h"

namespace
{
int get_string_for_print(lua_State* L, std::string* out)
{
    int n = lua_gettop(L); /* number of arguments */
    int i;

    lua_getglobal(L, "tostring");
    for (i = 1; i <= n; i++)
    {
        const char* s;
        lua_pushvalue(L, -1); /* function to be called */
        lua_pushvalue(L, i);  /* value to print */
        lua_call(L, 1, 1);
        size_t sz;
        s = lua_tolstring(L, -1, &sz); /* get result */
        if (s == NULL)
            return luaL_error(L, "'tostring' must return a string to 'print'");
        if (i > 1)
            out->append("\t");
        out->append(s, sz);
        lua_pop(L, 1); /* pop result */
    }
    return 0;
}

int lua_print(lua_State* L)
{
    std::string t;
    get_string_for_print(L, &t);
    AXLOG("[LUA-print] %s", t.c_str());

    return 0;
}

int lua_release_print(lua_State* L)
{
    std::string t;
    get_string_for_print(L, &t);
    ax::print("[LUA-print] %s", t.c_str());

    return 0;
}

int lua_version(lua_State* L)
{
    lua_pushinteger(L, LUA_VERSION_NUM);
    return 1;
}
}  // namespace

NS_AX_BEGIN

LuaStack* LuaStack::create()
{
    LuaStack* stack = new LuaStack();
    stack->init();
    stack->autorelease();
    return stack;
}

LuaStack::~LuaStack() {
    if (nullptr != _state)
    {
        lua_close(_state);
    }
}

bool LuaStack::init()
{
    _state = luaL_newstate();
    luaL_openlibs(_state);

    // Register our version of the global "print" function
    lua_register(_state, "print", lua_print);
    lua_register(_state, "release_print", lua_release_print);

    Tolua::init(_state);

#if (AX_TARGET_PLATFORM == AX_PLATFORM_IOS || AX_TARGET_PLATFORM == AX_PLATFORM_MAC)
    LuaObjcBridge::luaopen_luaoc(_state);
#endif

#if (AX_TARGET_PLATFORM == AX_PLATFORM_ANDROID)
    LuaJavaBridge::luaopen_luaj(_state);
#endif


    return true;
}


NS_AX_END
