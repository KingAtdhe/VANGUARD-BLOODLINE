extends RefCounted
## Drakon's own move set (D-063): throws, armour, reduced chip, low stomp.

const L: int = FighterInputFrame.BUTTON_LIGHT
const H: int = FighterInputFrame.BUTTON_HEAVY
const K: int = FighterInputFrame.BUTTON_KICK
const S: int = FighterInputFrame.BUTTON_SPECIAL
const B: int = FighterInputFrame.BUTTON_BLOCK


func _def(id: String) -> FighterDefinition:
	return load("res://data/fighters/%s.tres" % id)


## Drakon is P1 (faces right) at [param gap] metres from P2.
func _sim(opponent: String = "kairo", gap: float = 0.9) -> CombatSimulation:
	var sim := CombatSimulation.new()
	sim.setup(load("res://data/arenas/greybox_arena.tres"), _def("drakon"), _def(opponent),
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


func _run(sim: CombatSimulation, p1: FighterInputFrame, p2: FighterInputFrame, then_p2: FighterInputFrame, ticks: int = 70) -> void:
	sim.step([p1, p2])
	for _i: int in ticks:
		sim.step([FighterInputFrame.neutral(), then_p2])


func test_move_set_is_valid_and_complete() -> Array[String]:
	var f: Array[String] = []
	var def: FighterDefinition = _def("drakon")
	for m: MoveData in def.moves:
		for problem: String in m.validate():
			f.append(problem)
	for pattern: StringName in [&"LIGHT", &"HEAVY", &"KICK", &"DOWN_HEAVY", &"SPECIAL", &"FORWARD_SPECIAL", &"BACK_SPECIAL"]:
		if def.move_for(pattern) == null:
			f.append("no move for %s" % pattern)
	for id: StringName in [&"drakon_anvil_slam", &"drakon_molten_colossus"]:
		if def.move_for_id(id) == null or not def.move_for_id(id).is_throw():
			f.append("%s is not a throw" % id)
	# Nothing of Kairo's except the shared Surge activation.
	for m: MoveData in def.moves:
		if String(m.id).begins_with("kairo_") and not m.activates_surge:
			f.append("still uses %s" % m.id)
	return f


func test_throw_cannot_be_blocked() -> Array[String]:
	var f: Array[String] = []
	for low: bool in [false, true]:
		var sim: CombatSimulation = _sim()
		var guard: FighterInputFrame = FighterInputFrame.with_buttons(B, 0, -1 if low else 0)
		_run(sim, FighterInputFrame.with_buttons(S), guard, guard)
		if _count(sim, CombatEvent.Type.HIT, 0, &"drakon_anvil_slam") != 1 or _count(sim, CombatEvent.Type.BLOCK, 0) != 0:
			f.append("Anvil Slam vs %s block was not a clean hit" % ("low" if low else "standing"))
		if _count(sim, CombatEvent.Type.KNOCKDOWN, 0) != 1:
			f.append("Anvil Slam did not knock down")
	return f


func test_throw_whiffs_on_a_fighter_in_blockstun() -> Array[String]:
	var f: Array[String] = []
	var sim: CombatSimulation = _sim()
	var guard: FighterInputFrame = FighterInputFrame.with_buttons(B)
	var hammer: MoveData = _def("drakon").move_for(&"LIGHT")
	# Hammer Fist is blocked; buffer nothing, then grab while P2 is still in blockstun.
	sim.step([FighterInputFrame.with_buttons(L), guard])
	for _i: int in hammer.startup_frames - 1:
		sim.step([FighterInputFrame.neutral(), guard])
	if sim.fighters[1].action != FighterState.Action.BLOCKSTUN:
		return ["setup: Hammer Fist was not blocked (%s)" % sim.fighters[1].action_name()]
	# Force the grab to be active right now, on the stunned fighter.
	var slam: MoveData = _def("drakon").move_for(&"SPECIAL")
	sim.fighters[0].move = slam
	sim.fighters[0].move_frame = slam.startup_frames - 1
	sim.fighters[0].move_connected = false
	sim.fighters[1].stun_remaining = 30
	sim.hitstop_remaining = 0
	for _i: int in slam.active_frames + 1:
		sim.step([FighterInputFrame.neutral(), guard])
	if _count(sim, CombatEvent.Type.HIT, 0, &"drakon_anvil_slam") != 0:
		f.append("a throw connected on a fighter in blockstun")
	return f


func test_throw_beats_slip_counter() -> Array[String]:
	var f: Array[String] = []
	var sim: CombatSimulation = _sim()
	# P2 (Kairo, faces left) slips with back (+1) + special just before the grab lands.
	sim.step([FighterInputFrame.with_buttons(S), FighterInputFrame.neutral()])
	for _i: int in 3:
		sim.step([FighterInputFrame.neutral(), FighterInputFrame.neutral()])
	_run(sim, FighterInputFrame.neutral(), FighterInputFrame.with_buttons(S, 1), FighterInputFrame.neutral())
	if _count(sim, CombatEvent.Type.COUNTER, 1) != 0:
		f.append("Slip Counter caught a throw")
	if _count(sim, CombatEvent.Type.HIT, 0, &"drakon_anvil_slam") != 1:
		f.append("the throw did not hit the slipping fighter")
	return f


func test_forge_charge_armour_absorbs_one_hit_and_still_lands() -> Array[String]:
	var f: Array[String] = []
	var sim: CombatSimulation = _sim("kairo", 2.6)
	sim.fighters[0].meter = 100
	var jab: MoveData = _def("kairo").move_for(&"LIGHT")
	# Drakon charges (toward = +1); Kairo jabs into him as he arrives.
	sim.step([FighterInputFrame.with_buttons(S, 1), FighterInputFrame.neutral()])
	var jabbed: bool = false
	for _i: int in 80:
		var gap: float = sim.fighters[1].position_x - sim.fighters[0].position_x
		var p2: FighterInputFrame = FighterInputFrame.neutral()
		if not jabbed and gap < 1.95 and sim.fighters[1].is_neutral():
			p2 = FighterInputFrame.with_buttons(L)
			jabbed = true
		sim.step([FighterInputFrame.neutral(), p2])
	var armoured: int = 0
	for e: CombatEvent in sim.combat_log.all_events():
		if e.type == CombatEvent.Type.HIT and e.actor == 1 and e.armored:
			armoured += 1
	if armoured != 1:
		return ["expected 1 armoured hit on Drakon, got %d. log:\n%s" % [armoured, sim.combat_log.to_text()]]
	if sim.fighters[0].health != _def("drakon").base_health - jab.damage:
		f.append("armour should still take the jab's damage: hp %d" % sim.fighters[0].health)
	if _count(sim, CombatEvent.Type.HIT, 0, &"drakon_forge_charge") != 1:
		f.append("Forge Charge did not land after absorbing the jab")
	return f


func test_throw_ignores_armour() -> Array[String]:
	var f: Array[String] = []
	# Drakon (P2 here) charges into Drakon P1's grab.
	var sim := CombatSimulation.new()
	sim.setup(load("res://data/arenas/greybox_arena.tres"), _def("drakon"), _def("drakon"),
		load("res://data/rules/combat_tuning.tres"))
	sim.fighters[0].position_x = -0.5
	sim.fighters[1].position_x = 0.5
	var charge: MoveData = _def("drakon").move_for(&"FORWARD_SPECIAL")
	sim.fighters[1].action = FighterState.Action.ATTACK
	sim.fighters[1].move = charge
	sim.fighters[1].move_frame = charge.armor_start_frame
	sim.fighters[1].armor_left = charge.armor_hits
	_run(sim, FighterInputFrame.with_buttons(S), FighterInputFrame.neutral(), FighterInputFrame.neutral(), 30)
	if _count(sim, CombatEvent.Type.KNOCKDOWN, 0) != 1:
		f.append("the throw did not go through armour. log:\n%s" % sim.combat_log.to_text())
	return f


func test_drakon_takes_half_chip_and_has_more_health() -> Array[String]:
	var f: Array[String] = []
	var sim := CombatSimulation.new()
	sim.setup(load("res://data/arenas/greybox_arena.tres"), _def("kairo"), _def("drakon"),
		load("res://data/rules/combat_tuning.tres"))
	sim.fighters[0].position_x = -0.45
	sim.fighters[1].position_x = 0.45
	var heavy: MoveData = _def("kairo").move_for(&"HEAVY")
	var start_hp: int = sim.fighters[1].health
	if start_hp != 1150:
		f.append("Drakon starts with %d health, expected 1150" % start_hp)
	var guard: FighterInputFrame = FighterInputFrame.with_buttons(B)
	_run(sim, FighterInputFrame.with_buttons(H), guard, guard, 50)
	if start_hp - sim.fighters[1].health != heavy.chip_damage / 2:
		f.append("chip taken %d, expected %d" % [start_hp - sim.fighters[1].health, heavy.chip_damage / 2])
	return f


func test_stomp_and_quake_are_low() -> Array[String]:
	var f: Array[String] = []
	for id: StringName in [&"drakon_stomp", &"drakon_quake_stomp"]:
		if _def("drakon").move_for_id(id).hit_level != MoveData.HitLevel.LOW:
			f.append("%s is not LOW" % id)
	var sim: CombatSimulation = _sim()
	var guard: FighterInputFrame = FighterInputFrame.with_buttons(B)
	_run(sim, FighterInputFrame.with_buttons(K), guard, guard, 50)
	if _count(sim, CombatEvent.Type.HIT, 0, &"drakon_stomp") != 1:
		f.append("Stomp did not hit a standing block")
	return f


func test_model_has_every_animation_at_the_right_length() -> Array[String]:
	var f: Array[String] = []
	var def: FighterDefinition = _def("drakon")
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
