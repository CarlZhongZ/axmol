#include "Tolua.h"

extern "C" {
#include "lua.h"
#include "lualib.h"
#include "lauxlib.h"
}

#include "axmol.h"



#include "lua_module_register.h"

NS_AX_BEGIN

lua_State* Tolua::_state = nullptr;
std::unordered_map<uintptr_t, int> Tolua::_pushValues;
std::unordered_map<uintptr_t, const char*> Tolua::luaType;

void Tolua::init() {
    if (_state)
    {
        return;
    }

    _state = luaL_newstate();
    luaL_openlibs(_state);
    lua_module_register(_state);

    lua_register(_state, "tolua_push_static_cpp_values", [](lua_State* L) {
        pushStaticCppValues(L);
        return 0;
    });

    lua_register(_state, "tolua_on_restart", [](lua_State* L) {
        _pushValues.clear();
        return 0;
    });

    registerAutoCode();
}

void Tolua::destroy() {
    if (nullptr != _state)
    {
        lua_close(_state);
    }
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

    if (col)
    {
        lua_pushcfunction(_state, col);
        lua_setfield(_state, -2, "gc");
    }
    
    if (base && base[0])
    {
        lua_pushstring(_state, base);
        lua_setfield(_state, -2, "base");
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

static int _callFromLua = 0;

int Tolua::call(lua_State* L, int numArgs, int nRet)
{
    if (nRet < 0)
    {
        nRet = 0;
    }

    int functionIndex = -(numArgs + 1);
    if (!lua_isfunction(L, functionIndex))
    {
        AXLOG("value at stack [%d] is not function", functionIndex);
        lua_pop(L, numArgs + 2);  // remove function and arguments
        return 0;
    }

    int traceback = functionIndex - 1;
    if (!lua_isfunction(L, traceback)) {
        traceback = 0;
    }

    int error = 0;
    ++_callFromLua;
    error = lua_pcall(L, numArgs, nRet, traceback); /* L: ... [G] ret */
    --_callFromLua;
    if (error)
    {
        if (traceback == 0)
        {
            AXLOG("[LUA ERROR] %s", lua_tostring(L, -1)); /* L: ... error */
        }
        lua_pop(L, 2);
        return 0;
    }

    return nRet + 1;
}

void Tolua::pushFunction(lua_State* L, int function)
{
    lua_getglobal(L, "__G__TRACKBACK__");
    lua_getfield(L, LUA_REGISTRYINDEX, "__TOLUA_FUNCTIONS");
    lua_geti(L, -1, function);
    lua_remove(L, -2);
}

bool Tolua::isType(lua_State* L, const char* name, int lo)
{
    if (!lua_isuserdata(L, lo))
    {
        return false;
    }
    lua_getfield(L, LUA_REGISTRYINDEX, "__TOLUA_SUPER");  // __TOLUA_SUPER
    if (!lua_getmetatable(L, lo))    // __TOLUA_SUPER mt
    {
        lua_pop(L, 1);
        return false;
    }

    lua_getfield(L, -1, "__name"); // __TOLUA_SUPER mt __name
    if (lua_type(L, -1) != LUA_TSTRING)
    {
        lua_pop(L, 3);
        return false;
    }

    lua_rawget(L, -3); // // __TOLUA_SUPER mt bIsSuperClass
    auto ret = lua_toboolean(L, -1);
    lua_pop(L, 3);

    return ret;
}

void* Tolua::toType(lua_State* L, const char* name, int lo)
{
    if (!isType(L, name, lo))
    {
        return nullptr;
    }
    return *(void**)lua_touserdata(L, lo);
}

void Tolua::pushType(lua_State* L, void* obj, const char* name)
{
    if (!obj)
    {
        lua_pushnil(L);
        return;
    }

    lua_getfield(L, LUA_REGISTRYINDEX, name);  // mt
    if (!lua_istable(L, -1))
    {
        // 未注册类型
        return;
    }
    *(void**)lua_newuserdata(L, sizeof(void*)) = obj;  // mt ud
    lua_insert(L, -2);  // ud mt
    lua_setmetatable(L, -2);  // ud
}

void Tolua::pushRefType(lua_State* L, void* obj, const char* typeName, const char* curName)
{
    if (!obj)
    {
        lua_pushnil(L);
        return;
    }

    auto itType = luaType.find((uintptr_t)typeName);
    const char* name = itType == luaType.end() ? curName: itType->second;

    auto hashKey = (uintptr_t)obj;
    auto it = _pushValues.find(hashKey);
    if (it == _pushValues.end())
    {
        lua_getfield(L, LUA_REGISTRYINDEX, name);  // mt
        if (!lua_istable(L, -1))
        {
            // 未注册类型
            return;
        }

        // 首次 push
        *(void**)lua_newuserdata(L, sizeof(void*)) = obj;  // mt ud
        lua_insert(L, -2);                                 // ud mt
        lua_setmetatable(L, -2);                           // ud
        static int idx = 0;
        lua_getfield(L, LUA_REGISTRYINDEX, "__TOLUA_PUSH_DATA");  // ud __TOLUA_PUSH_DATA
        while (true)
        {
            // 找到一个空位放 userdata
            ++idx;
            if (idx > 2000000000)
                idx = 1;
            lua_geti(L, -1, idx);
            if (lua_isnil(L, -1))
            {
                lua_pop(L, 1);
                break;
            }
            else
            {
                lua_pop(L, 1);
            }
        }
        _pushValues[hashKey] = idx;
        lua_pushvalue(L, -2);                                     // ud __TOLUA_PUSH_DATA ud
        lua_seti(L, -2, idx);                                     // ud __TOLUA_PUSH_DATA
        lua_pop(L, 1);
    }
    else
    {
        // push cached
        lua_getfield(L, LUA_REGISTRYINDEX, "__TOLUA_PUSH_DATA");
        lua_geti(L, -1, it->second);
        lua_remove(L, -2);
    }
}

void Tolua::removeRefObject(void* obj)
{
    auto it = _pushValues.find((uintptr_t)obj);
    if (it == _pushValues.end())
    {
        return;
    }

    lua_getfield(_state, LUA_REGISTRYINDEX, "__TOLUA_PUSH_DATA");  // __TOLUA_PUSH_DATA
    lua_geti(_state, -1, it->second);                              // __TOLUA_PUSH_DATA ud

    // 移除 uservalue
    lua_pushnil(_state);
    lua_setuservalue(_state, -2);
    lua_pop(_state, 1);  // __TOLUA_PUSH_DATA

    // 从 __TOLUA_PUSH_DATA 移除
    lua_pushnil(_state);
    lua_seti(_state, -2, it->second);
    _pushValues.erase(it);

    lua_pop(_state, 1);

    // ? todo... 通知脚本移除相关索引(native callback etc)
}

void Tolua::execute_file(const std::string& path) {
    auto data = FileUtils::getInstance()->getDataFromFile(path);
    if (data.isNull())
    {
        AXLOG("error: %s not exist", path.c_str());
        return;
    }

    lua_pushnil(_state);  // errorFun
    int r = luaL_loadbuffer(_state, (const char*)data.getBytes(), data.getSize(), path.c_str());
    if (r)
    {
        AXLOG("error: %s", lua_tostring(_state, -1));
        lua_pop(_state, 2);
    }
    else
    {
        lua_pop(_state, call(_state, 0, 0));
    }
}

NS_AX_END
