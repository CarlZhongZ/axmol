#include "Tolua.h"



extern "C" {
#include "lua.h"
#include "lualib.h"
#include "lauxlib.h"
}


NS_AX_BEGIN

lua_State* Tolua::_state;
std::unordered_map<uintptr_t, int> Tolua::_pushValues;
std::unordered_map<uintptr_t, const char*> Tolua::luaType;

int tolua_on_restart(lua_State* L) {
    Tolua::on_restart();
    return 0;
}

void Tolua::init(lua_State* L) {
    _state = L;
    registerAutoCode();

    lua_register(L, "tolua_on_restart", tolua_on_restart);
}

void Tolua::on_restart() {
    _pushValues.clear();
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

    int traceback = lua_isfunction(L, functionIndex - 1) ? functionIndex - 1 : 0;

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

void Tolua::push_function(lua_State* L, int function)
{
    lua_getglobal(L, "__G__TRACKBACK__");
    lua_getfield(L, LUA_REGISTRYINDEX, "__TOLUA_FUNCTIONS");  // __G__TRACKBACK__ __TOLUA_FUNCTIONS
    lua_geti(L, -1, function);                                // __G__TRACKBACK__ __TOLUA_FUNCTIONS function
    lua_remove(L, -2);
}

bool Tolua::isusertype(lua_State* L, const char* name, int lo)
{
    if (!lua_isuserdata(L, lo))
    {
        return false;
    }
    lua_getfield(L, LUA_REGISTRYINDEX, "__TOLUA_SUPER"); // __TOLUA_SUPER
    if (!lua_getmetatable(L, lo))
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

void* Tolua::tousertype(lua_State* L, const char* name, int lo)
{
    if (!isusertype(L, name, lo))
    {
        return nullptr;
    }
    return *(void**)lua_touserdata(L, lo);
}

void Tolua::pushusertype(lua_State* L, void* obj, const char* name) {
    auto hashKey = (uintptr_t)obj;
    auto it = _pushValues.find(hashKey);
    if (it == _pushValues.end())
    {
        auto typeName = typeid(obj).name();
        lua_getfield(L, LUA_REGISTRYINDEX, typeName);  // mt
        if (lua_istable(L, -1))
        {
            // 首次 push
            *(void**)lua_newuserdata(L, sizeof(void*)) = obj; // mt ud
            lua_insert(L, -2); // ud mt
            lua_setmetatable(L, -2); // ud
            static int idx = 1;
            if (idx == 2000000000)
            {
                // reorder __TOLUA_PUSH_DATA
                auto size = _pushValues.size();
                std::unordered_set<int> oldIdxs;
                for (auto it = _pushValues.begin(); it != _pushValues.end(); ++it)
                {
                    oldIdxs.insert(it->second);
                }
                lua_getfield(L, LUA_REGISTRYINDEX, "__TOLUA_PUSH_DATA");
                int i = 1;
                for (auto it = _pushValues.begin(); it != _pushValues.end(); ++it)
                {
                    int oldIdx = it->second;
                    if (oldIdx > size)
                    {
                        while (oldIdxs.contains(i))
                        {
                            ++i;
                        }
                        lua_geti(L, -1, oldIdx);
                        lua_pushnil(L);
                        lua_seti(L, -3, oldIdx);
                        lua_seti(L, -2, i);
                        _pushValues[it->first] = i;
                    }
                }
                lua_pop(L, 1);
                idx = i + 1;
            }
            _pushValues[hashKey] = idx;
            lua_getfield(L, LUA_REGISTRYINDEX, "__TOLUA_PUSH_DATA"); // ud __TOLUA_PUSH_DATA
            lua_pushvalue(L, -2); // ud __TOLUA_PUSH_DATA ud
            lua_seti(L, -2, idx); // ud __TOLUA_PUSH_DATA
            lua_pop(L, 1);

            ++idx;
        }
        else
        {
            // 未注册类型
            lua_pop(L, 1);
            lua_pushnil(L);
        }
    }
    else
    {
        auto idx = it->second;
        lua_getfield(L, LUA_REGISTRYINDEX, "__TOLUA_PUSH_DATA");
        lua_geti(L, -1, idx);
        if (!lua_isuserdata(L, -1))
        {
            // 被 gc 了重新 push
            _pushValues.erase(it);
            lua_pop(L, 2);
            return pushusertype(L, obj, name);
        }
        lua_insert(L, -2);
        lua_pop(L, 1);
    }
}

void Tolua::removeScriptObjectByObject(Ref* obj)
{
    auto it = _pushValues.find((uintptr_t)obj);
    if (it != _pushValues.end())
    {
        lua_getfield(_state, LUA_REGISTRYINDEX, "__TOLUA_PUSH_DATA");  // __TOLUA_PUSH_DATA
        lua_geti(_state, -1, it->second);  // __TOLUA_PUSH_DATA ud
        // 移除 uservalue
        lua_pushnil(_state);
        lua_setuservalue(_state, -2);
        lua_pop(_state, 1);  // __TOLUA_PUSH_DATA

        lua_pushnil(_state);
        lua_seti(_state, -1, it->second);
        lua_pop(_state, 1);
        _pushValues.erase(it);

        // todo... 通知脚本移除相关索引(native callback etc)
    }
}

NS_AX_END
