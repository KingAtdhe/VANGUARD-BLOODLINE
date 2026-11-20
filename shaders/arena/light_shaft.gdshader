shader_type spatial;
render_mode unshaded, blend_add, cull_disabled, depth_draw_never, fog_disabled;
// Fake volumetric beam (searchlight, stage-light shaft): an open cone that
// fades towards its far end and towards its silhouette edges. Cheap on phones.
uniform vec4 color : source_color = vec4(1.0, 0.95, 0.85, 1.0);
uniform float strength = 0.08;
// UV.y runs along the cone; which end is the source:
uniform bool source_at_top = true;

void fragment() {
	float along = source_at_top ? UV.y : 1.0 - UV.y;
	float edge = pow(abs(dot(NORMAL, VIEW)), 1.5);
	ALBEDO = color.rgb * strength * (1.0 - along) * edge;
}
