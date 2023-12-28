/****************************************************************************
 Copyright (c) 2013-2016 Chukong Technologies Inc.
 Copyright (c) 2017-2018 Xiamen Yaji Software Co., Ltd.

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
#pragma once

#include <unordered_map>
#include <string>

#include "scripting/lua-bindings/manual/tolua_fix.h"

#include "scripting/lua-bindings/manual/Lua-BindingsExport.h"
#include "base/Value.h"

USING_NS_AX;

class ToluaConvert
{
public:
    static std::unordered_map<uintptr_t, const char*> g_luaType;
    static std::unordered_map<cxx17::string_view, const char*> g_typeCast;

    static bool luaval_is_usertype(lua_State* L, int lo, const char* type, int def);

    template <class T>
    static const char* getLuaTypeName(T* ret, const char* defaultTypeName)
    {
        if (nullptr != ret)
        {
            auto typeName = typeid(*ret).name();
            auto iter     = g_luaType.find(reinterpret_cast<uintptr_t>(typeName));
            if (g_luaType.end() != iter)
            {
                return iter->second;
            }
            else
            {  // unlike logic, for windows dll only
                cxx17::string_view strkey(typeName);
                auto iter2 = g_typeCast.find(strkey);
                if (iter2 != g_typeCast.end())
                {
                    g_luaType.emplace(reinterpret_cast<uintptr_t>(typeName), iter2->second);
                    return iter2->second;
                }
                return defaultTypeName;
            }
        }

        return nullptr;
    }

    static void registerAutoCode(lua_State* L);

    template <class T>
    static void tolua_push_value(lua_State* L, const T& value)
    {
        // lua_pushnumber(L, value);
    }

    template <>
    static void tolua_push_value(lua_State* L, const bool& value)
    {
        lua_pushboolean(L, value);
    }

    template <class T>
    static void tolua_get_value(lua_State* L, int loc, T& value)
    {
        // value = luaL_checknumber(L, loc);
    }

    template <>
    static void tolua_get_value(lua_State* L, int loc, bool& value)
    {
        value = lua_toboolean(L, loc);
    }
};
