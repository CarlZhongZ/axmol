/****************************************************************************
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

#ifndef _AX_QUADCOMMAND_H_
#define _AX_QUADCOMMAND_H_

#include <vector>

#include "renderer/CCTrianglesCommand.h"

/**
 * @addtogroup renderer
 * @{
 */

NS_AX_BEGIN

/**
 Command used to render one or more Quads, similar to TrianglesCommand.
 Every QuadCommand will have generate material ID by give textureID, glProgramState, Blend function
 if the material id is the same, these QuadCommands could be batched to save draw call.
 */
class AX_DLL QuadCommand : public TrianglesCommand
{
public:
    /**Constructor.*/
    QuadCommand();
    /**Destructor.*/
    ~QuadCommand();

    /** Initializes the command.
     @param globalOrder GlobalZOrder of the command.
     @param texture The texture used in the command.
     @param blendType Blend function for the command.
     @param quads Rendered quads for the command.
     @param quadCount The number of quads when rendering.
     @param mv ModelView matrix for the command.
     @param flags to indicate that the command is using 3D rendering or not.
     */
    void init(float globalOrder,
              Texture2D* texture,
              const BlendFunc& blendType,
              V3F_C4B_T2F_Quad* quads,
              ssize_t quadCount,
              const Mat4& mv,
              uint32_t flags);

protected:
    void reIndex(int indices);

    int _indexSize;
    std::vector<uint16_t*> _ownedIndices;

    // shared across all instances
    static int __indexCapacity;
    static uint16_t* __indices;
};

NS_AX_END

/**
 end of support group
 @}
 */
#endif  //_AX_QUADCOMMAND_H_
