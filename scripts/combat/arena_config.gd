class_name ArenaConfig
extends Resource
## Gameplay-relevant arena data (bounds, spawns). Visual geometry lives in the
## arena scene; this resource is the single source of truth for the rules.
## All distances in metres along the fighting plane's X axis.

@export var arena_id: StringName = &""
@export var display_name: String = ""
## Wall positions. A fighter's pushbox never crosses these.
@export var left_bound: float = -6.0
@export var right_bound: float = 6.0
## Maximum distance between fighter centres, so the camera can always frame
## both fighters within its zoom range.
@export var max_separation: float = 6.0
@export var p1_spawn_x: float = -1.5
@export var p2_spawn_x: float = 1.5


func width() -> float:
	return right_bound - left_bound


## Returns an empty array when valid, otherwise human-readable problems.
func validate() -> Array[String]:
	var problems: Array[String] = []
	if right_bound <= left_bound:
		problems.append("right_bound must be greater than left_bound")
	if max_separation <= 0.0:
		problems.append("max_separation must be positive")
	if p1_spawn_x >= p2_spawn_x:
		problems.append("P1 must spawn left of P2")
	if p1_spawn_x <= left_bound or p2_spawn_x >= right_bound:
		problems.append("spawn points must be inside the bounds")
	if p2_spawn_x - p1_spawn_x > max_separation:
		problems.append("spawn distance exceeds max_separation")
	return problems
