extends RefCounted
## Milestone 2: attacks, hitboxes, block, damage, hitstop, combat log.

const L: int = FighterInputFrame.BUTTON_LIGHT
const H: int = FighterInputFrame.BUTTON_HEAVY
const K: int = FighterInputFrame.BUTTON_KICK
const B: int = FighterInputFrame.BUTTON_BLOCK
const MOVE_PATHS: Array[String] = [
	"res://data/moves/kairo_light_punch.tres",
	"res://data/moves/kairo_heavy_punch.tres",
	"res://data/moves/kairo_kick.tres",
]


func _sim(separation: float = 0.9) -> CombatSimulation:
	var sim := CombatSimulation.new()
	sim.setup(load("res://data/arenas/greybox_arena.tres"),
		load("res://data/fighters/kairo.tres"), load("res://data/fighters/training_dummy.tres"))
	sim.fighters[0].position_x = -separation * 0.5
	sim.fighters[1].position_x = separation * 0.5
	return sim


## P2 guards low when _p2_down is set (LOW attacks need a low block, D-061).
var _p2_down: bool = false


func _step(sim: CombatSimulation, p1_buttons: int, p2_buttons: int, times: int = 1) -> void:
	for _i: int in times:
		sim.step([FighterInputFrame.with_buttons(p1_buttons),
			FighterInputFrame.with_buttons(p2_buttons, 0, -1 if _p2_down else 0)])


func _count(sim: CombatSimulation, type: CombatEvent.Type) -> int:
	var n: int = 0
	for e: CombatEvent in sim.combat_log.all_events():
		if e.type == type:
			n += 1
	return n


func _move(pattern: StringName) -> MoveData:
	return (load("res://data/fighters/kairo.tres") as FighterDefinition).move_for(pattern)


## Call right after the contact tick. Steps until both fighters are neutral
## again; returns [p1_free_tick, p2_free_tick].
func _free_ticks(sim: CombatSimulation, p1_buttons: int, p2_buttons: int) -> Array[int]:
	var free: Array[int] = [-1, -1]
	for i: int in 2:
		if sim.fighters[i].is_neutral():
			push_error("_free_ticks called before contact")
			return free
	for _t: int in 200:
		_step(sim, p1_buttons, p2_buttons)
		if sim.hitstop_remaining > 0:
			continue
		for i: int in 2:
			if free[i] < 0 and sim.fighters[i].is_neutral():
				free[i] = sim.tick
		if free[0] >= 0 and free[1] >= 0:
			break
	return free


func test_move_data_valid_and_matches_spec_table() -> Array[String]:
	var f: Array[String] = []
	# Spec §4.4 prototype values: startup / active / recovery / damage.
	var expected: Dictionary = {
		&"kairo_light_punch": [5, 3, 10, 35],
		&"kairo_heavy_punch": [12, 3, 19, 85],
		&"kairo_kick": [9, 4, 15, 60],
	}
	for path: String in MOVE_PATHS:
		var m: MoveData = load(path)
		for p: String in m.validate():
			f.append(p)
		var e: Array = expected[m.id]
		var got: Array = [m.startup_frames, m.active_frames, m.recovery_frames, m.damage]
		if got != e:
			f.append("%s frame data %s != spec %s" % [m.id, got, e])
	return f


func test_hitbox_only_during_active_frames() -> Array[String]:
	var f: Array[String] = []
	for pattern: StringName in [&"LIGHT", &"HEAVY", &"KICK"]:
		var m: MoveData = _move(pattern)
		var sim := _sim(4.0)  # out of range: never connects, so frames run uninterrupted
		var button: int = {&"LIGHT": L, &"HEAVY": H, &"KICK": K}[pattern]
		_step(sim, button, 0)
		for frame: int in range(1, m.total_frames() + 1):
			var s: FighterState = sim.fighters[0]
			if s.move_frame != frame:
				f.append("%s: expected frame %d, got %d" % [m.id, frame, s.move_frame])
				break
			var has_box: bool = HitboxSystem.hitbox(s).has_area()
			var should: bool = frame >= m.startup_frames and frame < m.startup_frames + m.active_frames
			if has_box != should:
				f.append("%s frame %d: hitbox %s, expected %s" % [m.id, frame, has_box, should])
			_step(sim, 0, 0)
		if sim.fighters[0].action != FighterState.Action.IDLE:
			f.append("%s: not idle after %d frames" % [m.id, m.total_frames()])
		if _count(sim, CombatEvent.Type.WHIFF) != 1:
			f.append("%s: whiff not logged" % m.id)
	return f


func test_one_hit_per_attack() -> Array[String]:
	var f: Array[String] = []
	for button: int in [L, H, K]:
		var sim := _sim(0.75)  # deep inside range for every active frame
		_step(sim, button, 0)
		_step(sim, button, 0, 80)  # keep holding: holding must not re-trigger either
		var hits: int = _count(sim, CombatEvent.Type.HIT)
		var starts: int = _count(sim, CombatEvent.Type.ATTACK_START)
		if hits != 1 or starts != 1:
			f.append("button %d: %d starts, %d hits (expected 1/1)" % [button, starts, hits])
	return f


func test_damage_and_hitstun() -> Array[String]:
	var f: Array[String] = []
	var m: MoveData = _move(&"LIGHT")
	var sim := _sim(0.9)
	_step(sim, L, 0, m.startup_frames)
	var d: FighterState = sim.fighters[1]
	if d.health != 1000 - m.damage:
		f.append("health %d, expected %d" % [d.health, 1000 - m.damage])
	if d.action != FighterState.Action.HITSTUN or d.stun_remaining != m.hitstun_frames:
		f.append("expected HITSTUN %d, got %s %d" % [m.hitstun_frames, d.action_name(), d.stun_remaining])
	if sim.hitstop_remaining != m.hitstop_frames:
		f.append("hitstop %d, expected %d" % [sim.hitstop_remaining, m.hitstop_frames])
	return f


func test_block_rules() -> Array[String]:
	var f: Array[String] = []
	for pattern: StringName in [&"LIGHT", &"HEAVY", &"KICK"]:
		var m: MoveData = _move(pattern)
		var button: int = {&"LIGHT": L, &"HEAVY": H, &"KICK": K}[pattern]
		var sim := _sim(0.9)
		_p2_down = m.hit_level == MoveData.HitLevel.LOW
		_step(sim, button, B, m.startup_frames)
		_p2_down = false
		var d: FighterState = sim.fighters[1]
		if _count(sim, CombatEvent.Type.BLOCK) != 1 or _count(sim, CombatEvent.Type.HIT) != 0:
			f.append("%s: not blocked" % m.id)
			continue
		if d.health != 1000 - m.chip_damage:
			f.append("%s: chip wrong, hp %d" % [m.id, d.health])
		if d.action != FighterState.Action.BLOCKSTUN or d.stun_remaining != m.blockstun_frames:
			f.append("%s: expected BLOCKSTUN %d, got %s %d" % [m.id, m.blockstun_frames, d.action_name(), d.stun_remaining])
	# Releasing block after blockstun returns to neutral; holding keeps blocking.
	var sim2 := _sim(0.9)
	_step(sim2, L, B, 60)
	if sim2.fighters[1].action != FighterState.Action.BLOCK:
		f.append("holding block after blockstun should return to BLOCK, got %s" % sim2.fighters[1].action_name())
	# A fighter in the middle of an attack cannot block, even holding block.
	var sim3 := _sim(0.9)
	var heavy: MoveData = _move(&"HEAVY")
	_step(sim3, 0, H | B)                         # P2 commits to a 12f heavy
	_step(sim3, L, H | B, _move(&"LIGHT").startup_frames)  # P1's 5f light lands first
	if _count(sim3, CombatEvent.Type.HIT) != 1 or _count(sim3, CombatEvent.Type.BLOCK) != 0:
		f.append("attacking fighter blocked. log:\n%s" % sim3.combat_log.to_text())
	if sim3.fighters[1].action != FighterState.Action.HITSTUN or sim3.fighters[1].move != null:
		f.append("P2's heavy was not interrupted (%s)" % sim3.fighters[1].action_name())
	if heavy == null:
		f.append("heavy missing")
	return f


func test_frame_advantage_matches_data() -> Array[String]:
	var f: Array[String] = []
	for pattern: StringName in [&"LIGHT", &"HEAVY", &"KICK"]:
		var m: MoveData = _move(pattern)
		var button: int = {&"LIGHT": L, &"HEAVY": H, &"KICK": K}[pattern]
		for blocking: bool in [false, true]:
			var sim := _sim(0.9)
			_p2_down = m.hit_level == MoveData.HitLevel.LOW
			_step(sim, button, B if blocking else 0, m.startup_frames)  # contact tick
			var free: Array[int] = _free_ticks(sim, 0, B if blocking else 0)
			_p2_down = false
			var measured: int = free[0] - free[1]  # >0 = attacker free later = defender advantage
			var expected: int = m.advantage_on_block() if blocking else m.advantage_on_hit()
			if -measured != expected:
				f.append("%s %s: measured %+d, data says %+d" % [
					m.id, "block" if blocking else "hit", -measured, expected])
	return f


func test_hitstop_freezes_both_fighters() -> Array[String]:
	var f: Array[String] = []
	var m: MoveData = _move(&"HEAVY")
	var sim := _sim(0.9)
	_step(sim, H, 0, m.startup_frames)
	var frozen: String = sim.describe().split("|", true, 1)[1]
	_step(sim, H, 0, m.hitstop_frames)
	var after: String = sim.describe().split("|", true, 1)[1]
	if frozen != after:
		f.append("state changed during hitstop:\n  %s\n  %s" % [frozen, after])
	if sim.hitstop_remaining != 0:
		f.append("hitstop not finished after %d ticks" % m.hitstop_frames)
	_step(sim, 0, 0)
	if sim.fighters[1].stun_remaining != m.hitstun_frames - 1:
		f.append("hitstun should start counting after hitstop")
	return f


func test_button_edges_tracked_through_hitstop() -> Array[String]:
	# Holding a button never re-triggers; a release+press during hitstop is a
	# fresh press (since M4 it is buffered and, here, legally cancels
	# Light -> Light on hit).
	var f: Array[String] = []
	var sim := _sim(0.9)
	var m: MoveData = _move(&"LIGHT")
	_step(sim, L, 0, m.startup_frames)  # connects → hitstop
	_step(sim, L, 0, 3)                  # keep holding during hitstop: no new press
	if not sim.fighters[0].buffer.is_empty():
		f.append("held button was buffered as a new press")
	_step(sim, 0, 0, 1)                  # release during hitstop
	_step(sim, L, 0, 1)                  # press again during hitstop
	_step(sim, L, 0, m.hitstop_frames + 2)
	var starts: Array[CombatEvent] = []
	for e: CombatEvent in sim.combat_log.all_events():
		if e.type == CombatEvent.Type.ATTACK_START:
			starts.append(e)
	if starts.size() != 2 or starts[1].cancel_from != m.id:
		f.append("expected exactly one Light->Light cancel, log:\n%s" % sim.combat_log.to_text())
	return f


func test_trade_both_get_hit() -> Array[String]:
	var f: Array[String] = []
	var sim := _sim(0.9)
	var m: MoveData = _move(&"LIGHT")
	_step(sim, L, L, m.startup_frames)
	if _count(sim, CombatEvent.Type.HIT) != 2:
		f.append("expected a trade (2 hits), log:\n%s" % sim.combat_log.to_text())
	for i: int in 2:
		if sim.fighters[i].health != 1000 - m.damage:
			f.append("P%d health %d after trade" % [i + 1, sim.fighters[i].health])
	return f


func test_heavy_on_block_is_punishable_by_light() -> Array[String]:
	var f: Array[String] = []
	var heavy: MoveData = _move(&"HEAVY")
	var light: MoveData = _move(&"LIGHT")
	if heavy.advantage_on_block() > -light.startup_frames:
		f.append("data: heavy %+d on block is not punishable by a %df light" % [heavy.advantage_on_block(), light.startup_frames])
	var sim := _sim(0.9)
	_step(sim, H, B, heavy.startup_frames)
	if _count(sim, CombatEvent.Type.BLOCK) != 1:
		return ["heavy was not blocked"]
	# P2 mashes light as soon as it can act (hold-release pattern each tick).
	for t: int in 60:
		_step(sim, 0, L if t % 2 == 0 else 0)
		if _count(sim, CombatEvent.Type.HIT) > 0:
			break
	var last: CombatEvent = sim.combat_log.recent(1)[0]
	if not (last.type == CombatEvent.Type.HIT and last.actor == 1):
		f.append("P2 light did not punish blocked heavy. log:\n%s" % sim.combat_log.to_text())
	return f


func test_pushback_and_corner_transfer() -> Array[String]:
	var f: Array[String] = []
	var m: MoveData = _move(&"HEAVY")
	# Mid-screen: defender slides back by exactly `pushback`, attacker stays.
	var sim := _sim(0.9)
	var a0: float = sim.fighters[0].position_x
	var d0: float = sim.fighters[1].position_x
	_step(sim, H, 0, m.startup_frames + m.hitstop_frames + HitResolver.PUSHBACK_TICKS + 2)
	if absf(sim.fighters[1].position_x - (d0 + m.pushback)) > 1e-4:
		f.append("defender pushback %.4f, expected %.4f" % [sim.fighters[1].position_x - d0, m.pushback])
	if absf(sim.fighters[0].position_x - a0) > 1e-4:
		f.append("attacker moved mid-screen")
	# Cornered: defender stays at the wall, attacker is pushed back instead.
	var sim2 := _sim(0.9)
	var wall_x: float = sim2.arena.right_bound - sim2.profile(1).pushbox_half_width
	sim2.fighters[1].position_x = wall_x
	sim2.fighters[0].position_x = wall_x - 0.9
	var a_start: float = sim2.fighters[0].position_x
	_step(sim2, H, 0, m.startup_frames + m.hitstop_frames + HitResolver.PUSHBACK_TICKS + 2)
	if absf(sim2.fighters[1].position_x - wall_x) > 1e-5:
		f.append("cornered defender left the wall")
	if absf((a_start - sim2.fighters[0].position_x) - m.pushback) > 1e-4:
		f.append("attacker corner pushback %.4f, expected %.4f" % [a_start - sim2.fighters[0].position_x, m.pushback])
	return f


func test_ko_and_reset() -> Array[String]:
	var f: Array[String] = []
	var sim := _sim(0.9)
	sim.fighters[1].health = 20
	_step(sim, L, 0, 5)
	if sim.fighters[1].health != 0 or sim.fighters[1].action != FighterState.Action.KO:
		f.append("expected KO at 0 hp, got %d %s" % [sim.fighters[1].health, sim.fighters[1].action_name()])
	if _count(sim, CombatEvent.Type.KO) != 1:
		f.append("KO not logged")
	if HitboxSystem.hurtbox(sim.definitions[1], sim.fighters[1]).has_area():
		f.append("KO fighter still has a hurtbox")
	_step(sim, 0, L, 30)
	if _count(sim, CombatEvent.Type.ATTACK_START) != 1:
		f.append("KO fighter accepted input")
	sim.reset()
	if sim.fighters[1].health != 1000 or sim.fighters[1].action != FighterState.Action.IDLE:
		f.append("reset did not restore the dummy")
	return f


func test_combat_log_is_deterministic() -> Array[String]:
	var f: Array[String] = []
	var dummy := TrainingDummyController.new()
	dummy.mode = TrainingDummyController.Mode.JAB
	var texts: Array[String] = []
	for run: int in 2:
		var sim := _sim(2.0)
		for t: int in 1200:
			var buttons: int = [0, L, 0, 0, K, 0, H, 0, B, B, 0, 0][(t / 9) % 12]
			var dir: int = [1, 1, 0, -1, 0, 1][(t / 23) % 6]
			sim.step([FighterInputFrame.with_buttons(buttons, dir), dummy.input_for_tick(sim.tick + 1)])
		texts.append(sim.combat_log.to_text() + "\n" + sim.describe())
	if texts[0] != texts[1]:
		f.append("combat log differs between identical runs")
	if texts[0].count("HIT") == 0 or texts[0].count("BLOCK") == 0:
		f.append("scripted fight produced no hits or no blocks — scenario too weak")
	return f
