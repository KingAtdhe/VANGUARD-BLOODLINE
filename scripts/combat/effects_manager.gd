class_name EffectsManager
extends Node3D
## Placeholder impact effects (spec §4.7): a short spark at the contact point.
## Hits: warm, bigger for more damage. Blocks: cool and small.
## Presentation only — never affects the simulation.

const LIFETIME: float = 0.18
const HIT_COLOR := Color(1.0, 0.75, 0.3)
const BLOCK_COLOR := Color(0.45, 0.75, 1.0)

var _sparks: Array[Dictionary] = []


func spawn_for(event: CombatEvent) -> void:
	var is_hit: bool = event.type == CombatEvent.Type.HIT
	var size: float = (0.25 + event.damage / 250.0) if is_hit else 0.22
	var mi := MeshInstance3D.new()
	var mesh := SphereMesh.new()
	mesh.radius = 0.5
	mesh.height = 1.0
	mesh.radial_segments = 12
	mesh.rings = 6
	mi.mesh = mesh
	var mat := StandardMaterial3D.new()
	mat.albedo_color = HIT_COLOR if is_hit else BLOCK_COLOR
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.no_depth_test = true
	mi.material_override = mat
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	mi.position = Vector3(event.point.x, event.point.y, 0.3)
	mi.scale = Vector3.ONE * size * 0.4
	add_child(mi)
	_sparks.append({"node": mi, "mat": mat, "age": 0.0, "size": size})


func _process(delta: float) -> void:
	for i: int in range(_sparks.size() - 1, -1, -1):
		var s: Dictionary = _sparks[i]
		s.age += delta
		var t: float = s.age / LIFETIME
		if t >= 1.0:
			(s.node as Node).queue_free()
			_sparks.remove_at(i)
			continue
		(s.node as Node3D).scale = Vector3.ONE * s.size * lerpf(0.4, 1.0, t)
		var c: Color = (s.mat as StandardMaterial3D).albedo_color
		c.a = 1.0 - t
		(s.mat as StandardMaterial3D).albedo_color = c
