class_name ProjectileState
extends RefCounted
## One projectile on the fighting plane (D-066). Plain simulation data, like
## FighterState: owned by CombatSimulation, drawn by the scene.
##
## A projectile is fired by a move with MoveData.projectile_speed > 0 on that
## move's first active frame. It carries the move's damage, stun and guard
## rule, travels at constant speed and ends when it connects, clashes with an
## opposing projectile, has travelled the move's projectile_range or reaches
## an arena wall. It keeps flying if its owner is hit after firing.

## Unique within one simulation (spawn order) — lets views track it.
var id: int = 0
## Fighter index (0 = P1, 1 = P2) that fired it.
var owner: int = 0
var move: MoveData = null
## Centre of the box on the fighting plane (metres) now and one tick ago.
## Hit detection sweeps the box from previous_x to position_x, so a fast
## projectile cannot tunnel through a hurtbox.
var position_x: float = 0.0
var previous_x: float = 0.0
## +1 = travelling toward +X, -1 = toward -X.
var direction: int = 1
var travelled: float = 0.0
## Connected or clashed this tick: removed at the end of the tick.
var spent: bool = false


func copy() -> ProjectileState:
	var p := ProjectileState.new()
	p.id = id
	p.owner = owner
	p.move = move
	p.position_x = position_x
	p.previous_x = previous_x
	p.direction = direction
	p.travelled = travelled
	p.spent = spent
	return p


## Area swept during the last tick (equals the box itself when it has not
## moved, e.g. on the tick it is fired).
func swept_box() -> Rect2:
	var half: Vector2 = move.hitbox_size * 0.5
	var x0: float = minf(previous_x, position_x) - half.x
	var x1: float = maxf(previous_x, position_x) + half.x
	return Rect2(x0, move.hitbox_center.y - half.y, x1 - x0, move.hitbox_size.y)


func describe() -> String:
	return "proj#%d P%d %s x=%s d=%d" % [id, owner + 1, move.id, var_to_str(position_x), direction]
