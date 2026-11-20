shader_type spatial;
// Arena surfaces (materials written by tools/blender/arena_builder.py).
// UV  : world-scale planar projection for the shared tiling textures.
// UV2 : unique unwrap carrying two baked maps:
//   ao_tex    - ambient occlusion (also drives grime: dirt gathers where
//               light can't reach, so wear follows the shapes),
//   light_tex - baked bounce light + light spilled by glowing surfaces
//               (neon, lamps, Origin cracks), sqrt-encoded, added as
//               emission on top of the real-time lights.
// A world-space macro noise breaks up visible texture tiling.
uniform vec4 tint : source_color = vec4(1.0);
uniform bool use_textures = true;
uniform sampler2D albedo_tex : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D normal_tex : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D rough_tex : hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D macro_tex : hint_default_white, filter_linear_mipmap, repeat_enable;
uniform sampler2D ao_tex : hint_default_white, filter_linear;
uniform sampler2D light_tex : hint_default_black, filter_linear;
uniform float roughness = 0.8;
uniform float metallic = 0.0;
uniform float normal_strength = 1.0;
uniform float macro = 0.3;
uniform float macro_size = 14.0;
uniform float grime = 0.6;
uniform float ao_light_affect = 0.7;
uniform float light_scale = 4.0;
uniform float light_strength = 1.0;
// Caps baked light right next to strong emitters so nearby paint doesn't blow out.
uniform float light_max = 0.8;
uniform vec4 emission_color : source_color = vec4(0.0, 0.0, 0.0, 1.0);
uniform float emission_energy = 0.0;
// > 0: brightness waves travel outward from the arena centre (Origin cracks).
uniform float flow = 0.0;

varying vec3 world_pos;

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	vec3 base = tint.rgb;
	float r = roughness;
	if (use_textures) {
		base *= texture(albedo_tex, UV).rgb;
		r *= texture(rough_tex, UV).r;
		NORMAL_MAP = texture(normal_tex, UV).rgb;
		NORMAL_MAP_DEPTH = normal_strength;
	}
	float m = texture(macro_tex, world_pos.xz / macro_size + world_pos.y * 0.03).r;
	base *= mix(1.0, 0.55 + 0.9 * m, macro);
	float ao = texture(ao_tex, UV2).r;
	float dirt = clamp((1.0 - ao) * 1.4, 0.0, 1.0) * grime;
	base *= 1.0 - dirt * 0.55;
	r = mix(r, 1.0, dirt * 0.5);
	ALBEDO = base;
	ROUGHNESS = clamp(r, 0.02, 1.0);
	METALLIC = metallic;
	AO = ao;
	AO_LIGHT_AFFECT = ao_light_affect;
	vec3 lm = texture(light_tex, UV2).rgb;
	EMISSION = base * min(lm * lm * light_scale * light_strength, vec3(light_max));
	if (emission_energy > 0.0) {
		float f = 1.0;
		if (flow > 0.0) {
			f = 0.55 + 0.45 * sin(length(world_pos.xz) * 1.3 - TIME * flow * 3.0);
		}
		EMISSION += emission_color.rgb * emission_energy * f;
	}
}
