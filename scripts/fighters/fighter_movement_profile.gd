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

@export_group("Dash")
## Double-tap a direction to dash (D-071). Distance in metres, length in
## 60 Hz ticks; most of the distance is covered early. A forward dash can
## be cut short by an attack (CombatTuning.dash_cancel_frame); a back dash
## is committed for its whole length. Neither can block.
@export var dash_forward_distance: float = 1.3
@export var dash_forward_ticks: int = 14
@export var dash_back_distance: float = 1.1
@export var dash_back_ticks: int = 18


func dash_distance(forward: bool) -> float:
	return dash_forward_distance if forward else dash_back_distance


func dash_ticks(forward: bool) -> int:
	return dash_forward_ticks if forward else dash_back_ticks


## Distance covered on tick [param frame] (1-based) of a dash: an ease-out,
## the weights (2(n - k) + 1) / n² sum to exactly 1 over the n ticks.
func dash_step(forward: bool, frame: int) -> float:
	var n: int = dash_ticks(forward)
	if frame < 1 or frame > n:
		return 0.0
	return dash_distance(forward) * float(2 * (n - frame) + 1) / float(n * n)


func validate() -> Array[String]:
	var problems: Array[String] = []
	if walk_forward_speed <= 0.0 or walk_backward_speed <= 0.0:
		problems.append("walk speeds must be positive")
	if dash_forward_distance <= 0.0 or dash_back_distance <= 0.0 or dash_forward_ticks < 2 or dash_back_ticks < 2:
		problems.append("invalid dash values")
	if pushbox_half_width <= 0.0:
		problems.append("pushbox_half_width must be positive")
	return problems
