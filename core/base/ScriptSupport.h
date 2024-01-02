/****************************************************************************
 Copyright (c) 2010-2012 cocos2d-x.org
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

#ifndef __SCRIPT_SUPPORT_H__
#define __SCRIPT_SUPPORT_H__

#include "base/Config.h"
#include "platform/Common.h"
#include "base/Touch.h"
#include "base/EventTouch.h"
#include "base/EventKeyboard.h"
#include <map>
#include <string>
#include <list>

/**
 * @addtogroup base
 * @{
 */

#if AX_ENABLE_SCRIPT_BINDING

NS_AX_BEGIN

/**
 * Don't make ScriptEngineProtocol inherits from Object since setScriptEngine is invoked only once in AppDelegate.cpp,
 * It will affect the lifecycle of ScriptEngine instance, the autorelease pool will be destroyed before destructing
 * ScriptEngine. So a crash will appear on Win32 if you click the close button.
 * @js NA
 */
class AX_DLL ScriptEngineProtocol
{
public:
    ScriptEngineProtocol() {}

    virtual ~ScriptEngineProtocol() {}

    virtual void removeScriptObjectByObject(Ref* /*obj*/) {}
};

class Node;
/**
 * ScriptEngineManager is a singleton which manager an object instance of ScriptEngineProtocol, such as LuaEngine.
 *
 * @since v0.99.5-x-0.8.5
 * @js NA
 */
class AX_DLL ScriptEngineManager
{
public:
    /**
     * Constructor of ScriptEngineManager.
     *
     * @lua NA
     * @js NA
     */
    ~ScriptEngineManager();
    /**
     * Get the ScriptEngineProtocol object.
     *
     * @return the ScriptEngineProtocol object.
     *
     * @lua NA
     * @js NA
     */
    ScriptEngineProtocol* getScriptEngine() { return _scriptEngine; }
    /**
     * Set the ScriptEngineProtocol object should be managed.
     *
     * @param scriptEngine should be managed.
     *
     * @lua NA
     * @js NA
     */
    void setScriptEngine(ScriptEngineProtocol* scriptEngine);

    /**
     * Remove the ScriptEngineProtocol object managed.
     *
     *
     * @lua NA
     * @js NA
     */
    void removeScriptEngine();
    /**
     * Get the instance of ScriptEngineManager object.
     *
     * @return the instance of ScriptEngineManager object.
     *
     * @lua NA
     * @js NA
     */
    static ScriptEngineManager* getInstance();
    /**
     * Destroy the singleton about ScriptEngineManager.
     *
     * @lua NA
     * @js NA
     */
    static void destroyInstance();
private:
    ScriptEngineManager() : _scriptEngine(nullptr) {}

    ScriptEngineProtocol* _scriptEngine;
};

NS_AX_END

#endif  // #if AX_ENABLE_SCRIPT_BINDING

// end group
/// @}

#endif  // __SCRIPT_SUPPORT_H__
