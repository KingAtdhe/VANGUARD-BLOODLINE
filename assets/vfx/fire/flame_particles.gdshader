shader_type spatial;
// Flames from the owner's flipbook (D-107; owner: "his flames look low quality").
// Billboard particles like StandardMaterial's, plus:
//  - the six drawn frames cross-fade instead of popping (it flickered at ~14 fps),
//  - a rising heat shimmer (scrolling noise bends the flame, more at its top),
//  - brightness mapped to fire colours: white-yellow core, orange, deep red edge.
// Additive: black is transparent.
render_mode blend_add, unshaded, cull_disabled, depth_draw_never, shadows_disabled;

uniform sampler2D flipbook : source_color, filter_linear_mipmap, repeat_disable;
uniform sampler2D noise_tex : filter_linear_mipmap, repeat_enable;
uniform int frames = 6;
uniform float distort = 0.07;
uniform float shimmer_speed = 1.1;
uniform vec4 core_color : source_color = vec4(1.0, 0.85, 0.5, 1.0);
uniform vec4 mid_color : source_color = vec4(1.0, 0.38, 0.06, 1.0);
uniform vec4 edge_color : source_color = vec4(0.55, 0.04, 0.01, 1.0);
uniform float intensity = 0.55;

varying float v_frame;
varying float v_seed;

void vertex() {
	mat4 mat_world = mat4(normalize(INV_VIEW_MATRIX[0]), normalize(INV_VIEW_MATRIX[1]), normalize(INV_VIEW_MATRIX[2]), MODEL_MATRIX[3]);
	mat_world = mat_world * mat4(vec4(cos(INSTANCE_CUSTOM.x), -sin(INSTANCE_CUSTOM.x), 0.0, 0.0),
			vec4(sin(INSTANCE_CUSTOM.x), cos(INSTANCE_CUSTOM.x), 0.0, 0.0), vec4(0.0, 0.0, 1.0, 0.0), vec4(0.0, 0.0, 0.0, 1.0));
	MODELVIEW_MATRIX = VIEW_MATRIX * mat_world;
	MODELVIEW_MATRIX = MODELVIEW_MATRIX * mat4(vec4(length(MODEL_MATRIX[0].xyz), 0.0, 0.0, 0.0),
			vec4(0.0, length(MODEL_MATRIX[1].xyz), 0.0, 0.0), vec4(0.0, 0.0, length(MODEL_MATRIX[2].xyz), 0.0), vec4(0.0, 0.0, 0.0, 1.0));
	MODELVIEW_NORMAL_MATRIX = mat3(MODELVIEW_MATRIX);
	v_frame = INSTANCE_CUSTOM.z * float(frames);
	v_seed = fract(MODEL_MATRIX[3].x * 3.7 + MODEL_MATRIX[3].y * 1.3);
}

vec4 cell(float f, vec2 uv) {
	float fr = mod(f, float(frames));
	return texture(flipbook, vec2((fr + clamp(uv.x, 0.004, 0.996)) / float(frames), clamp(uv.y, 0.004, 0.996)));
}

void fragment() {
	vec2 uv = UV;
	vec2 n = texture(noise_tex, uv * vec2(0.9, 1.3) + vec2(v_seed, v_seed * 0.7 - TIME * shimmer_speed)).rg - 0.5;
	uv += n * distort * (1.15 - uv.y);           // the tips flicker more than the base
	float f0 = floor(v_frame);
	vec4 c = mix(cell(f0, uv), cell(f0 + 1.0, uv), smoothstep(0.0, 1.0, fract(v_frame)));
	float heat = max(c.r, max(c.g, c.b));
	vec3 col = mix(edge_color.rgb, mid_color.rgb, smoothstep(0.18, 0.55, heat));
	col = mix(col, core_color.rgb, smoothstep(0.8, 1.0, heat));
	float a = c.a * COLOR.a;
	ALBEDO = col * intensity * a * COLOR.rgb;
	ALPHA = a;
}
