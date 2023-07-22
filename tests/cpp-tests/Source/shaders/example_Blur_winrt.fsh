#version 310 es
precision highp float;
precision highp int;

layout(location = 0) in vec4 v_fragmentColor;
layout(location = 1) in vec2 v_texCoord;


layout(binding = 0) uniform sampler2D u_tex0;

layout(std140, binding = 0) uniform fs_ub {
    vec2 resolution;
};

vec4 blur(vec2);

layout(location = 0) out vec4 FragColor;

void main(void)
{
    vec4 col = blur(v_texCoord); //* v_fragmentColor.rgb;
    FragColor = vec4(col) * v_fragmentColor;
}

vec4 blur(vec2 p)
{
        vec4 col = vec4(0);
        vec2 unit = 1.0 / resolution.xy;
        
        float count = 0.0;
        
        for(float x = -4.0; x <= 4.0; x += 2.0)
        {
            for(float y = -4.0; y <= 4.0; y += 2.0)
            {
                float weight = (4.0 - abs(x)) * (4.0 - abs(y));
                col += texture(u_tex0, p + vec2(x * unit.x, y * unit.y)) * weight;
                count += weight;
            }
        }
        
        return col / count;
}
