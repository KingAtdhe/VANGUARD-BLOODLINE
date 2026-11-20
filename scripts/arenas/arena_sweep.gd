class_name ArenaSweep
extends Node3D
## Swings this node back and forth around a local axis (searchlights).
## Presentation only; render-frame time.

@export var axis: Vector3 = Vector3(0, 0, 1)
@export var angle: float = 25.0     # degrees either side
@export var period: float = 9.0
@export var phase: float = 0.0

var _base: Basis
var _t: float = 0.0


func _ready() -> void:
	_base = transform.basis


func _process(delta: float) -> void:
	_t += delta
	var a: float = deg_to_rad(angle) * sin(TAU * _t / maxf(0.5, period) + phase)
	transform.basis = _base * Basis(axis.normalized(), a)
