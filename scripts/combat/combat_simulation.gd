class_name CombatSimulation
extends RefCounted
## Deterministic 1v1 combat simulation on the fighting plane (X axis).
##
## Owns no nodes; scenes read [member fighters] after each [method step] and
## render them. Given the same setup and the same input sequence it always
## produces the same states and the same combat log, regardless of render
## frame rate.
##
## Scope so far: walking, facing, pushboxes, walls, max separation (M1);
## attacks, hitboxes, block, damage, stun, pushback, hitstop, KO (M2).

var arena: ArenaConfig
var definitions: Array[FighterDefinition] = []
var fighters: Array[FighterState] = []
var combat_log := CombatLog.new()
var tick: int = 0
## Remaining global hitstop ticks. While > 0 every fighter is frozen.
var hitstop_remaining: int = 0

## Button → move pattern, in priority order when pressed on the same tick.
const _ATTACK_BUTTONS: Array[Array] = [
	[FighterInputFrame.BUTTON_HEAVY, &"HEAVY"],
	[FighterInputFrame.BUTTON_KICK, &"KICK"],
	[FighterInputFrame.BUTTON_LIGHT, &"LIGHT"],
]


func setup(arena_config: ArenaConfig, p1: FighterDefinition, p2: FighterDefinition) -> void:
	assert(arena_config != null and p1 != null and p2 != null)
	arena = arena_config
	definitions = [p1, p2]
	reset()


## Convenience accessor kept from M1 (movement tuning per fighter).
func profile(i: int) -> FighterMovementProfile:
	return definitions[i].movement


## Spawn positions, full health, neutral state, empty hitstop. Logs RESET.
func reset() -> void:
	fighters.clear()
	var spawns: Array[float] = [arena.p1_spawn_x, arena.p2_spawn_x]
	for i: int in 2:
		var s := FighterState.new()
		s.position_x = spawns[i]
		s.health = definitions[i].base_health
		fighters.append(s)
	_update_facing(true)
	hitstop_remaining = 0
	var ev := CombatEvent.new()
	ev.tick = tick
	ev.type = CombatEvent.Type.RESET
	combat_log.add(ev)


## Advances the simulation by exactly one fixed tick.
## [param inputs] must contain one FighterInputFrame per fighter (P1, P2).
##
## Phase order (always P1 before P2 inside each phase):
##   0. Hitstop     — if active: count down, latch new presses, freeze
##                    everything else.
##   1. State/input — advance attack/stun timers, detect button presses,
##                    start attacks, block, or set walking intent.
##   2. Integrate   — walking (forward/back speed) and pushback slide.
##   3. Max separation, pushbox resolve, wall clamp (wall-blocked pushback
##                    is transferred to the attacker).
##   4. Facing      — only fighters in neutral states turn around.
##   5. Hits        — detect contacts on post-movement boxes, then resolve
##                    them all against the pre-resolution state.
func step(inputs: Array[FighterInputFrame]) -> void:
	assert(inputs.size() == 2, "step() needs one input frame per fighter")
	tick += 1

	# 0. Hitstop freezes both fighters. Presses made during the freeze are
	# latched and applied on the first tick after it, so they are not lost.
	if hitstop_remaining > 0:
		hitstop_remaining -= 1
		for i: int in 2:
			var f: FighterState = fighters[i]
			var held: int = inputs[i].buttons if inputs[i] != null else 0
			f.pending_presses |= held & ~f.held_buttons
			f.held_buttons = held
			f.last_displacement = 0.0
		return

	var before: Array[float] = [fighters[0].position_x, fighters[1].position_x]

	# 1. State machine + input.
	for i: int in 2:
		var input: FighterInputFrame = inputs[i] if inputs[i] != null else FighterInputFrame.neutral()
		_update_state(i, input)

	# 2. Integrate walking and pushback.
	var pushback_applied: Array[float] = [0.0, 0.0]
	for i: int in 2:
		var f: FighterState = fighters[i]
		if f.action == FighterState.Action.WALK and f.move_x != 0:
			var speed: float = profile(i).walk_forward_speed if f.is_moving_forward() \
					else profile(i).walk_backward_speed
			f.position_x += f.move_x * speed * CombatConstants.TICK_DELTA
		if f.pushback_remaining != 0.0:
			var d: float = signf(f.pushback_remaining) * minf(absf(f.pushback_remaining), f.pushback_step)
			f.pushback_remaining -= d
			if absf(f.pushback_remaining) < 1e-9:
				f.pushback_remaining = 0.0
			f.position_x += d
			pushback_applied[i] = d

	# 3. Spacing constraints.
	_transfer_wall_pushback(pushback_applied)
	_enforce_max_separation(before)
	_resolve_pushboxes()
	_clamp_to_walls()
	_resolve_pushboxes()
	_clamp_to_walls()

	# 4. Facing.
	_update_facing(false)

	for i: int in 2:
		fighters[i].last_displacement = fighters[i].position_x - before[i]

	# 5. Hit detection and resolution.
	var contacts: Array[HitboxSystem.Contact] = HitboxSystem.find_contacts(definitions, fighters)
	hitstop_remaining = HitResolver.resolve(contacts, fighters, tick, combat_log)


func separation() -> float:
	return absf(fighters[1].position_x - fighters[0].position_x)


## Returns deep copies of the current fighter states (for interpolation).
func snapshot() -> Array[FighterState]:
	var out: Array[FighterState] = []
	for f: FighterState in fighters:
		out.append(f.copy())
	return out


## Exact text of the whole simulation state — for determinism tests.
func describe() -> String:
	return "tick=%d stop=%d | P1 %s | P2 %s" % [
		tick, hitstop_remaining, fighters[0].describe(), fighters[1].describe()]


# --- phase 1: state machine ---------------------------------------------------

func _update_state(i: int, input: FighterInputFrame) -> void:
	var f: FighterState = fighters[i]
	var pressed: int = (input.buttons & ~f.held_buttons) | f.pending_presses
	f.held_buttons = input.buttons
	f.pending_presses = 0

	match f.action:
		FighterState.Action.KO:
			f.move_x = 0
			return
		FighterState.Action.ATTACK:
			f.move_frame += 1
			if f.move_frame > f.move.total_frames():
				_end_attack(i)
		FighterState.Action.HITSTUN, FighterState.Action.BLOCKSTUN:
			# Actionable on the tick after stun reaches 0 (N ticks of no control).
			if f.stun_remaining <= 0:
				_to_idle(f)
			else:
				f.stun_remaining -= 1

	if not f.is_neutral():
		f.move_x = 0
		return

	for entry: Array in _ATTACK_BUTTONS:
		if pressed & int(entry[0]):
			var move: MoveData = definitions[i].move_for(entry[1])
			if move != null:
				_start_attack(i, move)
				return

	if input.is_held(FighterInputFrame.BUTTON_BLOCK):
		f.action = FighterState.Action.BLOCK
		f.move_x = 0
		return

	f.move_x = clampi(input.move_x, -1, 1)
	f.action = FighterState.Action.WALK if f.move_x != 0 else FighterState.Action.IDLE


func _start_attack(i: int, move: MoveData) -> void:
	var f: FighterState = fighters[i]
	f.action = FighterState.Action.ATTACK
	f.move = move
	f.move_frame = 1
	f.move_connected = false
	f.move_x = 0
	var ev := CombatEvent.new()
	ev.tick = tick
	ev.type = CombatEvent.Type.ATTACK_START
	ev.actor = i
	ev.move_id = move.id
	combat_log.add(ev)


func _end_attack(i: int) -> void:
	var f: FighterState = fighters[i]
	if not f.move_connected:
		var ev := CombatEvent.new()
		ev.tick = tick
		ev.type = CombatEvent.Type.WHIFF
		ev.actor = i
		ev.move_id = f.move.id
		combat_log.add(ev)
	_to_idle(f)


func _to_idle(f: FighterState) -> void:
	f.action = FighterState.Action.IDLE
	f.move = null
	f.move_frame = 0
	f.move_connected = false
	f.stun_remaining = 0


# --- phase 3: spacing ---------------------------------------------------------

## If a defender's pushback is stopped by a wall, the attacker slides back
## by the blocked amount instead (corner pushback).
func _transfer_wall_pushback(applied: Array[float]) -> void:
	for i: int in 2:
		if applied[i] == 0.0:
			continue
		var f: FighterState = fighters[i]
		var clamped: float = _clamped_x(i, f.position_x)
		var blocked: float = f.position_x - clamped
		if blocked == 0.0:
			continue
		f.position_x = clamped
		# The attacker takes the blocked slide now and the rest of the
		# defender's pushback over the following ticks.
		var other: FighterState = fighters[1 - i]
		other.position_x -= blocked
		other.pushback_remaining -= f.pushback_remaining
		other.pushback_step = f.pushback_step
		f.pushback_remaining = 0.0


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
	var min_dist: float = profile(0).pushbox_half_width + profile(1).pushbox_half_width
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
	var hw: float = profile(i).pushbox_half_width
	return clampf(x, arena.left_bound + hw, arena.right_bound - hw)


## Fighters face each other. Only fighters in neutral states turn (an attack
## or stun keeps its facing); [param force] turns everyone (spawn/reset).
## If centres coincide, facing is unchanged.
func _update_facing(force: bool) -> void:
	var dx: float = fighters[1].position_x - fighters[0].position_x
	if dx == 0.0:
		return
	var dir: int = 1 if dx > 0.0 else -1
	if force or fighters[0].is_neutral():
		fighters[0].facing = dir
	if force or fighters[1].is_neutral():
		fighters[1].facing = -dir
