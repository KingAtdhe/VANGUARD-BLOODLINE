extends RefCounted
## D-103: Kairo's throw (Light + Kick), Leg Sweep (down + Kick) and Rising
## Uppercut (down + Light), through the real simulation.

const L: int = FighterInputFrame.BUTTON_LIGHT
const K: int = FighterInputFrame.BUTTON_KICK


func _sim(gap: float) -> CombatSimulation:
	var sim := CombatSimulation.new()
	sim.setup(load("res://data/arenas/greybox_arena.tres"), load("res://data/fighters/kairo.tres"),
			load("res://data/fighters/training_dummy.tres"), load("res://data/rules/combat_tuning.tres"))
	sim.fighters[0].position_x = -gap * 0.5
	sim.fighters[1].position_x = gap * 0.5
	return sim


func _in(buttons: int, y: int = 0) -> FighterInputFrame:
	var f := FighterInputFrame.new()
	f.buttons = buttons
	f.move_y = y
	return f


## Runs [param presses] (one input frame per tick, then neutral) and returns
## the moves P1 started and the moves that hit.
func _run(sim: CombatSimulation, presses: Array, ticks: int) -> Dictionary:
	var idle := FighterInputFrame.new()
	for t: int in ticks:
		var p: FighterInputFrame = presses[t] if t < presses.size() else idle
		var ins: Array[FighterInputFrame] = [p, idle]
		sim.step(ins)
	var started: Array[StringName] = []
	var hits: Array[StringName] = []
	var knocked: bool = false
	for ev: CombatEvent in sim.combat_log.all_events():
		if ev.type == CombatEvent.Type.ATTACK_START and ev.actor == 0:
			started.append(ev.move_id)
		elif ev.type == CombatEvent.Type.HIT and ev.actor == 0:
			hits.append(ev.move_id)
		elif ev.type == CombatEvent.Type.KNOCKDOWN and ev.target == 1:
			knocked = true
	return {"started": started, "hits": hits, "knocked": knocked}


func test_light_and_kick_together_throw() -> Array[String]:
	var f: Array[String] = []
	var r: Dictionary = _run(_sim(0.9), [_in(L | K)], 60)
	if not (r.started as Array).has(&"kairo_knee_throw"):
		f.append("L+K together did not start the throw: %s" % [r.started])
	if not (r.hits as Array).has(&"kairo_knee_throw") or not r.knocked:
		f.append("the throw did not connect and knock down: hits %s" % [r.hits])
	# Light a tick before Kick: the jab just started turns into the throw
	var r2: Dictionary = _run(_sim(0.9), [_in(L), _in(L | K)], 60)
	if not (r2.started as Array).has(&"kairo_knee_throw"):
		f.append("Light then Kick one tick later did not throw: %s" % [r2.started])
	# Light alone is still the jab, Kick alone the kick
	var r3: Dictionary = _run(_sim(0.9), [_in(L)], 30)
	if (r3.started as Array).has(&"kairo_knee_throw") or not (r3.started as Array).has(&"kairo_light_punch"):
		f.append("Light alone: %s" % [r3.started])
	return f


func test_leg_sweep_hits_low_and_knocks_down() -> Array[String]:
	var f: Array[String] = []
	var r: Dictionary = _run(_sim(1.2), [_in(K, -1)], 60)
	if not (r.hits as Array).has(&"kairo_leg_sweep"):
		f.append("down + Kick did not land the sweep: %s / %s" % [r.started, r.hits])
	if not r.knocked:
		f.append("the sweep did not knock down")
	var m: MoveData = (load("res://data/fighters/kairo.tres") as FighterDefinition).move_for_id(&"kairo_leg_sweep")
	if m.hit_level != MoveData.HitLevel.LOW:
		f.append("the sweep is not a low")
	return f


func test_rising_uppercut_is_invulnerable_anti_air() -> Array[String]:
	var f: Array[String] = []
	var def: FighterDefinition = load("res://data/fighters/kairo.tres")
	var m: MoveData = def.move_for_id(&"kairo_rising_uppercut")
	if m == null or m.input_pattern != &"DOWN_LIGHT":
		return ["no Rising Uppercut on down + Light"]
	if m.invuln_start_frame != 1 or m.invuln_end_frame < m.startup_frames:
		f.append("not invulnerable through its startup (%d..%d)" % [m.invuln_start_frame, m.invuln_end_frame])
	if m.hitbox_center.y - m.hitbox_size.y * 0.5 > 1.3 or m.hitbox_center.y + m.hitbox_size.y * 0.5 < 2.0:
		f.append("hitbox does not cover the air above him")
	var r: Dictionary = _run(_sim(0.9), [_in(L, -1)], 50)
	if not (r.hits as Array).has(&"kairo_rising_uppercut") or not r.knocked:
		f.append("down + Light did not land a knockdown uppercut: %s / %s" % [r.started, r.hits])
	return f


## The Knee Throw holds its victim from the grab and lands on the knee
## (throw_release_frame): no damage before, the hit on that frame.
func test_knee_throw_holds_then_lands_on_the_knee() -> Array[String]:
	var f: Array[String] = []
	var sim: CombatSimulation = _sim(0.9)
	var idle := FighterInputFrame.new()
	var release: int = (load("res://data/moves/kairo_knee_throw.tres") as MoveData).throw_release_frame
	var held_seen: bool = false
	var hit_frame: int = -1
	var hp0: int = sim.fighters[1].health
	for t: int in 40:
		var ins: Array[FighterInputFrame] = [_in(L | K) if t == 0 else idle, idle]
		sim.step(ins)
		if sim.fighters[1].held_by == 0:
			held_seen = true
			if sim.fighters[1].health != hp0:
				f.append("damage taken while only held")
		for ev: CombatEvent in sim.combat_log.events_since(sim.combat_log.total_count() - 3):
			if ev.type == CombatEvent.Type.HIT and ev.move_id == &"kairo_knee_throw" and hit_frame < 0:
				hit_frame = sim.fighters[0].move_frame
	if not held_seen:
		f.append("the grab did not hold the opponent")
	if hit_frame != release:
		f.append("the throw landed on move frame %d, expected the knee (%d)" % [hit_frame, release])
	if sim.fighters[1].held_by != -1 or sim.fighters[0].throw_target != -1:
		f.append("hold not cleared after the throw")
	return f
