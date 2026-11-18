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
			if mat == null or mat.vertex_color_use_as_albedo:
				continue
			var colors: Variant = mesh.surface_get_arrays(s)[Mesh.ARRAY_COLOR]
			if colors != null and (colors as PackedColorArray).size() > 0:
				mat.vertex_color_use_as_albedo = true
