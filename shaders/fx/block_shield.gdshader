shader_type spatial;
// Block barrier (presentation only): a curved energy shell in front of the
// blocking fighter. Additive, unshaded: hex lattice, bright rim at the shell's
// edges and toward grazing angles, a ripple travelling up, and a flash on
// `hit` (0..1, set by FighterView when a blocked hit lands).
render_mode unshaded, blend_add, cull_disabled, depth_draw_never, shadows_disabled;

uniform vec4 tint : source_color = vec4(0.86, 0.11, 0.16, 1.0);
uniform float hit = 0.0;
uniform float strength = 0.55;

float hex_edge(vec2 p) {
	p *= vec2(1.0, 1.1547);
	vec2 a = mod(p, vec2(1.0, 1.732)) - vec2(0.5, 0.866);
	vec2 b = mod(p + vec2(0.5, 0.866), vec2(1.0, 1.732)) - vec2(0.5, 0.866);
	vec2 g = dot(a, a) < dot(b, b) ? a : b;
	g = abs(g);
	float d = max(dot(g, normalize(vec2(1.0, 1.732))), g.x);
	return smoothstep(0.44, 0.49, d);
}

void fragment() {
	vec2 uv = UV;
	float t = TIME;
	float edge = max(smoothstep(0.82, 1.0, abs(uv.x * 2.0 - 1.0)), smoothstep(0.88, 1.0, abs(uv.y * 2.0 - 1.0)));
	float fres = pow(1.0 - abs(dot(NORMAL, VIEW)), 2.0);
	float hexes = hex_edge(vec2(uv.x * 9.0, uv.y * 16.0));
	float ripple = smoothstep(0.08, 0.0, abs(fract(uv.y - t * 0.9) - 0.5) - 0.42);
	float fade = smoothstep(0.0, 0.12, uv.y) * smoothstep(1.0, 0.85, uv.y);
	float a = (0.03 + 0.22 * hexes + 0.7 * edge + 0.35 * fres + 0.5 * ripple * hexes) * fade;
	a *= strength * (1.0 + 2.5 * hit);
	ALBEDO = mix(tint.rgb, vec3(1.0, 0.85, 0.6), 0.25 * hexes + 0.6 * hit) * a;
}
