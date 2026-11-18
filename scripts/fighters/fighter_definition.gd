class_name FighterDefinition
extends Resource
## Data-driven fighter definition (spec §9.5). Grows per milestone:
## animation mapping, specials, Origin Surge, audio and cosmetics come later.

@export var fighter_id: StringName = &""
@export var display_name: String = ""
@export var base_health: int = 1000
@export var movement: FighterMovementProfile
## Standing hurtbox: half-width around the centre and height from the floor.
@export var hurtbox_half_width: float = 0.3
@export var hurtbox_height: float = 1.8
## Move list. Each move is selected by its input_pattern.
@export var moves: Array[MoveData] = []


func move_for(pattern: StringName) -> MoveData:
	for m: MoveData in moves:
		if m != null and m.input_pattern == pattern:
			return m
	return null


func validate() -> Array[String]:
	var p: Array[String] = []
	if fighter_id == &"":
		p.append("fighter_id is empty")
	if base_health <= 0:
		p.append("%s: base_health must be positive" % fighter_id)
	if movement == null:
		p.append("%s: movement profile missing" % fighter_id)
	else:
		p.append_array(movement.validate())
	if hurtbox_half_width <= 0.0 or hurtbox_height <= 0.0:
		p.append("%s: invalid hurtbox" % fighter_id)
	var patterns: Dictionary = {}
	for m: MoveData in moves:
		if m == null:
			p.append("%s: null move entry" % fighter_id)
			continue
		p.append_array(m.validate())
		if patterns.has(m.input_pattern):
			p.append("%s: duplicate input_pattern %s" % [fighter_id, m.input_pattern])
		patterns[m.input_pattern] = true
	return p
