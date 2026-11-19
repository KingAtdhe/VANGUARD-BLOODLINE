shader_type spatial;
// Cloth banner hanging from its top edge (QuadMesh, UV.y = 0 at the top):
// the free end sways in the wind. Presentation only.
uniform sampler2D albedo_tex : source_color, filter_linear_mipmap_anisotropic;
uniform float sway = 0.18;
uniform float speed = 1.6;
uniform float phase = 0.0;

void vertex() {
	float w = pow(UV.y, 1.5);
	float t = TIME * speed + phase;
	VERTEX.z += (sin(t + UV.y * 3.0) * 0.7 + sin(t * 2.3 + UV.y * 7.0) * 0.3) * sway * w;
	VERTEX.x += sin(t * 0.7 + phase) * sway * 0.25 * w;
}

void fragment() {
	vec4 c = texture(albedo_tex, UV);
	ALBEDO = c.rgb;
	ROUGHNESS = mix(0.85, 0.3, c.a);   // alpha marks gold thread
	METALLIC = c.a * 0.8;
}
