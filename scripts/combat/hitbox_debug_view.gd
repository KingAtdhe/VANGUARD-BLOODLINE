class_name HitboxDebugView
extends Node3D
## Draws hurtboxes (green), live hitboxes (red) and spent hitboxes (grey)
## straight from the simulation, so what you see is exactly what is tested.
## Toggle with F4 (debug_toggle_hitboxes). Presentation only.

const HURT_COLOR := Color(0.1, 0.9, 0.3, 0.12)
const HIT_COLOR := Color(1.0, 0.1, 0.1, 0.55)
const SPENT_COLOR := Color(0.6, 0.6, 0.6, 0.3)
const DEPTH: float = 0.9

var _hurt: Array[MeshInstance3D] = []
var _hit: Array[MeshInstance3D] = []
var _hit_mats: Array[StandardMaterial3D] = []


func _ready() -> void:
	for i: int in 2:
		_hurt.append(_make_box(HURT_COLOR))
		var hit: MeshInstance3D = _make_box(HIT_COLOR)
		_hit.append(hit)
		_hit_mats.append(hit.material_override as StandardMaterial3D)


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed(InputActions.DEBUG_TOGGLE_HITBOXES):
		visible = not visible


## Shows boxes for the latest tick. [param render_x] is each fighter's
## interpolated x, so boxes stay glued to the drawn bodies.
func show_boxes(sim: CombatSimulation, render_x: Array[float]) -> void:
	if not visible:
		return
	for i: int in 2:
		var s: FighterState = sim.fighters[i]
		var offset: float = render_x[i] - s.position_x
		_place(_hurt[i], HitboxSystem.hurtbox(sim.definitions[i], s), offset)
		var hb: Rect2 = HitboxSystem.hitbox(s)
		_hit_mats[i].albedo_color = SPENT_COLOR if s.move_connected else HIT_COLOR
		_place(_hit[i], hb, offset)


func _place(box: MeshInstance3D, rect: Rect2, x_offset: float) -> void:
	box.visible = rect.has_area()
	if not box.visible:
		return
	var c: Vector2 = rect.get_center()
	box.position = Vector3(c.x + x_offset, c.y, 0.0)
	box.scale = Vector3(rect.size.x, rect.size.y, DEPTH)


func _make_box(color: Color) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var mesh := BoxMesh.new()
	mesh.size = Vector3.ONE
	mi.mesh = mesh
	var mat := StandardMaterial3D.new()
	mat.albedo_color = color
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.no_depth_test = true
	mat.cull_mode = BaseMaterial3D.CULL_DISABLED
	mi.material_override = mat
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	mi.visible = false
	add_child(mi)
	return mi
