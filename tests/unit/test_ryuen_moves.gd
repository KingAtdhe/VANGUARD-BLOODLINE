extends RefCounted
## Ryuen's own move set (D-068): multi-hit Chain Punch, a counter that turns
## the attacker round, an ultimate that is a counter stance, deflecting
## block, evasive step, throw.

const L: int = FighterInputFrame.BUTTON_LIGHT
const H: int = FighterInputFrame.BUTTON_HEAVY
const K: int = FighterInputFrame.BUTTON_KICK
const S: int = FighterInputFrame.BUTTON_SPECIAL
const B: int = FighterInputFrame.BUTTON_BLOCK
const U: int = FighterInputFrame.BUTTON_ULTIMATE


func _def(id: String) -> FighterDefinition:
	return load("res://data/fighters/%s.tres" % id)


func _sim(p1: String = "ryuen", p2: String = "kairo", gap: float = 0.9) -> CombatSimulation:
	var sim := CombatSimulation.new()
	sim.setup(load("res://data/arenas/greybox_arena.tres"), _def(p1), _def(p2),
		load("res://data/rules/combat_tuning.tres"))
	sim.fighters[0].position_x = -gap * 0.5
	sim.fighters[1].position_x = gap * 0.5
	return sim


func _count(sim: CombatSimulation, type: CombatEvent.Type, actor: int, move_id: StringName = &"") -> int:
	var n: int = 0
	for e: CombatEvent in sim.combat_log.all_events():
		if e.type == type and e.actor == actor and (move_id == &"" or e.move_id == move_id):
			n += 1
	return n


func _last(sim: CombatSimulation, type: CombatEvent.Type, actor: int) -> CombatEvent:
	var found: CombatEvent = null
	for e: CombatEvent in sim.combat_log.all_events():
		if e.type == type and e.actor == actor:
			found = e
	return found


func _n() -> FighterInputFrame:
	return FighterInputFrame.neutral()


func _idle(sim: CombatSimulation, ticks: int, p2: FighterInputFrame = null) -> void:
	for _i: int in ticks:
		sim.step([_n(), p2 if p2 != null else _n()])


func _press(button: int, dir: int = 0, down: bool = false) -> FighterInputFrame:
	return FighterInputFrame.with_buttons(button, dir, -1 if down else 0)


## Waits until P1's attack has landed [param hits] times and hitstop is over, then presses [param next].
func _cancel_into(sim: CombatSimulation, next: FighterInputFrame, hits: int = 1, limit: int = 80) -> bool:
	var start: int = _count(sim, CombatEvent.Type.HIT, 0)
	for _i: int in limit:
		if _count(sim, CombatEvent.Type.HIT, 0) - start >= hits and sim.hitstop_remaining == 0:
			sim.step([next, _n()])
			return true
		sim.step([_n(), _n()])
	return false


# --- data ----------------------------------------------------------------------

func test_move_set_is_valid_and_complete() -> Array[String]:
	var f: Array[String] = []
	var def: FighterDefinition = _def("ryuen")
	f.append_array(def.validate())
	for m: MoveData in def.moves:
		if String(m.id).begins_with("kairo_") and not m.activates_surge:
			f.append("still uses %s" % m.id)
	for pattern: StringName in [&"LIGHT", &"HEAVY", &"KICK", &"DOWN_HEAVY", &"SPECIAL", &"FORWARD_SPECIAL",
			&"BACK_SPECIAL", &"DOWN_SPECIAL", &"ULTIMATE"]:
		if def.move_for(pattern) == null:
			f.append("no move for %s" % pattern)
	if def.base_health != 1000 or def.block_pushes_attacker <= 0.0:
		f.append("expected 1000 health and a deflecting block")
	# Ryuen walks slower than the agile fighters. Drakon (heavy) and, since
	# D-107, Kairo (the owner asked for a slower, deliberate walk) are slower.
	var walks: Array[float] = []
	for id: String in ["seraphina", "nox", "vexa"]:
		walks.append(_def(id).movement.walk_forward_speed)
	if def.movement.fighter_id != &"ryuen" or def.movement.walk_forward_speed >= walks.min():
		f.append("Ryuen should walk slower than Seraphina, Nox and Vexa (%s vs %s)" % [def.movement.walk_forward_speed, walks])
	return f


func test_frame_data_matches_the_design() -> Array[String]:
	var f: Array[String] = []
	var def: FighterDefinition = _def("ryuen")
	var want: Dictionary = {&"ryuen_palm_heel": [5, 3, 10], &"ryuen_chain_punch": [9, 6, 16], &"ryuen_shin_stamp": [8, 3, 14],
		&"ryuen_sinking_elbow": [10, 3, 16], &"ryuen_mountain_push": [15, 4, 22]}
	for id: StringName in want:
		var m: MoveData = def.move_for_id(id)
		if m == null:
			f.append("missing %s" % id)
		elif [m.startup_frames, m.active_frames, m.recovery_frames] != want[id]:
			f.append("%s is %d/%d/%d, design %s" % [id, m.startup_frames, m.active_frames, m.recovery_frames, want[id]])
	var chain: MoveData = def.move_for(&"HEAVY")
	if chain.rehit_interval != 2 or chain.hit_count() != 3:
		f.append("Chain Punch should be three hits, two frames each")
	var wave: MoveData = def.move_for(&"BACK_SPECIAL")
	if wave.total_frames() != 36 or wave.counter_start_frame != 3 or wave.counter_end_frame != 18 \
			or not wave.counter_switches_sides or wave.counter_followup == null:
		f.append("Returning Wave should be a 36-frame counter (3-18) that switches sides")
	if wave.counter_levels != [MoveData.HitLevel.HIGH, MoveData.HitLevel.MID, MoveData.HitLevel.LOW]:
		f.append("Returning Wave should catch every strike (high, mid, low) and nothing else")
	var step: MoveData = def.move_for(&"FORWARD_SPECIAL")
	if step.total_frames() != 20 or step.invuln_start_frame != 2 or step.invuln_end_frame != 11 or not step.no_hitbox:
		f.append("Flowing Step should be 20 frames, invulnerable 2-11, with no attack")
	var ult: MoveData = def.move_for(&"ULTIMATE")
	for m: MoveData in def.moves_for(&"ULTIMATE"):
		if m.requires_surge:
			ult = m
	if not ult.is_counter() or ult.counter_start_frame != 4 or ult.counter_end_frame != 30 or not ult.consumes_all_meter:
		f.append("Thousand Rivers should be a counter stance (4-30) that spends the meter")
	if def.move_for(&"KICK").hit_level != MoveData.HitLevel.LOW or not def.move_for(&"DOWN_SPECIAL").is_throw():
		f.append("Shin Stamp should be LOW and down + SP a throw")
	if def.move_for(&"LIGHT").advantage_on_block() < -2:
		f.append("Palm Heel should be safe on block (is %d)" % def.move_for(&"LIGHT").advantage_on_block())
	return f


# --- multi-hit -----------------------------------------------------------------

func test_chain_punch_hits_three_times() -> Array[String]:
	var f: Array[String] = []
	var chain: MoveData = _def("ryuen").move_for(&"HEAVY")
	var sim: CombatSimulation = _sim()
	sim.step([_press(H), _n()])
	_idle(sim, 70)
	var hits: Array[CombatEvent] = []
	for e: CombatEvent in sim.combat_log.all_events():
		if e.type == CombatEvent.Type.HIT and e.actor == 0:
			hits.append(e)
	if hits.size() != 3:
		f.append("Chain Punch landed %d hits, expected 3. log:\n%s" % [hits.size(), sim.combat_log.to_text()])
		return f
	if hits[2].combo_hits != 3:
		f.append("the three hits should be one combo (last hit is combo hit %d)" % hits[2].combo_hits)
	if sim.fighters[0].meter != 3 * chain.meter_gain_on_hit:
		f.append("meter %d after three hits, expected %d" % [sim.fighters[0].meter, 3 * chain.meter_gain_on_hit])
	if _count(sim, CombatEvent.Type.WHIFF, 0) != 0:
		f.append("a connected Chain Punch was logged as a whiff")
	# more meter per use than any other fighter's normal
	for id: String in ["kairo", "drakon", "seraphina", "nox", "vexa"]:
		for m: MoveData in _def(id).moves:
			if m.tags.has("normal") and m.meter_gain_on_hit * m.hit_count() >= 3 * chain.meter_gain_on_hit:
				f.append("%s builds as much meter as Chain Punch" % m.id)
	return f


func test_chain_punch_blocked_is_three_blocks_and_a_single_hit_move_still_hits_once() -> Array[String]:
	var f: Array[String] = []
	var sim: CombatSimulation = _sim()
	var guard: FighterInputFrame = FighterInputFrame.with_buttons(B)
	sim.step([_press(H), guard])
	_idle(sim, 70, guard)
	if _count(sim, CombatEvent.Type.BLOCK, 0, &"ryuen_chain_punch") != 3 or _count(sim, CombatEvent.Type.HIT, 0) != 0:
		f.append("a blocked Chain Punch should be blocked three times. log:\n%s" % sim.combat_log.to_text())
	var one: CombatSimulation = _sim()
	one.step([_press(L), _n()])
	_idle(one, 40)
	if _count(one, CombatEvent.Type.HIT, 0) != 1:
		f.append("Palm Heel should hit exactly once")
	return f


# --- counters ------------------------------------------------------------------

func test_returning_wave_catches_strikes_turns_the_attacker_and_hits_from_behind() -> Array[String]:
	var f: Array[String] = []
	# [attacker, button, down, move id]: a mid, a low and an overhead
	for c: Array in [["kairo", L, false, &"kairo_light_punch"], ["kairo", K, true, &"kairo_leg_sweep"],
			["nox", H, true, &"nox_drop_heel"]]:
		var move: MoveData = _def(c[0]).move_for_id(c[3])
		var sim: CombatSimulation = _sim("ryuen", c[0], 0.9)
		sim.step([_n(), FighterInputFrame.with_buttons(c[1], 0, -1 if c[2] else 0)])
		_idle(sim, maxi(0, move.startup_frames - 6))
		sim.step([_press(S, -1), _n()])
		for _t: int in 12:
			if _count(sim, CombatEvent.Type.COUNTER, 0) > 0:
				break
			_idle(sim, 1)
		if _count(sim, CombatEvent.Type.COUNTER, 0, &"ryuen_returning_wave") != 1:
			f.append("Returning Wave did not catch %s. log:\n%s" % [c[3], sim.combat_log.to_text()])
			continue
		# The attacker started on the right; it must now be on Ryuen's left, facing away.
		if sim.fighters[1].position_x >= sim.fighters[0].position_x:
			f.append("%s: the attacker was not turned past Ryuen" % c[3])
		if sim.fighters[0].facing != -1 or sim.fighters[1].facing != -1:
			f.append("%s: Ryuen should face the attacker's back (facings %d / %d)" % [
				c[3], sim.fighters[0].facing, sim.fighters[1].facing])
		_idle(sim, 60)
		if _count(sim, CombatEvent.Type.HIT, 0, &"ryuen_wave_palm") != 1 or sim.fighters[0].health != 1000:
			f.append("%s: the palm in the back did not land cleanly. log:\n%s" % [c[3], sim.combat_log.to_text()])
		if sim.fighters[0].facing != -1 * signi(int(signf(sim.fighters[0].position_x - sim.fighters[1].position_x))):
			f.append("%s: fighters do not face each other afterwards" % c[3])
	return f


func test_returning_wave_reaches_a_long_range_attacker_and_respects_walls() -> Array[String]:
	var f: Array[String] = []
	# Seraphina's side kick from far out: the follow-up has to close the distance.
	var kick: MoveData = _def("seraphina").move_for(&"HEAVY")
	var sim: CombatSimulation = _sim("ryuen", "seraphina", 1.6)
	sim.step([_n(), FighterInputFrame.with_buttons(H)])
	_idle(sim, kick.startup_frames - 6)
	sim.step([_press(S, -1), _n()])
	_idle(sim, 70)
	if _count(sim, CombatEvent.Type.COUNTER, 0) != 1 or _count(sim, CombatEvent.Type.HIT, 0, &"ryuen_wave_palm") != 1:
		f.append("the palm did not reach an attacker caught at 1.6 m. log:\n%s" % sim.combat_log.to_text())
	# Ryuen with his back to the left wall: there is no room behind him, nobody may leave the arena.
	var wall: CombatSimulation = _sim("ryuen", "kairo", 0.9)
	wall.fighters[0].position_x = wall.arena.left_bound + wall.profile(0).pushbox_half_width
	wall.fighters[1].position_x = wall.fighters[0].position_x + 0.9
	wall.step([_n(), FighterInputFrame.with_buttons(L)])
	wall.step([_press(S, -1), _n()])
	_idle(wall, 70)
	for i: int in 2:
		var hw: float = wall.profile(i).pushbox_half_width
		if wall.fighters[i].position_x < wall.arena.left_bound + hw - 0.001 \
				or wall.fighters[i].position_x > wall.arena.right_bound - hw + 0.001:
			f.append("fighter %d left the arena after a counter at the wall" % i)
	if _count(wall, CombatEvent.Type.COUNTER, 0) != 1 or _count(wall, CombatEvent.Type.HIT, 0, &"ryuen_wave_palm") != 1:
		f.append("counter at the wall did not work. log:\n%s" % wall.combat_log.to_text())
	return f


func test_throws_and_projectiles_beat_returning_wave() -> Array[String]:
	var f: Array[String] = []
	var grab: MoveData = _def("drakon").move_for(&"SPECIAL")
	var sim: CombatSimulation = _sim("ryuen", "drakon", 0.9)
	sim.step([_n(), FighterInputFrame.with_buttons(S)])
	_idle(sim, grab.startup_frames - 6)
	sim.step([_press(S, -1), _n()])
	_idle(sim, 50)
	if _count(sim, CombatEvent.Type.COUNTER, 0) != 0 or _count(sim, CombatEvent.Type.HIT, 1, &"drakon_anvil_slam") != 1:
		f.append("a throw should beat Returning Wave. log:\n%s" % sim.combat_log.to_text())
	for delay: int in range(8, 30):
		var shot: CombatSimulation = _sim("ryuen", "vexa", 3.0)
		shot.step([_n(), FighterInputFrame.with_buttons(S)])
		_idle(shot, delay)
		shot.step([_press(S, -1), _n()])
		_idle(shot, 70)
		if _count(shot, CombatEvent.Type.COUNTER, 0) != 0 or _count(shot, CombatEvent.Type.HIT, 1, &"vexa_pulse_shot") != 1:
			f.append("a projectile should beat Returning Wave (delay %d)" % delay)
	return f


func test_thousand_rivers_is_a_counter_that_spends_the_meter_either_way() -> Array[String]:
	var f: Array[String] = []
	# Struck during the stance: the answer lands, the surge and meter are gone.
	var sim: CombatSimulation = _sim()
	sim.fighters[0].meter = 100
	sim.fighters[0].surge_remaining = 300
	sim.step([_press(U), _n()])
	_idle(sim, 8)
	sim.step([_n(), FighterInputFrame.with_buttons(L)])
	_idle(sim, 160)
	var hit: CombatEvent = _last(sim, CombatEvent.Type.HIT, 0)
	if _count(sim, CombatEvent.Type.COUNTER, 0, &"ryuen_thousand_rivers") != 1 or hit == null \
			or hit.move_id != &"ryuen_thousand_rivers_strike":
		f.append("Thousand Rivers did not answer a strike. log:\n%s" % sim.combat_log.to_text())
	elif hit.damage < 250:
		f.append("Thousand Rivers did only %d damage" % hit.damage)
	if sim.fighters[0].health != 1000:
		f.append("Ryuen took damage during a successful Thousand Rivers")
	if sim.fighters[0].meter != 0 or sim.fighters[0].in_surge():
		f.append("the meter should be spent")
	# Nothing hits him: the meter is spent for nothing.
	var miss: CombatSimulation = _sim("ryuen", "kairo", 3.0)
	miss.fighters[0].meter = 100
	miss.fighters[0].surge_remaining = 300
	miss.step([_press(U), _n()])
	_idle(miss, 60)
	if miss.fighters[0].meter != 0 or miss.fighters[0].in_surge() or _count(miss, CombatEvent.Type.HIT, 0) != 0:
		f.append("an unanswered Thousand Rivers should cost the whole meter and do nothing")
	if miss.fighters[0].action != FighterState.Action.IDLE:
		f.append("Ryuen did not recover from the stance")
	# Not in Surge: the button is Surge activation, not the stance.
	var cold: CombatSimulation = _sim()
	cold.fighters[0].meter = 50
	cold.step([_press(U), _n()])
	_idle(cold, 3)
	if _count(cold, CombatEvent.Type.ATTACK_START, 0) != 0:
		f.append("Thousand Rivers started without Surge")
	return f


# --- defence -------------------------------------------------------------------

func test_deflecting_block_pushes_the_attacker_back() -> Array[String]:
	var f: Array[String] = []
	var seps: Array[float] = []
	for defender: String in ["ryuen", "kairo"]:
		var sim: CombatSimulation = _sim("kairo", defender, 0.9)
		var guard: FighterInputFrame = FighterInputFrame.with_buttons(B)
		sim.step([FighterInputFrame.with_buttons(H), guard])
		for _t: int in 60:
			sim.step([_n(), guard])
		seps.append(sim.separation())
	var extra: float = seps[0] - seps[1]
	if absf(extra - _def("ryuen").block_pushes_attacker) > 0.01:
		f.append("Ryuen's block should add %.2f m of distance, added %.2f" % [_def("ryuen").block_pushes_attacker, extra])
	return f


func test_flowing_step_lets_an_attack_pass() -> Array[String]:
	var f: Array[String] = []
	var sim: CombatSimulation = _sim()
	# Kairo's jab (5 f) and the step start together: the jab arrives on step frame 5.
	sim.step([_press(S, 1), FighterInputFrame.with_buttons(L)])
	_idle(sim, 40)
	if _count(sim, CombatEvent.Type.HIT, 1) != 0 or sim.fighters[0].health != 1000:
		f.append("Flowing Step was hit during its evasive frames")
	if _count(sim, CombatEvent.Type.HIT, 0) != 0:
		f.append("Flowing Step should not attack")
	# After frame 11 he can be hit.
	var late: CombatSimulation = _sim()
	late.step([_press(S, 1), _n()])
	_idle(late, 8)
	late.step([_n(), FighterInputFrame.with_buttons(L)])
	_idle(late, 30)
	if _count(late, CombatEvent.Type.HIT, 1) != 1:
		f.append("Flowing Step should be open after its evasive frames")
	return f


func test_wrist_throw_beats_block() -> Array[String]:
	var f: Array[String] = []
	var sim: CombatSimulation = _sim()
	var guard: FighterInputFrame = FighterInputFrame.with_buttons(B)
	sim.step([_press(S, 0, true), guard])
	_idle(sim, 60, guard)
	if _count(sim, CombatEvent.Type.HIT, 0, &"ryuen_wrist_throw") != 1:
		f.append("the throw should beat a block. log:\n%s" % sim.combat_log.to_text())
	return f


# --- combos --------------------------------------------------------------------

func test_combo_palm_chain_push() -> Array[String]:
	var f: Array[String] = []
	for gap: float in [0.8, 0.95]:
		var sim: CombatSimulation = _sim("ryuen", "kairo", gap)
		sim.fighters[0].meter = 40
		sim.step([_press(L), _n()])
		var ok: bool = _cancel_into(sim, _press(H)) and _cancel_into(sim, _press(S), 3)
		_idle(sim, 80)
		var hit: CombatEvent = _last(sim, CombatEvent.Type.HIT, 0)
		if not ok or hit == null or hit.move_id != &"ryuen_mountain_push" or hit.combo_hits != 5:
			f.append("gap %.2f: Palm Heel, Chain Punch, Mountain Push is not a 5-hit combo. log:\n%s" % [gap, sim.combat_log.to_text()])
		elif sim.separation() < 3.0:
			f.append("Mountain Push should send the opponent across the stage (%.2f m apart)" % sim.separation())
	return f


func test_combo_wave_elbow_chain() -> Array[String]:
	var f: Array[String] = []
	var sim: CombatSimulation = _sim()
	sim.step([_n(), FighterInputFrame.with_buttons(L)])
	sim.step([_press(S, -1), _n()])
	# the palm follows by itself; then Sinking Elbow, then Chain Punch
	var ok: bool = _cancel_into(sim, _press(H, 0, true)) and _cancel_into(sim, _press(H))
	_idle(sim, 80)
	var hit: CombatEvent = _last(sim, CombatEvent.Type.HIT, 0)
	if not ok or _count(sim, CombatEvent.Type.COUNTER, 0) != 1 or hit == null or hit.move_id != &"ryuen_chain_punch" \
			or hit.combo_hits != 5:
		f.append("Returning Wave, Sinking Elbow, Chain Punch should be 5 hits in one combo. log:\n%s" % sim.combat_log.to_text())
	return f


# --- AI ------------------------------------------------------------------------

func test_cpu_ryuen_uses_his_counters() -> Array[String]:
	var f: Array[String] = []
	var profile: AIProfile = (load("res://data/ai/expert.tres") as AIProfile).duplicate()
	profile.block_reaction_chance = 1.0
	profile.counter_chance = 1.0
	profile.ultimate_chance = 1.0
	# Scripted Kairo jabs every 40 ticks at close range.
	var waves: int = 0
	var rivers: int = 0
	for surge: bool in [false, true]:
		var sim: CombatSimulation = _sim("kairo", "ryuen", 0.9)
		sim.ko_enabled = false
		var ai := AIController.new(profile, 1, _def("ryuen"), _def("kairo"), 5)
		for t: int in 1800:
			if surge and sim.fighters[1].surge_remaining < 200 and _count(sim, CombatEvent.Type.COUNTER, 1) == 0:
				sim.fighters[1].meter = 100
				sim.fighters[1].surge_remaining = 300
			ai.observe(AIObservation.from_sim(sim))
			sim.step([FighterInputFrame.with_buttons(H if t % 60 == 5 else 0), ai.next_input()])
		waves += _count(sim, CombatEvent.Type.COUNTER, 1, &"ryuen_returning_wave")
		rivers += _count(sim, CombatEvent.Type.COUNTER, 1, &"ryuen_thousand_rivers")
	if waves == 0:
		f.append("CPU Ryuen never landed Returning Wave against repeated heavy punches")
	if rivers == 0:
		f.append("CPU Ryuen in Surge never landed Thousand Rivers")
	return f


# --- model ---------------------------------------------------------------------

func test_model_has_every_animation_at_the_right_length() -> Array[String]:
	var f: Array[String] = []
	var def: FighterDefinition = _def("ryuen")
	var model: Node = def.model_scene.instantiate()
	var ap: AnimationPlayer = model.find_child("AnimationPlayer", true, false)
	for a: StringName in def.required_animations():
		if not ap.has_animation(a):
			f.append("missing animation %s" % a)
	for m: MoveData in def.moves:
		var anim: StringName = def.resolve_anim(m.animation)
		if ap.has_animation(anim):
			var frames: float = ap.get_animation(anim).length * CombatConstants.TICK_RATE + 1.0
			if absf(frames - m.total_frames()) > 0.01:
				f.append("%s lasts %.1f frames, move has %d" % [anim, frames, m.total_frames()])
	model.free()
	return f
