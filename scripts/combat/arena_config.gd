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

@export_group("Presentation")
## Arena scene (root = ArenaView). Stored as a path so the scene can hold a
## reference back to this config without a load cycle.
@export_file("*.tscn") var scene_path: String = ""
## Height (m) of the arena model's floor under the fighting line, above the
## arena scene's origin. Presentation only: in a match the arena is lowered by
## this much, so fighters (who always stand on y = 0) stand ON a raised stage
## instead of inside it. tests/integration/test_arena_floor.gd checks it
## against the real mesh.
@export var stage_height: float = 0.0
## One line for the arena select screen.
@export var tagline: String = ""
## Unlocked from the start (false = earned through Story/Arcade).
@export var unlocked_by_default: bool = true
## How a locked arena is earned, shown on the arena select screen.
@export var unlock_hint: String = ""

@export_group("Fighter lighting")
## Each fighter carries a key light (from the camera side) and a rim light
## (from behind) that light only the fighters (render layer 2), so painted
## models read clearly against any arena. Tuned per arena to its mood.
@export var fighter_key_color: Color = Color(1.0, 0.95, 0.9)
@export var fighter_key_energy: float = 1.2
@export var fighter_rim_color: Color = Color(1.0, 0.55, 0.35)
@export var fighter_rim_energy: float = 1.6


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
