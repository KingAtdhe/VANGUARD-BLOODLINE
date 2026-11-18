class_name MenuBackdrop
extends SubViewportContainer
## Live 3D backdrop for menus: an arena with a fighter model idling in it,
## seen through a slowly drifting camera. Presentation only. Sized to its
## parent; renders in its own World3D so it never touches a match.

const IDLE_FALLBACK: StringName = &"KAIRO_IDLE_A"

var _viewport: SubViewport
var _world_root: Node3D
var _arena: Node3D = null
var _fighter_pivot: Node3D
var _fighter: Node3D = null
var _camera: Camera3D
var _t: float = 0.0
var arena_id: StringName = &""
var fighter_id: StringName = &""
## Camera framing: "fighter" (close, fighter on the left third) or "arena".
var framing: String = "fighter"
## Horizontal screen offset of the fighter (+ = camera looks further right).
var fighter_offset: float = 1.1


func _init() -> void:
	stretch = true
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	set_anchors_preset(Control.PRESET_FULL_RECT)
	_viewport = SubViewport.new()
	_viewport.own_world_3d = true
	_viewport.msaa_3d = Viewport.MSAA_2X
	add_child(_viewport)
	_world_root = Node3D.new()
	_viewport.add_child(_world_root)
	_fighter_pivot = Node3D.new()
	_world_root.add_child(_fighter_pivot)
	_camera = Camera3D.new()
	_camera.fov = 32.0
	_camera.current = true
	_world_root.add_child(_camera)


func show_arena(id: StringName) -> void:
	if id == arena_id:
		return
	arena_id = id
	if _arena != null:
		_arena.queue_free()
		_arena = null
	var cfg: ArenaConfig = Catalog.arena(id)
	if cfg == null or not ResourceLoader.exists(cfg.scene_path):
		return
	_arena = (load(cfg.scene_path) as PackedScene).instantiate() as Node3D
	_world_root.add_child(_arena)
	_world_root.move_child(_arena, 0)


func show_fighter(id: StringName) -> void:
	if id == fighter_id:
		return
	fighter_id = id
	if _fighter != null:
		_fighter.queue_free()
		_fighter = null
	var def: FighterDefinition = Catalog.fighter(id)
	if def == null or def.model_scene == null:
		return
	_fighter = def.model_scene.instantiate() as Node3D
	_fighter_pivot.add_child(_fighter)
	_fighter.rotation_degrees.y = 28.0   # three-quarter view toward camera
	var ap: AnimationPlayer = _fighter.find_child("AnimationPlayer", true, false) as AnimationPlayer
	if ap != null:
		var idle: StringName = def.resolve_anim(def.anim_idle)
		if ap.has_animation(idle):
			ap.get_animation(idle).loop_mode = Animation.LOOP_LINEAR
			ap.play(idle)


func play_pose(logical: StringName) -> void:
	if _fighter == null:
		return
	var def: FighterDefinition = Catalog.fighter(fighter_id)
	var ap: AnimationPlayer = _fighter.find_child("AnimationPlayer", true, false) as AnimationPlayer
	if ap != null and def != null and ap.has_animation(def.resolve_anim(logical)):
		ap.play(def.resolve_anim(logical), 0.15)


func _process(delta: float) -> void:
	_t += delta
	var sway: float = sin(_t * 0.25) * 0.35
	if framing == "fighter":
		# Looking at a point beside the fighter puts them off-centre, leaving
		# room for the menu panel on the other side.
		_camera.position = Vector3(fighter_offset + sway, 1.3, 4.6)
		_camera.look_at(Vector3(fighter_offset + sway * 0.5, 1.0, 0.0))
	else:
		_camera.position = Vector3(sway * 3.0, 1.9, 9.0)
		_camera.look_at(Vector3(sway * 2.0, 1.6, -4.0))
