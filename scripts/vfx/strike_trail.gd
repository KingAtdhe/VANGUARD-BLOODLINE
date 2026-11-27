class_name StrikeTrail
extends MeshInstance3D
## A short fading ribbon behind a fast-moving fist or foot (D-141, owner:
## "on fast strikes add 1-2 smear or motion-trail frames on the striking limb
## so it reads on a phone screen").
##
## Presentation only: the simulation never reads it. FighterView feeds it the
## limb's world position every rendered frame while a strike is coming out;
## the ribbon is drawn only between samples that moved fast, so a guard hand
## that drifts leaves nothing. Old samples fade out by age, so a trail also
## dies away during hit-stop. One ImmediateMesh of at most MAX_POINTS * 2
## vertices per limb: cheap enough for mid-range Android.

const MAX_POINTS: int = 8
## Seconds a sample stays visible.
const LIFE: float = 0.12
## Metres per second below which a stretch of the path is not drawn.
const MIN_SPEED: float = 4.0

var width: float = 0.16
var color: Color = Color(1.0, 0.72, 0.38)

var _points: Array[Vector3] = []
var _ages: Array[float] = []
var _speeds: Array[float] = []
var _mesh: ImmediateMesh = ImmediateMesh.new()
var _mat: StandardMaterial3D = StandardMaterial3D.new()


func _ready() -> void:
	top_level = true                    # world-space points
	mesh = _mesh
	cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	_mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	_mat.blend_mode = BaseMaterial3D.BLEND_MODE_MIX       # additive vanished against the bright arenas
	_mat.cull_mode = BaseMaterial3D.CULL_DISABLED
	_mat.vertex_color_use_as_albedo = true
	_mat.no_depth_test = false
	material_override = _mat


## Adds this frame's limb position. [param active] false = only age the trail.
func feed(world_pos: Vector3, delta: float, active: bool) -> void:
	for i: int in _ages.size():
		_ages[i] += delta
	while not _ages.is_empty() and _ages[0] > LIFE:
		_points.pop_front()
		_ages.pop_front()
		_speeds.pop_front()
	if active and delta > 0.0:
		var spd: float = 0.0
		if not _points.is_empty():
			spd = _points.back().distance_to(world_pos) / delta
		if _points.is_empty() or _points.back().distance_squared_to(world_pos) > 1e-6:
			_points.append(world_pos)
			_ages.append(0.0)
			_speeds.append(spd)
	while _points.size() > MAX_POINTS:
		_points.pop_front()
		_ages.pop_front()
		_speeds.pop_front()
	_rebuild()


func clear() -> void:
	_points.clear()
	_ages.clear()
	_speeds.clear()
	_mesh.clear_surfaces()


func _rebuild() -> void:
	_mesh.clear_surfaces()
	if _points.size() < 2:
		return
	var cam: Camera3D = get_viewport().get_camera_3d() if is_inside_tree() else null
	var view: Vector3 = Vector3.BACK if cam == null else cam.global_transform.basis.z
	var drawn: bool = false
	for i: int in range(1, _points.size()):
		if _speeds[i] < MIN_SPEED:
			continue
		if not drawn:
			_mesh.surface_begin(Mesh.PRIMITIVE_TRIANGLES)
			drawn = true
		var a: Vector3 = _points[i - 1]
		var b: Vector3 = _points[i]
		var along: Vector3 = (b - a).normalized()
		var side: Vector3 = along.cross(view).normalized()
		# thin and faint at the old end, wide and bright at the limb
		var ta: float = 1.0 - clampf(_ages[i - 1] / LIFE, 0.0, 1.0)
		var tb: float = 1.0 - clampf(_ages[i] / LIFE, 0.0, 1.0)
		var wa: float = width * 0.5 * ta
		var wb: float = width * 0.5 * tb
		var ca := Color(color.r, color.g, color.b, 0.75 * ta)
		var cb := Color(color.r, color.g, color.b, 0.75 * tb)
		var v0: Vector3 = a - side * wa
		var v1: Vector3 = a + side * wa
		var v2: Vector3 = b - side * wb
		var v3: Vector3 = b + side * wb
		for pair: Array in [[v0, ca], [v1, ca], [v2, cb], [v1, ca], [v3, cb], [v2, cb]]:
			_mesh.surface_set_color(pair[1])
			_mesh.surface_add_vertex(pair[0])
	if drawn:
		_mesh.surface_end()
