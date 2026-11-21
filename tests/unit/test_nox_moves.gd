extends RefCounted
## Nox's own move set (D-065): pass-through side switch, overhead, lows, weak block.

const L: int = FighterInputFrame.BUTTON_LIGHT
const H: int = FighterInputFrame.BUTTON_HEAVY
const K: int = FighterInputFrame.BUTTON_KICK
const S: int = FighterInputFrame.BUTTON_SPECIAL
const B: int = FighterInputFrame.BUTTON_BLOCK


func _def(id: String) -> FighterDefinition:
	return load("res://data/fighters/%s.tres" % id)


func _sim(p1: String = "nox", p2: String = "kairo", gap: float = 0.9) -> CombatSimulation:
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


func _idle(sim: CombatSimulation, ticks: int, p2: FighterInputFrame = null) -> void:
	for _i: int in ticks:
		sim.step([FighterInputFrame.neutral(), p2 if p2 != null else FighterInputFrame.neutral()])


func test_move_set_is_valid_and_complete() -> Array[String]:
	var f: Array[String] = []
	var def: FighterDefinition = _def("nox")
	for m: MoveData in def.moves:
		for problem: String in m.validate():
			f.append(problem)
		if String(m.id).begins_with("kairo_") and not m.activates_surge:
			f.append("still uses %s" % m.id)
	for pattern: StringName in [&"LIGHT", &"HEAVY", &"KICK", &"DOWN_HEAVY", &"SPECIAL", &"FORWARD_SPECIAL", &"BACK_SPECIAL"]:
		if def.move_for(pattern) == null:
			f.append("no move for %s" % pattern)
	if def.base_health != 850 or def.chip_taken_percent != 150:
		f.append("health %d / chip %d%%, expected 850 / 150%%" % [def.base_health, def.chip_taken_percent])
	return f


func test_shade_step_passes_through_and_switches_sides() -> Array[String]:
	var f: Array[String] = []
	var sim: CombatSimulation = _sim()
	var step: MoveData = _def("nox").move_for(&"SPECIAL")
	# Kairo jabs on the same tick; Nox is invulnerable as it would land.
	sim.step([FighterInputFrame.with_buttons(S), FighterInputFrame.with_buttons(L)])
	_idle(sim, step.total_frames() + 6)
	if _count(sim, CombatEvent.Type.HIT, 1) != 0:
		f.append("the jab hit Nox during Shade Step. log:\n%s" % sim.combat_log.to_text())
	if sim.fighters[0].position_x <= sim.fighters[1].position_x:
		f.append("Nox did not end up behind the opponent (x %.2f vs %.2f)" % [
			sim.fighters[0].position_x, sim.fighters[1].position_x])
	if sim.fighters[0].facing != -1 or sim.fighters[1].facing != 1:
		f.append("fighters did not turn to face each other after the switch")
	if _count(sim, CombatEvent.Type.HIT, 0) + _count(sim, CombatEvent.Type.BLOCK, 0) != 0:
		f.append("Shade Step touched the opponent")
	if sim.separation() < sim.profile(0).pushbox_half_width + sim.profile(1).pushbox_half_width - 1e-4:
		f.append("fighters overlap after the step")
	return f


func test_drop_heel_is_an_overhead_and_the_lows_are_low() -> Array[String]:
	var f: Array[String] = []
	# [button, down held, move id, guard that must FAIL]
	var cases: Array = [
		[H, true, &"nox_drop_heel", true],      # overhead beats a low block
		[K, false, &"nox_scythe_sweep", false],  # low beats a standing block
	]
	for c: Array in cases:
		for guard_low: bool in [false, true]:
			var sim: CombatSimulation = _sim()
			var guard: FighterInputFrame = FighterInputFrame.with_buttons(B, 0, -1 if guard_low else 0)
			sim.step([FighterInputFrame.neutral(), guard])
			sim.step([FighterInputFrame.with_buttons(c[0], 0, -1 if c[1] else 0), guard])
			_idle(sim, 50, guard)
			var hit: bool = _count(sim, CombatEvent.Type.HIT, 0, c[2]) == 1
			if hit != (guard_low == c[3]):
				f.append("%s vs %s block: hit=%s" % [c[2], "low" if guard_low else "standing", hit])
	var feint: MoveData = _def("nox").move_for(&"BACK_SPECIAL")
	if feint.hit_level != MoveData.HitLevel.LOW or feint.startup_frames != 22:
		f.append("Feint Fang should be a LOW that hits on frame 22")
	return f


func test_nox_takes_extra_chip() -> Array[String]:
	var f: Array[String] = []
	var sim: CombatSimulation = _sim("kairo", "nox")
	var heavy: MoveData = _def("kairo").move_for(&"HEAVY")
	var guard: FighterInputFrame = FighterInputFrame.with_buttons(B)
	sim.step([FighterInputFrame.with_buttons(H), guard])
	_idle(sim, 50, guard)
	if 850 - sim.fighters[1].health != heavy.chip_damage * 150 / 100:
		f.append("chip taken %d, expected %d" % [850 - sim.fighters[1].health, heavy.chip_damage * 150 / 100])
	return f


func test_throat_pierce_travels_and_hits() -> Array[String]:
	var f: Array[String] = []
	var sim: CombatSimulation = _sim("nox", "kairo", 3.2)
	sim.fighters[0].meter = 100
	sim.step([FighterInputFrame.with_buttons(S, 1), FighterInputFrame.neutral()])
	_idle(sim, 50)
	if _count(sim, CombatEvent.Type.HIT, 0, &"nox_throat_pierce") != 1:
		f.append("Throat Pierce did not reach from 3.2 m. log:\n%s" % sim.combat_log.to_text())
	return f


func test_model_has_every_animation_at_the_right_length() -> Array[String]:
	var f: Array[String] = []
	var def: FighterDefinition = _def("nox")
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
