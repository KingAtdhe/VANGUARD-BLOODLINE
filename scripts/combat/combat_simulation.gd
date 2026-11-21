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
## attacks, hitboxes, block, damage, stun, pushback, hitstop, KO (M2);
## input buffer, cancel routes, combo counter and damage scaling (M4);
## specials, moving attacks, Origin meter/Surge, ultimate, knockdown (M6).

var arena: ArenaConfig
var definitions: Array[FighterDefinition] = []
var fighters: Array[FighterState] = []
var combat_log := CombatLog.new()
var tick: int = 0
## Remaining global hitstop ticks. While > 0 every fighter is frozen.
var hitstop_remaining: int = 0
var tuning: CombatTuning
## False in training: health never drops below 1.
var ko_enabled: bool = true

## Attack buttons in REVERSE priority. Presses on the same tick are buffered
## in this order, and the buffer is read newest-first, so simultaneous
## presses resolve Heavy > Kick > Light.
const _BUFFER_ORDER: Array[int] = [
	FighterInputFrame.BUTTON_LIGHT,
	FighterInputFrame.BUTTON_KICK,
	FighterInputFrame.BUTTON_HEAVY,
	FighterInputFrame.BUTTON_SPECIAL,
	FighterInputFrame.BUTTON_ULTIMATE,
]
const _PATTERNS: Dictionary = {
	FighterInputFrame.BUTTON_LIGHT: &"LIGHT",
	FighterInputFrame.BUTTON_KICK: &"KICK",
	FighterInputFrame.BUTTON_HEAVY: &"HEAVY",
	FighterInputFrame.BUTTON_SPECIAL: &"SPECIAL",
	FighterInputFrame.CMD_FORWARD_SPECIAL: &"FORWARD_SPECIAL",
	FighterInputFrame.BUTTON_ULTIMATE: &"ULTIMATE",
	FighterInputFrame.CMD_BACK_SPECIAL: &"BACK_SPECIAL",
	FighterInputFrame.CMD_DOWN_SPECIAL: &"DOWN_SPECIAL",
	FighterInputFrame.CMD_DOWN_LIGHT: &"DOWN_LIGHT",
	FighterInputFrame.CMD_DOWN_HEAVY: &"DOWN_HEAVY",
	FighterInputFrame.CMD_DOWN_KICK: &"DOWN_KICK",
}
## Direction + button commands a fighter has no move for act as the plain
## button, so holding a direction never eats an attack.
const _FALLBACK: Dictionary = {
	FighterInputFrame.CMD_BACK_SPECIAL: FighterInputFrame.BUTTON_SPECIAL,
	FighterInputFrame.CMD_DOWN_SPECIAL: FighterInputFrame.BUTTON_SPECIAL,
	FighterInputFrame.CMD_DOWN_LIGHT: FighterInputFrame.BUTTON_LIGHT,
	FighterInputFrame.CMD_DOWN_HEAVY: FighterInputFrame.BUTTON_HEAVY,
	FighterInputFrame.CMD_DOWN_KICK: FighterInputFrame.BUTTON_KICK,
}
const _DOWN_COMMANDS: Dictionary = {
	FighterInputFrame.BUTTON_SPECIAL: FighterInputFrame.CMD_DOWN_SPECIAL,
	FighterInputFrame.BUTTON_LIGHT: FighterInputFrame.CMD_DOWN_LIGHT,
	FighterInputFrame.BUTTON_HEAVY: FighterInputFrame.CMD_DOWN_HEAVY,
	FighterInputFrame.BUTTON_KICK: FighterInputFrame.CMD_DOWN_KICK,
}


func setup(arena_config: ArenaConfig, p1: FighterDefinition, p2: FighterDefinition,
		combat_tuning: CombatTuning = null) -> void:
	assert(arena_config != null and p1 != null and p2 != null)
	arena = arena_config
	definitions = [p1, p2]
	tuning = combat_tuning if combat_tuning != null else CombatTuning.new()
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
##   0. Hitstop     — if active: count down, buffer new presses (buffer ages
##                    do not advance), freeze everything else.
##   1. State/input — buffer new presses; advance attack/stun timers; a
##                    fighter in an attack may cancel into a buffered move
##                    if the route is legal; a neutral fighter starts the
##                    newest buffered attack, blocks, or walks; age buffer.
##   2. Integrate   — walking (forward/back speed) and pushback slide.
##   3. Max separation, pushbox resolve, wall clamp (wall-blocked pushback
##                    is transferred to the attacker).
##   4. Facing      — only fighters in neutral states turn around.
##   5. Hits        — detect contacts on post-movement boxes, then resolve
##                    them all against the pre-resolution state.
func step(inputs: Array[FighterInputFrame]) -> void:
	assert(inputs.size() == 2, "step() needs one input frame per fighter")
	tick += 1

	# 0. Hitstop freezes both fighters. New presses are buffered; the buffer
	# does not age, so a press during hitstop is still fresh afterwards
	# (this is what makes "press Light during the hit" cancels work).
	if hitstop_remaining > 0:
		hitstop_remaining -= 1
		for i: int in 2:
			var f: FighterState = fighters[i]
			_register_presses(f, inputs[i])
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
		if f.action == FighterState.Action.ATTACK and f.move != null and f.move.moves_on_frame(f.move_frame):
			f.position_x += f.facing * f.move.move_step()
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
	hitstop_remaining = HitResolver.resolve(contacts, self)


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
	_register_presses(f, input)
	if OriginMeter.tick_surge(f, definitions[i], tuning):
		_log_simple(CombatEvent.Type.SURGE_END, i)

	match f.action:
		FighterState.Action.KO:
			f.move_x = 0
			f.buffer.clear()
			return
		FighterState.Action.ATTACK:
			f.move_frame += 1
			if f.move_frame > f.move.total_frames():
				_end_attack(i)
		FighterState.Action.KNOCKDOWN:
			# On the ground (no hurtbox), then get up.
			if f.stun_remaining <= 0:
				f.action = FighterState.Action.WAKEUP
				f.stun_remaining = tuning.wakeup_ticks
			else:
				f.stun_remaining -= 1
		FighterState.Action.LAUNCHED:
			# In the air; lands knocked down, which ends the combo.
			if f.stun_remaining <= 0:
				f.action = FighterState.Action.KNOCKDOWN
				f.stun_remaining = tuning.knockdown_ticks
				f.combo_hits = 0
				f.combo_damage = 0
				f.juggle_hits = 0
				f.juggle_exhausted = false
				f.launch_total = 0
			else:
				f.stun_remaining -= 1
		FighterState.Action.WAKEUP, FighterState.Action.HITSTUN, FighterState.Action.BLOCKSTUN:
			# Guard height can be switched during blockstun (read live), so a
			# high/low string has to be blocked hit by hit.
			if f.action == FighterState.Action.BLOCKSTUN and input != null:
				f.block_low = input.move_y < 0
			# Actionable on the tick after stun reaches 0 (N ticks of no control).
			if f.stun_remaining <= 0:
				_recover(f)
			else:
				f.stun_remaining -= 1

	if f.action == FighterState.Action.ATTACK:
		# Still attacking: only a legal cancel may consume a buffered press.
		f.move_x = 0
		var cancel_move: MoveData = _take_buffered(i, _can_cancel_into.bind(i))
		if cancel_move != null:
			_start_attack(i, cancel_move, true)
		_age_buffer(f)
		return

	if not f.is_neutral():
		f.move_x = 0
		_age_buffer(f)
		return

	var move: MoveData = _take_buffered(i, func(_m: MoveData) -> bool: return true)
	if move != null:
		_start_attack(i, move, false)
		_age_buffer(f)
		return

	if input.is_held(FighterInputFrame.BUTTON_BLOCK):
		f.action = FighterState.Action.BLOCK
		f.block_low = input.move_y < 0
		f.move_x = 0
	else:
		f.move_x = clampi(input.move_x, -1, 1)
		f.action = FighterState.Action.WALK if f.move_x != 0 else FighterState.Action.IDLE
	_age_buffer(f)


## Adds attack buttons pressed this tick (held now, not held last tick).
## SPECIAL pressed while holding toward the opponent is buffered as the
## FORWARD_SPECIAL command (direction is judged at the moment of the press).
func _register_presses(f: FighterState, input: FighterInputFrame) -> void:
	var held: int = input.buttons if input != null else 0
	var move_x: int = input.move_x if input != null else 0
	var move_y: int = input.move_y if input != null else 0
	var pressed: int = held & ~f.held_buttons
	f.held_buttons = held
	for button: int in _BUFFER_ORDER:
		if pressed & button:
			var code: int = button
			if move_y < 0 and _DOWN_COMMANDS.has(button):
				code = _DOWN_COMMANDS[button]
			elif button == FighterInputFrame.BUTTON_SPECIAL and move_x != 0:
				code = FighterInputFrame.CMD_FORWARD_SPECIAL if move_x == f.facing \
						else FighterInputFrame.CMD_BACK_SPECIAL
			f.buffer.append(Vector2i(code, 0))


## Advances buffer ages by one tick and drops expired presses.
func _age_buffer(f: FighterState) -> void:
	for k: int in range(f.buffer.size() - 1, -1, -1):
		var e: Vector2i = f.buffer[k]
		e.y += 1
		if e.y > tuning.input_buffer_ticks:
			f.buffer.remove_at(k)
		else:
			f.buffer[k] = e


## Newest buffered press whose move [param accept] allows; consumes it.
## Rejected presses stay buffered (they may become legal before expiring).
func _take_buffered(i: int, accept: Callable) -> MoveData:
	var f: FighterState = fighters[i]
	for k: int in range(f.buffer.size() - 1, -1, -1):
		var code: int = f.buffer[k].x
		if _FALLBACK.has(code) and definitions[i].moves_for(_PATTERNS[code]).is_empty():
			code = _FALLBACK[code]
		for move: MoveData in definitions[i].moves_for(_PATTERNS.get(code, &"")):
			# Meter/Surge conditions first: an unaffordable move stays buffered.
			if OriginMeter.can_use(f, definitions[i], move, tuning) and accept.call(move):
				f.buffer.remove_at(k)
				return move
	return null


## Cancel legality (spec §4.5, docs/COMBAT_FRAME_DATA.md):
##   - the current attack has connected (hit or block),
##   - we are between its first active frame and cancel_grace_frames after
##     its last active frame,
##   - the target's tags are in the current move's cancel_tags,
##   - the target has not been used max_same_move_in_chain times already.
func _can_cancel_into(target: MoveData, i: int) -> bool:
	var f: FighterState = fighters[i]
	var m: MoveData = f.move
	if m == null or not f.move_connected:
		return false
	var last_active: int = m.startup_frames + m.active_frames - 1
	if f.move_frame < m.startup_frames or f.move_frame > last_active + tuning.cancel_grace_frames:
		return false
	if not m.can_cancel_into(target):
		return false
	return f.chain.count(target.id) < tuning.max_same_move_in_chain


func _start_attack(i: int, move: MoveData, is_cancel: bool) -> void:
	var f: FighterState = fighters[i]
	var from_id: StringName = f.move.id if (is_cancel and f.move != null) else &""
	f.action = FighterState.Action.ATTACK
	f.move = move
	f.move_frame = 1
	f.move_connected = false
	f.armor_left = move.armor_hits
	f.move_x = 0
	if is_cancel:
		f.chain.append(move.id)
	else:
		f.chain = [move.id]
	var ev := CombatEvent.new()
	ev.tick = tick
	ev.type = CombatEvent.Type.ATTACK_START
	ev.actor = i
	ev.move_id = move.id
	ev.cancel_from = from_id
	combat_log.add(ev)
	# Pay after logging the start, so an ultimate reads "starts … / surge ends".
	if OriginMeter.pay(f, definitions[i], move):
		_log_simple(CombatEvent.Type.SURGE_END, i)


## Starts a move that is not triggered by input (a counter's follow-up).
func start_followup(i: int, move: MoveData) -> void:
	_start_attack(i, move, false)


func _end_attack(i: int) -> void:
	var f: FighterState = fighters[i]
	if f.move.activates_surge:
		OriginMeter.start_surge(f, definitions[i], tuning)
		_log_simple(CombatEvent.Type.SURGE_START, i)
		_to_idle(f)
		return
	if not f.move_connected:
		var ev := CombatEvent.new()
		ev.tick = tick
		ev.type = CombatEvent.Type.WHIFF
		ev.actor = i
		ev.move_id = f.move.id
		combat_log.add(ev)
	_to_idle(f)


func _log_simple(type: CombatEvent.Type, actor: int) -> void:
	var ev := CombatEvent.new()
	ev.tick = tick
	ev.type = type
	ev.actor = actor
	combat_log.add(ev)


## Back to neutral from hitstun/blockstun/wake-up: any combo on this fighter ends.
func _recover(f: FighterState) -> void:
	_to_idle(f)
	f.combo_hits = 0
	f.combo_damage = 0


func _to_idle(f: FighterState) -> void:
	f.action = FighterState.Action.IDLE
	f.move = null
	f.move_frame = 0
	f.move_connected = false
	f.stun_remaining = 0
	f.chain.clear()


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
