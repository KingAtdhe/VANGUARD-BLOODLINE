class_name ArenaBlink
extends Node3D
## Blinks this node on and off (aircraft warning lights on far towers).

@export var period: float = 1.6
@export var on_time: float = 0.25
@export var phase: float = 0.0

var _t: float = 0.0


func _process(delta: float) -> void:
	_t += delta
	visible = fposmod(_t + phase, period) < on_time
