class_name FighterView
extends Node3D
## Visual representation of one fighter. Reads FighterState, never writes it.
##
## With a FighterDefinition that has a model_scene (Milestone 7: the
## from-scratch roster models), the model is instanced under ModelRoot and animated by
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
var _shield_mat: ShaderMaterial = null
var _shield_hit: float = 0.0
var _shield_rest_y: float = 0.0
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
## [param recolor_accent]: recolour the model's accent material to this
## view's accent_color (used to tell a mirror match apart); otherwise the
## fighter keeps its own Origin colour.
func setup(def: FighterDefinition, recolor_accent: bool = true) -> void:
	if def == null or def.model_scene == null:
		return
	if not recolor_accent:
		accent_color = def.accent_color
	model = def.model_scene.instantiate() as Node3D
	ModelUtil.prepare(model)
	_model_root.add_child(model)
	for n: Node in model.find_children("*", "Skeleton3D", true, false):
		skeleton = n as Skeleton3D
	var ap: AnimationPlayer = model.find_child("AnimationPlayer", true, false) as AnimationPlayer
	if ap != null:
		animator = FighterAnimator.new(ap, def)
	for n: Node in model.find_children("*", "MeshInstance3D", true, false):
		var mi := n as MeshInstance3D
		_model_meshes.append(mi)
		mi.layers |= FIGHTER_LAYER          # lit by the fighter key/rim lights
		# Per-fighter accent: duplicate the Origin-energy material and recolour.
		for surf: int in mi.mesh.get_surface_count():
			var mat := mi.get_active_material(surf) as StandardMaterial3D
			if mat != null and (mat.resource_name.contains("OriginRed") or mat.resource_name.ends_with("_Accent")):
				var m2 := mat.duplicate() as StandardMaterial3D
				if recolor_accent:
					m2.albedo_color = accent_color.darkened(0.25)
					m2.emission = accent_color
				mi.set_surface_override_material(surf, m2)
				_accent_materials.append(m2)
		# Painted (textured) fighters have no separate accent part: in a mirror
		# match P2 gets a light colour wash over the whole texture instead
		# (an alternate-colour costume). Their own look is otherwise untouched.
		if _accent_materials.is_empty() and recolor_accent:
			for surf: int in mi.mesh.get_surface_count():
				var tm := mi.get_active_material(surf) as StandardMaterial3D
				if tm != null and tm.albedo_texture != null and tm.resource_name.ends_with("_Body"):
					var t2 := tm.duplicate() as StandardMaterial3D
					t2.albedo_color = Color.WHITE.lerp(accent_color, 0.45)
					mi.set_surface_override_material(surf, t2)
					_accent_materials.append(t2)
	_make_energy_shield()
	_shield_rest_y = _shield.position.y
	# The capsule placeholder hides; the shield stays as a block indicator.
	_body.visible = false
	_fist.visible = false
	_aura.light_color = accent_color


## Swaps the placeholder block box for a curved energy shell (an arc of a
## cylinder wrapped in front of the fighter, so it reads from the side-on
## fight camera), tinted with this fighter's accent. Presentation only.
func _make_energy_shield() -> void:
	var mi := _shield as MeshInstance3D
	if mi == null:
		return
	const RADIUS: float = 0.62
	const HEIGHT: float = 1.9
	const SPAN: float = deg_to_rad(150.0)
	const SEG: int = 18
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for k: int in SEG:
		var a0: float = -SPAN * 0.5 + SPAN * k / SEG
		var a1: float = -SPAN * 0.5 + SPAN * (k + 1) / SEG
		var p0 := Vector3(cos(a0) * RADIUS, 0, sin(a0) * RADIUS)
		var p1 := Vector3(cos(a1) * RADIUS, 0, sin(a1) * RADIUS)
		var u0: float = float(k) / SEG
		var u1: float = float(k + 1) / SEG
		var quad: Array = [[p0, u0, 0.0], [p1, u1, 0.0], [p1 + Vector3.UP * HEIGHT, u1, 1.0],
			[p0, u0, 0.0], [p1 + Vector3.UP * HEIGHT, u1, 1.0], [p0 + Vector3.UP * HEIGHT, u0, 1.0]]
		for v: Array in quad:
			var pos: Vector3 = v[0]
			st.set_normal(Vector3(pos.x, 0, pos.z).normalized())
			st.set_uv(Vector2(v[1], 1.0 - v[2]))
			st.add_vertex(pos)
	mi.mesh = st.commit()
	var mat := ShaderMaterial.new()
	mat.shader = load("res://shaders/fx/block_shield.gdshader")
	mat.set_shader_parameter("tint", accent_color)
	mi.material_override = mat
	mi.set_surface_override_material(0, null)
	# centred on the body, feet to head (FacingMarker sits at y 1.5)
	mi.position = Vector3(0.0, -1.5 + 0.05, 0.0)
	_shield_mat = mat


## Render layer that only fighters are on (in addition to layer 1).
const FIGHTER_LAYER: int = 1 << 1
var _key_light: OmniLight3D = null
var _rim_light: OmniLight3D = null


## Key + rim light that follow this fighter and light only fighters
## (cull mask = FIGHTER_LAYER). Presentation only; values from ArenaConfig.
func set_fighter_lighting(key_color: Color, key_energy: float, rim_color: Color, rim_energy: float) -> void:
	if _key_light == null:
		_key_light = OmniLight3D.new()
		_key_light.name = "FighterKey"
		_key_light.position = Vector3(0.0, 1.7, 2.4)        # camera side, above head height
		_key_light.omni_range = 4.5
		_key_light.omni_attenuation = 0.8
		_key_light.light_specular = 0.35
		_key_light.light_cull_mask = FIGHTER_LAYER
		add_child(_key_light)
		_rim_light = OmniLight3D.new()
		_rim_light.name = "FighterRim"
		_rim_light.position = Vector3(0.0, 2.1, -1.6)       # behind, edges the silhouette
		_rim_light.omni_range = 3.6
		_rim_light.omni_attenuation = 1.2
		_rim_light.light_specular = 0.8
		_rim_light.light_cull_mask = FIGHTER_LAYER
		add_child(_rim_light)
	_key_light.light_color = key_color
	_key_light.light_energy = key_energy
	_rim_light.light_color = rim_color
	_rim_light.light_energy = rim_energy


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
			or current.action == FighterState.Action.LAUNCHED \
			or current.action == FighterState.Action.BLOCKSTUN
	if frozen and victim:
		x += sin(Time.get_ticks_msec() * 0.09) * HITSTOP_SHAKE
	position.x = x
	# A launched fighter is drawn on its arc (presentation only).
	position.y = lerpf(previous.launch_height(), current.launch_height(), alpha)
	_facing_marker.scale.x = float(current.facing)
	_shield.visible = current.is_blocking()
	# Low block: the shield drops to cover the legs.
	_shield.position.y = lerpf(_shield.position.y, _shield_rest_y - (0.45 if current.block_low else 0.0),
			minf(1.0, delta * 18.0))
	if _shield_mat != null:
		# flash when a blocked hit lands (block stun starts)
		if current.action == FighterState.Action.BLOCKSTUN and previous.action != FighterState.Action.BLOCKSTUN:
			_shield_hit = 1.0
		_shield_hit = maxf(0.0, _shield_hit - delta * 4.0)
		_shield_mat.set_shader_parameter("hit", _shield_hit)
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
