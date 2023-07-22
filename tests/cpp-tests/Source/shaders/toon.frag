#version 310 es
precision highp float;
precision highp int;
layout(location = 0) in vec2 v_texture_coord;
layout(binding = 0) uniform sampler2D u_sampler0; 
layout(location = 1) in vec3 v_normal;
layout(std140, binding = 0) uniform fs_ub {
    vec4 u_color;
};

layout(location = 0) out vec4 FragColor;

void main(void)
{
	vec3 light_direction = vec3(1,-1,-1);
	light_direction = normalize(light_direction);
	vec3 light_color = vec3(1,1,1);
	vec3 normal  = normalize(v_normal);
	float diffuse_factor = dot(normal,-light_direction);
	vec4 diffuse_color = texture(u_sampler0,v_texture_coord);

    if (diffuse_factor > 0.95)      diffuse_factor=1.0;
    else if (diffuse_factor > 0.75) diffuse_factor = 0.8;
    else if (diffuse_factor > 0.50) diffuse_factor = 0.6;
    else                       diffuse_factor = 0.4;

	light_color = light_color * diffuse_factor;
    FragColor = vec4(light_color,1.0) * diffuse_color * u_color;
}
