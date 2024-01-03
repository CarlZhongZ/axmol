/****************************************************************************
 Copyright (c) 2012      cocos2d-x.org
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

#ifndef __AX_LUA_ENGINE_H__
#define __AX_LUA_ENGINE_H__

extern "C" {
#include "lua.h"
}

#include "base/ScriptSupport.h"
#include "scripting/lua-bindings/manual/LuaValue.h"
#include "scripting/lua-bindings/manual/Lua-BindingsExport.h"

/**
 * @addtogroup lua
 * @{
 */

NS_AX_BEGIN

/**
 * The Lua engine integrated into the axmol to process the interactive operation between lua and c++.
 *
 * @lua NA
 * @js NA
 */
class AX_LUA_DLL LuaEngine : public ScriptEngineProtocol
{
public:
    /**
     * Get instance of LuaEngine.
     *
     * @return the instance of LuaEngine.
     */
    static LuaEngine* getInstance(void);

    /**
     * Destructor of LuaEngine.
     */
    virtual ~LuaEngine(void);

    virtual void removeScriptObjectByObject(Ref* obj);

private:
    LuaEngine(void) {}
    bool init(void);
private:
    static LuaEngine* _defaultEngine;
};

NS_AX_END

// end group
/// @}

#endif  // __AX_LUA_ENGINE_H__
