extends RefCounted
## Milestone 1: movement, facing, walls, pushboxes, max separation.

const ARENA_PATH: String = "res://data/arenas/greybox_arena.tres"
const P1_PATH: String = "res://data/fighters/kairo_movement.tres"
const P2_PATH: String = "res://data/fighters/training_dummy_movement.tres"
const EPS: float = 1e-5


func _new_sim() -> CombatSimulation:
	var sim := CombatSimulation.new()
	sim.setup(load(ARENA_PATH), load(P1_PATH), load(P2_PATH))
	return sim


func _run(sim: CombatSimulation, p1_move: int, p2_move: int, ticks: int) -> void:
	for _i: int in ticks:
		sim.step([FighterInputFrame.moving(p1_move), FighterInputFrame.moving(p2_move)])


func test_data_resources_valid() -> Array[String]:
	var f: Array[String] = []
	var arena: ArenaConfig = load(ARENA_PATH)
	for p: String in arena.validate():
		f.append("arena: " + p)
	for path: String in [P1_PATH, P2_PATH]:
		var prof: FighterMovementProfile = load(path)
		for p: String in prof.validate():
			f.append("%s: %s" % [path, p])
	return f


func test_spawn_and_initial_facing() -> Array[String]:
	var f: Array[String] = []
	var sim := _new_sim()
	if absf(sim.fighters[0].position_x - sim.arena.p1_spawn_x) > EPS:
		f.append("P1 not at spawn")
	if sim.fighters[0].facing != 1 or sim.fighters[1].facing != -1:
		f.append("fighters do not face each other at spawn")
	return f


func test_walk_speed_forward_and_backward() -> Array[String]:
	var f: Array[String] = []
	var sim := _new_sim()
	var start: float = sim.fighters[0].position_x
	_run(sim, 1, 0, 30)  # 0.5 s toward opponent
	var expected: float = start + sim.profiles[0].walk_forward_speed * 0.5
	if absf(sim.fighters[0].position_x - expected) > 1e-4:
		f.append("forward walk: got %.5f expected %.5f" % [sim.fighters[0].position_x, expected])
	sim = _new_sim()
	_run(sim, -1, 0, 30)  # 0.5 s away from opponent
	expected = start - sim.profiles[0].walk_backward_speed * 0.5
	if absf(sim.fighters[0].position_x - expected) > 1e-4:
		f.append("backward walk: got %.5f expected %.5f" % [sim.fighters[0].position_x, expected])
	return f


func test_fighters_stay_inside_walls() -> Array[String]:
	var f: Array[String] = []
	var sim := _new_sim()
	# Both walk outward for 10 s; max separation will stop them first,
	# so also test each wall with the opponent pinned near it.
	_run(sim, -1, 1, 600)
	for i: int in 2:
		var hw: float = sim.profiles[i].pushbox_half_width
		var x: float = sim.fighters[i].position_x
		if x - hw < sim.arena.left_bound - EPS or x + hw > sim.arena.right_bound + EPS:
			f.append("P%d left the arena at x=%.4f" % [i + 1, x])
	# Push P2 into the right wall: P1 walks right for 20 s.
	sim = _new_sim()
	_run(sim, 1, 1, 1200)
	var p2_max: float = sim.arena.right_bound - sim.profiles[1].pushbox_half_width
	if absf(sim.fighters[1].position_x - p2_max) > EPS:
		f.append("P2 should rest against right wall, x=%.4f" % sim.fighters[1].position_x)
	# Left wall.
	sim = _new_sim()
	_run(sim, -1, -1, 1200)
	var p1_min: float = sim.arena.left_bound + sim.profiles[0].pushbox_half_width
	if absf(sim.fighters[0].position_x - p1_min) > EPS:
		f.append("P1 should rest against left wall, x=%.4f" % sim.fighters[0].position_x)
	return f


func test_pushboxes_never_overlap() -> Array[String]:
	var f: Array[String] = []
	var sim := _new_sim()
	var min_dist: float = sim.profiles[0].pushbox_half_width + sim.profiles[1].pushbox_half_width
	for t: int in 600:
		sim.step([FighterInputFrame.moving(1), FighterInputFrame.moving(-1)])
		if sim.separation() < min_dist - EPS:
			f.append("overlap at tick %d: sep %.5f < %.5f" % [t, sim.separation(), min_dist])
			break
	# Pushed into a wall, the wall-side fighter stays put and the bodies touch.
	sim = _new_sim()
	_run(sim, 1, 0, 1200)
	if absf(sim.separation() - min_dist) > EPS:
		f.append("cornered fighters should touch: sep %.5f" % sim.separation())
	return f


func test_fighters_cannot_cross_and_keep_facing() -> Array[String]:
	var f: Array[String] = []
	var sim := _new_sim()
	_run(sim, 1, -1, 600)
	if sim.fighters[0].position_x >= sim.fighters[1].position_x:
		f.append("P1 crossed P2 without a jump")
	if sim.fighters[0].facing != 1 or sim.fighters[1].facing != -1:
		f.append("facing wrong after collision")
	return f


func test_facing_follows_side_switch() -> Array[String]:
	var f: Array[String] = []
	var sim := _new_sim()
	# Side switches can't happen by walking (no jumps yet); force positions
	# as a future throw/cross-up would, then confirm facing updates in one tick.
	sim.fighters[0].position_x = 2.0
	sim.fighters[1].position_x = -2.0
	_run(sim, 0, 0, 1)
	if sim.fighters[0].facing != -1 or sim.fighters[1].facing != 1:
		f.append("facing did not flip after side switch")
	return f


func test_max_separation() -> Array[String]:
	var f: Array[String] = []
	var sim := _new_sim()
	_run(sim, -1, 1, 600)
	if sim.separation() > sim.arena.max_separation + EPS:
		f.append("separation %.4f exceeds max %.4f" % [sim.separation(), sim.arena.max_separation])
	if absf(sim.separation() - sim.arena.max_separation) > 1e-3:
		f.append("fighters should be held exactly at max separation, got %.4f" % sim.separation())
	# An idle opponent must not be dragged by the retreating fighter.
	sim = _new_sim()
	var p2_start: float = sim.fighters[1].position_x
	_run(sim, -1, 0, 600)
	if absf(sim.fighters[1].position_x - p2_start) > EPS:
		f.append("idle P2 moved when P1 retreated")
	return f


func test_determinism_same_inputs_same_result() -> Array[String]:
	var f: Array[String] = []
	var pattern: Array[int] = [1, 1, 0, -1, -1, -1, 0, 1, 0, 0, -1, 1]
	var results: Array[String] = []
	for run: int in 2:
		var sim := _new_sim()
		for t: int in 900:
			var p1: int = pattern[(t / 7) % pattern.size()]
			var p2: int = pattern[(t / 11 + 3) % pattern.size()]
			sim.step([FighterInputFrame.moving(p1), FighterInputFrame.moving(p2)])
		results.append("%s|%s|%d|%d" % [var_to_str(sim.fighters[0].position_x),
			var_to_str(sim.fighters[1].position_x), sim.fighters[0].facing, sim.tick])
	if results[0] != results[1]:
		f.append("non-deterministic: %s vs %s" % results)
	return f
