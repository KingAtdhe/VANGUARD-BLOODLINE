class_name FighterView
extends Node3D
## Visual representation of one fighter. Reads FighterState, never writes it.
## Placeholder capsule until the Blender model arrives (Milestone 6):
##   - "fist" extends toward the hitbox during startup/active, retracts in recovery
##   - shield plate in front while blocking
##   - leans back in hitstun, falls over on KO
##   - white flash on taking a hit, shake while frozen in hitstop

@export var body_color: Color = Color(0.8, 0.2, 0.2)
@export var label_text: String = "FIGHTER"

const FLASH_SECONDS: float = 0.12
const HITSTOP_SHAKE: float = 0.03

@onready var _body_pivot: Node3D = %BodyPivot
@onready var _body: MeshInstance3D = %Body
@onready var _facing_marker: Node3D = %FacingMarker
@onready var _fist: Node3D = %Fist
@onready var _shield: Node3D = %Shield
@onready var _label: Label3D = %NameLabel

var _material: StandardMaterial3D
var _flash_left: float = 0.0
var _fist_rest: Vector3


func _ready() -> void:
	_material = StandardMaterial3D.new()
	_material.albedo_color = body_color
	_material.roughness = 0.7
	_body.material_override = _material
	_label.text = label_text
	# Empty label = hidden (the match HUD shows names).
	_label.visible = not label_text.is_empty()
	_fist_rest = _fist.position


## Places the view between two tick states. [param alpha] in 0..1.
## [param frozen] is true while global hitstop is running.
func sync(previous: FighterState, current: FighterState, alpha: float,
		frozen: bool, delta: float) -> void:
	if previous == null or current == null:
		return
	var x: float = lerpf(previous.position_x, current.position_x, alpha)
	var victim: bool = current.action == FighterState.Action.HITSTUN \
			or current.action == FighterState.Action.BLOCKSTUN
	if frozen and victim:
		x += sin(Time.get_ticks_msec() * 0.09) * HITSTOP_SHAKE
	position.x = x
	_facing_marker.scale.x = float(current.facing)
	_update_pose(current)
	_update_flash(delta)


func flash() -> void:
	_flash_left = FLASH_SECONDS


func _update_pose(s: FighterState) -> void:
	# Fist reach follows the attack phase.
	var reach: float = 0.0
	var height: float = _fist_rest.y
	if s.action == FighterState.Action.ATTACK and s.move != null:
		var m: MoveData = s.move
		var target: float = m.hitbox_center.x - 0.05
		if s.move_frame < m.startup_frames:
			reach = target * 0.35 * float(s.move_frame) / m.startup_frames
		elif m.is_active_frame(s.move_frame):
			reach = target
		else:
			var into_recovery: float = float(s.move_frame - (m.startup_frames + m.active_frames - 1))
			reach = target * (1.0 - into_recovery / maxf(1.0, m.recovery_frames))
		height = m.hitbox_center.y - _facing_marker.position.y
	_fist.position = Vector3(_fist_rest.x + reach, height, _fist_rest.z)

	_shield.visible = s.is_blocking()

	var lean: float = 0.0
	match s.action:
		FighterState.Action.HITSTUN:
			lean = 0.3
		FighterState.Action.BLOCKSTUN:
			lean = 0.12
		FighterState.Action.KO:
			lean = PI * 0.5
	# Lean away from the opponent (backwards relative to facing).
	_body_pivot.rotation.z = lean * float(s.facing)


func _update_flash(delta: float) -> void:
	_flash_left = maxf(0.0, _flash_left - delta)
	_material.albedo_color = body_color.lerp(Color.WHITE, 0.8) if _flash_left > 0.0 else body_color
