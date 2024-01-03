#pragma once
#include "base/Types.h"

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
    static void declare_ns(const char* name);
	static void declare_cclass(const char* name, const char* base, lua_CFunction col);
    static void declare_member_type(const char* type);
    static void add_member(const char* name, lua_CFunction func);
    static void declare_end();

public:
    static void init();
    static void destroy();

    static lua_State* getLuaState() { return _state; }
    static void removeRefObject(void* obj);

    static void execute_file(const std::string& path);
    static void execute_string(const std::string& code, const std::string& path);

    // call stack: __trackback fun args...
    static int call(lua_State* L, int numArgs, int nRet);
    static void pushFunction(lua_State* L, int function);

    static bool isType(lua_State* L, const char* name, int lo);
    static void* toType(lua_State* L, const char* name, int lo);
    static void pushType(lua_State* L, void* obj, const char* name);
    static void pushRefType(lua_State* L, void* obj);
};

NS_AX_END
