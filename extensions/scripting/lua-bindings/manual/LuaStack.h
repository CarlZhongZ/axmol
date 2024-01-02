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
     * Method used to get a pointer to the lua_State that the script module is attached to.
     *
     * @return A pointer to the lua_State that the script module is attached to.
     */
    lua_State* getLuaState() { return _state; }

protected:
    LuaStack() {}
    ~LuaStack();

    bool init();

    lua_State* _state = nullptr;
};

NS_AX_END

// end group
/// @}
#endif  // __AX_LUA_STACK_H_
