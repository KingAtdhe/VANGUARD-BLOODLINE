class_name FighterView
extends Node3D
## Visual representation of one fighter. Reads FighterState, never writes it.
##
## With a FighterDefinition that has a model_scene (Milestone 6: Kairo
## blockout), the model is instanced under ModelRoot and animated by
## FighterAnimator from simulation state. Without one, the M1 placeholder
## capsule is shown (fist extension, lean).
## Both show: block shield, hit flash, hitstop shake, Origin Surge aura.

@export var body_color: Color = Color(0.8, 0.2, 0.2)
@export var label_text: String = "FIGHTER"
## Accent (Origin energy) colour for the model; P2 uses a different hue.
@export var accent_color: Color = Color(1.0, 0.08, 0.06)
## Model yaw toward the camera: 90° = pure profile. Slightly less reads better.
@export_range(60.0, 90.0) var profile_yaw_degrees: float = 78.0

const FLASH_SECONDS: float = 0.12
const HITSTOP_SHAKE: float = 0.03

@onready var _body_pivot: Node3D = %BodyPivot
@onready var _body: MeshInstance3D = %Body
@onready var _facing_marker: Node3D = %FacingMarker
@onready var _fist: Node3D = %Fist
@onready var _shield: Node3D = %Shield
@onready var _label: Label3D = %NameLabel
@onready var _model_root: Node3D = %ModelRoot
@onready var _aura: OmniLight3D = %SurgeAura

var animator: FighterAnimator = null
var model: Node3D = null
var skeleton: Skeleton3D = null
var _material: StandardMaterial3D
var _flash_material: StandardMaterial3D
var _model_meshes: Array[MeshInstance3D] = []
var _accent_materials: Array[StandardMaterial3D] = []
var _flash_left: float = 0.0
var _fist_rest: Vector3


func _ready() -> void:
	_material = StandardMaterial3D.new()
	_material.albedo_color = body_color
	_material.roughness = 0.7
	_body.material_override = _material
	_label.text = label_text
	_label.visible = not label_text.is_empty()
	_fist_rest = _fist.position
	_flash_material = StandardMaterial3D.new()
	_flash_material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	_flash_material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	_flash_material.albedo_color = Color(1, 1, 1, 0.65)
	_aura.visible = false


## Instances the definition's model (if any). Call once after _ready.
func setup(def: FighterDefinition) -> void:
	if def == null or def.model_scene == null:
		return
	model = def.model_scene.instantiate() as Node3D
	_model_root.add_child(model)
	for n: Node in model.find_children("*", "Skeleton3D", true, false):
		skeleton = n as Skeleton3D
	var ap: AnimationPlayer = model.find_child("AnimationPlayer", true, false) as AnimationPlayer
	if ap != null:
		animator = FighterAnimator.new(ap, def)
	for n: Node in model.find_children("*", "MeshInstance3D", true, false):
		var mi := n as MeshInstance3D
		_model_meshes.append(mi)
		# Per-fighter accent: duplicate the Origin-energy material and recolour.
		for surf: int in mi.mesh.get_surface_count():
			var mat := mi.get_active_material(surf) as StandardMaterial3D
			if mat != null and mat.resource_name.contains("OriginRed"):
				var m2 := mat.duplicate() as StandardMaterial3D
				m2.albedo_color = accent_color.darkened(0.25)
				m2.emission = accent_color
				mi.set_surface_override_material(surf, m2)
				_accent_materials.append(m2)
	# The capsule placeholder hides; the shield stays as a block indicator.
	_body.visible = false
	_fist.visible = false
	_aura.light_color = accent_color


func has_model() -> bool:
	return model != null


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
	_shield.visible = current.is_blocking()
	if model != null:
		# glTF models face +Z; turn to face the opponent (±X), slightly toward camera.
		_model_root.rotation.y = deg_to_rad(profile_yaw_degrees) * float(current.facing)
		if animator != null:
			animator.update(current, alpha, frozen, delta)
	else:
		_update_capsule_pose(current)
	_update_surge(current, delta)
	_update_flash(delta)


func flash() -> void:
	_flash_left = FLASH_SECONDS


func _update_capsule_pose(s: FighterState) -> void:
	# Fist reach follows the attack phase.
	var reach: float = 0.0
	var height: float = _fist_rest.y
	if s.action == FighterState.Action.ATTACK and s.move != null and not s.move.activates_surge:
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
	var lean: float = 0.0
	match s.action:
		FighterState.Action.HITSTUN:
			lean = 0.3
		FighterState.Action.BLOCKSTUN:
			lean = 0.12
		FighterState.Action.KO, FighterState.Action.KNOCKDOWN:
			lean = PI * 0.5
		FighterState.Action.WAKEUP:
			lean = PI * 0.25
	_body_pivot.rotation.z = lean * float(s.facing)


func _update_surge(s: FighterState, _delta: float) -> void:
	var on: bool = s.in_surge() or (s.action == FighterState.Action.ATTACK and s.move != null and s.move.activates_surge)
	_aura.visible = on
	if on:
		_aura.light_energy = 1.6 + 0.5 * sin(Time.get_ticks_msec() * 0.012)
	for m: StandardMaterial3D in _accent_materials:
		m.emission_energy_multiplier = 4.0 if on else 1.0


func _update_flash(delta: float) -> void:
	_flash_left = maxf(0.0, _flash_left - delta)
	var flashing: bool = _flash_left > 0.0
	_material.albedo_color = body_color.lerp(Color.WHITE, 0.8) if flashing else body_color
	for mi: MeshInstance3D in _model_meshes:
		mi.material_overlay = _flash_material if flashing else null
