extends RefCounted
## Seraphina's own move set (D-064): launch and air hits, evasive step, overhead dive.

const L: int = FighterInputFrame.BUTTON_LIGHT
const H: int = FighterInputFrame.BUTTON_HEAVY
const K: int = FighterInputFrame.BUTTON_KICK
const S: int = FighterInputFrame.BUTTON_SPECIAL
const B: int = FighterInputFrame.BUTTON_BLOCK


func _def(id: String) -> FighterDefinition:
	return load("res://data/fighters/%s.tres" % id)


func _sim(p1: String = "seraphina", p2: String = "kairo", gap: float = 0.9) -> CombatSimulation:
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
	var def: FighterDefinition = _def("seraphina")
	for m: MoveData in def.moves:
		for problem: String in m.validate():
			f.append(problem)
		if String(m.id).begins_with("kairo_") and not m.activates_surge:
			f.append("still uses %s" % m.id)
	for pattern: StringName in [&"LIGHT", &"HEAVY", &"KICK", &"DOWN_KICK", &"SPECIAL", &"FORWARD_SPECIAL", &"BACK_SPECIAL"]:
		if def.move_for(pattern) == null:
			f.append("no move for %s" % pattern)
	if def.base_health != 900:
		f.append("health %d, expected 900" % def.base_health)
	return f


func test_crescent_arc_launches_and_side_kick_juggles() -> Array[String]:
	var f: Array[String] = []
	var sim: CombatSimulation = _sim()
	sim.fighters[0].meter = 100
	var arc: MoveData = _def("seraphina").move_for(&"SPECIAL")
	sim.step([FighterInputFrame.with_buttons(S), FighterInputFrame.neutral()])
	_idle(sim, arc.startup_frames + 2)
	if sim.fighters[1].action != FighterState.Action.LAUNCHED:
		return ["Crescent Arc did not launch (%s)" % sim.fighters[1].action_name()]
	_idle(sim, 14)   # past the hitstop: the arc starts
	if sim.fighters[1].launch_height() <= 0.0:
		f.append("launched fighter has no height")
	# Mash Heavy: the Side Kick comes out as soon as she recovers and hits in the air.
	for t: int in 70:
		sim.step([FighterInputFrame.with_buttons(H if t % 2 == 0 else 0), FighterInputFrame.neutral()])
		if _count(sim, CombatEvent.Type.HIT, 0, &"seraphina_side_kick") > 0:
			break
	var air_hit: CombatEvent = null
	for e: CombatEvent in sim.combat_log.all_events():
		if e.type == CombatEvent.Type.HIT and e.move_id == &"seraphina_side_kick":
			air_hit = e
	if air_hit == null:
		return ["Side Kick did not hit the launched fighter. log:\n%s" % sim.combat_log.to_text()]
	if air_hit.combo_hits != 2:
		f.append("air hit was combo hit %d, expected 2" % air_hit.combo_hits)
	if sim.fighters[1].action != FighterState.Action.LAUNCHED or sim.fighters[1].juggle_hits != 1:
		f.append("after the air hit: %s, juggle %d" % [sim.fighters[1].action_name(), sim.fighters[1].juggle_hits])
	_idle(sim, 40)
	if sim.fighters[1].action != FighterState.Action.KNOCKDOWN or sim.fighters[1].combo_hits != 0:
		f.append("did not land knocked down with the combo ended (%s, combo %d)" % [
			sim.fighters[1].action_name(), sim.fighters[1].combo_hits])
	_idle(sim, 80)
	if not sim.fighters[1].is_neutral():
		f.append("launched fighter never got back up")
	return f


func test_juggle_limit_and_no_throws_in_the_air() -> Array[String]:
	var f: Array[String] = []
	var sim: CombatSimulation = _sim("drakon", "kairo")
	var d: FighterState = sim.fighters[1]
	d.action = FighterState.Action.LAUNCHED
	d.stun_remaining = 40
	d.launch_total = 40
	# A throw cannot grab a launched fighter.
	sim.step([FighterInputFrame.with_buttons(S), FighterInputFrame.neutral()])
	_idle(sim, 14)
	if _count(sim, CombatEvent.Type.HIT, 0) != 0:
		f.append("a throw connected on a launched fighter")
	# At the juggle limit the fighter cannot be hit at all.
	d.juggle_exhausted = true
	if HitboxSystem.hurtbox(sim.definitions[1], d).has_area():
		f.append("a fighter at the juggle limit still has a hurtbox")
	return f


func test_halo_step_moves_back_and_is_invulnerable() -> Array[String]:
	var f: Array[String] = []
	var sim: CombatSimulation = _sim()
	var halo: MoveData = _def("seraphina").move_for(&"BACK_SPECIAL")
	var x0: float = sim.fighters[0].position_x
	# P1 faces right: back is -1. Kairo jabs on the same tick; it would land on frame 5.
	sim.step([FighterInputFrame.with_buttons(S, -1), FighterInputFrame.with_buttons(L)])
	_idle(sim, halo.move_end_frame + 1)
	if _count(sim, CombatEvent.Type.HIT, 1) != 0:
		f.append("the jab hit her during Halo Step")
	if absf((sim.fighters[0].position_x - x0) - halo.move_distance) > 1e-4:
		f.append("moved %.3f m, expected %.3f" % [sim.fighters[0].position_x - x0, halo.move_distance])
	if not halo.is_invulnerable_on(halo.invuln_start_frame) or halo.is_invulnerable_on(halo.invuln_end_frame + 1):
		f.append("invulnerability window wrong")
	return f


func test_seraph_dive_is_an_overhead() -> Array[String]:
	var f: Array[String] = []
	for low: bool in [false, true]:
		var sim: CombatSimulation = _sim("seraphina", "kairo", 2.6)
		var guard: FighterInputFrame = FighterInputFrame.with_buttons(B, 0, -1 if low else 0)
		sim.step([FighterInputFrame.with_buttons(S, 1), guard])
		_idle(sim, 60, guard)
		var hits: int = _count(sim, CombatEvent.Type.HIT, 0, &"seraphina_seraph_dive")
		var blocks: int = _count(sim, CombatEvent.Type.BLOCK, 0, &"seraphina_seraph_dive")
		if low and hits != 1:
			f.append("the dive did not hit a low block (%d hits, %d blocks)" % [hits, blocks])
		if not low and blocks != 1:
			f.append("the dive was not stopped by a standing block (%d hits, %d blocks)" % [hits, blocks])
	return f


func test_model_has_every_animation_at_the_right_length() -> Array[String]:
	var f: Array[String] = []
	var def: FighterDefinition = _def("seraphina")
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
