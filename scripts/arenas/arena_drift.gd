class_name ArenaDrift
extends Node3D
## Moves this node around a slow loop (e.g. a drone over the Severed Line).
## Presentation only; render-frame time.

@export var radius: Vector2 = Vector2(18.0, 6.0)
@export var height_wave: float = 1.0
## Seconds per loop.
@export var period: float = 40.0

var _origin: Vector3
var _t: float = 0.0


func _ready() -> void:
	_origin = position


func _process(delta: float) -> void:
	_t += delta
	var a: float = TAU * _t / maxf(1.0, period)
	var p: Vector3 = _origin + Vector3(cos(a) * radius.x, sin(a * 2.0) * height_wave, sin(a) * radius.y)
	var ahead: Vector3 = _origin + Vector3(cos(a + 0.05) * radius.x, sin((a + 0.05) * 2.0) * height_wave,
		sin(a + 0.05) * radius.y)
	position = p
	if not p.is_equal_approx(ahead):
		look_at(ahead, Vector3.UP)
