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
#ifndef __COCOS2DX_SCRIPTING_LUA_COCOS2DXSUPPORT_LUABAISCCONVERSIONS_H__
#define __COCOS2DX_SCRIPTING_LUA_COCOS2DXSUPPORT_LUABAISCCONVERSIONS_H__

#include <unordered_map>
#include <string>

#include "scripting/lua-bindings/manual/tolua_fix.h"

#include "scripting/lua-bindings/manual/Lua-BindingsExport.h"
#include "base/Value.h"

USING_NS_AX;

extern std::unordered_map<uintptr_t, const char*> g_luaType;
extern std::unordered_map<cxx17::string_view, const char*> g_typeCast;

/**
 * @addtogroup lua
 * @{
 */

/**
 * If the typename of userdata at the given acceptable index of stack is equal to type it return true, otherwise return
 * false. If def != 0, lo could greater than the top index of stack, return value is true. If the value of the given
 * index is nil, return value also is true.
 *
 * @param L the current lua_State.
 * @param lo the given acceptable index of stack.
 * @param type the typename used to judge.
 * @param def whether has default value.
 * @return Return true if the typename of userdata at the given acceptable index of stack is equal to type, otherwise
 * return false.
 */
extern bool luaval_is_usertype(lua_State* L, int lo, const char* type, int def);
// to native

/**
 * Get the real typename for the specified typename.
 * Because all override functions wouldn't be bound,so we must use `typeid` to get the real class name.
 *
 * @param ret the pointer points to a type T object.
 * @param type the string pointer points to specified typename.
 * @return return the pointer points to the real typename, or nullptr.
 */
template <class T>
const char* getLuaTypeName(T* ret, const char* defaultTypeName)
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


template<class T>
void tolua_push_value(lua_State* L, const T& value) {
    lua_pushnumber(L, value);
}

template <>
void tolua_push_value(lua_State* L, const bool& value) {
    lua_pushboolean(L, value);
}

template <class T>
void tolua_get_value(lua_State* L, int loc, T& value) {
    value = luaL_checknumber(L, loc);
}

// end group
/// @}
#endif  //__COCOS2DX_SCRIPTING_LUA_COCOS2DXSUPPORT_LUABAISCCONVERSIONS_H__
