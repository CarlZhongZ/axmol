#pragma once

#include "Tolua.h"
#include "axmol.h"

NS_AX_BEGIN

void tolua_push_value(lua_State* L, const Data& value)
{
    if (value.isNull())
    {
        lua_pushnil(L);
    }
    else
    {
        lua_pushlstring(L, (const char*)value.getBytes(), value.getSize());
    }
}

void tolua_get_value(lua_State* L, int loc, Data& value)
{
    size_t len;
    auto s = lua_tolstring(L, loc, &len);
    if (s)
    {
        value.copy((const unsigned char*)s, len);
    }
    else
    {
        value.clear();
    }
}

void tolua_push_value(lua_State* L, const std::string& value)
{
    lua_pushlstring(L, (const char*)value.data(), value.size());
}

void tolua_get_value(lua_State* L, int loc, std::string& value)
{
    size_t len;
    auto s = lua_tolstring(L, loc, &len);
    if (s)
    {
        value.assign(s, len);
    }
}

void tolua_push_value(lua_State* L, const std::string_view& value)
{
    lua_pushlstring(L, (const char*)value.data(), value.size());
}

void tolua_get_value(lua_State* L, int loc, std::string_view& value)
{
    auto s = lua_tostring(L, loc);
    if (s)
    {
        value = s;
    }
}

NS_AX_END
