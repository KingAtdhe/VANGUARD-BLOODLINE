extends Node3D
## Greybox arena view. Positions the visible wall markers from the
## ArenaConfig so the visuals can never disagree with the gameplay bounds.

@export var config: ArenaConfig

@onready var _left_wall: Node3D = %LeftWall
@onready var _right_wall: Node3D = %RightWall


func _ready() -> void:
	if config == null:
		push_error("GreyboxArena: no ArenaConfig assigned")
		return
	_left_wall.position.x = config.left_bound
	_right_wall.position.x = config.right_bound
