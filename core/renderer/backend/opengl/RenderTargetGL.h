#pragma once
#include "../RenderTarget.h"
#include "platform/GL.h"
#include "OpenGLState.h"

NS_AX_BACKEND_BEGIN

class DriverGL;

class RenderTargetGL : public RenderTarget
{
public:
    /*
     * generateFBO, false, use for screen framebuffer
     */
    RenderTargetGL(bool defaultRenderTarget, DriverGL* driver);
    ~RenderTargetGL();

    void bindFrameBuffer() const;
    void unbindFrameBuffer() const;

    void update() const;

public:
    GLuint _FBO = 0;
};

NS_AX_BACKEND_END
