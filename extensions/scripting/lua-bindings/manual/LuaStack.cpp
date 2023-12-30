/****************************************************************************
 Copyright (c) 2011-2012 cocos2d-x.org
 Copyright (c) 2013-2016 Chukong Technologies Inc.
 Copyright (c) 2017-2018 Xiamen Yaji Software Co., Ltd.
 Copyright (c) 2019-present Axmol Engine contributors (see AUTHORS.md).

 https://axmolengine.github.io/

 Permission is hereby granted, free of charge, to any person obtaining a copy
 of this software and associated documentation files (the "Software"), to deal
 in the Software without restriction, including without limitation the rights
 to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 copies of the Software, and to permit persons to whom the Software is
 furnished to do so, subject to the following conditions:

 The above copyright notice and this permission notice shall be included in
 all copies or substantial portions of the Software.

 THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 THE SOFTWARE.
 ****************************************************************************/

#include "scripting/lua-bindings/manual/LuaStack.h"
#include <string.h>
extern "C" {
#include "lua.h"
#include "lualib.h"
#include "lauxlib.h"
}

#include "scripting/lua-bindings/manual/AxluaLoader.h"

#if (AX_TARGET_PLATFORM == AX_PLATFORM_IOS || AX_TARGET_PLATFORM == AX_PLATFORM_MAC)
#    include "scripting/lua-bindings/manual/platform/ios/LuaObjcBridge.h"
#endif

#if (AX_TARGET_PLATFORM == AX_PLATFORM_ANDROID)
#    include "scripting/lua-bindings/manual/platform/android/LuaJavaBridge.h"
#endif

#include "scripting/lua-bindings/manual/Tolua.h"
#include "base/ZipUtils.h"
#include "platform/FileUtils.h"

namespace
{
int get_string_for_print(lua_State* L, std::string* out)
{
    int n = lua_gettop(L); /* number of arguments */
    int i;

    lua_getglobal(L, "tostring");
    for (i = 1; i <= n; i++)
    {
        const char* s;
        lua_pushvalue(L, -1); /* function to be called */
        lua_pushvalue(L, i);  /* value to print */
        lua_call(L, 1, 1);
        size_t sz;
        s = lua_tolstring(L, -1, &sz); /* get result */
        if (s == NULL)
            return luaL_error(L, "'tostring' must return a string to 'print'");
        if (i > 1)
            out->append("\t");
        out->append(s, sz);
        lua_pop(L, 1); /* pop result */
    }
    return 0;
}

int lua_print(lua_State* L)
{
    std::string t;
    get_string_for_print(L, &t);
    AXLOG("[LUA-print] %s", t.c_str());

    return 0;
}

int lua_release_print(lua_State* L)
{
    std::string t;
    get_string_for_print(L, &t);
    ax::print("[LUA-print] %s", t.c_str());

    return 0;
}

int lua_version(lua_State* L)
{
    lua_pushinteger(L, LUA_VERSION_NUM);
    return 1;
}
}  // namespace

NS_AX_BEGIN

LuaStack::~LuaStack()
{
    if (nullptr != _state)
    {
        lua_close(_state);
    }
}

LuaStack* LuaStack::create()
{
    LuaStack* stack = new LuaStack();
    stack->init();
    stack->autorelease();
    return stack;
}

LuaStack* LuaStack::attach(lua_State* L)
{
    LuaStack* stack = new LuaStack();
    stack->initWithLuaState(L);
    stack->autorelease();
    return stack;
}

bool LuaStack::init()
{
    _state = lua_open();
    luaL_openlibs(_state);

    // Register our version of the global "print" function
    lua_register(_state, "print", lua_print);
    lua_register(_state, "release_print", lua_release_print);

    Tolua::registerAutoCode(_state);

#if (AX_TARGET_PLATFORM == AX_PLATFORM_IOS || AX_TARGET_PLATFORM == AX_PLATFORM_MAC)
    LuaObjcBridge::luaopen_luaoc(_state);
#endif

#if (AX_TARGET_PLATFORM == AX_PLATFORM_ANDROID)
    LuaJavaBridge::luaopen_luaj(_state);
#endif

    // add cocos2dx loader
    addLuaLoader(axlua_loader);

    return true;
}

bool LuaStack::initWithLuaState(lua_State* L)
{
    _state = L;
    return true;
}

void LuaStack::addSearchPath(const char* path)
{
    lua_getglobal(_state, "package"); /* L: package */
    lua_getfield(_state, -1, "path"); /* get package.path, L: package path */
    const char* cur_path = lua_tostring(_state, -1);
    lua_pushfstring(_state, "%s/?.lua;%s", path, cur_path); /* L: package path newpath */
    lua_setfield(_state, -3, "path");                       /* package.path = newpath, L: package path */
    lua_pop(_state, 2);                                     /* L: - */
}

void LuaStack::addLuaLoader(lua_CFunction func)
{
    if (!func)
        return;

#if LUA_VERSION_NUM >= 504 || (LUA_VERSION_NUM >= 502 && !defined(LUA_COMPAT_LOADERS))
    const char* realname = "searchers";
#else
    const char* realname = "loaders";
#endif

    // stack content after the invoking of the function
    // get loader table
    lua_getglobal(_state, "package");   /* L: package */
    lua_getfield(_state, -1, realname); /* L: package, loaders */

    // insert loader into index 2
    lua_pushcfunction(_state, func); /* L: package, loaders, func */
    for (int i = (int)(lua_objlen(_state, -2) + 1); i > 2; --i)
    {
        lua_rawgeti(_state, -2, i - 1); /* L: package, loaders, func, function */
        // we call lua_rawgeti, so the loader table now is at -3
        lua_rawseti(_state, -3, i); /* L: package, loaders, func */
    }
    lua_rawseti(_state, -2, 2); /* L: package, loaders */

    // set loaders into package
    lua_setfield(_state, -2, realname); /* L: package */

    lua_pop(_state, 1);
}

void LuaStack::removeScriptObjectByObject(Ref* pObj)
{
    Tolua::removeObjectByRefID(_state, pObj->_luaID);
}

int LuaStack::executeString(const char* codes)
{
    luaL_loadstring(_state, codes);
    return executeFunction(0);
}

int LuaStack::executeScriptFile(const char* filename)
{
    AXASSERT(filename, "CCLuaStack::executeScriptFile() - invalid filename");

    std::string filePath{filename};
    Data data = FileUtils::getInstance()->getDataFromFile(filePath);
    int rn    = 0;
    if (!data.isNull())
    {
        filePath.insert(filePath.begin(), '@');  // lua standard, add file chunck mark '@'
        if (luaLoadBuffer(_state, (const char*)data.getBytes(), (int)data.getSize(), filePath.c_str()) == 0)
        {
            rn = executeFunction(0);
        }
    }
    return rn;
}

int LuaStack::executeGlobalFunction(const char* functionName)
{
    lua_getglobal(_state, functionName); /* query function by name, stack: function */
    if (!lua_isfunction(_state, -1))
    {
        AXLOG("[LUA ERROR] name '%s' does not represent a Lua function", functionName);
        lua_pop(_state, 1);
        return 0;
    }
    return executeFunction(0);
}

void LuaStack::clean()
{
    lua_settop(_state, 0);
}

int LuaStack::executeFunction(int numArgs)
{
    int functionIndex = -(numArgs + 1);
    if (!lua_isfunction(_state, functionIndex))
    {
        AXLOG("value at stack [%d] is not function", functionIndex);
        lua_pop(_state, numArgs + 1);  // remove function and arguments
        return 0;
    }

    int traceback = 0;
    lua_getglobal(_state, "__G__TRACKBACK__"); /* L: ... func arg1 arg2 ... G */
    if (!lua_isfunction(_state, -1))
    {
        lua_pop(_state, 1); /* L: ... func arg1 arg2 ... */
    }
    else
    {
        lua_insert(_state, functionIndex - 1); /* L: ... G func arg1 arg2 ... */
        traceback = functionIndex - 1;
    }

    int error = 0;
    ++_callFromLua;
    error = lua_pcall(_state, numArgs, 1, traceback); /* L: ... [G] ret */
    --_callFromLua;
    if (error)
    {
        if (traceback == 0)
        {
            AXLOG("[LUA ERROR] %s", lua_tostring(_state, -1)); /* L: ... error */
            lua_pop(_state, 1);                                // remove error message from stack
        }
        else /* L: ... G error */
        {
            lua_pop(_state, 2);  // remove __G__TRACKBACK__ and error message from stack
        }
        return 0;
    }

    // get return value
    int ret = 0;
    if (lua_isnumber(_state, -1))
    {
        ret = (int)lua_tointeger(_state, -1);
    }
    else if (lua_isboolean(_state, -1))
    {
        ret = (int)lua_toboolean(_state, -1);
    }
    // remove return value from stack
    lua_pop(_state, 1); /* L: ... [G] */

    if (traceback)
    {
        lua_pop(_state, 1);  // remove __G__TRACKBACK__ from stack      /* L: ... */
    }

    return ret;
}

bool LuaStack::handleAssert(const char* msg)
{
    if (_callFromLua == 0)
        return false;

    lua_pushfstring(_state, "ASSERT FAILED ON LUA EXECUTE: %s", msg ? msg : "unknown");
    lua_error(_state);
    return true;
}

int LuaStack::reload(const char* moduleFileName)
{
    if (nullptr == moduleFileName || strlen(moduleFileName) == 0)
    {
        AXLOG("moudulFileName is null");
        return 1;
    }

    lua_getglobal(_state, "package");   /* L: package */
    lua_getfield(_state, -1, "loaded"); /* L: package loaded */
    lua_pushstring(_state, moduleFileName);
    lua_gettable(_state, -2); /* L:package loaded module */
    if (!lua_isnil(_state, -1))
    {
        lua_pushstring(_state, moduleFileName); /* L:package loaded module name */
        lua_pushnil(_state);                    /* L:package loaded module name nil*/
        lua_settable(_state, -4);               /* L:package loaded module */
    }
    lua_pop(_state, 3);

    std::string name    = moduleFileName;
    std::string require = "require \'" + name + "\'";
    return executeString(require.c_str());
}

namespace
{

void skipBOM(const char*& chunk, int& chunkSize)
{
    // UTF-8 BOM? skip
    if (chunkSize >= 3 && static_cast<unsigned char>(chunk[0]) == 0xEF &&
        static_cast<unsigned char>(chunk[1]) == 0xBB && static_cast<unsigned char>(chunk[2]) == 0xBF)
    {
        chunk += 3;
        chunkSize -= 3;
    }
}

}  // end anonymous namespace

int LuaStack::luaLoadBuffer(lua_State* L, const char* chunk, int chunkSize, const char* chunkName)
{
    int r = 0;

    skipBOM(chunk, chunkSize);
    r = luaL_loadbuffer(L, chunk, chunkSize, chunkName);

#if defined(_AX_DEBUG) && _AX_DEBUG > 0
    if (r)
    {
        switch (r)
        {
        case LUA_ERRSYNTAX:
            AXLOG("[LUA ERROR] load \"%s\", error: syntax error during pre-compilation.", chunkName);
            break;

        case LUA_ERRMEM:
            AXLOG("[LUA ERROR] load \"%s\", error: memory allocation error.", chunkName);
            break;

        case LUA_ERRFILE:
            AXLOG("[LUA ERROR] load \"%s\", error: cannot open/read file.", chunkName);
            break;

        default:
            AXLOG("[LUA ERROR] load \"%s\", error: unknown.", chunkName);
        }
    }
#endif
    return r;
}

NS_AX_END
