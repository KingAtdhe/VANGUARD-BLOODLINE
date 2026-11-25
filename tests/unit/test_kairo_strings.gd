extends RefCounted
## D-113: Kairo's jab string. Light after a jab that connects is the One-Two
## Cross (kairo_string_cross); Kick after the cross is the Low Kick. The cross
## never comes out on its own.

const L: int = FighterInputFrame.BUTTON_LIGHT
const K: int = FighterInputFrame.BUTTON_KICK


func _sim(separation: float) -> CombatSimulation:
	var sim := CombatSimulation.new()
	sim.setup(load("res://data/arenas/greybox_arena.tres"),
		load("res://data/fighters/kairo.tres"), load("res://data/fighters/training_dummy.tres"),
		load("res://data/rules/combat_tuning.tres"))
	sim.fighters[0].position_x = -separation * 0.5
	sim.fighters[1].position_x = separation * 0.5
	return sim


func _step(sim: CombatSimulation, p1: int, times: int = 1) -> void:
	for _i: int in times:
		sim.step([FighterInputFrame.with_buttons(p1, 0), FighterInputFrame.with_buttons(0)])


func _starts(sim: CombatSimulation) -> Array[StringName]:
	var out: Array[StringName] = []
	for e: CombatEvent in sim.combat_log.all_events():
		if e.type == CombatEvent.Type.ATTACK_START and e.actor == 0:
			out.append(e.move_id)
	return out


## Presses each button of [param route] every other tick until it starts.
func _route(sim: CombatSimulation, route: Array[int], ticks: int = 200) -> void:
	var k: int = 0
	var seen: int = 0
	for t: int in ticks:
		_step(sim, route[k] if k < route.size() and t % 2 == 0 else 0)
		var n: int = _starts(sim).size()
		if n > seen:
			seen = n
			k += 1


func test_cross_is_in_the_moveset_and_valid() -> Array[String]:
	var def: FighterDefinition = load("res://data/fighters/kairo.tres")
	var cross: MoveData = def.move_for_id(&"kairo_string_cross")
	if cross == null:
		return ["kairo_string_cross missing from Kairo's moves"]
	var f: Array[String] = cross.validate()
	if cross.string_after != &"kairo_light_punch" or cross.input_pattern != &"LIGHT":
		f.append("cross should follow the jab on Light")
	if def.move_for(&"LIGHT").id != &"kairo_light_punch":
		f.append("plain Light must stay the jab")
	return f


func test_light_alone_is_always_the_jab() -> Array[String]:
	var sim := _sim(4.0)   # out of reach: every jab whiffs, nothing to cancel
	for t: int in 160:
		_step(sim, L if t % 2 == 0 else 0)
	for id: StringName in _starts(sim):
		if id != &"kairo_light_punch":
			return ["Light out of a string gave %s" % id]
	return [] if _starts(sim).size() >= 2 else ["mashing Light out of range started fewer than 2 jabs"]


func test_jab_cross_low_kick() -> Array[String]:
	var sim := _sim(0.9)
	var route: Array[int] = [L, L, K]
	_route(sim, route)
	var want: Array[StringName] = [&"kairo_light_punch", &"kairo_string_cross", &"kairo_low_kick"]
	var got: Array[StringName] = _starts(sim)
	if got.slice(0, 3) != want:
		return ["string started %s, expected %s" % [got, want]]
	var combo: int = 0
	for e: CombatEvent in sim.combat_log.all_events():
		if e.type == CombatEvent.Type.HIT and e.actor == 0:
			combo = maxi(combo, e.combo_hits)
	return [] if combo == 3 else ["jab, cross, low kick should be a 3-hit combo (got %d)" % combo]


func test_string_stops_after_three() -> Array[String]:
	# jab, cross, low kick, then Light again: the low kick may cancel into a
	# jab on its own, but not as a fourth normal in the same chain
	var sim := _sim(0.9)
	var route: Array[int] = [L, L, K, L]
	_route(sim, route, 260)
	var combo: int = 0
	for e: CombatEvent in sim.combat_log.all_events():
		if e.type == CombatEvent.Type.HIT and e.actor == 0:
			combo = maxi(combo, e.combo_hits)
	return [] if combo <= 3 else ["the string ran to %d hits" % combo]
