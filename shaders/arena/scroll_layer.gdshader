shader_type spatial;
render_mode unshaded, blend_mix, cull_disabled, depth_draw_never, fog_disabled;
// A far backdrop layer (cloud bank, dust haze) whose texture drifts sideways.
uniform sampler2D layer_tex : source_color, filter_linear_mipmap, repeat_enable;
uniform vec4 tint : source_color = vec4(1.0);
uniform float speed = 0.004;     // UV per second
uniform float repeat_x = 2.0;
uniform float opacity = 1.0;

void fragment() {
	vec4 c = texture(layer_tex, vec2(UV.x * repeat_x + TIME * speed, UV.y));
	ALBEDO = c.rgb * tint.rgb;
	ALPHA = c.a * tint.a * opacity;
}
