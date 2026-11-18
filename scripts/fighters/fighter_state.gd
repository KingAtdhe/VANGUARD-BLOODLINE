class_name FighterState
extends RefCounted
## Authoritative per-fighter simulation state for one combat tick.
## Plain data only — no nodes — so it can be copied, compared and tested.

## Position of the fighter's centre on the fighting plane (metres).
var position_x: float = 0.0
## +1 = facing right (toward +X), -1 = facing left.
var facing: int = 1
## World-space movement direction requested this tick (-1, 0, +1).
var move_x: int = 0
## Distance moved during the last tick (metres, signed).
var last_displacement: float = 0.0


func copy() -> FighterState:
	var s := FighterState.new()
	s.position_x = position_x
	s.facing = facing
	s.move_x = move_x
	s.last_displacement = last_displacement
	return s


## True when the fighter is walking toward the side it faces.
func is_moving_forward() -> bool:
	return move_x != 0 and move_x == facing
