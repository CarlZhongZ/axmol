#pragma once
#include "base/Types.h"
#include "base/Ref.h"

extern "C" {
#include "lua.h"
#include "lualib.h"
#include "lauxlib.h"
}


#define lua_open   luaL_newstate
#define lua_objlen lua_rawlen


NS_AX_BEGIN

class Tolua
{
public:
    static std::unordered_map<uintptr_t, const char*> luaType;

    static void registerAutoCode(lua_State* L);

    static void declare_ns(lua_State* L, const char* name);
	static void declare_cclass(lua_State* L, const char* name, const char* base, lua_CFunction col);
    static void declare_member_type(lua_State* L, const char* type);
    static void add_member(lua_State* L, const char* name, lua_CFunction func);
    static void declare_end(lua_State* L);

    static bool isusertype(lua_State* L, const char* name, int lo);
    static void* tousertype(lua_State* L, const char* name, int lo);
    static void pushusertype(lua_State* L, void* obj, const char* name);

    template <class T>
    static void tolua_push_value(lua_State* L, const T& value) {}

    template <class T>
    static void tolua_get_value(lua_State* L, int loc, T& value) {}

    static void removeObjectByRefID(lua_State* L, int refID);

    static void pushCObject(lua_State* L, int refid, int* p_refid, void* ptr, const char* type);
};

NS_AX_END
