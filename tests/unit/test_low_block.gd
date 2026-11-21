extends RefCounted
## Guard height (D-061): low block, hit levels, direction + button commands.

const L: int = FighterInputFrame.BUTTON_LIGHT
const K: int = FighterInputFrame.BUTTON_KICK
const S: int = FighterInputFrame.BUTTON_SPECIAL
const B: int = FighterInputFrame.BUTTON_BLOCK


## Kairo with his kick's hit level replaced, plus an optional extra move.
func _kairo(kick_level: MoveData.HitLevel, extra: MoveData = null) -> FighterDefinition:
	var def: FighterDefinition = (load("res://data/fighters/kairo.tres") as FighterDefinition).duplicate()
	var moves: Array[MoveData] = []
	for m: MoveData in def.moves:
		if m.input_pattern == &"KICK":
			var k: MoveData = m.duplicate()
			k.hit_level = kick_level
			moves.append(k)
		else:
			moves.append(m)
	if extra != null:
		moves.append(extra)
	def.moves = moves
	return def


func _sim(attacker: FighterDefinition) -> CombatSimulation:
	var sim := CombatSimulation.new()
	sim.setup(load("res://data/arenas/greybox_arena.tres"), attacker,
		load("res://data/fighters/training_dummy.tres"), load("res://data/rules/combat_tuning.tres"))
	sim.fighters[0].position_x = -0.45
	sim.fighters[1].position_x = 0.45
	return sim


## P1 presses [param button] (with [param p1_down]); P2 holds block, low or
## standing. Returns "HIT", "BLOCK" or "NONE" for P1's first contact.
func _outcome(sim: CombatSimulation, button: int, guard_low: bool, p1_down: bool = false) -> String:
	var guard: FighterInputFrame = FighterInputFrame.with_buttons(B, 0, -1 if guard_low else 0)
	sim.step([FighterInputFrame.neutral(), guard])
	sim.step([FighterInputFrame.with_buttons(button, 0, -1 if p1_down else 0), guard])
	for _i: int in 60:
		sim.step([FighterInputFrame.neutral(), guard])
	for e: CombatEvent in sim.combat_log.all_events():
		if e.actor == 0 and e.type == CombatEvent.Type.HIT:
			return "HIT"
		if e.actor == 0 and e.type == CombatEvent.Type.BLOCK:
			return "BLOCK"
	return "NONE"


func test_low_attack_beats_standing_block_and_loses_to_low_block() -> Array[String]:
	var f: Array[String] = []
	var standing: String = _outcome(_sim(_kairo(MoveData.HitLevel.LOW)), K, false)
	var low: String = _outcome(_sim(_kairo(MoveData.HitLevel.LOW)), K, true)
	if standing != "HIT":
		f.append("LOW vs standing block: %s (expected HIT)" % standing)
	if low != "BLOCK":
		f.append("LOW vs low block: %s (expected BLOCK)" % low)
	return f


func test_overhead_beats_low_block_and_loses_to_standing_block() -> Array[String]:
	var f: Array[String] = []
	var standing: String = _outcome(_sim(_kairo(MoveData.HitLevel.HIGH)), K, false)
	var low: String = _outcome(_sim(_kairo(MoveData.HitLevel.HIGH)), K, true)
	if standing != "BLOCK":
		f.append("HIGH vs standing block: %s (expected BLOCK)" % standing)
	if low != "HIT":
		f.append("HIGH vs low block: %s (expected HIT)" % low)
	return f


func test_mid_is_stopped_by_either_guard() -> Array[String]:
	var f: Array[String] = []
	for guard_low: bool in [false, true]:
		var r: String = _outcome(_sim(_kairo(MoveData.HitLevel.MID)), K, guard_low)
		if r != "BLOCK":
			f.append("MID vs %s block: %s (expected BLOCK)" % ["low" if guard_low else "standing", r])
	return f


func test_block_low_flag_follows_input_and_is_copied() -> Array[String]:
	var f: Array[String] = []
	var sim: CombatSimulation = _sim(_kairo(MoveData.HitLevel.MID))
	sim.step([FighterInputFrame.neutral(), FighterInputFrame.with_buttons(B, 0, -1)])
	if not sim.fighters[1].block_low or not sim.fighters[1].copy().block_low:
		f.append("down + block did not set block_low (or copy lost it)")
	sim.step([FighterInputFrame.neutral(), FighterInputFrame.with_buttons(B)])
	if sim.fighters[1].block_low:
		f.append("block_low still set after releasing down")
	return f


func test_down_button_uses_its_own_move_or_falls_back() -> Array[String]:
	var f: Array[String] = []
	# No DOWN_KICK move: down + kick is the normal kick.
	var sim: CombatSimulation = _sim(_kairo(MoveData.HitLevel.MID))
	sim.step([FighterInputFrame.with_buttons(K, 0, -1), FighterInputFrame.neutral()])
	sim.step([FighterInputFrame.neutral(), FighterInputFrame.neutral()])
	if sim.fighters[0].move == null or sim.fighters[0].move.input_pattern != &"KICK":
		f.append("down + kick without a DOWN_KICK move did not fall back to KICK")
	# With one: it is used, and the plain button still gives the plain move.
	var sweep: MoveData = (load("res://data/moves/kairo_kick.tres") as MoveData).duplicate()
	sweep.id = &"test_sweep"
	sweep.input_pattern = &"DOWN_KICK"
	sweep.hit_level = MoveData.HitLevel.LOW
	sim = _sim(_kairo(MoveData.HitLevel.MID, sweep))
	sim.step([FighterInputFrame.with_buttons(K, 0, -1), FighterInputFrame.neutral()])
	sim.step([FighterInputFrame.neutral(), FighterInputFrame.neutral()])
	if sim.fighters[0].move == null or sim.fighters[0].move.id != &"test_sweep":
		f.append("down + kick did not start the DOWN_KICK move")
	sim = _sim(_kairo(MoveData.HitLevel.MID, sweep))
	sim.step([FighterInputFrame.with_buttons(K), FighterInputFrame.neutral()])
	sim.step([FighterInputFrame.neutral(), FighterInputFrame.neutral()])
	if sim.fighters[0].move == null or sim.fighters[0].move.input_pattern != &"KICK":
		f.append("plain kick was replaced by the DOWN_KICK move")
	return f


func test_back_special_falls_back_to_special() -> Array[String]:
	var f: Array[String] = []
	var sim: CombatSimulation = _sim(_kairo(MoveData.HitLevel.MID))
	sim.fighters[0].meter = 100
	# P1 faces right (+1): holding left is "back".
	sim.step([FighterInputFrame.with_buttons(S, -1), FighterInputFrame.neutral()])
	sim.step([FighterInputFrame.neutral(), FighterInputFrame.neutral()])
	if sim.fighters[0].move == null or sim.fighters[0].move.input_pattern != &"SPECIAL":
		f.append("back + special without a BACK_SPECIAL move did not fall back to SPECIAL")
	return f
