class_name AIController
extends RefCounted
## Finite-state-machine opponent (spec §5). Not machine learning.
##
## FAIRNESS CONTRACT
##   - Input: only AIObservation snapshots fed through [method observe]. The
##     WHOLE screen — opponent and itself — is seen
##     [member AIProfile.reaction_delay_ticks] late, like a human's reaction
##     time. Nothing about the opponent's input can reach it earlier.
##   - Output: a FighterInputFrame per tick — exactly what a human controller
##     produces. The simulation enforces startup, recovery, cancel rules and
##     hit detection, so the AI cannot bypass them.
##   - It never touches the simulation, the other player's input or buffer.
##   - Frame data of moves is treated as public "matchup knowledge".
##   - Deterministic: all randomness comes from a seeded RNG.
##
## States: NEUTRAL, APPROACH, RETREAT, ATTACK, BLOCK, PUNISH, RECOVER,
## STUNNED, KNOCKDOWN, WAKEUP. (KNOCKDOWN/WAKEUP are reserved: there are no
## knockdowns in the game yet; KO maps to KNOCKDOWN.)

enum State { NEUTRAL, APPROACH, RETREAT, ATTACK, BLOCK, PUNISH, RECOVER, STUNNED, KNOCKDOWN, WAKEUP }
## Distance bands, from this fighter's own move ranges (spec §5).
enum Band { CLOSE, MID, FAR }

const L: int = FighterInputFrame.BUTTON_LIGHT
const H: int = FighterInputFrame.BUTTON_HEAVY
const K: int = FighterInputFrame.BUTTON_KICK
const B: int = FighterInputFrame.BUTTON_BLOCK
const S: int = FighterInputFrame.BUTTON_SPECIAL
const U: int = FighterInputFrame.BUTTON_ULTIMATE
const _BUTTON_FOR: Dictionary = {&"LIGHT": L, &"HEAVY": H, &"KICK": K,
	&"SPECIAL": S, &"FORWARD_SPECIAL": S, &"ULTIMATE": U,
	&"DOWN_LIGHT": L, &"DOWN_HEAVY": H, &"DOWN_KICK": K, &"DOWN_SPECIAL": S, &"BACK_SPECIAL": S}
const _ALL_PATTERNS: Array[StringName] = [&"LIGHT", &"KICK", &"HEAVY", &"SPECIAL", &"FORWARD_SPECIAL",
	&"DOWN_LIGHT", &"DOWN_HEAVY", &"DOWN_KICK", &"DOWN_SPECIAL", &"BACK_SPECIAL"]
## Extra distance at which a visible attack is treated as a threat.
const THREAT_MARGIN: float = 0.35

var profile: AIProfile
var index: int
var me_def: FighterDefinition
var opp_def: FighterDefinition
var decision_log := AIDecisionLog.new()
var state: State = State.NEUTRAL

var _rng := RandomNumberGenerator.new()
var _queue: Array[AIObservation] = []
var _intent: State = State.NEUTRAL
var _intent_ticks: int = 0
var _decide_cooldown: int = 0
var _guard_left: int = 0
var _pending: int = 0          # button waiting to be tapped
var _pending_label: String = ""
var _last_buttons: int = 0
var _idle_ticks: int = 0
var _threat_key: int = -1
var _threat_block: bool = false
var _counter_key: int = -1
## Guard height chosen for the attack currently seen (true = low block).
var _block_low: bool = false
## The next emitted frame holds down (down + button command).
var _tap_down: bool = false
var _punish_key: int = -1
var _route_commit: bool = false
var _route_pos: int = 0
var _route_pressed_for: int = -1   # own attack instance already followed up
var _own_attack_key: int = -1
var _was_stunned: bool = false
var _mash_out: bool = false
var _pattern_step: int = 0
var _last_opp_attack_tick: int = -100000
var _opp_aggr: float = 0.0     # adaptive: how often the opponent attacks
var _opp_block: float = 0.0    # adaptive: how often the opponent blocks
var _tick: int = 0
var _toward: int = 1
## Own fighter as last seen (meter/surge decide which moves are affordable).
var _me: AIObservation.Seen = null


func _init(ai_profile: AIProfile, fighter_index: int, my_definition: FighterDefinition,
		opponent_definition: FighterDefinition, seed: int = 1) -> void:
	profile = ai_profile
	index = fighter_index
	me_def = my_definition
	opp_def = opponent_definition
	_rng.seed = seed
	decision_log.label = "P%d:%s" % [index + 1, profile.difficulty_name]


## New round / rematch: forget everything perceived (keeps RNG stream).
func reset() -> void:
	_queue.clear()
	state = State.NEUTRAL
	_intent = State.NEUTRAL
	_intent_ticks = 0
	_decide_cooldown = 0
	_guard_left = 0
	_pending = 0
	_last_buttons = 0
	_idle_ticks = 0
	_threat_key = -1
	_punish_key = -1
	_route_commit = false
	_route_pressed_for = -1
	_own_attack_key = -1
	_pattern_step = 0
	_was_stunned = false
	_mash_out = false


## Feed the latest snapshot (state after the previous tick). Call once per tick.
func observe(obs: AIObservation) -> void:
	_queue.append(obs)
	# Keep the delayed snapshot plus ONE older one (for velocity). Nothing
	# newer than reaction_delay ticks is ever read.
	while _queue.size() > profile.reaction_delay_ticks + 2:
		_queue.pop_front()


## Input for the coming tick.
func next_input() -> FighterInputFrame:
	_tick += 1
	if _queue.is_empty():
		return _emit(0, 0)
	# _queue[-1] is the newest snapshot; the one we may act on is
	# reaction_delay_ticks older than that.
	var seen_idx: int = _queue.size() - 1 - profile.reaction_delay_ticks
	if seen_idx < 0:
		return _emit(0, 0)  # first reaction_delay ticks of a round: nothing seen yet
	var delayed: AIObservation = _queue[seen_idx]
	var me: AIObservation.Seen = delayed.fighters[index]
	var opp: AIObservation.Seen = delayed.fighters[1 - index]
	_learn(delayed, opp)

	if me.action != FighterState.Action.HITSTUN and me.action != FighterState.Action.BLOCKSTUN:
		_was_stunned = false
	# Spacing: project where a walking opponent is NOW from the velocity seen
	# between the delayed snapshot and the one before it (both already
	# "seen"). Pure reading of visible motion, capped to walking speed.
	var opp_x: float = opp.x
	if seen_idx >= 1 and profile.anticipation > 0.0:
		var before: AIObservation.Seen = _queue[seen_idx - 1].fighters[1 - index]
		var max_step: float = opp_def.movement.walk_forward_speed * CombatConstants.TICK_DELTA
		var velocity: float = clampf(opp.x - before.x, -max_step, max_step)
		opp_x += velocity * profile.reaction_delay_ticks * profile.anticipation
	var dist: float = absf(opp_x - me.x)
	var toward: int = 1 if opp_x > me.x else -1
	_toward = toward
	_me = me

	match me.action:
		FighterState.Action.KO:
			_set_state(State.KNOCKDOWN, "KO")
			return _emit(0, 0)
		FighterState.Action.HITSTUN, FighterState.Action.BLOCKSTUN:
			if not _was_stunned:
				_was_stunned = true
				_mash_out = _rng.randf() < profile.mash_out_chance
				decision_log.add(_tick, "STUNNED", "in %s → %s" % [
					FighterState.Action.keys()[me.action], "mash Light" if _mash_out else "hold"])
			_set_state(State.STUNNED, "")
			var hold: int = B if (_last_buttons & B) else 0
			# Tap Light every other tick so the buffer releases it on recovery —
			# but only while the opponent is within Light range (a whiffed
			# reversal is a free punish for them).
			var light: MoveData = me_def.move_for(&"LIGHT")
			var opp_dist: float = absf(opp.x - me.x)
			if _mash_out and light != null and opp_dist <= _reach(light, opp_def) - 0.05:
				return _emit(0, hold | (L if _tick % 2 == 0 else 0))
			return _emit(0, hold)
		FighterState.Action.ATTACK:
			return _attacking(delayed, me)

	# --- neutral: block what we see coming ---------------------------------
	var opp_move: MoveData = opp_def.move_for_id(opp.move_id) if opp.move_id != &"" else null
	if opp.action == FighterState.Action.ATTACK and opp_move != null \
			and opp.move_frame < opp_move.startup_frames + opp_move.active_frames \
			and dist <= _reach(opp_move, me_def) + THREAT_MARGIN:
		var key: int = delayed.tick - opp.move_frame
		if key != _threat_key:
			_threat_key = key
			_threat_block = _rng.randf() < minf(1.0, profile.block_reaction_chance)
			# Guard height: only LOW and HIGH attacks need a read (and a roll).
			_block_low = false
			if opp_move.hit_level == MoveData.HitLevel.LOW or opp_move.hit_level == MoveData.HitLevel.HIGH:
				var right_height: bool = _rng.randf() < profile.low_block_chance
				_block_low = (opp_move.hit_level == MoveData.HitLevel.LOW) == right_height
			decision_log.add(_tick, State.keys()[state], "sees %s (f%d, d=%.2f) → %s" % [
				opp.move_id, opp.move_frame, dist, "BLOCK" if _threat_block else "no block"])
		# Counter stance instead of a block, if this fighter has one that
		# catches the attack (rolled once per attack seen).
		if key != _counter_key:
			_counter_key = key
			var stance: MoveData = me_def.move_for(&"BACK_SPECIAL")
			if _threat_block and profile.counter_chance > 0.0 and stance != null and stance.is_counter() \
					and stance.counter_levels.has(opp_move.hit_level) and _rng.randf() < profile.counter_chance:
				_set_state(State.BLOCK, "counter stance")
				return _tap(&"BACK_SPECIAL", "counter %s" % opp.move_id, 0)
		if _threat_block or _guard_left > 0:
			_set_state(State.BLOCK, "reaction")
			return _emit(0, B)

	# --- punish visible recovery -----------------------------------------
	if opp.action == FighterState.Action.ATTACK and opp_move != null \
			and opp.move_frame >= opp_move.startup_frames + opp_move.active_frames:
		var key2: int = delayed.tick - opp.move_frame
		if key2 != _punish_key:
			_punish_key = key2
			if _rng.randf() < profile.punish_chance:
				# Remaining recovery as it really is now (we see it late).
				var remaining: int = opp_move.total_frames() - opp.move_frame - profile.reaction_delay_ticks
				var punish: StringName = _pick_punish(remaining, dist)
				if punish != &"":
					_set_state(State.PUNISH, "%s recovering ~%d f" % [opp.move_id, remaining])
					_start_route_if(punish)
					return _tap(punish, "punish %s" % opp.move_id, 0)
				decision_log.add(_tick, State.keys()[state], "no punish fits (%d f left, d=%.2f)" % [remaining, dist])

	# --- guard window ------------------------------------------------------
	if _guard_left > 0:
		_guard_left -= 1
		_set_state(State.BLOCK, "guarding")
		return _emit(0, B)

	# --- Origin Surge / ultimate (meter visible on the HUD) ---------------
	if me.meter >= 100 and not me.in_surge and _decide_cooldown <= 1 and _rng.randf() < profile.surge_chance:
		_set_state(State.ATTACK, "meter full")
		return _tap(&"ULTIMATE", "activate Origin Surge", 0)
	if me.in_surge and _decide_cooldown <= 1 and _move_in_range(&"ULTIMATE", dist, true) \
			and _rng.randf() < profile.ultimate_chance:
		_set_state(State.ATTACK, "Surge, in range")
		return _tap(&"ULTIMATE", "ultimate Origin Break", 0)

	# --- periodic neutral decision ----------------------------------------
	_decide_cooldown -= 1
	if _decide_cooldown <= 0:
		_decide_cooldown = profile.decision_interval_ticks
		_decide(dist, opp)
	if _idle_ticks >= profile.max_idle_ticks:
		var in_range: Array[StringName] = _moves_in_range(dist)
		if in_range.is_empty():
			_intent = State.APPROACH
			decision_log.add(_tick, State.keys()[state], "anti-idle → APPROACH")
		else:
			_intent = State.ATTACK
			_pending_label = String(in_range[0])
			decision_log.add(_tick, State.keys()[state], "anti-idle → ATTACK %s" % in_range[0])
	return _act_on_intent(toward, dist)


# --- attacking / combos ----------------------------------------------------------

func _attacking(latest: AIObservation, me: AIObservation.Seen) -> FighterInputFrame:
	var m: MoveData = me_def.move_for_id(me.move_id)
	if m == null:
		return _emit(0, 0)
	var attack_key: int = latest.tick - me.move_frame
	if attack_key != _own_attack_key:
		_own_attack_key = attack_key
	var phase_active: bool = me.move_frame < m.startup_frames + m.active_frames
	_set_state(State.ATTACK if phase_active else State.RECOVER, String(m.id))
	# Follow the committed combo route once the current hit connects.
	if _route_commit and me.move_connected and _route_pressed_for != attack_key \
			and _route_pos + 1 < profile.combo_route.size():
		_route_pressed_for = attack_key
		_route_pos += 1
		var next: StringName = StringName(profile.combo_route[_route_pos])
		if not _affordable(next):
			_route_commit = false
			return _emit(0, 0)
		return _tap(next, "combo %d/%d" % [_route_pos + 1, profile.combo_route.size()], 0)
	return _emit(0, 0)


func _start_route_if(pattern: StringName) -> void:
	_route_pos = 0
	_route_commit = not profile.combo_route.is_empty() \
			and StringName(profile.combo_route[0]) == pattern \
			and _rng.randf() < profile.combo_chance
	_route_pressed_for = -1


# --- neutral decisions -------------------------------------------------------------

func _decide(dist: float, opp: AIObservation.Seen) -> void:
	var in_range: Array[StringName] = _moves_in_range(dist)
	if profile.predictable_pattern:
		# Fixed cycle: walk in → attack with the first available move → back off.
		match _pattern_step:
			0:
				if in_range.is_empty():
					_set_intent(State.APPROACH, "pattern: walk in")
				else:
					_pattern_step = 1
			1:
				_set_intent(State.ATTACK, "pattern: attack")
				_pending_label = String(in_range[0] if not in_range.is_empty() else &"LIGHT")
				_pattern_step = 2
			2:
				_set_intent(State.RETREAT, "pattern: back off")
				_pattern_step = 0
		if _pattern_step == 1 and not in_range.is_empty():
			_set_intent(State.ATTACK, "pattern: attack")
			_pending_label = String(in_range[0])
			_pattern_step = 2
		return

	var aggression: float = profile.aggression
	var guard: float = profile.guard_chance
	if profile.adaptive:
		guard = minf(0.9, guard + 0.35 * _opp_aggr)
		aggression *= 1.0 - 0.4 * _opp_block
	var r: float = _rng.randf()
	if in_range.is_empty():
		if r < aggression:
			_set_intent(State.APPROACH, "far (d=%.2f)" % dist)
		elif r < aggression + profile.retreat_chance:
			_set_intent(State.RETREAT, "far, backing off")
		else:
			_set_intent(State.NEUTRAL, "far, waiting")
		return
	if r < aggression:
		var choice: StringName = _weighted_choice(in_range, band(dist) == Band.CLOSE)
		if _rng.randf() < profile.range_mistake_chance:
			choice = _weighted_choice(_ALL_PATTERNS)
		_set_intent(State.ATTACK, "in range of %s (d=%.2f)" % [in_range, dist])
		_pending_label = String(choice)
	elif r < aggression + guard:
		_guard_left = profile.guard_ticks
		_set_intent(State.BLOCK, "close, guarding %d" % profile.guard_ticks)
	elif r < aggression + guard + profile.retreat_chance:
		_set_intent(State.RETREAT, "close, backing off")
	else:
		_set_intent(State.NEUTRAL, "close, waiting")


func _act_on_intent(toward: int, dist: float) -> FighterInputFrame:
	match _intent:
		State.APPROACH:
			_set_state(State.APPROACH, "")
			if not _moves_in_range(dist).is_empty() and not profile.predictable_pattern:
				_decide_cooldown = 0  # re-decide as soon as we arrive
			return _emit(toward, 0)
		State.RETREAT:
			_set_state(State.RETREAT, "")
			_intent_ticks += 1
			if _intent_ticks > profile.decision_interval_ticks * 2:
				_intent = State.NEUTRAL
			return _emit(-toward, 0)
		State.ATTACK:
			_intent = State.NEUTRAL
			var pattern: StringName = StringName(_pending_label) if _pending_label != "" else &"LIGHT"
			_start_route_if(pattern)
			_set_state(State.ATTACK, "")
			return _tap(pattern, "neutral attack", 0)
		State.BLOCK:
			_intent = State.NEUTRAL
			return _emit(0, B)
	_set_state(State.NEUTRAL, "")
	return _emit(0, 0)


func _set_intent(s: State, reason: String) -> void:
	_intent = s
	_intent_ticks = 0
	decision_log.add(_tick, State.keys()[state], "decide %s: %s" % [State.keys()[s], reason])


# --- helpers ---------------------------------------------------------------------

## Max centre distance at which [param m] hits a fighter with [param target]'s hurtbox.
static func _reach(m: MoveData, target: FighterDefinition) -> float:
	return m.hitbox_center.x + m.hitbox_size.x * 0.5 + target.hurtbox_half_width


func _moves_in_range(dist: float) -> Array[StringName]:
	var out: Array[StringName] = []
	for pattern: StringName in _ALL_PATTERNS:
		if _move_in_range(pattern, dist, false):
			out.append(pattern)
	return out


## In range and affordable (meter/Surge as seen on the HUD).
func _move_in_range(pattern: StringName, dist: float, surge_move: bool) -> bool:
	for m: MoveData in me_def.moves_for(pattern):
		if m.activates_surge or m.requires_surge != surge_move or m.is_counter():
			continue
		var reach: float = _reach(m, opp_def) + m.move_distance
		if dist <= reach - 0.05 and _affordable_move(m):
			return true
	return false


func _affordable(pattern: StringName) -> bool:
	for m: MoveData in me_def.moves_for(pattern):
		if not m.activates_surge and not m.requires_surge and _affordable_move(m):
			return true
	return false


func _affordable_move(m: MoveData) -> bool:
	if _me == null:
		return m.meter_cost == 0
	if m.requires_surge and not _me.in_surge:
		return false
	var free: bool = _me.in_surge and me_def.surge_free_specials and m.tags.has("special")
	if free:
		return true
	# Meter discipline: save a nearly-full meter for Origin Surge.
	if m.meter_cost > 0 and not m.requires_surge and _me.meter >= profile.save_for_surge_above:
		return false
	return _me.meter >= m.meter_cost


func band(dist: float) -> Band:
	var light: MoveData = me_def.move_for(&"LIGHT")
	var far: float = 0.0
	for pattern: StringName in [&"LIGHT", &"KICK", &"HEAVY"]:
		var m: MoveData = me_def.move_for(pattern)
		if m != null:
			far = maxf(far, _reach(m, opp_def))
	if light != null and dist <= _reach(light, opp_def):
		return Band.CLOSE
	return Band.MID if dist <= far else Band.FAR


func _weighted_choice(options: Array[StringName], close: bool = false) -> StringName:
	var weights: Array[float] = []
	var total: float = 0.0
	for o: StringName in options:
		var w: float = float(profile.attack_weights.get(o, 1.0))
		if close and o == &"LIGHT":
			w *= profile.close_light_bias
		weights.append(w)
		total += w
	var r: float = _rng.randf() * total
	for k: int in options.size():
		r -= weights[k]
		if r <= 0.0:
			return options[k]
	return options[-1]


func _pick_punish(remaining: int, dist: float) -> StringName:
	# Moves that start in time and reach. Non-optimal AIs take the first that
	# fits (Light first); optimal AIs take the most damaging one.
	var best: StringName = &""
	var best_damage: int = -1
	for pattern: StringName in _ALL_PATTERNS:
		var m: MoveData = me_def.move_for(pattern)
		if m == null or m.startup_frames > remaining or dist > _reach(m, opp_def) + m.move_distance - 0.05 \
				or not _affordable_move(m):
			continue
		if not profile.punish_optimally:
			return pattern
		if m.damage > best_damage:
			best_damage = m.damage
			best = pattern
	return best


func _learn(obs: AIObservation, opp: AIObservation.Seen) -> void:
	if not profile.adaptive:
		return
	if opp.action == FighterState.Action.ATTACK and opp.move_frame == 1:
		_last_opp_attack_tick = obs.tick
	var attacked_recently: float = 1.0 if obs.tick - _last_opp_attack_tick < 60 else 0.0
	var blocking: float = 1.0 if opp.action == FighterState.Action.BLOCK or opp.action == FighterState.Action.BLOCKSTUN else 0.0
	_opp_aggr = lerpf(_opp_aggr, attacked_recently, 0.01)
	_opp_block = lerpf(_opp_block, blocking, 0.01)


func _set_state(s: State, reason: String) -> void:
	if s == state:
		return
	if reason != "":
		decision_log.add(_tick, State.keys()[s], reason)
	state = s


## Queues a button tap; emits a release tick first if the button is still held,
## so the simulation always sees a fresh press.
func _tap(pattern: StringName, reason: String, move_x: int) -> FighterInputFrame:
	var button: int = _BUTTON_FOR.get(pattern, L)
	# Specials are direction-sensitive: forward = toward the opponent.
	if pattern == &"FORWARD_SPECIAL":
		move_x = _toward
	elif pattern == &"BACK_SPECIAL":
		move_x = -_toward
	_tap_down = String(pattern).begins_with("DOWN_")
	decision_log.add(_tick, State.keys()[state], "press %s (%s)" % [pattern, reason])
	if _last_buttons & button:
		_pending = button
		return _emit(move_x, 0)
	return _emit(move_x, button)


func _emit(move_x: int, buttons: int) -> FighterInputFrame:
	if _pending != 0 and (buttons & _pending) == 0 and (_last_buttons & _pending) == 0:
		buttons |= _pending
		_pending = 0
	_last_buttons = buttons
	if move_x == 0 and buttons == 0:
		_idle_ticks += 1
	else:
		_idle_ticks = 0
	var down: bool = _tap_down or (_block_low and (buttons & B) != 0)
	_tap_down = false
	return FighterInputFrame.with_buttons(buttons, move_x, -1 if down else 0)
