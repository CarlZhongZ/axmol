#version 310 es
#ifdef GLES2
precision mediump float;
#else
precision highp float;
#endif

layout(location = COLOR0) in vec4 v_color;
layout(location = TEXCOORD0) in vec2 v_texCoord;

layout(binding = 0) uniform sampler2D u_tex0;

layout(std140) uniform fs_ub {
    vec4 baseColor;
};

layout(location = SV_Target0) out vec4 FragColor;

void main()
{
    FragColor = texture(u_tex0, v_texCoord) * baseColor;
    FragColor = vec4(FragColor.rgb * FragColor.a,  FragColor.a);
}