class_name ArenaSpin
extends Node3D
## Rotates this node at a constant rate (presentation only, e.g. the Origin
## heart's rings). Uses render-frame delta: it never affects gameplay timing.

@export var axis: Vector3 = Vector3.UP
## Degrees per second.
@export var speed: float = 15.0


func _process(delta: float) -> void:
	if axis.length_squared() > 0.0:
		rotate_object_local(axis.normalized(), deg_to_rad(speed) * delta)
