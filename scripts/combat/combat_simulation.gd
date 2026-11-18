class_name CombatSimulation
extends RefCounted
## Deterministic 1v1 combat simulation on the fighting plane (X axis).
##
## Owns no nodes; scenes read [member fighters] after each [method step] and
## render them. Given the same setup and the same input sequence it always
## produces the same states, regardless of render frame rate.
##
## Milestone 1 scope: walking, facing, pushboxes, walls, max separation.
## Attacks, hit resolution and match rules are added in later milestones as
## extra phases in [method step] — keep the phase order documented.

var arena: ArenaConfig
var profiles: Array[FighterMovementProfile] = []
var fighters: Array[FighterState] = []
var tick: int = 0


func setup(arena_config: ArenaConfig, p1_profile: FighterMovementProfile,
		p2_profile: FighterMovementProfile) -> void:
	assert(arena_config != null and p1_profile != null and p2_profile != null)
	arena = arena_config
	profiles = [p1_profile, p2_profile]
	reset_positions()


## Places both fighters on their spawn points facing each other.
func reset_positions() -> void:
	fighters.clear()
	var spawns: Array[float] = [arena.p1_spawn_x, arena.p2_spawn_x]
	for i: int in 2:
		var s := FighterState.new()
		s.position_x = spawns[i]
		fighters.append(s)
	_update_facing()
	tick = 0


## Advances the simulation by exactly one fixed tick.
## [param inputs] must contain one FighterInputFrame per fighter (P1, P2).
##
## Phase order (always P1 before P2 inside each phase):
##   1. Read intent      — store move_x per fighter.
##   2. Integrate        — move by forward/backward speed relative to facing.
##   3. Max separation   — undo movement that would push fighters too far apart.
##   4. Pushbox resolve  — separate overlapping bodies (walls win).
##   5. Wall clamp       — keep pushboxes inside the arena.
##   6. Facing           — face the opponent based on final positions.
func step(inputs: Array[FighterInputFrame]) -> void:
	assert(inputs.size() == 2, "step() needs one input frame per fighter")
	var before: Array[float] = [fighters[0].position_x, fighters[1].position_x]

	# 1 + 2. Intent and integration. Facing is from the previous tick, so a
	# fighter walking toward the opponent always uses the forward speed.
	for i: int in 2:
		var f: FighterState = fighters[i]
		var input: FighterInputFrame = inputs[i] if inputs[i] != null else FighterInputFrame.neutral()
		f.move_x = clampi(input.move_x, -1, 1)
		if f.move_x == 0:
			continue
		var speed: float = profiles[i].walk_forward_speed if f.is_moving_forward() \
				else profiles[i].walk_backward_speed
		f.position_x += f.move_x * speed * CombatConstants.TICK_DELTA

	_enforce_max_separation(before)
	_resolve_pushboxes()
	_clamp_to_walls()
	# Walls can re-create overlap only if the arena is narrower than both
	# bodies, which ArenaConfig validation prevents; resolve once more anyway.
	_resolve_pushboxes()
	_clamp_to_walls()
	_update_facing()

	for i: int in 2:
		fighters[i].last_displacement = fighters[i].position_x - before[i]
	tick += 1


func separation() -> float:
	return absf(fighters[1].position_x - fighters[0].position_x)


## Returns deep copies of the current fighter states (for interpolation).
func snapshot() -> Array[FighterState]:
	var out: Array[FighterState] = []
	for f: FighterState in fighters:
		out.append(f.copy())
	return out


# --- phases -----------------------------------------------------------------

func _enforce_max_separation(before: Array[float]) -> void:
	var excess: float = separation() - arena.max_separation
	if excess <= 0.0:
		return
	# Only fighters that moved away from the opponent are pulled back.
	var away: Array[bool] = [false, false]
	for i: int in 2:
		var other_x: float = fighters[1 - i].position_x
		var moved: float = fighters[i].position_x - before[i]
		var away_dir: float = signf(fighters[i].position_x - other_x)
		away[i] = moved != 0.0 and signf(moved) == away_dir
	var movers: int = int(away[0]) + int(away[1])
	if movers == 0:
		return
	for i: int in 2:
		if not away[i]:
			continue
		var toward_other: float = signf(fighters[1 - i].position_x - fighters[i].position_x)
		fighters[i].position_x += toward_other * excess / movers


func _resolve_pushboxes() -> void:
	var a: FighterState = fighters[0]
	var b: FighterState = fighters[1]
	var min_dist: float = profiles[0].pushbox_half_width + profiles[1].pushbox_half_width
	var dx: float = b.position_x - a.position_x
	var overlap: float = min_dist - absf(dx)
	if overlap <= 0.0:
		return
	# Exactly on top of each other: keep the previous left/right order.
	var dir: float = signf(dx) if dx != 0.0 else float(a.facing)
	a.position_x -= dir * overlap * 0.5
	b.position_x += dir * overlap * 0.5
	# If a wall blocks one fighter, the other absorbs the remaining push.
	var a_clamped: float = _clamped_x(0, a.position_x)
	var b_clamped: float = _clamped_x(1, b.position_x)
	if a_clamped != a.position_x:
		b.position_x += a_clamped - a.position_x
		a.position_x = a_clamped
	elif b_clamped != b.position_x:
		a.position_x += b_clamped - b.position_x
		b.position_x = b_clamped


func _clamp_to_walls() -> void:
	for i: int in 2:
		fighters[i].position_x = _clamped_x(i, fighters[i].position_x)


func _clamped_x(i: int, x: float) -> float:
	var hw: float = profiles[i].pushbox_half_width
	return clampf(x, arena.left_bound + hw, arena.right_bound - hw)


## Fighters always face each other. If centres coincide, keep current facing.
func _update_facing() -> void:
	var dx: float = fighters[1].position_x - fighters[0].position_x
	if dx == 0.0:
		return
	var dir: int = 1 if dx > 0.0 else -1
	fighters[0].facing = dir
	fighters[1].facing = -dir
