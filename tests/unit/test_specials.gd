extends RefCounted
## Milestone 6: specials, Origin meter, Origin Surge, ultimate, knockdown.

const L: int = FighterInputFrame.BUTTON_LIGHT
const H: int = FighterInputFrame.BUTTON_HEAVY
const K: int = FighterInputFrame.BUTTON_KICK
const B: int = FighterInputFrame.BUTTON_BLOCK
const S: int = FighterInputFrame.BUTTON_SPECIAL
const U: int = FighterInputFrame.BUTTON_ULTIMATE


func _sim(sep: float = 0.9, meter: int = 0) -> CombatSimulation:
	var sim := CombatSimulation.new()
	sim.setup(load("res://data/arenas/greybox_arena.tres"), load("res://data/fighters/kairo.tres"),
		load("res://data/fighters/training_dummy.tres"), load("res://data/rules/combat_tuning.tres"))
	sim.fighters[0].position_x = -sep * 0.5
	sim.fighters[1].position_x = sep * 0.5
	sim.fighters[0].meter = meter
	return sim


func _step(sim: CombatSimulation, p1: int, p2: int = 0, times: int = 1, dir: int = 0) -> void:
	for _i: int in times:
		sim.step([FighterInputFrame.with_buttons(p1, dir), FighterInputFrame.with_buttons(p2)])


func _events(sim: CombatSimulation, type: CombatEvent.Type, actor: int = -2) -> Array[CombatEvent]:
	var out: Array[CombatEvent] = []
	for e: CombatEvent in sim.combat_log.all_events():
		if e.type == type and (actor == -2 or e.actor == actor):
			out.append(e)
	return out


func _started(sim: CombatSimulation, id: StringName) -> int:
	var n: int = 0
	for e: CombatEvent in _events(sim, CombatEvent.Type.ATTACK_START, 0):
		if e.move_id == id:
			n += 1
	return n


func _def() -> FighterDefinition:
	return load("res://data/fighters/kairo.tres")


func test_definitions_and_spec_values() -> Array[String]:
	var f: Array[String] = []
	f.append_array(_def().validate())
	f.append_array((load("res://data/fighters/training_dummy.tres") as FighterDefinition).validate())
	f.append_array((load("res://data/rules/combat_tuning.tres") as CombatTuning).validate())
	var palm: MoveData = _def().move_for_id(&"kairo_origin_palm")
	if [palm.startup_frames, palm.active_frames, palm.recovery_frames, palm.damage] != [14, 5, 24, 105] or palm.meter_cost <= 0:
		f.append("Origin Palm must match spec §4.4 (14/5/24, 105, meter cost)")
	return f


func test_special_needs_meter_and_spends_it() -> Array[String]:
	var f: Array[String] = []
	var sim := _sim(4.0, 0)
	_step(sim, S)
	_step(sim, 0, 0, 10)
	if _started(sim, &"kairo_origin_palm") != 0:
		f.append("Origin Palm started without meter")
	var sim2 := _sim(4.0, 60)
	_step(sim2, S)
	if _started(sim2, &"kairo_origin_palm") != 1 or sim2.fighters[0].meter != 35:
		f.append("Origin Palm with 60 meter: started %d, meter %d (expected 1, 35)" % [
			_started(sim2, &"kairo_origin_palm"), sim2.fighters[0].meter])
	return f


func test_forward_special_is_rift_break_and_moves() -> Array[String]:
	var f: Array[String] = []
	var rift: MoveData = _def().move_for_id(&"kairo_rift_break")
	var sim := _sim(5.0)
	var x0: float = sim.fighters[0].position_x
	_step(sim, S, 0, 1, 1)  # toward P2 (P1 faces right)
	_step(sim, 0, 0, rift.total_frames() + 2)
	if _started(sim, &"kairo_rift_break") != 1:
		return ["forward+special did not start Rift Break"]
	if absf(sim.fighters[0].position_x - x0 - rift.move_distance) > 1e-4:
		f.append("Rift Break travelled %.4f m, expected %.4f" % [sim.fighters[0].position_x - x0, rift.move_distance])
	var sim2 := _sim(5.0, 60)
	_step(sim2, S, 0, 1, -1)  # back+special = Origin Palm
	if _started(sim2, &"kairo_origin_palm") != 1:
		f.append("back+special should be Origin Palm")
	return f


func test_knockdown_wakeup_and_invulnerability() -> Array[String]:
	var f: Array[String] = []
	var tuning: CombatTuning = load("res://data/rules/combat_tuning.tres")
	var sim := _sim(1.6)
	_step(sim, S, 0, 1, 1)
	for _t: int in 40:
		_step(sim, 0)
		if sim.fighters[1].action == FighterState.Action.KNOCKDOWN:
			break
	if sim.fighters[1].action != FighterState.Action.KNOCKDOWN or _events(sim, CombatEvent.Type.KNOCKDOWN).size() != 1:
		return ["Rift Break hit did not knock down. log:\n%s" % sim.combat_log.to_text()]
	if HitboxSystem.hurtbox(sim.definitions[1], sim.fighters[1]).has_area():
		f.append("knocked-down fighter has a hurtbox")
	# Mash attacks on the downed opponent: nothing may connect.
	var hits_before: int = _events(sim, CombatEvent.Type.HIT).size()
	sim.fighters[0].position_x = sim.fighters[1].position_x - 0.8
	var saw_wakeup: bool = false
	var down_ticks: int = 0
	for t: int in 200:
		_step(sim, L if t % 2 == 0 else 0)
		var a: FighterState.Action = sim.fighters[1].action
		if a == FighterState.Action.KNOCKDOWN or a == FighterState.Action.WAKEUP:
			down_ticks += 1
		saw_wakeup = saw_wakeup or a == FighterState.Action.WAKEUP
		if sim.fighters[1].is_neutral() or a == FighterState.Action.HITSTUN:
			break
	if _events(sim, CombatEvent.Type.HIT).size() > hits_before and down_ticks < tuning.knockdown_ticks + tuning.wakeup_ticks:
		f.append("hit landed on a downed opponent")
	if not saw_wakeup:
		f.append("no WAKEUP phase")
	if sim.fighters[1].combo_hits > 1:
		f.append("combo continued through a knockdown")
	return f


func test_meter_gains() -> Array[String]:
	var f: Array[String] = []
	var light: MoveData = _def().move_for(&"LIGHT")
	var sim := _sim(0.9)
	_step(sim, L, 0, light.startup_frames)
	var tuning: CombatTuning = load("res://data/rules/combat_tuning.tres")
	var expected_def: int = light.damage * tuning.meter_on_damage_taken_percent / 100
	if sim.fighters[0].meter != light.meter_gain_on_hit or sim.fighters[1].meter != expected_def:
		f.append("hit: attacker %d (exp %d), defender %d (exp %d)" % [
			sim.fighters[0].meter, light.meter_gain_on_hit, sim.fighters[1].meter, expected_def])
	var sim2 := _sim(0.9)
	_step(sim2, L, B, light.startup_frames)
	if sim2.fighters[0].meter != light.meter_gain_on_block or sim2.fighters[1].meter != tuning.meter_on_block_taken:
		f.append("block: attacker %d, defender %d" % [sim2.fighters[0].meter, sim2.fighters[1].meter])
	var sim3 := _sim(0.9, 99)
	_step(sim3, L, 0, light.startup_frames)
	if sim3.fighters[0].meter != 100:
		f.append("meter not capped at 100 (%d)" % sim3.fighters[0].meter)
	return f


func test_origin_surge_activation_drain_and_bonus() -> Array[String]:
	var f: Array[String] = []
	var def: FighterDefinition = _def()
	var surge: MoveData = def.move_for_id(&"kairo_origin_surge")
	var sim := _sim(4.0, 99)
	_step(sim, U)
	_step(sim, 0, 0, 40)
	if _started(sim, &"kairo_origin_surge") != 0:
		f.append("Surge activated at 99 meter")
	var sim2 := _sim(4.0, 100)
	_step(sim2, U)
	_step(sim2, 0, 0, surge.total_frames())
	if _events(sim2, CombatEvent.Type.SURGE_START, 0).size() != 1 or not sim2.fighters[0].in_surge():
		return ["Surge did not start after its %d-frame activation" % surge.total_frames()]
	# Specials are free in Surge, and damage is boosted.
	var meter_before: int = sim2.fighters[0].meter
	sim2.fighters[0].position_x = sim2.fighters[1].position_x - 0.9
	_step(sim2, S, 0, 1, -1)
	if _started(sim2, &"kairo_origin_palm") != 1:
		f.append("Origin Palm did not start in Surge")
	elif sim2.fighters[0].meter < meter_before - 1:
		f.append("special was not free in Surge (%d -> %d)" % [meter_before, sim2.fighters[0].meter])
	_step(sim2, 0, 0, 20)
	var hits: Array[CombatEvent] = _events(sim2, CombatEvent.Type.HIT, 0)
	if hits.is_empty() or hits[0].damage != 105 * def.surge_damage_percent / 100:
		f.append("Surge damage bonus wrong: %s" % [hits[0].damage if not hits.is_empty() else "no hit"])
	# Drains to 0 and ends.
	_step(sim2, 0, 0, def.surge_duration_ticks + 60)
	if sim2.fighters[0].in_surge() or sim2.fighters[0].meter != 0 or _events(sim2, CombatEvent.Type.SURGE_END, 0).size() != 1:
		f.append("Surge did not drain and end (meter %d, surge %d)" % [sim2.fighters[0].meter, sim2.fighters[0].surge_remaining])
	return f


func test_ultimate_rules() -> Array[String]:
	var f: Array[String] = []
	var def: FighterDefinition = _def()
	var surge: MoveData = def.move_for_id(&"kairo_origin_surge")
	# Enter Surge, then press Ultimate in range → Origin Break, spends all meter.
	var sim := _sim(4.0, 100)
	_step(sim, U)
	_step(sim, 0, 0, surge.total_frames())
	sim.fighters[0].position_x = sim.fighters[1].position_x - 1.0
	_step(sim, U)
	if _started(sim, &"kairo_origin_break") != 1:
		return ["Ultimate did not start in Surge. log:\n%s" % sim.combat_log.to_text()]
	if sim.fighters[0].meter != 0 or sim.fighters[0].in_surge():
		f.append("Ultimate did not consume the meter / end Surge")
	_step(sim, 0, 0, 30)
	var ult_hits: int = 0
	for e: CombatEvent in _events(sim, CombatEvent.Type.HIT, 0):
		if e.move_id == &"kairo_origin_break":
			ult_hits += 1
	if ult_hits != 1 or sim.fighters[1].action != FighterState.Action.KNOCKDOWN:
		f.append("Origin Break should hit once and knock down")
	# Late in Surge (meter below the 30 minimum) the ultimate is unavailable.
	var sim2 := _sim(4.0, 100)
	_step(sim2, U)
	_step(sim2, 0, 0, surge.total_frames() + def.surge_duration_ticks * 3 / 4)
	if not sim2.fighters[0].in_surge() or sim2.fighters[0].meter >= 30:
		f.append("setup: expected Surge with < 30 meter, got %d" % sim2.fighters[0].meter)
	_step(sim2, U)
	_step(sim2, 0, 0, 5)
	if _started(sim2, &"kairo_origin_break") != 0:
		f.append("Ultimate allowed below its minimum meter")
	return f


func test_spec_route_light_light_kick_palm() -> Array[String]:
	var f: Array[String] = []
	var sim := _sim(0.8, 50)
	var route: Array[int] = [L, L, K, S]
	var k: int = 0
	var seen: int = 0
	for t: int in 300:
		_step(sim, route[k] if k < route.size() and t % 2 == 0 else 0)
		var starts: int = _events(sim, CombatEvent.Type.ATTACK_START, 0).size()
		if starts > seen:
			seen = starts
			k += 1
	var max_combo: int = 0
	for e: CombatEvent in _events(sim, CombatEvent.Type.HIT, 0):
		max_combo = maxi(max_combo, e.combo_hits)
	if max_combo != 4:
		f.append("spec route L, L, K, Origin Palm should be a 4-hit combo, got %d. log:\n%s" % [max_combo, sim.combat_log.to_text()])
	return f


func test_no_infinite_combo_with_specials_and_free_surge() -> Array[String]:
	# Every route of 1..4 commands from {L, K, H, S, fwd+S}, mashed, mid-screen
	# and cornered, with a full meter AND with Surge active (specials free).
	var f: Array[String] = []
	var cmds: Array = [[L, 0], [K, 0], [H, 0], [S, -1], [S, 1]]
	var routes: Array = [[]]
	var all: Array = []
	for _len: int in 4:
		var next: Array = []
		for r: Array in routes:
			for c: Array in cmds:
				var nr: Array = r.duplicate()
				nr.append(c)
				next.append(nr)
				all.append(nr)
		routes = next
	var worst: int = 0
	var worst_desc: String = ""
	for r: Array in all:
		for cornered: bool in [false, true]:
			for surge: bool in [false, true]:
				var sim := _sim(0.75, 100)
				if cornered:
					var wall: float = sim.arena.right_bound - sim.profile(1).pushbox_half_width
					sim.fighters[1].position_x = wall
					sim.fighters[0].position_x = wall - 0.75
				if surge:
					OriginMeter.start_surge(sim.fighters[0], sim.definitions[0], sim.tuning)
				var k: int = 0
				var seen: int = 0
				var after: int = 0
				for t: int in 700:
					var cmd: Array = r[k] if k < r.size() else [0, 0]
					var dir: int = cmd[1] if k < r.size() else 0
					_step(sim, cmd[0] if t % 2 == 0 else 0, 0, 1, dir)
					var starts: int = _events(sim, CombatEvent.Type.ATTACK_START, 0).size()
					if starts > seen:
						seen = starts
						k += 1
					if k >= r.size():
						after += 1
						if after > 150 and sim.fighters[1].is_neutral():
							break
				var mc: int = 0
				for e: CombatEvent in _events(sim, CombatEvent.Type.HIT, 0):
					mc = maxi(mc, e.combo_hits)
				if mc > worst:
					worst = mc
					worst_desc = "%s corner=%s surge=%s" % [r, cornered, surge]
				if not sim.fighters[1].is_neutral():
					f.append("defender never recovered: %s corner=%s surge=%s" % [r, cornered, surge])
	if worst > 5:
		f.append("combo of %d hits (%s) exceeds the designed bound of 5" % [worst, worst_desc])
	if worst < 4:
		f.append("expected the 4-hit route to be found (max %d)" % worst)
	return f
