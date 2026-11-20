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
	_fx_enabled = enabled
	for n: Node in get_tree().get_nodes_in_group(FX_GROUP):
		if not is_ancestor_of(n):
			continue
		if n is GPUParticles3D:
			(n as GPUParticles3D).emitting = enabled
			(n as GPUParticles3D).visible = enabled
		elif n is Node3D:
			(n as Node3D).visible = enabled


# --- reactions to the fight (presentation only) --------------------------

var _excite: float = 0.0
var _crowd_mats: Array[ShaderMaterial] = []
var _crowd_base: float = 0.6
var _fx_enabled: bool = true


## Called by the combat scene for notable moments. [param kind] is
## &"hit", &"knockdown" or &"ko"; [param x] is the fighting-plane position;
## [param strength] is roughly 0..1. Never affects gameplay.
func react(kind: StringName, x: float, strength: float) -> void:
	if not _fx_enabled:
		return
	var big: bool = kind != &"hit" or strength > 0.6
	if big:
		var dust: Node = get_node_or_null("Reactions/ImpactDust")
		if dust is GPUParticles3D:
			var p: GPUParticles3D = dust
			p.position = Vector3(x, 0.05, 0.0)   # Reactions sits at the arena origin
			p.amount_ratio = clampf(0.4 + strength * 0.6, 0.4, 1.0)
			p.restart()
	_excite = maxf(_excite, 1.0 if kind == &"ko" else (0.6 if kind == &"knockdown" else 0.25 * strength))
	for n: Node in find_children("*", "Node3D", true, false):
		if n is EmissionPulse:
			(n as EmissionPulse).flare(1.2 if kind == &"ko" else (0.6 if big else 0.2))


func _process(delta: float) -> void:
	if _crowd_mats.is_empty():
		for n: Node in find_children("*", "MeshInstance3D", true, false):
			var mi: MeshInstance3D = n
			for s: int in mi.get_surface_override_material_count():
				var m: Material = mi.get_surface_override_material(s)
				if m is ShaderMaterial and m.resource_name == "PIT_CrowdShader" and not _crowd_mats.has(m):
					_crowd_mats.append(m as ShaderMaterial)
					_crowd_base = float((m as ShaderMaterial).get_shader_parameter("excitement"))
		if _crowd_mats.is_empty():
			set_process(false)
			return
	_excite = maxf(0.0, _excite - delta * 0.25)
	for m: ShaderMaterial in _crowd_mats:
		m.set_shader_parameter("excitement", clampf(_crowd_base + _excite * 0.4, 0.0, 1.0))
		m.set_shader_parameter("hop", 0.13 + _excite * 0.12)
