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
    static std::unordered_map<uintptr_t, int> _pushValues;
    static void registerAutoCode();

public:
    static std::unordered_map<uintptr_t, const char*> luaType;
    
    static void init(lua_State* L);
    static void on_restart();

    static void declare_ns(const char* name);
	static void declare_cclass(const char* name, const char* base, lua_CFunction col);
    static void declare_member_type(const char* type);
    static void add_member(const char* name, lua_CFunction func);
    static void declare_end();

    // call stack: __trackback fun args...
    static int call(lua_State* L, int numArgs, int nRet);
    static void push_function(lua_State* L, int function);

    static bool isusertype(lua_State* L, const char* name, int lo);
    static void* tousertype(lua_State* L, const char* name, int lo);
    static void pushusertype(lua_State* L, void* obj, const char* name);

    static void removeScriptObjectByObject(Ref* obj);
};

NS_AX_END
