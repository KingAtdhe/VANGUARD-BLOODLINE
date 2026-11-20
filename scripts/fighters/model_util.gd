class_name ModelUtil
extends RefCounted
## Fix-ups for imported fighter models.


## Fighter colours are painted per vertex. The glTF importer does not always
## flag every surface's material to use them (the first surface is skipped),
## which leaves that surface plain white — so set the flag wherever a
## surface carries colour data.
static func enable_vertex_colors(model: Node) -> void:
	for n: Node in model.find_children("*", "MeshInstance3D", true, false):
		var mesh: Mesh = (n as MeshInstance3D).mesh
		if mesh == null:
			continue
		for s: int in mesh.get_surface_count():
			var mat := mesh.surface_get_material(s) as StandardMaterial3D
			if mat == null or mat.vertex_color_use_as_albedo or mat.albedo_texture != null:
				continue
			var colors: Variant = mesh.surface_get_arrays(s)[Mesh.ARRAY_COLOR]
			if colors != null and (colors as PackedColorArray).size() > 0:
				mat.vertex_color_use_as_albedo = true


## Outline thickness in metres (inverted-hull method).
const OUTLINE_WIDTH: float = 0.0055

static var _outline: StandardMaterial3D = null


## Cel look to match the 2D character art: banded toon lighting, a soft rim
## light and an inked outline (a second pass that draws the mesh slightly
## inflated, back faces only, in near-black). Cheap enough for mobile: no
## post-processing, one extra draw per surface.
static func apply_toon_style(model: Node) -> void:
	if _outline == null:
		_outline = StandardMaterial3D.new()
		_outline.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		_outline.albedo_color = Color(0.03, 0.025, 0.03)
		_outline.cull_mode = BaseMaterial3D.CULL_FRONT
		_outline.grow = true
		_outline.grow_amount = OUTLINE_WIDTH
	for n: Node in model.find_children("*", "MeshInstance3D", true, false):
		var mesh: Mesh = (n as MeshInstance3D).mesh
		if mesh == null:
			continue
		for s: int in mesh.get_surface_count():
			var mat := mesh.surface_get_material(s) as StandardMaterial3D
			if mat == null or mat.next_pass == _outline:
				continue
			# Painted (textured) hero models are shown exactly as authored:
			# no toon banding, rim or outline that would change their look.
			if mat.albedo_texture != null:
				continue
			mat.diffuse_mode = BaseMaterial3D.DIFFUSE_TOON
			mat.specular_mode = BaseMaterial3D.SPECULAR_TOON
			mat.rim_enabled = true
			mat.rim = 0.35
			mat.rim_tint = 0.4
			mat.next_pass = _outline


## Everything a freshly instanced fighter model needs before it is shown.
static func prepare(model: Node) -> void:
	enable_vertex_colors(model)
	apply_toon_style(model)
