/****************************************************************************
 Copyright (c) 2012 cocos2d-x.org
 Copyright (c) 2010 Sangwoo Im
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

#ifndef __CCTABLEVIEWCELL_H__
#define __CCTABLEVIEWCELL_H__

#include "extensions/ExtensionMacros.h"
#include "2d/CCNode.h"
#include "extensions/ExtensionExport.h"

/**
 * @addtogroup ui
 * @{
 */
NS_AX_EXT_BEGIN

/**
 * Abstract class for SWTableView cell node
 */
class AX_EX_DLL TableViewCell : public Node
{
public:
    CREATE_FUNC(TableViewCell);

    TableViewCell() {}
    /**
     * The index used internally by SWTableView and its subclasses
     */
    ssize_t getIdx() const;
    void setIdx(ssize_t uIdx);
    /**
     * Cleans up any resources linked to this cell and resets <code>idx</code> property.
     */
    void reset();

private:
    ssize_t _idx;
};

NS_AX_EXT_END
// end of ui group
/// @}

#endif /* __CCTABLEVIEWCELL_H__ */
