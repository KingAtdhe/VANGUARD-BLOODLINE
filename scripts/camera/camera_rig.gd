class_name CameraRig
extends Node3D
## Side-on fighting camera (spec §2.2).
##
## Tracks the midpoint between fighters with smoothing and bounded zoom. It
## never rotates during normal combat. After smoothing it applies a hard
## visibility guarantee: both fighters (plus margin) are always on screen.
## Presentation only — it never affects the simulation.

## Camera height above the floor and its fixed downward pitch.
@export var height: float = 1.5
@export_range(-30.0, 0.0) var pitch_degrees: float = -5.0
## Distance range from the fighting plane (zoom bounds).
@export var min_distance: float = 6.5
@export var max_distance: float = 14.0
## Space kept between each fighter's centre and the screen edge (metres).
@export var edge_margin: float = 1.5
## Smoothing rates (higher = snappier). Frame-rate independent.
@export var follow_rate: float = 8.0
@export var zoom_rate: float = 4.0
## Impact shake. 0 disables it (accessibility setting "reduced camera shake"
## will drive this from M7). Shake moves only the Camera node, never the rig,
## and is too small to push a fighter out of frame (< edge_margin).
@export_range(0.0, 1.0) var shake_scale: float = 1.0
@export var shake_decay: float = 14.0
const MAX_SHAKE: float = 0.08

## Body half-width used when the frame is pinned at an arena wall. Fighters
## never pass walls, so near a wall only their body needs to stay in frame.
const WALL_BODY_MARGIN: float = 0.45
## How far past an arena wall the frame may show (metres).
const WALL_OVERSHOOT: float = 0.5

@onready var camera: Camera3D = %Camera

var _arena: ArenaConfig
var _center_x: float = 0.0
var _distance: float = 6.0
var _initialised: bool = false
var _shake: float = 0.0
var _shake_time: float = 0.0


func configure(arena: ArenaConfig) -> void:
	_arena = arena


func _ready() -> void:
	camera.rotation_degrees = Vector3(pitch_degrees, 0.0, 0.0)


## Call once per render frame with the rendered (interpolated) fighter X.
func follow(p1_x: float, p2_x: float, delta: float) -> void:
	var target_center: float = (p1_x + p2_x) * 0.5
	var target_distance: float = required_distance(absf(p2_x - p1_x))

	if not _initialised:
		_center_x = target_center
		_distance = target_distance
		_initialised = true
	else:
		_center_x = lerpf(_center_x, target_center, 1.0 - exp(-follow_rate * delta))
		_distance = lerpf(_distance, target_distance, 1.0 - exp(-zoom_rate * delta))

	# Hard guarantee: smoothing may lag, but fighters never leave the frame.
	_distance = maxf(_distance, target_distance)
	var half_w: float = visible_half_width(_distance)
	var lo: float = maxf(p1_x, p2_x) + edge_margin - half_w
	var hi: float = minf(p1_x, p2_x) - edge_margin + half_w
	_center_x = clampf(_center_x, lo, hi) if lo <= hi else target_center
	_center_x = _clamp_to_arena(_center_x, half_w, p1_x, p2_x)

	position = Vector3(_center_x, height, _distance)
	_apply_shake(delta)


## Adds an impact shake impulse (metres of offset, capped at MAX_SHAKE).
func add_shake(amount: float) -> void:
	_shake = minf(MAX_SHAKE, _shake + amount * shake_scale)


func _apply_shake(delta: float) -> void:
	_shake_time += delta
	_shake *= exp(-shake_decay * delta)
	if _shake < 0.0005:
		_shake = 0.0
	camera.position = Vector3(sin(_shake_time * 71.0), cos(_shake_time * 53.0), 0.0) * _shake


## Distance needed to show both fighters with margins (clamped to zoom range).
func required_distance(separation: float) -> float:
	var tan_half_h: float = _tan_half_hfov()
	if tan_half_h <= 0.0:
		return max_distance
	var needed: float = (separation * 0.5 + edge_margin) / tan_half_h
	return clampf(needed, min_distance, max_distance)


## Half the visible width on the fighting plane (z = 0) at [param distance].
func visible_half_width(distance: float) -> float:
	return distance * _tan_half_hfov()


func center_x() -> float:
	return _center_x


func distance() -> float:
	return _distance


func _tan_half_hfov() -> float:
	var size: Vector2 = get_viewport().get_visible_rect().size if is_inside_tree() else Vector2(16, 9)
	var aspect: float = size.x / maxf(size.y, 1.0)
	return tan(deg_to_rad(camera.fov) * 0.5) * aspect


## Avoid showing past the arena walls when possible, without losing fighters.
func _clamp_to_arena(x: float, half_w: float, p1_x: float, p2_x: float) -> float:
	if _arena == null:
		return x
	var lo: float = _arena.left_bound - WALL_OVERSHOOT + half_w
	var hi: float = _arena.right_bound + WALL_OVERSHOOT - half_w
	if lo > hi:
		return (_arena.left_bound + _arena.right_bound) * 0.5
	var clamped: float = clampf(x, lo, hi)
	# Only accept the clamp if both fighters stay inside the frame.
	var left_edge: float = clamped - half_w
	var right_edge: float = clamped + half_w
	if minf(p1_x, p2_x) - WALL_BODY_MARGIN < left_edge or maxf(p1_x, p2_x) + WALL_BODY_MARGIN > right_edge:
		return x
	return clamped
