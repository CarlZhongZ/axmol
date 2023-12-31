/****************************************************************************
 Copyright (c) 2011-2012 cocos2d-x.org
 Copyright (c) 2013-2016 Chukong Technologies Inc.
 Copyright (c) 2017-2018 Xiamen Yaji Software Co., Ltd.

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

#ifndef __AX_LUA_STACK_H_
#define __AX_LUA_STACK_H_

extern "C" {
#include "lua.h"
}

#include "scripting/lua-bindings/manual/LuaValue.h"

/**
 * @addtogroup lua
 * @{
 */

NS_AX_BEGIN

/**
 * LuaStack is used to manager the operation on the lua_State,eg., push data onto the lua_State, execute the function
 * depended on the lua_State. In the current mechanism, there is only one lua_State in one LuaStack object.
 *
 * @lua NA
 * @js NA
 */
class LuaStack : public Ref
{
public:
    /**
     * Create a LuaStack object, it will new a lua_State.
     */
    static LuaStack* create();
    /**
     * Create a LuaStack object with the existed lua_State.
     */
    static LuaStack* attach(lua_State* L);

    /** Destructor. */
    virtual ~LuaStack();

    /**
     * Method used to get a pointer to the lua_State that the script module is attached to.
     *
     * @return A pointer to the lua_State that the script module is attached to.
     */
    lua_State* getLuaState() { return _state; }

    /**
     * Add a path to find lua files in.
     *
     * @param path to be added to the Lua search path.
     */
    virtual void addSearchPath(const char* path);

    /**
     * Add lua loader.
     *
     * @param func a function pointer point to the loader function.
     */
    virtual void addLuaLoader(lua_CFunction func);

    /**
     * Reload script code corresponding to moduleFileName.
     * If value of package["loaded"][moduleFileName] is existed, it would set the value nil.Then,it calls executeString
     * function.
     *
     * @param moduleFileName String object holding the filename of the script file that is to be executed.
     * @return 0 if the string is executed correctly or other if the string is executed wrongly.
     */
    virtual int reload(const char* moduleFileName);

    /**
     * Execute script code contained in the given string.
     *
     * @param codes holding the valid script code that should be executed.
     * @return 0 if the string is executed correctly, other if the string is executed wrongly.
     */
    virtual int executeString(const char* codes);

    /**
     * Execute a script file.
     *
     * @param filename String object holding the filename of the script file that is to be executed.
     * @return the return values by calling executeFunction.
     */
    virtual int executeScriptFile(const char* filename);

    /**
     * Execute a scripted global function.
     * The function should not take any parameters and should return an integer.
     *
     * @param functionName String object holding the name of the function, in the global script environment, that is to
     * be executed.
     * @return The integer value returned from the script function.
     */
    virtual int executeGlobalFunction(const char* functionName);

    /**
     * Set the stack top index 0.
     */
    virtual void clean();

    /**
     * Execute the lua function on the -(numArgs + 1) index on the stack by the numArgs variables passed.
     *
     * @param numArgs the number of variables.
     * @return 0 if it happen the error or it hasn't return value, otherwise it return the value by calling the lua
     * function.
     */
    virtual int executeFunction(int numArgs);

    /**
     * Handle the assert message.
     *
     * @return return true if current _callFromLua of LuaStack is not equal to 0 otherwise return false.
     */
    virtual bool handleAssert(const char* msg);

    /**
     * Loads a buffer as a Lua chunk.This function uses lua_load to load the Lua chunk in the buffer pointed to by chunk
     * with size chunkSize. If it supports xxtea encryption algorithm, the chunk and the chunkSize would be processed by
     * calling xxtea_decrypt to the real buffer and buffer size.
     *
     * @param L the current lua_State.
     * @param chunk the buffer pointer.
     * @param chunkSize the size of buffer.
     * @param chunkName the name of chunk pointer.
     * @return 0, LUA_ERRSYNTAX or LUA_ERRMEM:.
     */
    int luaLoadBuffer(lua_State* L, const char* chunk, int chunkSize, const char* chunkName);
protected:
    LuaStack() : _state(nullptr), _callFromLua(0) {}

    bool init();
    bool initWithLuaState(lua_State* L);

    lua_State* _state;
    int _callFromLua;
};

NS_AX_END

// end group
/// @}
#endif  // __AX_LUA_STACK_H_
