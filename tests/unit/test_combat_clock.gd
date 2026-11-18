extends RefCounted
## Milestone 1: fixed 60 Hz tick independent of render frame rate.


## Simulates [param seconds] of real time at the given frame deltas, walking
## P1 right, and returns the per-tick P1 positions.
func _simulate(frame_deltas: Array[float], seconds: float) -> Array[float]:
	var sim := CombatSimulation.new()
	sim.setup(load("res://data/arenas/greybox_arena.tres"),
		load("res://data/fighters/kairo.tres"),
		load("res://data/fighters/training_dummy.tres"))
	var clock := CombatClock.new()
	var positions: Array[float] = []
	var elapsed: float = 0.0
	var i: int = 0
	while elapsed < seconds - 1e-9:
		var d: float = frame_deltas[i % frame_deltas.size()]
		elapsed += d
		i += 1
		for _t: int in clock.advance(d):
			sim.step([FighterInputFrame.moving(-1), FighterInputFrame.neutral()])
			positions.append(sim.fighters[0].position_x)
	return positions


func test_tick_count_matches_real_time_at_any_fps() -> Array[String]:
	var f: Array[String] = []
	for fps: float in [30.0, 60.0, 90.0, 120.0, 144.0]:
		var ticks: int = _simulate([1.0 / fps], 2.0).size()
		if absi(ticks - 120) > 1:
			f.append("%d fps: %d ticks in 2 s (expected 120 ±1)" % [int(fps), ticks])
	return f


func test_same_positions_at_any_fps() -> Array[String]:
	var f: Array[String] = []
	var reference: Array[float] = _simulate([1.0 / 60.0], 2.0)
	var patterns: Dictionary = {
		"30fps": [1.0 / 30.0],
		"144fps": [1.0 / 144.0],
		"jittery": [0.010, 0.025, 0.016, 0.033, 0.007, 0.020],
	}
	for name: String in patterns:
		var deltas: Array[float] = []
		deltas.assign(patterns[name])
		var got: Array[float] = _simulate(deltas, 2.0)
		var n: int = mini(got.size(), reference.size())
		for t: int in n:
			if got[t] != reference[t]:
				f.append("%s: tick %d position %.6f != %.6f" % [name, t, got[t], reference[t]])
				break
	return f


func test_catch_up_is_capped() -> Array[String]:
	var f: Array[String] = []
	var clock := CombatClock.new()
	var ticks: int = clock.advance(5.0)  # e.g. app resumed after 5 s
	if ticks != CombatConstants.MAX_CATCH_UP_TICKS:
		f.append("expected %d ticks after a 5 s stall, got %d" % [CombatConstants.MAX_CATCH_UP_TICKS, ticks])
	if clock.dropped_ticks() <= 0:
		f.append("dropped ticks not recorded")
	if clock.advance(1.0 / 60.0) != 1:
		f.append("clock did not recover to normal stepping after stall")
	return f


func test_alpha_in_range() -> Array[String]:
	var f: Array[String] = []
	var clock := CombatClock.new()
	clock.advance(0.5 / 60.0)
	var a: float = clock.alpha()
	if a < 0.49 or a > 0.51:
		f.append("alpha after half a tick = %.3f" % a)
	return f
