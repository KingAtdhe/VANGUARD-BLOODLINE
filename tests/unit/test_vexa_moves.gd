extends RefCounted
## Vexa's own move set (D-066): projectile, parry, long normals, close-range
## elbow and knee.

const L: int = FighterInputFrame.BUTTON_LIGHT
const H: int = FighterInputFrame.BUTTON_HEAVY
const K: int = FighterInputFrame.BUTTON_KICK
const S: int = FighterInputFrame.BUTTON_SPECIAL
const B: int = FighterInputFrame.BUTTON_BLOCK
const ROSTER: Array[String] = ["kairo", "drakon", "seraphina", "nox", "vexa"]


func _def(id: String) -> FighterDefinition:
	return load("res://data/fighters/%s.tres" % id)


func _sim(p1: String = "vexa", p2: String = "kairo", gap: float = 0.9) -> CombatSimulation:
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


func _idle(sim: CombatSimulation, ticks: int, p2: FighterInputFrame = null) -> void:
	for _i: int in ticks:
		sim.step([FighterInputFrame.neutral(), p2 if p2 != null else FighterInputFrame.neutral()])


func _n() -> FighterInputFrame:
	return FighterInputFrame.neutral()


## Vexa (P1, facing right) presses a button; forward = +1, back = -1.
func _press(button: int, dir: int = 0, down: bool = false) -> FighterInputFrame:
	return FighterInputFrame.with_buttons(button, dir, -1 if down else 0)


## Steps until P1's current attack has connected and hitstop is over, then
## presses [param next] (a cancel). Returns false if nothing connected.
func _cancel_into(sim: CombatSimulation, next: FighterInputFrame, limit: int = 60) -> bool:
	for _i: int in limit:
		if sim.fighters[0].move_connected and sim.hitstop_remaining == 0:
			sim.step([next, _n()])
			return true
		sim.step([_n(), _n()])
	return false


# --- data ----------------------------------------------------------------------

func test_move_set_is_valid_and_complete() -> Array[String]:
	var f: Array[String] = []
	var def: FighterDefinition = _def("vexa")
	f.append_array(def.validate())
	for m: MoveData in def.moves:
		if String(m.id).begins_with("kairo_") and not m.activates_surge:
			f.append("still uses %s" % m.id)
	for pattern: StringName in [&"LIGHT", &"HEAVY", &"KICK", &"DOWN_HEAVY", &"SPECIAL", &"FORWARD_SPECIAL",
			&"BACK_SPECIAL", &"ULTIMATE"]:
		if def.move_for(pattern) == null:
			f.append("no move for %s" % pattern)
	if def.base_health != 1000 or def.chip_taken_percent != 100:
		f.append("health %d / chip %d%%, expected 1000 / 100%%" % [def.base_health, def.chip_taken_percent])
	if def.movement.fighter_id != &"vexa":
		f.append("Vexa has no movement profile of her own")
	return f


func test_frame_data_matches_the_design() -> Array[String]:
	var f: Array[String] = []
	var def: FighterDefinition = _def("vexa")
	var want: Dictionary = {&"vexa_piston_jab": [6, 3, 11], &"vexa_teep": [11, 4, 18], &"vexa_cut_kick": [10, 4, 17],
		&"vexa_slashing_elbow": [8, 3, 15], &"vexa_overclock_knee": [13, 5, 24], &"vexa_system_overdrive": [9, 4, 46]}
	for id: StringName in want:
		var m: MoveData = def.move_for_id(id)
		if m == null:
			f.append("missing %s" % id)
		elif [m.startup_frames, m.active_frames, m.recovery_frames] != want[id]:
			f.append("%s is %d/%d/%d, design %s" % [id, m.startup_frames, m.active_frames, m.recovery_frames, want[id]])
	var shot: MoveData = def.move_for(&"SPECIAL")
	if shot.startup_frames != 16 or shot.total_frames() != 26 or not shot.is_projectile() \
			or shot.hit_level != MoveData.HitLevel.PROJECTILE:
		f.append("Pulse Shot should fire on frame 16 of 26 as a projectile")
	var guard: MoveData = def.move_for(&"BACK_SPECIAL")
	if guard.total_frames() != 30 or guard.counter_start_frame != 3 or guard.counter_end_frame != 11 \
			or guard.counter_followup != null:
		f.append("Arc Guard should be a 30-frame parry with a 3-11 window and no follow-up")
	if guard.counter_levels != [MoveData.HitLevel.HIGH, MoveData.HitLevel.MID]:
		f.append("Arc Guard should parry HIGH and MID only")
	if def.move_for(&"KICK").hit_level != MoveData.HitLevel.LOW:
		f.append("Cut Kick should be LOW")
	if def.move_for(&"FORWARD_SPECIAL").advantage_on_block() > -10:
		f.append("Overclock Knee should be punishable on block (is %d)" % def.move_for(&"FORWARD_SPECIAL").advantage_on_block())
	if not def.move_for(&"DOWN_HEAVY").can_cancel_into(def.move_for(&"FORWARD_SPECIAL")):
		f.append("Slashing Elbow should cancel into Overclock Knee")
	return f


func test_piston_jab_is_the_longest_light_and_teep_pushes_furthest() -> Array[String]:
	var f: Array[String] = []
	var jab: MoveData = _def("vexa").move_for(&"LIGHT")
	var teep: MoveData = _def("vexa").move_for(&"HEAVY")
	var jab_reach: float = jab.hitbox_center.x + jab.hitbox_size.x * 0.5
	for id: String in ROSTER:
		if id == "vexa":
			continue
		var other: MoveData = _def(id).move_for(&"LIGHT")
		if other.hitbox_center.x + other.hitbox_size.x * 0.5 >= jab_reach:
			f.append("%s reaches as far as the Piston Jab" % other.id)
		for m: MoveData in _def(id).moves:
			if m.tags.has("normal") and m.pushback >= teep.pushback:
				f.append("%s pushes as far as the Teep" % m.id)
	return f


# --- projectile ----------------------------------------------------------------

func test_pulse_shot_fires_on_frame_16_and_hits_across_the_stage() -> Array[String]:
	var f: Array[String] = []
	var sim: CombatSimulation = _sim("vexa", "kairo", 5.5)
	var shot: MoveData = _def("vexa").move_for(&"SPECIAL")
	sim.step([_press(S), _n()])
	var start: int = sim.tick
	_idle(sim, 14)
	if not sim.projectiles.is_empty():
		f.append("projectile exists before frame 16")
	_idle(sim, 1)
	if sim.projectiles.size() != 1 or sim.tick - start + 1 != 16:
		f.append("no projectile on frame 16")
	elif absf(sim.projectiles[0].position_x - (sim.fighters[0].position_x + shot.hitbox_center.x)) > 0.001:
		f.append("projectile did not start in front of Vexa")
	_idle(sim, 60)
	var hit: CombatEvent = _last(sim, CombatEvent.Type.HIT, 0)
	if hit == null or hit.move_id != &"vexa_pulse_shot" or hit.damage != shot.damage:
		f.append("Pulse Shot did not hit from 5.5 m. log:\n%s" % sim.combat_log.to_text())
	if not sim.projectiles.is_empty():
		f.append("projectile still exists after it hit")
	if _count(sim, CombatEvent.Type.WHIFF, 0) != 0:
		f.append("a fired Pulse Shot was logged as a whiff")
	if sim.fighters[0].action != FighterState.Action.IDLE:
		f.append("Vexa did not recover")
	return f


func test_pulse_shot_is_blocked_by_either_guard() -> Array[String]:
	var f: Array[String] = []
	var shot: MoveData = _def("vexa").move_for(&"SPECIAL")
	for low: bool in [false, true]:
		var sim: CombatSimulation = _sim("vexa", "kairo", 4.0)
		var guard: FighterInputFrame = FighterInputFrame.with_buttons(B, 0, -1 if low else 0)
		sim.step([_press(S), guard])
		_idle(sim, 60, guard)
		if _count(sim, CombatEvent.Type.BLOCK, 0, &"vexa_pulse_shot") != 1 or _count(sim, CombatEvent.Type.HIT, 0) != 0:
			f.append("%s guard did not block the shot" % ("low" if low else "standing"))
		if 1000 - sim.fighters[1].health != shot.chip_damage:
			f.append("chip %d, expected %d" % [1000 - sim.fighters[1].health, shot.chip_damage])
	return f


func test_only_one_pulse_shot_on_screen() -> Array[String]:
	var f: Array[String] = []
	# Kairo walks away at max separation so the first shot is in flight for long.
	var sim: CombatSimulation = _sim("vexa", "kairo", 6.0)
	var shot: MoveData = _def("vexa").move_for(&"SPECIAL")
	sim.step([_press(S), _n()])
	_idle(sim, shot.total_frames())
	if sim.projectiles.size() != 1:
		f.append("expected the first shot to be in flight, found %d" % sim.projectiles.size())
	sim.step([_press(S), _n()])
	_idle(sim, 3)
	if _count(sim, CombatEvent.Type.ATTACK_START, 0) != 1:
		f.append("a second Pulse Shot started while the first was in flight")
	_idle(sim, 60)
	if not sim.projectiles.is_empty():
		f.append("first shot never ended")
	sim.step([_press(S), _n()])
	_idle(sim, 20)
	if _count(sim, CombatEvent.Type.PROJECTILE_FIRED, 0) != 2:
		f.append("could not fire again after the first shot ended")
	return f


func test_shot_passes_through_an_invulnerable_fighter_and_ends_at_the_wall() -> Array[String]:
	var f: Array[String] = []
	# Nox's Shade Step has no hurtbox on frames 4-14; timed so the shot arrives then.
	var passed: bool = false
	for delay: int in range(10, 40):
		var sim: CombatSimulation = _sim("vexa", "nox", 4.0)
		sim.step([_press(S), _n()])
		_idle(sim, delay)
		sim.step([_n(), FighterInputFrame.with_buttons(S)])
		_idle(sim, 90)
		if not sim.projectiles.is_empty():
			f.append("delay %d: the shot never ended" % delay)
		if _count(sim, CombatEvent.Type.HIT, 0) == 0 and _count(sim, CombatEvent.Type.BLOCK, 0) == 0:
			passed = true
	if not passed:
		f.append("no timing let the Shade Step pass through the shot")
	return f


func test_interrupted_before_firing_means_no_shot_but_a_fired_shot_keeps_flying() -> Array[String]:
	var f: Array[String] = []
	# Point blank: Kairo's jab (5 f) lands long before frame 16.
	var sim: CombatSimulation = _sim("vexa", "kairo", 0.9)
	sim.step([_press(S), FighterInputFrame.with_buttons(L)])
	_idle(sim, 60)
	if _count(sim, CombatEvent.Type.PROJECTILE_FIRED, 0) != 0:
		f.append("a shot was fired although Vexa was hit during startup")
	# Once fired, the shot no longer depends on her: knock her out of the
	# move right after frame 16 and it still arrives.
	var s2: CombatSimulation = _sim("vexa", "kairo", 5.0)
	s2.step([_press(S), _n()])
	_idle(s2, 16)
	if s2.projectiles.size() != 1:
		f.append("expected a shot in flight")
	s2.fighters[0].action = FighterState.Action.HITSTUN
	s2.fighters[0].move = null
	s2.fighters[0].stun_remaining = 20
	_idle(s2, 60)
	if _count(s2, CombatEvent.Type.HIT, 0, &"vexa_pulse_shot") != 1:
		f.append("the shot vanished when its owner was hit")
	return f


func test_counter_stances_do_not_catch_projectiles() -> Array[String]:
	var f: Array[String] = []
	# Every timing of Kairo's Slip Counter and of a mirror Arc Guard against the shot.
	for target: String in ["kairo", "vexa"]:
		for delay: int in range(8, 34):
			var sim: CombatSimulation = _sim("vexa", target, 3.0)
			sim.step([_press(S), _n()])
			_idle(sim, delay)
			sim.step([_n(), FighterInputFrame.with_buttons(S, 1)])  # P2 faces left: +1 is "back"
			_idle(sim, 70)
			if _count(sim, CombatEvent.Type.COUNTER, 1) != 0:
				f.append("%s countered a projectile (delay %d)" % [target, delay])
			if _count(sim, CombatEvent.Type.HIT, 0, &"vexa_pulse_shot") != 1:
				f.append("%s: shot did not hit through the stance (delay %d)" % [target, delay])
	return f


func test_armour_absorbs_a_projectile() -> Array[String]:
	var f: Array[String] = []
	var absorbed: bool = false
	for delay: int in range(0, 30):
		var sim: CombatSimulation = _sim("vexa", "drakon", 3.2)
		sim.fighters[1].meter = 100
		sim.step([_press(S), _n()])
		_idle(sim, delay)
		sim.step([_n(), FighterInputFrame.with_buttons(S, -1)])  # Forge Charge (toward)
		for _t: int in 80:
			sim.step([_n(), _n()])
			var ev: CombatEvent = _last(sim, CombatEvent.Type.HIT, 0)
			if ev != null and ev.armored and not absorbed:
				absorbed = true
				if sim.fighters[1].action != FighterState.Action.ATTACK or sim.fighters[1].health >= 1150:
					f.append("armour should take the damage and keep charging")
				if not sim.projectiles.is_empty():
					f.append("the absorbed shot was not used up")
	if not absorbed:
		f.append("Forge Charge never absorbed a Pulse Shot")
	return f


func test_mirror_shots_clash() -> Array[String]:
	var f: Array[String] = []
	var sim: CombatSimulation = _sim("vexa", "vexa", 5.0)
	sim.step([_press(S), FighterInputFrame.with_buttons(S)])
	_idle(sim, 70)
	var clashes: int = 0
	for e: CombatEvent in sim.combat_log.all_events():
		if e.type == CombatEvent.Type.PROJECTILE_CLASH:
			clashes += 1
	if clashes != 1 or _count(sim, CombatEvent.Type.HIT, 0) + _count(sim, CombatEvent.Type.HIT, 1) != 0:
		f.append("two Pulse Shots should cancel each other. log:\n%s" % sim.combat_log.to_text())
	if not sim.projectiles.is_empty():
		f.append("projectiles left after the clash")
	return f


func test_projectile_pushback_never_moves_the_shooter() -> Array[String]:
	var f: Array[String] = []
	var sim: CombatSimulation = _sim("vexa", "kairo", 0.9)
	# Kairo with his back on the right wall, Vexa 3 m away.
	sim.fighters[1].position_x = sim.arena.right_bound - sim.profile(1).pushbox_half_width
	sim.fighters[0].position_x = sim.fighters[1].position_x - 3.0
	var x0: float = sim.fighters[0].position_x
	sim.step([_press(S), _n()])
	_idle(sim, 70)
	if _count(sim, CombatEvent.Type.HIT, 0) != 1:
		f.append("shot did not hit the cornered fighter")
	if absf(sim.fighters[0].position_x - x0) > 0.0001:
		f.append("the shooter slid %.3f m" % (sim.fighters[0].position_x - x0))
	return f


func test_projectiles_are_deterministic_and_cleared_on_reset() -> Array[String]:
	var f: Array[String] = []
	var texts: Array[String] = []
	for _run: int in 2:
		var sim: CombatSimulation = _sim("vexa", "vexa", 4.0)
		var text: String = ""
		for t: int in 120:
			sim.step([_press(S if t % 31 == 0 else 0), _press(S if t % 37 == 5 else 0, -1 if t % 2 == 0 else 0)])
			text += sim.describe() + "\n"
		texts.append(text)
		if _run == 0:
			sim.step([_press(S), _n()])
			_idle(sim, 18)
			sim.reset()
			if not sim.projectiles.is_empty():
				f.append("reset() left a projectile in flight")
	if texts[0] != texts[1]:
		f.append("same inputs gave different states")
	if not texts[0].contains("proj#"):
		f.append("describe() does not include projectiles")
	return f


# --- parry ---------------------------------------------------------------------

func test_arc_guard_parries_mid_and_high_and_frees_vexa_at_once() -> Array[String]:
	var f: Array[String] = []
	# [attacker, button, down held, move id]
	for c: Array in [["kairo", L, false, &"kairo_light_punch"], ["nox", H, true, &"nox_drop_heel"]]:
		var move: MoveData = _def(c[0]).move_for_id(c[3])
		var sim: CombatSimulation = _sim("vexa", c[0], 0.9)
		# The attack starts first; Arc Guard is pressed so the hit lands on its frame 5.
		sim.step([_n(), FighterInputFrame.with_buttons(c[1], 0, -1 if c[2] else 0)])
		_idle(sim, move.startup_frames - 6)
		sim.step([_press(S, -1), _n()])
		_idle(sim, 5)
		if _count(sim, CombatEvent.Type.COUNTER, 0, &"vexa_arc_guard") != 1:
			f.append("Arc Guard did not parry %s. log:\n%s" % [c[3], sim.combat_log.to_text()])
			continue
		if sim.fighters[0].health != 1000:
			f.append("parried %s still did damage" % c[3])
		if sim.fighters[1].action != FighterState.Action.HITSTUN:
			f.append("attacker is not staggered after the parry")
		while sim.hitstop_remaining > 0:
			_idle(sim, 1)
		_idle(sim, 1)
		if sim.fighters[0].action != FighterState.Action.IDLE:
			f.append("Vexa is not free right after the parry (%s)" % sim.fighters[0].action_name())
	return f


func test_lows_throws_and_late_hits_beat_arc_guard() -> Array[String]:
	var f: Array[String] = []
	# [attacker, button, direction for P2, move id]
	for c: Array in [["kairo", K, 0, &"kairo_low_kick"], ["drakon", S, 0, &"drakon_anvil_slam"]]:
		var move: MoveData = _def(c[0]).move_for_id(c[3])
		var sim: CombatSimulation = _sim("vexa", c[0], 0.9)
		sim.step([_n(), FighterInputFrame.with_buttons(c[1], c[2])])
		_idle(sim, move.startup_frames - 6)
		sim.step([_press(S, -1), _n()])
		_idle(sim, 40)
		if _count(sim, CombatEvent.Type.COUNTER, 0) != 0 or _count(sim, CombatEvent.Type.HIT, 1, c[3]) != 1:
			f.append("%s should beat Arc Guard. log:\n%s" % [c[3], sim.combat_log.to_text()])
	# Whiffed parry: a jab that lands after frame 11 hits her.
	var late: CombatSimulation = _sim("vexa", "kairo", 0.9)
	late.step([_press(S, -1), _n()])
	_idle(late, 9)
	late.step([_n(), FighterInputFrame.with_buttons(L)])   # lands on Arc Guard frame 15
	_idle(late, 30)
	if _count(late, CombatEvent.Type.COUNTER, 0) != 0 or _count(late, CombatEvent.Type.HIT, 1) != 1:
		f.append("a hit after the parry window should land")
	return f


# --- combos --------------------------------------------------------------------

func test_combo_jab_teep_pulse_shot() -> Array[String]:
	var f: Array[String] = []
	for gap: float in [0.8, 1.0, 1.25]:
		var sim: CombatSimulation = _sim("vexa", "kairo", gap)
		sim.step([_press(L), _n()])
		var ok: bool = _cancel_into(sim, _press(H)) and _cancel_into(sim, _press(S))
		_idle(sim, 60)
		var hit: CombatEvent = _last(sim, CombatEvent.Type.HIT, 0)
		if not ok or hit == null or hit.move_id != &"vexa_pulse_shot" or hit.combo_hits != 3:
			f.append("gap %.2f: Jab, Teep, Pulse Shot is not a 3-hit combo. log:\n%s" % [gap, sim.combat_log.to_text()])
		elif sim.separation() < 2.5:
			f.append("gap %.2f: the combo should leave them far apart (%.2f m)" % [gap, sim.separation()])
	return f


func test_combo_cut_kick_elbow_knee() -> Array[String]:
	var f: Array[String] = []
	for gap: float in [0.8, 1.0, 1.25]:
		var sim: CombatSimulation = _sim("vexa", "kairo", gap)
		sim.fighters[0].meter = 50
		sim.step([_press(K), _n()])
		var ok: bool = _cancel_into(sim, _press(H, 0, true)) and _cancel_into(sim, _press(S, 1))
		_idle(sim, 60)
		var hit: CombatEvent = _last(sim, CombatEvent.Type.HIT, 0)
		if not ok or hit == null or hit.move_id != &"vexa_overclock_knee" or hit.combo_hits != 3:
			f.append("gap %.2f: Cut Kick, Elbow, Knee is not a 3-hit combo. log:\n%s" % [gap, sim.combat_log.to_text()])
		var def: FighterDefinition = _def("vexa")
		var gained: int = def.move_for(&"KICK").meter_gain_on_hit + def.move_for(&"DOWN_HEAVY").meter_gain_on_hit \
				+ def.move_for(&"FORWARD_SPECIAL").meter_gain_on_hit
		if ok and sim.fighters[0].meter != 50 + gained - def.move_for(&"FORWARD_SPECIAL").meter_cost:
			f.append("gap %.2f: meter %d after the combo, Overclock Knee should cost %d" % [
				gap, sim.fighters[0].meter, def.move_for(&"FORWARD_SPECIAL").meter_cost])
	return f


func test_combo_parry_elbow_knee() -> Array[String]:
	var f: Array[String] = []
	var sim: CombatSimulation = _sim("vexa", "kairo", 0.9)
	sim.fighters[0].meter = 50
	sim.step([_n(), FighterInputFrame.with_buttons(L)])
	sim.step([_press(S, -1), _n()])
	_idle(sim, 5)
	while sim.hitstop_remaining > 0:
		_idle(sim, 1)
	sim.step([_press(H, 0, true), _n()])
	var ok: bool = _cancel_into(sim, _press(S, 1))
	_idle(sim, 60)
	var hit: CombatEvent = _last(sim, CombatEvent.Type.HIT, 0)
	if not ok or _count(sim, CombatEvent.Type.COUNTER, 0) != 1 or hit == null \
			or hit.move_id != &"vexa_overclock_knee" or hit.combo_hits != 2:
		f.append("parry, Elbow, Knee did not connect as a combo. log:\n%s" % sim.combat_log.to_text())
	if _count(sim, CombatEvent.Type.HIT, 1) != 0:
		f.append("Kairo hit Vexa during the parry combo")
	return f


func test_overclock_knee_travels() -> Array[String]:
	var f: Array[String] = []
	var sim: CombatSimulation = _sim("vexa", "kairo", 2.6)
	sim.fighters[0].meter = 100
	sim.step([_press(S, 1), _n()])
	_idle(sim, 60)
	if _count(sim, CombatEvent.Type.HIT, 0, &"vexa_overclock_knee") != 1:
		f.append("Overclock Knee did not reach from 2.6 m. log:\n%s" % sim.combat_log.to_text())
	return f


# --- AI ------------------------------------------------------------------------

func test_ai_sees_and_blocks_a_pulse_shot_and_uses_it_itself() -> Array[String]:
	var f: Array[String] = []
	var profile: AIProfile = (load("res://data/ai/expert.tres") as AIProfile).duplicate()
	profile.block_reaction_chance = 1.0
	# the blocker has no projectile of its own (Kairo answers with his
	# Fireball since D-101, and the two shots clash)
	var sim: CombatSimulation = _sim("vexa", "drakon", 5.0)
	var ai := AIController.new(profile, 1, _def("drakon"), _def("vexa"), 7)
	for t: int in 70:
		ai.observe(AIObservation.from_sim(sim))
		sim.step([_press(S if t == 0 else 0), ai.next_input()])
	if _count(sim, CombatEvent.Type.BLOCK, 0, &"vexa_pulse_shot") != 1:
		f.append("an AI that always reacts did not block the shot. log:\n%s" % sim.combat_log.to_text())
	# A CPU Vexa fires Pulse Shots of her own over a few seconds at range.
	var sim2: CombatSimulation = _sim("kairo", "vexa", 5.0)
	var vexa_ai := AIController.new(load("res://data/ai/standard.tres"), 1, _def("vexa"), _def("kairo"), 11)
	for _t: int in 900:
		vexa_ai.observe(AIObservation.from_sim(sim2))
		sim2.step([_n(), vexa_ai.next_input()])
	if _count(sim2, CombatEvent.Type.PROJECTILE_FIRED, 1) == 0:
		f.append("CPU Vexa never fired a Pulse Shot in 15 s")
	return f


# --- model ---------------------------------------------------------------------

func test_model_has_every_animation_at_the_right_length() -> Array[String]:
	var f: Array[String] = []
	var def: FighterDefinition = _def("vexa")
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
