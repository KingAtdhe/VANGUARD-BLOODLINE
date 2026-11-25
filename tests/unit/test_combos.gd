extends RefCounted
## Milestone 4: input buffer, cancel routes, combo counter/scaling, training.

const L: int = FighterInputFrame.BUTTON_LIGHT
const H: int = FighterInputFrame.BUTTON_HEAVY
const K: int = FighterInputFrame.BUTTON_KICK
const B: int = FighterInputFrame.BUTTON_BLOCK


func _tuning() -> CombatTuning:
	return load("res://data/rules/combat_tuning.tres")


func _sim(separation: float = 0.9, cornered: bool = false) -> CombatSimulation:
	var sim := CombatSimulation.new()
	sim.setup(load("res://data/arenas/greybox_arena.tres"),
		load("res://data/fighters/kairo.tres"), load("res://data/fighters/training_dummy.tres"), _tuning())
	if cornered:
		var wall_x: float = sim.arena.right_bound - sim.profile(1).pushbox_half_width
		sim.fighters[1].position_x = wall_x
		sim.fighters[0].position_x = wall_x - separation
	else:
		sim.fighters[0].position_x = -separation * 0.5
		sim.fighters[1].position_x = separation * 0.5
	return sim


func _step(sim: CombatSimulation, p1: int, p2: int = 0, times: int = 1, p1_dir: int = 0) -> void:
	for _i: int in times:
		sim.step([FighterInputFrame.with_buttons(p1, p1_dir), FighterInputFrame.with_buttons(p2)])


func _move(pattern: StringName) -> MoveData:
	return (load("res://data/fighters/kairo.tres") as FighterDefinition).move_for(pattern)


func _events(sim: CombatSimulation, type: CombatEvent.Type, actor: int = -2) -> Array[CombatEvent]:
	var out: Array[CombatEvent] = []
	for e: CombatEvent in sim.combat_log.all_events():
		if e.type == type and (actor == -2 or e.actor == actor):
			out.append(e)
	return out


## Steps until P1's attack is on [param frame] (and not in hitstop).
func _advance_to_frame(sim: CombatSimulation, frame: int, held: int = 0) -> bool:
	for _t: int in 120:
		var f: FighterState = sim.fighters[0]
		if f.action == FighterState.Action.ATTACK and f.move_frame == frame and sim.hitstop_remaining == 0:
			return true
		_step(sim, held)
	return false


func test_tuning_and_moves_valid() -> Array[String]:
	var f: Array[String] = _tuning().validate()
	for pattern: StringName in [&"LIGHT", &"HEAVY", &"KICK"]:
		f.append_array(_move(pattern).validate())
	return f


# --- input buffer -------------------------------------------------------------

func test_buffer_executes_at_first_legal_tick_within_window() -> Array[String]:
	var f: Array[String] = []
	var heavy: MoveData = _move(&"HEAVY")
	var window: int = _tuning().input_buffer_ticks
	for early: int in [1, 2, window, window + 1, window + 3]:
		var sim := _sim(4.0)  # out of range: heavy whiffs, no hitstop
		_step(sim, H)
		# After advancing to frame (total - early), the next tick (the press)
		# is frame total-early+1, i.e. 'early' ticks before the first neutral tick.
		_advance_to_frame(sim, heavy.total_frames() - early)
		_step(sim, L)        # tap Light during recovery
		_step(sim, 0, 0, early + 2)
		var lights: Array[CombatEvent] = []
		for e: CombatEvent in _events(sim, CombatEvent.Type.ATTACK_START, 0):
			if e.move_id == &"kairo_light_punch":
				lights.append(e)
		var should: bool = early <= window
		if (lights.size() == 1) != should:
			f.append("pressed %d ticks before neutral: light started=%s, expected %s" % [early, lights.size() == 1, should])
		elif should:
			var heavy_start: int = _events(sim, CombatEvent.Type.ATTACK_START, 0)[0].tick
			if lights[0].tick != heavy_start + heavy.total_frames():
				f.append("buffered light started at t%d, first neutral tick is t%d" % [lights[0].tick, heavy_start + heavy.total_frames()])
	return f


func test_buffer_not_used_while_stunned_reversal_within_window() -> Array[String]:
	var f: Array[String] = []
	var light: MoveData = _move(&"LIGHT")
	var window: int = _tuning().input_buffer_ticks
	for early: int in [2, window + 4]:
		var sim := _sim(0.9)
		# P1 hits P2 with a light; P2 is in hitstun for hitstun_frames after hitstop.
		for _t: int in light.startup_frames:
			sim.step([FighterInputFrame.with_buttons(L), FighterInputFrame.neutral()])
		for _t: int in light.hitstop_frames:
			sim.step([FighterInputFrame.neutral(), FighterInputFrame.neutral()])
		# Hitstun of N: P2 acts on tick N+1. Press 'early' ticks before that.
		var wait: int = light.hitstun_frames + 1 - early
		for _t: int in wait - 1:
			sim.step([FighterInputFrame.neutral(), FighterInputFrame.neutral()])
		sim.step([FighterInputFrame.neutral(), FighterInputFrame.with_buttons(H)])
		var started_during_stun: bool = false
		for _t: int in early + 3:
			var was_stunned: bool = sim.fighters[1].action == FighterState.Action.HITSTUN
			sim.step([FighterInputFrame.neutral(), FighterInputFrame.neutral()])
			if was_stunned and sim.fighters[1].action == FighterState.Action.ATTACK and sim.fighters[1].stun_remaining > 0:
				started_during_stun = true
		if started_during_stun:
			f.append("P2 attacked while still in hitstun")
		var p2_starts: int = _events(sim, CombatEvent.Type.ATTACK_START, 1).size()
		var should: bool = early <= window
		if (p2_starts == 1) != should:
			f.append("reversal pressed %d early: started=%s expected %s" % [early, p2_starts == 1, should])
	return f


func test_buffer_ages_freeze_during_hitstop() -> Array[String]:
	var f: Array[String] = []
	var sim := _sim(0.9)
	var light: MoveData = _move(&"LIGHT")
	_step(sim, L, 0, light.startup_frames)  # hit → hitstop
	_step(sim, 0)                            # release
	_step(sim, K)                            # press kick during hitstop
	var age_at_press: int = sim.fighters[0].buffer[-1].y
	_step(sim, K, 0, 2)
	if sim.hitstop_remaining > 0 and sim.fighters[0].buffer[-1].y != age_at_press:
		f.append("buffer aged during hitstop")
	return f


# --- cancels --------------------------------------------------------------------

func test_documented_route_light_light_kick() -> Array[String]:
	var f: Array[String] = []
	var sim := _sim(0.9)
	# Mash L, L, K: press each button every other tick until it starts.
	var route: Array[int] = [L, L, K]
	var k: int = 0
	var starts_seen: int = 0
	for t: int in 200:
		var b: int = route[k] if k < route.size() and t % 2 == 0 else 0
		_step(sim, b)
		var starts: int = _events(sim, CombatEvent.Type.ATTACK_START, 0).size()
		if starts > starts_seen:
			starts_seen = starts
			k += 1
	var hits: Array[CombatEvent] = _events(sim, CombatEvent.Type.HIT, 0)
	if hits.size() != 3:
		return ["route L,L,K should hit 3 times, log:\n%s" % sim.combat_log.to_text()]
	# D-113: the second Light is the string's One-Two Cross (55)
	var expected_dmg: Array[int] = [35, 55, 40]   # low kick (50) scaled to 80 %
	var expected_pct: Array[int] = [100, 100, 80]
	for h: int in 3:
		if hits[h].combo_hits != h + 1 or hits[h].damage != expected_dmg[h] or hits[h].scaling_percent != expected_pct[h]:
			f.append("hit %d: combo %d dmg %d pct %d" % [h + 1, hits[h].combo_hits, hits[h].damage, hits[h].scaling_percent])
	var starts_ev: Array[CombatEvent] = _events(sim, CombatEvent.Type.ATTACK_START, 0)
	if starts_ev[1].cancel_from != &"kairo_light_punch" or starts_ev[2].cancel_from != &"kairo_string_cross" \
			or starts_ev[1].move_id != &"kairo_string_cross":
		f.append("route was not performed through the jab, cross, low kick string")
	if sim.fighters[1].combo_hits != 0 or sim.fighters[1].health != 1000 - 130:
		f.append("after combo: P2 combo %d (should reset on recovery), hp %d (expected 870)" % [
			sim.fighters[1].combo_hits, sim.fighters[1].health])
	return f


func test_invalid_cancel_routes_rejected() -> Array[String]:
	var f: Array[String] = []
	# [first, second, expect_cancel]
	var cases: Array = [
		[L, H, false],   # light cannot cancel into heavy
		[K, H, false],   # kick cannot cancel into heavy
		[K, L, true],    # Kairo's low kick cancels into the jab (D-062)
		[H, L, false],   # heavy cannot cancel into light
		[L, K, true],
		[L, L, true],
	]
	for c: Array in cases:
		var sim := _sim(0.9)
		var first: MoveData = sim.definitions[0].move_for({L: &"LIGHT", H: &"HEAVY", K: &"KICK"}[c[0]])
		_step(sim, c[0], 0, first.startup_frames)  # connects
		_step(sim, 0)
		_step(sim, c[1])                           # press during hitstop
		_step(sim, 0, 0, first.hitstop_frames + 4)
		var cancels: int = 0
		for e: CombatEvent in _events(sim, CombatEvent.Type.ATTACK_START, 0):
			if e.cancel_from != &"":
				cancels += 1
		if (cancels == 1) != c[2]:
			f.append("%s -> button %d: cancel=%s expected %s" % [first.id, c[1], cancels == 1, c[2]])
	return f


func test_no_cancel_on_whiff_or_outside_window() -> Array[String]:
	var f: Array[String] = []
	var light: MoveData = _move(&"LIGHT")
	# Whiff: pressing light during a whiffed light's active frames is no cancel.
	var sim := _sim(4.0)
	_step(sim, L)
	_advance_to_frame(sim, light.startup_frames)
	_step(sim, 0)
	_step(sim, L)
	_step(sim, 0, 0, 3)
	for e: CombatEvent in _events(sim, CombatEvent.Type.ATTACK_START, 0):
		if e.cancel_from != &"":
			f.append("cancelled a whiffed attack")
	# Too late: press after last_active + grace.
	var tuning: CombatTuning = _tuning()
	var late_frame: int = light.startup_frames + light.active_frames - 1 + tuning.cancel_grace_frames + 1
	var sim2 := _sim(0.9)
	_step(sim2, L)
	if not _advance_to_frame(sim2, late_frame, L):
		return ["could not reach frame %d" % late_frame]
	_step(sim2, 0)  # the frame check happens on the next tick, so release+press lands at late_frame+1
	_step(sim2, L)
	for e: CombatEvent in _events(sim2, CombatEvent.Type.ATTACK_START, 0):
		if e.cancel_from != &"":
			f.append("cancel allowed after the cancel window (frame %d)" % sim2.fighters[0].move_frame)
	# Cancel on block is allowed.
	var sim3 := _sim(0.9)
	_step(sim3, L, B, light.startup_frames)
	_step(sim3, 0, B)
	_step(sim3, L, B)
	_step(sim3, 0, B, light.hitstop_frames + 2)
	var cancelled: bool = false
	for e: CombatEvent in _events(sim3, CombatEvent.Type.ATTACK_START, 0):
		cancelled = cancelled or e.cancel_from != &""
	if not cancelled:
		f.append("light -> light cancel on block should be allowed")
	return f


func test_same_move_repeat_limit() -> Array[String]:
	var f: Array[String] = []
	var sim := _sim(0.7)
	for t: int in 120:
		_step(sim, L if t % 2 == 0 else 0)
	var chain_cancels: int = 0
	for e: CombatEvent in _events(sim, CombatEvent.Type.ATTACK_START, 0):
		if e.cancel_from == &"kairo_light_punch":
			chain_cancels += 1
	# Each chain may hold at most 2 lights → at most 1 light->light cancel per
	# chain, and the mash must never produce a 3-light chain.
	var max_combo: int = 0
	for e: CombatEvent in _events(sim, CombatEvent.Type.HIT, 0):
		max_combo = maxi(max_combo, e.combo_hits)
	if max_combo > _tuning().max_same_move_in_chain:
		f.append("light mash produced a %d-hit combo (limit %d)" % [max_combo, _tuning().max_same_move_in_chain])
	if chain_cancels == 0:
		f.append("light mash never cancelled (route L,L should work)")
	return f


# --- infinite-combo search ----------------------------------------------------

## Mash a fixed sequence of attack buttons (each pressed every other tick until
## that attack starts), optionally walking forward. Returns the longest combo.
func _run_route(route: Array[int], cornered: bool, walk: bool, sep: float) -> Dictionary:
	var sim := _sim(sep, cornered)
	var k: int = 0
	var starts_seen: int = 0
	var max_combo: int = 0
	var after_route: int = 0
	for t: int in 600:
		var b: int = route[k] if k < route.size() and t % 2 == 0 else 0
		_step(sim, b, 0, 1, 1 if walk else 0)
		var starts: int = _events(sim, CombatEvent.Type.ATTACK_START, 0).size()
		if starts > starts_seen:
			starts_seen = starts
			k += 1
		if k >= route.size():
			after_route += 1
			if after_route > 120 and sim.fighters[1].is_neutral() and sim.fighters[0].is_neutral():
				break
	for e: CombatEvent in _events(sim, CombatEvent.Type.HIT, 0):
		max_combo = maxi(max_combo, e.combo_hits)
	return {"max_combo": max_combo, "p2_neutral": sim.fighters[1].is_neutral()}


func test_no_infinite_combo_exhaustive_routes() -> Array[String]:
	# Every route of 1..5 attacks from {L, K, H}, mashed so that every cancel
	# and every possible link is attempted, mid-screen and in the corner, with
	# and without walking forward. The longest possible combo must stay bounded
	# (L, L, K = 3) and the defender must always get back to neutral.
	var f: Array[String] = []
	var buttons: Array[int] = [L, K, H]
	var routes: Array = [[]]
	var all_routes: Array = []
	for _len: int in 5:
		var next: Array = []
		for r: Array in routes:
			for b: int in buttons:
				var nr: Array = r.duplicate()
				nr.append(b)
				next.append(nr)
				all_routes.append(nr)
		routes = next
	var worst: int = 0
	var worst_desc: String = ""
	for r: Array in all_routes:
		var typed: Array[int] = []
		typed.assign(r)
		for cornered: bool in [false, true]:
			for walk: bool in [false, true]:
				var res: Dictionary = _run_route(typed, cornered, walk, 0.75)
				if res.max_combo > worst:
					worst = res.max_combo
					worst_desc = "%s corner=%s walk=%s" % [r, cornered, walk]
				if not res.p2_neutral:
					f.append("defender never recovered: route %s corner=%s walk=%s" % [r, cornered, walk])
	if worst > 3:
		f.append("combo of %d hits found (%s) — exceeds the designed max of 3" % [worst, worst_desc])
	if worst < 3:
		f.append("designed 3-hit route not found by the search (max %d)" % worst)
	if not f.is_empty():
		f.append("searched %d routes x 4 situations" % all_routes.size())
	return f


# --- movement + attack, training -------------------------------------------------

func test_simultaneous_movement_and_attack() -> Array[String]:
	var f: Array[String] = []
	var sim := _sim(3.0)
	_step(sim, 0, 0, 5, 1)          # walking right
	var x_before: float = sim.fighters[0].position_x
	_step(sim, L, 0, 1, 1)          # press light while still holding right
	if sim.fighters[0].action != FighterState.Action.ATTACK:
		return ["light did not start while holding a direction"]
	_step(sim, L, 0, 10, 1)
	if absf(sim.fighters[0].position_x - (x_before)) > 1e-6:
		f.append("fighter moved during its attack")
	_step(sim, 0, 0, 20, 1)         # attack over, still holding right
	if sim.fighters[0].action != FighterState.Action.WALK or sim.fighters[0].position_x <= x_before:
		f.append("walking did not resume after the attack (%s)" % sim.fighters[0].action_name())
	return f


func test_training_rules() -> Array[String]:
	var f: Array[String] = []
	var sim := _sim(0.9)
	var d := MatchDirector.new(load("res://data/rules/training.tres"))
	d.start_match(sim)
	if d.phase != MatchDirector.Phase.FIGHT:
		f.append("training should start in FIGHT, got %s" % d.phase_name())
	if sim.ko_enabled:
		f.append("KO should be disabled in training")
	sim.fighters[0].position_x = -0.45
	sim.fighters[1].position_x = 0.45
	var timer: int = d.timer_ticks
	# Set low health and land the hit with direct sim steps (the director
	# would refill a neutral fighter immediately, which is training behaviour).
	sim.fighters[1].health = 20
	for t: int in 5:
		sim.step([FighterInputFrame.with_buttons(L), FighterInputFrame.neutral()])
	if sim.fighters[1].health != 1 or sim.fighters[1].action == FighterState.Action.KO:
		f.append("training hit should stop at 1 hp, got %d %s" % [sim.fighters[1].health, sim.fighters[1].action_name()])
	for t: int in 80:
		d.step(sim, [FighterInputFrame.neutral(), FighterInputFrame.neutral()])
	if sim.fighters[1].health != sim.definitions[1].base_health:
		f.append("health did not refill after the combo ended (%d)" % sim.fighters[1].health)
	if d.timer_ticks != timer or d.phase != MatchDirector.Phase.FIGHT or not d.results.is_empty():
		f.append("training timer/rounds changed")
	sim.fighters[0].position_x = 4.0
	d.training_reset(sim)
	if sim.fighters[0].position_x != sim.arena.p1_spawn_x:
		f.append("training reset did not restore positions")
	return f
