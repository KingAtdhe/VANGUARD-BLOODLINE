extends RefCounted
## Kairo's own move set (D-062): low kick, body hook, Slip Counter.

const L: int = FighterInputFrame.BUTTON_LIGHT
const H: int = FighterInputFrame.BUTTON_HEAVY
const K: int = FighterInputFrame.BUTTON_KICK
const S: int = FighterInputFrame.BUTTON_SPECIAL
const B: int = FighterInputFrame.BUTTON_BLOCK


func _kairo() -> FighterDefinition:
	return load("res://data/fighters/kairo.tres")


func _sim(opponent: String = "kairo") -> CombatSimulation:
	var sim := CombatSimulation.new()
	sim.setup(load("res://data/arenas/greybox_arena.tres"), _kairo(),
		load("res://data/fighters/%s.tres" % opponent), load("res://data/rules/combat_tuning.tres"))
	sim.fighters[0].position_x = -0.45
	sim.fighters[1].position_x = 0.45
	return sim


func _events(sim: CombatSimulation, type: CombatEvent.Type, actor: int, move_id: StringName = &"") -> int:
	var n: int = 0
	for e: CombatEvent in sim.combat_log.all_events():
		if e.type == type and e.actor == actor and (move_id == &"" or e.move_id == move_id):
			n += 1
	return n


func _idle(sim: CombatSimulation, ticks: int) -> void:
	for _i: int in ticks:
		sim.step([FighterInputFrame.neutral(), FighterInputFrame.neutral()])


func test_move_set_is_valid_and_complete() -> Array[String]:
	var f: Array[String] = []
	var def: FighterDefinition = _kairo()
	for m: MoveData in def.moves:
		for problem: String in m.validate():
			f.append(problem)
	for pattern: StringName in [&"LIGHT", &"HEAVY", &"KICK", &"DOWN_HEAVY", &"SPECIAL", &"FORWARD_SPECIAL", &"BACK_SPECIAL"]:
		if def.move_for(pattern) == null:
			f.append("no move for %s" % pattern)
	if def.move_for(&"KICK") != null and def.move_for(&"KICK").hit_level != MoveData.HitLevel.LOW:
		f.append("Kairo's kick is not LOW")
	var slip: MoveData = def.move_for(&"BACK_SPECIAL")
	if slip != null and (not slip.is_counter() or slip.counter_followup == null):
		f.append("Slip Counter has no counter window or follow-up")
	return f


func test_low_kick_hits_a_standing_block_and_is_stopped_by_a_low_block() -> Array[String]:
	var f: Array[String] = []
	for low: bool in [false, true]:
		var sim: CombatSimulation = _sim()
		var guard: FighterInputFrame = FighterInputFrame.with_buttons(B, 0, -1 if low else 0)
		sim.step([FighterInputFrame.neutral(), guard])
		sim.step([FighterInputFrame.with_buttons(K), guard])
		for _i: int in 40:
			sim.step([FighterInputFrame.neutral(), guard])
		var hits: int = _events(sim, CombatEvent.Type.HIT, 0)
		var blocks: int = _events(sim, CombatEvent.Type.BLOCK, 0)
		if low and (hits != 0 or blocks != 1):
			f.append("low block: %d hits, %d blocks (expected 0, 1)" % [hits, blocks])
		if not low and (hits != 1 or blocks != 0):
			f.append("standing block: %d hits, %d blocks (expected 1, 0)" % [hits, blocks])
	return f


func test_slip_counter_catches_a_punch_and_answers_with_the_hook() -> Array[String]:
	var f: Array[String] = []
	var sim: CombatSimulation = _sim()
	# P2 faces left, so "back" is +1. Both press on the same tick: the jab
	# lands on frame 5, inside the counter window (4..16).
	sim.step([FighterInputFrame.with_buttons(L), FighterInputFrame.with_buttons(S, 1)])
	_idle(sim, 60)
	if _events(sim, CombatEvent.Type.COUNTER, 1) != 1:
		f.append("no COUNTER event")
	if _events(sim, CombatEvent.Type.HIT, 0) != 0:
		f.append("the countered jab still hit")
	if _events(sim, CombatEvent.Type.HIT, 1, &"kairo_counter_hook") != 1:
		f.append("the counter hook did not hit")
	var hook: MoveData = load("res://data/moves/kairo_counter_hook.tres")
	if sim.fighters[1].health != 1000 or sim.fighters[0].health != 1000 - hook.damage:
		f.append("health after counter: P1 %d P2 %d" % [sim.fighters[0].health, sim.fighters[1].health])
	return f


func test_low_kick_beats_slip_counter() -> Array[String]:
	var f: Array[String] = []
	var sim: CombatSimulation = _sim()
	sim.step([FighterInputFrame.with_buttons(K), FighterInputFrame.with_buttons(S, 1)])
	_idle(sim, 60)
	if _events(sim, CombatEvent.Type.COUNTER, 1) != 0:
		f.append("Slip Counter caught a LOW attack")
	if _events(sim, CombatEvent.Type.HIT, 0, &"kairo_low_kick") != 1:
		f.append("the low kick did not hit the slipping fighter")
	return f


func test_slip_counter_has_no_hitbox_and_recovers() -> Array[String]:
	var f: Array[String] = []
	var sim: CombatSimulation = _sim("training_dummy")
	sim.step([FighterInputFrame.with_buttons(S, -1), FighterInputFrame.neutral()])
	_idle(sim, 2)
	if sim.fighters[0].move == null or sim.fighters[0].move.id != &"kairo_slip_counter":
		f.append("back + special did not start Slip Counter")
	_idle(sim, 40)
	if _events(sim, CombatEvent.Type.HIT, 0) + _events(sim, CombatEvent.Type.BLOCK, 0) != 0:
		f.append("Slip Counter touched the opponent")
	if not sim.fighters[0].is_neutral():
		f.append("did not recover to neutral after a whiffed Slip Counter")
	return f


func test_jab_cancels_into_body_hook() -> Array[String]:
	var f: Array[String] = []
	var sim: CombatSimulation = _sim("training_dummy")
	sim.step([FighterInputFrame.with_buttons(L), FighterInputFrame.neutral()])
	_idle(sim, 4)
	sim.step([FighterInputFrame.with_buttons(H, 0, -1), FighterInputFrame.neutral()])
	_idle(sim, 40)
	var found: bool = false
	for e: CombatEvent in sim.combat_log.all_events():
		if e.type == CombatEvent.Type.ATTACK_START and e.move_id == &"kairo_body_hook" \
				and e.cancel_from == &"kairo_light_punch":
			found = true
	if not found:
		f.append("jab did not cancel into the body hook")
	if _events(sim, CombatEvent.Type.HIT, 0, &"kairo_body_hook") != 1:
		f.append("the body hook did not combo after the jab")
	return f
