#pragma once
#include "base/Types.h"
#include "base/Ref.h"

extern "C" {
#include "lua.h"
#include "lualib.h"
#include "lauxlib.h"
}


NS_AX_BEGIN

class Tolua
{
    static lua_State* _state;
    static void registerAutoCode();
public:
    static std::unordered_map<uintptr_t, const char*> luaType;
    static void init(lua_State* L);

    static void declare_ns(const char* name);
	static void declare_cclass(const char* name, const char* base, lua_CFunction col);
    static void declare_member_type(const char* type);
    static void add_member(const char* name, lua_CFunction func);
    static void declare_end();

    static bool executeFunction(int function, int numArgs, int numRet);

    static bool isusertype(lua_State* L, const char* name, int lo);
    static void* tousertype(lua_State* L, const char* name, int lo);
    static void pushusertype(lua_State* L, void* obj, const char* name);

    template <class T>
    static void tolua_push_value(lua_State* L, const T& value) {}

    template <class T>
    static void tolua_get_value(lua_State* L, int loc, T& value) {}

    template <class T>
    static void push(lua_State* L, const T& value) {}

    template <class T>
    static void get(lua_State* L, int loc, T& value) {}

    static void removeObjectByRefID(int refID);
};

NS_AX_END
