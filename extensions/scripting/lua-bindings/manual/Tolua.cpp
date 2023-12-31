#include "Tolua.h"

#include "axmol.h"

extern "C" {
#include "lua.h"
#include "lualib.h"
#include "lauxlib.h"
}


NS_AX_BEGIN

lua_State* Tolua::_state;
std::unordered_map<uintptr_t, const char*> Tolua::luaType;


void Tolua::init(lua_State* L) {
    _state = L;
    registerAutoCode();
}

void Tolua::declare_ns(const char* name)
{
    if (name)
    {
        lua_getfield(_state, -1, name);
        if (lua_isnil(_state, -1))
        {
            lua_pop(_state, 1);
            lua_newtable(_state);
            lua_pushvalue(_state, -1);
            lua_setfield(_state, -3, name);
        }
    }
    else
    {
        lua_pushglobaltable(_state);
    }
}

void Tolua::declare_cclass(const char* name, const char* base, lua_CFunction col)
{
    declare_ns(name);
    lua_pushboolean(_state, 1);
    lua_setfield(_state, -2, "__class");

    if (col)
    {
        lua_pushcfunction(_state, col);
        lua_setfield(_state, -2, "__gc");
    }
    
    if (base && base[0])
    {
        lua_pushstring(_state, base);
        lua_setfield(_state, -2, "__base");
    }
}

void Tolua::declare_member_type(const char* type)
{
    declare_ns(type);
}

void Tolua::add_member(const char* name, lua_CFunction func)
{
    lua_pushcfunction(_state, func);
    lua_setfield(_state, -2, name);
}

void Tolua::declare_end()
{
    lua_pop(_state, 1);
}

bool Tolua::executeFunction(int function, int numArgs, int numRet)
{
    return false;
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

void Tolua::removeObjectByRefID(int refID) {}




//manual convert code
template <>
void Tolua::push(lua_State* L, const Data& value)
{
    lua_pushlstring(L, (const char*)value.getBytes(), value.getSize());
}

template <>
void Tolua::get(lua_State* L, int loc, Data& value)
{
    size_t len;
    auto s = lua_tolstring(L, loc, &len);
    value.copy((const unsigned char*)s, len);
}

template <>
void Tolua::push(lua_State* L, const std::string& value)
{
    lua_pushlstring(L, (const char*)value.data(), value.size());
}

template <>
void Tolua::get(lua_State* L, int loc, std::string& value)
{
    size_t len;
    auto s = lua_tolstring(L, loc, &len);
    value.assign(s, len);
}

template <>
void Tolua::push(lua_State* L, const std::string_view& value)
{
    lua_pushlstring(L, (const char*)value.data(), value.size());
}

template <>
void Tolua::get(lua_State* L, int loc, std::string_view& value)
{
    value = lua_tostring(L, loc);
}

NS_AX_END
