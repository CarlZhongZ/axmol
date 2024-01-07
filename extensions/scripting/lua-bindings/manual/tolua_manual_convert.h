#pragma once

#include "Tolua.h"
#include "axmol.h"

NS_AX_BEGIN

void tolua_push_value(lua_State* L, const Data& value);

void tolua_get_value(lua_State* L, int loc, Data& value);

void tolua_push_value(lua_State* L, const std::string& value);

void tolua_get_value(lua_State* L, int loc, std::string& value);

void tolua_push_value(lua_State* L, const std::string_view& value);

void tolua_get_value(lua_State* L, int loc, std::string_view& value);

NS_AX_END
