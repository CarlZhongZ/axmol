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

#include <regex>

#include "lua.hpp"

extern "C" {
#include "lua_cjson.h"
#include "luasocket/luasocket.h"
#include "luasocket/luasocket_scripts.h"
#include "luasocket/mime.h"
}



#include "axmol.h"

#if (AX_TARGET_PLATFORM == AX_PLATFORM_IOS || AX_TARGET_PLATFORM == AX_PLATFORM_MAC)
#    include "scripting/lua-bindings/manual/platform/ios/LuaObjcBridge.h"
#endif

#if (AX_TARGET_PLATFORM == AX_PLATFORM_ANDROID)
#    include "scripting/lua-bindings/manual/platform/android/LuaJavaBridge.h"
#endif

USING_NS_AX;

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

static int luaext_loadfile(lua_State* L)
{
    const char* filePath = luaL_checkstring(L, 1);

    auto data = ax::FileUtils::getInstance()->getDataFromFile(filePath);
    if (data.isNull())
        return 0;

    int status = luaL_loadbuffer(L, (const char*)(data.getBytes()), data.getSize(), filePath);
    if (status == 0)
    {
        return 1;
    }

    /* error (message is on top of the stack) */
    lua_pushnil(L);
    lua_insert(L, -2); /* put before error message */
    return 2;
}

static int stringid(const char* s, int length)
{
    unsigned h          = 0;
    const unsigned seed = 131;
    for (int i = 0; i < length; ++i)
    {
        h = seed * h + *s++;
    }

    return h & 0x7fffffff;
}

static int luaext_hash_str(lua_State* L)
{
    size_t bufferLength = 0;
    const char* buffer  = luaL_checklstring(L, 1, &bufferLength);

    lua_pushinteger(L, stringid(buffer, bufferLength));
    return 1;
}

static int luaext_file_md5(lua_State* L)
{
    const char* path = luaL_checkstring(L, 1);
    auto data        = ax::FileUtils::getInstance()->getDataFromFile(path);
    if (data.isNull())
    {
        return 0;
    }

    auto md5 = ax::utils::getDataMD5Hash(data);
    lua_pushstring(L, md5.c_str());
    return 1;
}

static int luaext_md5(lua_State* L)
{
    size_t bufferLength = 0;
    const char* buffer  = luaL_checklstring(L, 1, &bufferLength);

    Data data;
    data.copy((uint8_t*)buffer, bufferLength);
    auto md5 = ax::utils::getDataMD5Hash(data);
    lua_pushstring(L, md5.c_str());
    return 1;
}

static int luaext_get_tick(lua_State* L)
{
    timeval tm = {0};
    gettimeofday(&tm, NULL);
    lua_pushnumber(L, tm.tv_sec + (double)tm.tv_usec / 1000000);
    return 1;
}

static int luaext_string_match(lua_State* L)
{
    std::string str = luaL_checkstring(L, 1);
    std::regex pattern(luaL_checkstring(L, 2));
    std::cmatch cm;
    if (std::regex_match(str.c_str(), cm, pattern))
    {
        int sz = cm.size();
        lua_newtable(L);
        for (int i = 0; i < sz; ++i)
        {
            lua_pushinteger(L, i);
            lua_pushstring(L, cm[i].str().c_str());
            lua_rawset(L, -3);
        }
        return 1;
    }
    else
    {
        return 0;
    }
}

static int luaext_string_search(lua_State* L)
{
    std::string str = luaL_checkstring(L, 1);
    std::regex pattern(luaL_checkstring(L, 2));
    std::cmatch cm;
    if (std::regex_search(str.c_str(), cm, pattern))
    {
        int sz = cm.size();
        lua_newtable(L);
        for (int i = 0; i < sz; ++i)
        {
            lua_pushinteger(L, i);
            lua_pushstring(L, cm[i].str().c_str());
            lua_rawset(L, -3);
        }
        return 1;
    }
    else
    {
        return 0;
    }
}

static int luaext_base64_encode(lua_State* L)
{
    size_t size = 0;
    auto in     = (const unsigned char*)luaL_checklstring(L, 1, &size);

    char* out = nullptr;
    auto ret  = ax::utils::base64Encode(in, size);
    lua_pushlstring(L, ret.c_str(), ret.length());
    return 1;
}

static int luaext_base64_decode(lua_State* L)
{
    size_t size = 0;
    auto in     = (const unsigned char*)luaL_checklstring(L, 1, &size);

    unsigned char* out = nullptr;
    auto outSize       = ax::utils::base64Decode(in, size, &out);
    if (out == nullptr)
    {
        return 0;
    }

    lua_pushlstring(L, (const char*)out, outSize);
    return 1;
}

static int luaext_islightuserdata(lua_State* L)
{
    lua_pushboolean(L, lua_islightuserdata(L, 1) == 1);
    return 1;
}

static int luaext_create_table(lua_State* L)
{
    int narr  = luaL_checkint(L, 1);
    int nnarr = luaL_checkint(L, 2);
    lua_createtable(L, narr, nnarr);
    return 1;
}


static void lua_register_extensions(lua_State* L)
{

    static luaL_Reg lua_exts[] = {
        {"cjson", luaopen_cjson}, {NULL, NULL},
        {"socket.core", luaopen_socket_core},
        {"mime.core", luaopen_mime_core},
    };

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
    lua_register(L, "luaext_loadfile", luaext_loadfile);
    lua_register(L, "luaext_islightuserdata", luaext_islightuserdata);
    lua_register(L, "luaext_create_table", luaext_create_table);

    lua_register(L, "luaext_hash_str", luaext_hash_str);
    lua_register(L, "luaext_md5", luaext_md5);
    lua_register(L, "luaext_file_md5", luaext_file_md5);
    lua_register(L, "luaext_get_tick", luaext_get_tick);
    lua_register(L, "luaext_string_match", luaext_string_match);
    lua_register(L, "luaext_string_search", luaext_string_search);
    lua_register(L, "luaext_base64_encode", luaext_base64_encode);
    lua_register(L, "luaext_base64_decode", luaext_base64_decode);


#if (AX_TARGET_PLATFORM == AX_PLATFORM_IOS || AX_TARGET_PLATFORM == AX_PLATFORM_MAC)
    LuaObjcBridge::luaopen_luaoc(L);
#endif

#if (AX_TARGET_PLATFORM == AX_PLATFORM_ANDROID)
    LuaJavaBridge::luaopen_luaj(L);
#endif

    lua_register_extensions(L);
    return 1;
}
