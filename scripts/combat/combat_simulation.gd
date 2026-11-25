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
## specials, moving attacks, Origin meter/Surge, ultimate, knockdown (M6);
## projectiles (D-066); jumping, crouching and air attacks (D-087).

var arena: ArenaConfig
var definitions: Array[FighterDefinition] = []
var fighters: Array[FighterState] = []
## Live projectiles, oldest first.
var projectiles: Array[ProjectileState] = []
var _next_projectile_id: int = 1
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
	FighterInputFrame.CMD_THROW: &"THROW",
}
## Light and Kick pressed this many ticks apart or less count as together
## (the throw, D-103). A Light or Kick attack already started that recently
## is turned into the throw (fighting games call this throw leniency).
const THROW_WINDOW: int = 1
## How fast a held victim is drawn in to the thrower (m per tick, D-104).
const THROW_PULL_PER_TICK: float = 0.05
## Direction + button commands a fighter has no move for act as the plain
## button, so holding a direction never eats an attack.
const _FALLBACK: Dictionary = {
	FighterInputFrame.CMD_BACK_SPECIAL: FighterInputFrame.BUTTON_SPECIAL,
	FighterInputFrame.CMD_DOWN_SPECIAL: FighterInputFrame.BUTTON_SPECIAL,
	FighterInputFrame.CMD_DOWN_LIGHT: FighterInputFrame.BUTTON_LIGHT,
	FighterInputFrame.CMD_DOWN_HEAVY: FighterInputFrame.BUTTON_HEAVY,
	FighterInputFrame.CMD_DOWN_KICK: FighterInputFrame.BUTTON_KICK,
	FighterInputFrame.CMD_THROW: FighterInputFrame.BUTTON_LIGHT,
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
	projectiles.clear()
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
		for p: ProjectileState in projectiles:
			p.previous_x = p.position_x  # frozen too (keeps interpolation still)
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
		if f.action == FighterState.Action.DASH:
			f.position_x += f.dash_dir * profile(i).dash_step(f.dash_forward, f.dash_frame)
		if f.is_airborne() and f.jump_dir != 0 and f.jump_frame > 0:
			f.position_x += f.jump_dir * profile(i).jump_step(f.jump_dir == f.facing)
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

	_move_projectiles()

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

	# 5. Hit detection and resolution. Projectiles are fired first (after all
	# movement, so they start from where the fighter now stands and can hit
	# on the tick they appear); opposing projectiles that meet cancel out.
	_fire_projectiles()
	for point: Vector2 in HitboxSystem.find_clashes(projectiles):
		var clash := CombatEvent.new()
		clash.tick = tick
		clash.type = CombatEvent.Type.PROJECTILE_CLASH
		clash.point = point
		combat_log.add(clash)
	var contacts: Array[HitboxSystem.Contact] = HitboxSystem.find_contacts(definitions, fighters, projectiles)
	contacts = _throw_holds(contacts)
	hitstop_remaining = HitResolver.resolve(contacts, self)
	for k: int in range(projectiles.size() - 1, -1, -1):
		if projectiles[k].spent:
			projectiles.remove_at(k)


## Throws that hold their victim (MoveData.throw_release_frame, D-103).
## A grab before the release frame only catches: the victim is held in place
## (HITSTUN, no hurtbox) until the thrower reaches the release frame, where a
## contact is made for the throw to land. If the thrower is no longer in that
## throw (hit by a projectile, say), the victim is let go.
func _throw_holds(contacts: Array[HitboxSystem.Contact]) -> Array[HitboxSystem.Contact]:
	var out: Array[HitboxSystem.Contact] = []
	for a: int in 2:
		var f: FighterState = fighters[a]
		if f.throw_target < 0:
			continue
		var d: FighterState = fighters[f.throw_target]
		var holding: bool = f.action == FighterState.Action.ATTACK and f.move != null \
				and f.move.throw_release_frame > 0 and f.move_frame <= f.move.throw_release_frame
		if not holding:
			d.held_by = -1                       # let go: the victim recovers at once
			d.stun_remaining = mini(d.stun_remaining, 1)
			f.throw_target = -1
		elif f.move_frame < f.move.throw_release_frame:
			# drawn in to the clinch over a few ticks (pushboxes ignored while held)
			if f.move.throw_hold_distance > 0.0:
				var want: float = f.position_x + f.facing * f.move.throw_hold_distance
				d.position_x = _clamped_x(f.throw_target, move_toward(d.position_x, want, THROW_PULL_PER_TICK))
		if holding and f.move_frame == f.move.throw_release_frame:
			var c := HitboxSystem.Contact.new()
			c.attacker = a
			c.defender = f.throw_target
			c.move = f.move
			c.point = Vector2(d.position_x - f.facing * 0.1, f.move.hitbox_center.y - 0.2)
			d.held_by = -1
			d.action = FighterState.Action.IDLE   # the throw starts a fresh combo, not hit 2 of the hold
			d.combo_hits = 0
			d.combo_damage = 0
			f.throw_target = -1
			out.append(c)
	for c: HitboxSystem.Contact in contacts:
		var att: FighterState = fighters[c.attacker]
		if c.projectile == null and c.move.is_throw() and c.move.throw_release_frame > att.move_frame:
			var d: FighterState = fighters[c.defender]
			d.action = FighterState.Action.HITSTUN
			d.stun_remaining = c.move.throw_release_frame - att.move_frame + 2
			d.hit_zone = FighterState.HitZone.BODY
			d.move = null
			d.chain.clear()
			d.pushback_remaining = 0.0
			d.held_by = c.attacker
			att.throw_target = c.defender
			att.move_connected = true
			continue
		out.append(c)
	return out


func separation() -> float:
	return absf(fighters[1].position_x - fighters[0].position_x)


## Returns deep copies of the current fighter states (for interpolation).
func snapshot() -> Array[FighterState]:
	var out: Array[FighterState] = []
	for f: FighterState in fighters:
		out.append(f.copy())
	return out


## Deep copies of the live projectiles (for interpolation and the AI).
func projectile_snapshot() -> Array[ProjectileState]:
	var out: Array[ProjectileState] = []
	for p: ProjectileState in projectiles:
		out.append(p.copy())
	return out


## True if fighter [param i] has a projectile of its own in flight.
func has_projectile(i: int) -> bool:
	for p: ProjectileState in projectiles:
		if p.owner == i:
			return true
	return false


## Exact text of the whole simulation state — for determinism tests.
func describe() -> String:
	var text: String = "tick=%d stop=%d | P1 %s | P2 %s" % [
		tick, hitstop_remaining, fighters[0].describe(), fighters[1].describe()]
	for p: ProjectileState in projectiles:
		text += " | " + p.describe()
	return text


# --- projectiles ----------------------------------------------------------------

## Constant-speed travel; a projectile ends after its range or at a wall.
func _move_projectiles() -> void:
	for k: int in range(projectiles.size() - 1, -1, -1):
		var p: ProjectileState = projectiles[k]
		var step_x: float = p.move.projectile_speed * CombatConstants.TICK_DELTA
		p.previous_x = p.position_x
		p.position_x += p.direction * step_x
		p.travelled += step_x
		if p.travelled > p.move.projectile_range or p.position_x < arena.left_bound \
				or p.position_x > arena.right_bound:
			projectiles.remove_at(k)


## A projectile move fires on its first active frame (startup_frames). A
## fighter hit before that frame has been interrupted and fires nothing.
func _fire_projectiles() -> void:
	for i: int in 2:
		var f: FighterState = fighters[i]
		if f.action != FighterState.Action.ATTACK or f.move == null or not f.move.is_projectile() \
				or f.move_frame != f.move.startup_frames or f.move_connected:
			continue
		# move_connected doubles as "already fired" for a projectile move: the
		# fighter's own body never connects with it. It also keeps the move
		# from being logged as a whiff and lets it be cancelled like a hit.
		f.move_connected = true
		var p := ProjectileState.new()
		p.id = _next_projectile_id
		_next_projectile_id += 1
		p.owner = i
		p.move = f.move
		p.direction = f.facing
		p.position_x = f.position_x + f.facing * f.move.hitbox_center.x
		p.previous_x = p.position_x
		projectiles.append(p)
		var ev := CombatEvent.new()
		ev.tick = tick
		ev.type = CombatEvent.Type.PROJECTILE_FIRED
		ev.actor = i
		ev.move_id = f.move.id
		ev.point = Vector2(p.position_x, f.move.hitbox_center.y)
		combat_log.add(ev)


# --- phase 1: state machine ---------------------------------------------------

func _update_state(i: int, input: FighterInputFrame) -> void:
	var f: FighterState = fighters[i]
	_register_presses(f, input)
	_read_dash_taps(f, input)
	if OriginMeter.tick_surge(f, definitions[i], tuning):
		_log_simple(CombatEvent.Type.SURGE_END, i)

	match f.action:
		FighterState.Action.KO:
			f.move_x = 0
			f.buffer.clear()
			return
		FighterState.Action.ATTACK:
			f.move_frame += 1
			if f.is_jumping():
				# An air attack rides the jump and is cut off by the landing.
				_advance_jump(i)
				if not f.is_airborne() or f.move_frame > f.move.total_frames():
					_end_attack(i)
					f.action = FighterState.Action.JUMP
			elif f.move_frame > f.move.total_frames():
				_end_attack(i)
		FighterState.Action.JUMP:
			_advance_jump(i)
			if f.jump_frame > profile(i).jump_total_ticks():
				f.end_jump()
				_to_idle(f)
		FighterState.Action.DASH:
			f.dash_frame += 1
			if f.dash_frame > profile(i).dash_ticks(f.dash_forward):
				_to_idle(f)
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
		# A throw input completed on the first frames of a Light / Kick attack
		# replaces that attack (D-103, see _merge_throw).
		if f.move != null and not f.move_connected and f.move_frame <= THROW_WINDOW + 1 and f.chain.size() <= 1 \
				and (f.move.input_pattern in [&"LIGHT", &"DOWN_LIGHT", &"KICK", &"DOWN_KICK"]):
			var throw_move: MoveData = _take_buffered(i, func(m: MoveData) -> bool: return m.input_pattern == &"THROW")
			if throw_move != null:
				f.chain.clear()
				_start_attack(i, throw_move, false)
				_age_buffer(f)
				return
		# Still attacking: only a legal cancel may consume a buffered press.
		f.move_x = 0
		var cancel_move: MoveData = _take_buffered(i, _can_cancel_into.bind(i))
		if cancel_move != null:
			_start_attack(i, cancel_move, true)
		_age_buffer(f)
		return

	if f.action == FighterState.Action.JUMP:
		# Committed: no blocking, no steering. One attack while in the air.
		f.move_x = 0
		var air_move: MoveData = definitions[i].move_for(&"AIR")
		if f.is_airborne() and not f.air_attacked and air_move != null and _take_air_press(f):
			f.air_attacked = true
			_start_attack(i, air_move, false)
		_age_buffer(f)
		return

	if f.action == FighterState.Action.DASH:
		# A forward dash can be cut short by an attack; a back dash cannot.
		f.move_x = 0
		if f.dash_forward and f.dash_frame >= tuning.dash_cancel_frame:
			var out_of_dash: MoveData = _take_buffered(i, func(_m: MoveData) -> bool: return true)
			if out_of_dash != null:
				_start_attack(i, out_of_dash, false)
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

	# A double-tapped direction dashes (not while holding block or down).
	if f.dash_pending != 0 and not input.is_held(FighterInputFrame.BUTTON_BLOCK) and input.move_y >= 0:
		f.action = FighterState.Action.DASH
		f.dash_dir = f.dash_pending
		f.dash_forward = f.dash_pending == f.facing
		f.dash_frame = 1
		f.dash_pending = 0
		f.move_x = 0
		var ev := CombatEvent.new()
		ev.tick = tick
		ev.type = CombatEvent.Type.DASH
		ev.actor = i
		ev.move_id = &"dash_forward" if f.dash_forward else &"dash_back"
		combat_log.add(ev)
		_age_buffer(f)
		return

	if input.is_held(FighterInputFrame.BUTTON_BLOCK):
		f.action = FighterState.Action.BLOCK
		f.block_low = input.move_y < 0
		f.move_x = 0
	elif input.move_y > 0:
		# Up: jump. The direction held now decides the jump and stays fixed.
		f.action = FighterState.Action.JUMP
		f.jump_frame = 1
		f.jump_dir = clampi(input.move_x, -1, 1)
		f.height = 0.0
		f.air_attacked = false
		f.move_x = 0
		var jump_ev := CombatEvent.new()
		jump_ev.tick = tick
		jump_ev.type = CombatEvent.Type.JUMP
		jump_ev.actor = i
		jump_ev.move_id = &"jump" if f.jump_dir == 0 else (&"jump_forward" if f.jump_dir == f.facing else &"jump_back")
		combat_log.add(jump_ev)
	elif input.move_y < 0:
		# Down: crouch (a shorter hurtbox; still neutral, cannot walk).
		f.action = FighterState.Action.CROUCH
		f.move_x = 0
	else:
		f.move_x = clampi(input.move_x, -1, 1)
		f.action = FighterState.Action.WALK if f.move_x != 0 else FighterState.Action.IDLE
	_age_buffer(f)


## One tick of the jump arc. The height is set here; the horizontal travel
## is applied in the integrate phase.
func _advance_jump(i: int) -> void:
	var f: FighterState = fighters[i]
	f.jump_frame += 1
	f.height = profile(i).jump_height_at(f.jump_frame)


## Consumes a buffered Light/Heavy/Kick press (with or without down held) for
## the jumping attack. Other presses stay buffered and expire as usual.
func _take_air_press(f: FighterState) -> bool:
	for k: int in range(f.buffer.size() - 1, -1, -1):
		var code: int = f.buffer[k].x
		if code == FighterInputFrame.BUTTON_LIGHT or code == FighterInputFrame.BUTTON_HEAVY \
				or code == FighterInputFrame.BUTTON_KICK or code == FighterInputFrame.CMD_DOWN_LIGHT \
				or code == FighterInputFrame.CMD_DOWN_HEAVY or code == FighterInputFrame.CMD_DOWN_KICK:
			f.buffer.remove_at(k)
			return true
	return false


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
	if pressed & (FighterInputFrame.BUTTON_LIGHT | FighterInputFrame.BUTTON_KICK):
		_merge_throw(f)


## Light + Kick together → one THROW press (D-103), only for a fighter that
## has a throw on that input (everyone else keeps Light and Kick as they were).
## The partner press may be in the buffer, or may already have started its
## attack in the last THROW_WINDOW ticks (that attack is then replaced, see
## _update_state).
func _merge_throw(f: FighterState) -> void:
	var i: int = fighters.find(f)
	if i < 0 or definitions[i] == null or definitions[i].moves_for(&"THROW").is_empty():
		return
	# A throw starts from neutral, or from a Light / Kick that has only just
	# started on its own. Never out of a running combo: there Light and Kick
	# stay what they are (the L, L, K route).
	var started: bool = f.action == FighterState.Action.ATTACK and f.move != null and not f.move_connected \
			and f.move_frame <= THROW_WINDOW + 1 and f.chain.size() <= 1
	if not (f.is_neutral() or started):
		return
	var light_k: int = -1
	var kick_k: int = -1
	for k: int in range(f.buffer.size() - 1, -1, -1):
		var e: Vector2i = f.buffer[k]
		if e.y > THROW_WINDOW:
			continue
		if light_k < 0 and (e.x == FighterInputFrame.BUTTON_LIGHT or e.x == FighterInputFrame.CMD_DOWN_LIGHT):
			light_k = k
		elif kick_k < 0 and (e.x == FighterInputFrame.BUTTON_KICK or e.x == FighterInputFrame.CMD_DOWN_KICK):
			kick_k = k
	if started:
		var pat: StringName = f.move.input_pattern
		if light_k < 0 and (pat == &"LIGHT" or pat == &"DOWN_LIGHT"):
			light_k = -2                       # the Light half is the attack just started
		elif kick_k < 0 and (pat == &"KICK" or pat == &"DOWN_KICK"):
			kick_k = -2
	if light_k == -1 or kick_k == -1:
		return
	for k: int in [maxi(light_k, kick_k), mini(light_k, kick_k)]:
		if k >= 0:
			f.buffer.remove_at(k)
	f.buffer.append(Vector2i(FighterInputFrame.CMD_THROW, 0))


## Double-tap detection on the horizontal direction (see CombatTuning "Dash").
## A detected dash waits (dash_pending) for at most the input buffer time
## until the fighter is free to start it.
func _read_dash_taps(f: FighterState, input: FighterInputFrame) -> void:
	var dir: int = clampi(input.move_x, -1, 1) if input != null else 0
	if dir != f.stick_dir:
		if dir != 0:
			if f.tap_dir == dir and f.tap_age >= 0 and f.tap_age <= tuning.dash_tap_window_ticks:
				f.dash_pending = dir
				f.dash_pending_age = 0
				f.tap_dir = 0
				f.tap_age = -1
			f.stick_held_ticks = 0
		elif f.stick_dir != 0:
			if f.stick_held_ticks <= tuning.dash_tap_hold_ticks:
				f.tap_dir = f.stick_dir
				f.tap_age = 0
			else:
				f.tap_dir = 0
				f.tap_age = -1
		f.stick_dir = dir
	elif dir != 0:
		f.stick_held_ticks += 1
	elif f.tap_age >= 0:
		f.tap_age += 1
		if f.tap_age > tuning.dash_tap_window_ticks:
			f.tap_dir = 0
			f.tap_age = -1
	if f.dash_pending != 0:
		f.dash_pending_age += 1
		if f.dash_pending_age > tuning.input_buffer_ticks + 1:
			f.dash_pending = 0


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
		for move: MoveData in _string_first(i, definitions[i].moves_for(_PATTERNS.get(code, &""))):
			# Meter/Surge conditions first: an unaffordable move stays buffered.
			# One own projectile on screen: the press waits in the buffer.
			if move.is_projectile() and has_projectile(i):
				continue
			if OriginMeter.can_use(f, definitions[i], move, tuning) and accept.call(move):
				f.buffer.remove_at(k)
				return move
	return null


## Strings (D-113): a move with [member MoveData.string_after] is offered only
## while P[param i] is attacking with that move, and then ahead of the
## ordinary move on the same input; otherwise it is left out.
func _string_first(i: int, candidates: Array[MoveData]) -> Array[MoveData]:
	var f: FighterState = fighters[i]
	var current: StringName = f.move.id if (f.action == FighterState.Action.ATTACK and f.move != null) else &""
	var strings: Array[MoveData] = []
	var rest: Array[MoveData] = []
	for m: MoveData in candidates:
		if m.string_after == &"":
			rest.append(m)
		elif current != &"" and m.string_after == current:
			strings.append(m)
	strings.append_array(rest)
	return strings


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
	if target.tags.has("normal") and f.chain.size() >= tuning.max_normals_in_chain:
		return false
	return f.chain.count(target.id) < tuning.max_same_move_in_chain


func _start_attack(i: int, move: MoveData, is_cancel: bool) -> void:
	var f: FighterState = fighters[i]
	var from_id: StringName = f.move.id if (is_cancel and f.move != null) else &""
	f.action = FighterState.Action.ATTACK
	f.move = move
	f.move_frame = 1
	f.move_connected = false
	f.last_hit_window = -1
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


## The opponent of fighter [param i] is put on [param i]'s other side, at the
## same distance (less if a wall is in the way), still facing the way it
## was going; [param i] turns round to face its back. Used by counters that
## turn the attacker past them.
func switch_sides(i: int) -> void:
	var me: FighterState = fighters[i]
	var other: FighterState = fighters[1 - i]
	var gap: float = maxf(absf(other.position_x - me.position_x),
		profile(0).pushbox_half_width + profile(1).pushbox_half_width)
	var side: float = -signf(other.position_x - me.position_x)
	if side == 0.0:
		side = -float(me.facing)
	other.position_x = _clamped_x(1 - i, me.position_x + side * gap)
	# against a wall there is less room: the countering fighter gives way
	me.position_x = _clamped_x(i, other.position_x - side * gap)
	me.facing = int(side)


## Ends fighter [param i]'s current move at once (a successful parry).
func end_move(i: int) -> void:
	_to_idle(fighters[i])


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
	f.counter_hit = false


func _to_idle(f: FighterState) -> void:
	f.action = FighterState.Action.IDLE
	f.move = null
	f.move_frame = 0
	f.move_connected = false
	f.stun_remaining = 0
	f.dash_frame = 0
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
		if not f.pushback_transfers:
			f.pushback_remaining = 0.0  # pushed by a projectile: just stop at the wall
			continue
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
	if overlap <= 0.0 or a.held_by >= 0 or b.held_by >= 0:     # a clinch: the held fighter is inside the pushboxes
		return
	# A pass-through move (side switch) ignores pushboxes while it travels,
	# and so does a fighter high enough in a jump (it can land behind).
	for f: FighterState in fighters:
		if f.height > tuning.jump_pass_height:
			return
		if f.action == FighterState.Action.ATTACK and f.move != null and f.move.passes_through \
				and f.move.moves_on_frame(f.move_frame):
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
