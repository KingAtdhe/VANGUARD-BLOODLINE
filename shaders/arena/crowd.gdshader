shader_type spatial;
render_mode cull_disabled;
// Crowd for The Pit. Each vertex carries UV = (seed, kind):
// kind 0 = spectator (cheers with small hops), 1 = waved flag cloth,
// 2 = phone light / flare, 3 = static prop (flag pole). Clothes colour comes from the seed, so one
// mesh and one draw call give a varied crowd. Presentation only.
uniform float hop = 0.13;
uniform float excitement = 0.6;   // share of spectators jumping
varying vec3 v_col;
varying float v_kind;

vec3 palette(float s) {
	vec3 dark[5] = vec3[](vec3(0.05,0.05,0.06), vec3(0.12,0.05,0.04), vec3(0.08,0.09,0.11),
		vec3(0.15,0.12,0.09), vec3(0.04,0.06,0.1));
	vec3 team[5] = vec3[](vec3(0.45,0.05,0.03), vec3(0.05,0.25,0.08), vec3(0.25,0.08,0.32),
		vec3(0.05,0.13,0.38), vec3(0.42,0.32,0.1));
	int i = int(fract(s * 7.13) * 5.0);
	return (fract(s * 3.71) < 0.18 ? team[i] : dark[i]) * (0.55 + 0.3 * fract(s * 17.3));
}

void vertex() {
	float seed = UV.x;
	v_kind = UV.y;
	v_col = palette(seed);
	float t = TIME;
	if (v_kind < 0.5) {
		float on = step(1.0 - excitement, fract(seed * 13.7));
		float h = max(0.0, sin(t * (5.0 + seed * 3.0) + seed * 40.0));
		VERTEX.y += h * h * hop * on;
	} else if (v_kind < 1.5) {
		VERTEX.x += sin(t * 3.0 + seed * 20.0 + VERTEX.x * 2.0) * 0.18;
		VERTEX.z += cos(t * 2.4 + seed * 11.0 + VERTEX.x * 3.0) * 0.12;
	}
}

void fragment() {
	if (v_kind > 2.5) {
		ALBEDO = vec3(0.06);
		ROUGHNESS = 0.5;
		METALLIC = 0.6;
	} else if (v_kind > 1.5) {
		ALBEDO = vec3(1.0);
		EMISSION = vec3(1.0, 0.94, 0.85) * 3.0;
	} else if (v_kind > 0.5) {
		ALBEDO = v_col * 2.0;
		ROUGHNESS = 0.8;
	} else {
		ALBEDO = v_col;
		ROUGHNESS = 0.9;
	}
}
