#include "Tolua.h"

extern "C" {
#include "lua.h"
#include "lualib.h"
#include "lauxlib.h"
}


NS_AX_BEGIN

std::unordered_map<uintptr_t, const char*> Tolua::luaType;

template <>
static void Tolua::tolua_push_value(lua_State* L, const bool& value)
{
    lua_pushboolean(L, value);
}

template <>
static void Tolua::tolua_get_value(lua_State* L, int loc, bool& value)
{
    value = lua_toboolean(L, loc);
}


void Tolua::declare_ns(lua_State* L, const char* name)
{
    if (name)
    {
        lua_getfield(L, -1, name);
        if (lua_isnil(L, -1))
        {
            lua_pop(L, 1);
            lua_newtable(L);
            lua_setfield(L, -2, name);
        }
    }
    else
    {
        lua_pushglobaltable(L);
    }
}

void Tolua::declare_cclass(lua_State* L, const char* name, const char* base, lua_CFunction col)
{
    lua_getfield(L, -1, name);
    if (lua_isnil(L, -1))
    {
        lua_pop(L, 1);
        lua_newtable(L);
        lua_setfield(L, -2, name);
    }

    lua_pushboolean(L, 1);
    lua_setfield(L, -2, "__class");

    if (col)
    {
        lua_pushcfunction(L, col);
        lua_setfield(L, -2, "__gc");
    }
    
    if (base && base[0])
    {
        lua_pushstring(L, base);
        lua_setfield(L, -2, "__base");
    }
}

void Tolua::declare_member_type(lua_State* L, const char* type)
{
    lua_getfield(L, -1, type);
    if (!lua_isnil(L, -1))
    {
        lua_pop(L, 1);
        lua_newtable(L);
        lua_setfield(L, -2, type);
    }
}

void Tolua::add_member(lua_State* L, const char* name, lua_CFunction func)
{
    lua_pushcfunction(L, func);
    lua_setfield(L, -2, name);
}

void Tolua::declare_end(lua_State* L)
{
    lua_pop(L, 1);
}

bool Tolua::isusertype(lua_State* L, const char* name, int lo)
{
    return false;
}

void* Tolua::tousertype(lua_State* L, const char* name, int lo)
{
    return nullptr;
}

void Tolua::pushusertype(lua_State* L, void* obj, const char* name) {}

void Tolua::removeObjectByRefID(lua_State* L, int refID) {}

void Tolua::pushCObject(lua_State* L, int refid, int* p_refid, void* ptr, const char* type) {}

NS_AX_END
