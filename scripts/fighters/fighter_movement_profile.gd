class_name FighterMovementProfile
extends Resource
## Per-fighter movement tuning. Balance data — lives in data/fighters/, never
## hardcoded in controllers. Speeds are metres per second; the simulation
## converts them to per-tick distances.

@export var fighter_id: StringName = &""
@export var display_name: String = ""
## Speed when walking toward the opponent.
@export var walk_forward_speed: float = 2.6
## Speed when walking away from the opponent (usually slower).
@export var walk_backward_speed: float = 2.0
## Half-width of the body pushbox. Fighters cannot overlap pushboxes and
## the pushbox edge stops at arena walls.
@export var pushbox_half_width: float = 0.35


func validate() -> Array[String]:
	var problems: Array[String] = []
	if walk_forward_speed <= 0.0 or walk_backward_speed <= 0.0:
		problems.append("walk speeds must be positive")
	if pushbox_half_width <= 0.0:
		problems.append("pushbox_half_width must be positive")
	return problems
