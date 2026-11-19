class_name ArenaView
extends Node3D
## Presentation root of an arena scene: geometry (Blender GLB), lighting,
## environment, ambient effects and signage. Purely visual — the gameplay
## bounds come from [member config] (ArenaConfig) only, never from meshes.
##
## Nodes in the group "arena_fx" are optional ambience (particles, flicker)
## and are switched off by the "reduced effects" setting.

const FX_GROUP: StringName = &"arena_fx"

@export var config: ArenaConfig
## Folder of per-surface materials; empty = "materials" next to the GLB.
@export_dir var material_dir: String = ""


func _ready() -> void:
	if config == null:
		push_error("ArenaView %s: no ArenaConfig assigned" % name)
	apply_surface_materials()


## Swaps the flat glTF materials for the textured ones written by
## tools/blender/arena_builder.py (tiling textures + baked AO on UV2).
## Looked up by material name in res://assets/arenas/<folder>/materials/.
## A material without a matching file keeps its imported look.
func apply_surface_materials() -> void:
	var dir: String = material_dir
	if dir == "":
		var geo: Node = get_node_or_null("Geometry")
		if geo == null or geo.scene_file_path == "":
			return
		dir = geo.scene_file_path.get_base_dir().path_join("materials")
	for n: Node in find_children("*", "MeshInstance3D", true, false):
		var mi: MeshInstance3D = n
		if mi.mesh == null:
			continue
		for s: int in mi.mesh.get_surface_count():
			var src: Material = mi.mesh.surface_get_material(s)
			if src == null or src.resource_name == "":
				continue
			var path: String = dir.path_join(src.resource_name + ".tres")
			if ResourceLoader.exists(path):
				mi.set_surface_override_material(s, load(path) as Material)


## [param enabled] false hides ambient particles for low-end devices.
func set_ambient_effects(enabled: bool) -> void:
	for n: Node in get_tree().get_nodes_in_group(FX_GROUP):
		if not is_ancestor_of(n):
			continue
		if n is GPUParticles3D:
			(n as GPUParticles3D).emitting = enabled
			(n as GPUParticles3D).visible = enabled
		elif n is Node3D:
			(n as Node3D).visible = enabled
