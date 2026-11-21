extends RefCounted
## Dashes (D-071): double-tap input, distance per fighter, what a dash can
## and cannot do.

const L: int = FighterInputFrame.BUTTON_LIGHT
const B: int = FighterInputFrame.BUTTON_BLOCK
const ROSTER: Array[String] = ["kairo", "drakon", "seraphina", "nox", "vexa", "ryuen"]


func _def(id: String) -> FighterDefinition:
	return load("res://data/fighters/%s.tres" % id)


func _sim(p1: String = "kairo", p2: String = "kairo", gap: float = 3.0) -> CombatSimulation:
	var sim := CombatSimulation.new()
	sim.setup(load("res://data/arenas/greybox_arena.tres"), _def(p1), _def(p2),
		load("res://data/rules/combat_tuning.tres"))
	sim.fighters[0].position_x = -gap * 0.5
	sim.fighters[1].position_x = gap * 0.5
	return sim


func _n() -> FighterInputFrame:
	return FighterInputFrame.neutral()


func _dir(d: int, buttons: int = 0, down: bool = false) -> FighterInputFrame:
	return FighterInputFrame.with_buttons(buttons, d, -1 if down else 0)


## P1 taps [param d] twice (2 ticks held, 2 released, then held), P2 idle.
func _double_tap(sim: CombatSimulation, d: int) -> void:
	for frame: FighterInputFrame in [_dir(d), _dir(d), _n(), _n(), _dir(d)]:
		sim.step([frame, _n()])


func _dashes(sim: CombatSimulation, actor: int) -> int:
	var n: int = 0
	for e: CombatEvent in sim.combat_log.all_events():
		if e.type == CombatEvent.Type.DASH and e.actor == actor:
			n += 1
	return n


func test_double_tap_dashes_and_covers_the_fighters_distance() -> Array[String]:
	var f: Array[String] = []
	for id: String in ROSTER:
		var m: FighterMovementProfile = _def(id).movement
		f.append_array(m.validate())
		for forward: bool in [true, false]:
			var sim: CombatSimulation = _sim(id, "kairo", 3.0)
			_double_tap(sim, 1 if forward else -1)
			var x0: float = sim.fighters[0].position_x
			if sim.fighters[0].action != FighterState.Action.DASH or sim.fighters[0].dash_forward != forward:
				f.append("%s: double tap %s did not start a dash" % [id, "toward" if forward else "away"])
				continue
			# counts the steps until it is over: the start tick is tick 1, the
			# step that ends it comes after tick N
			var ticks: int = 0
			while sim.fighters[0].action == FighterState.Action.DASH and ticks < 60:
				sim.step([_n(), _n()])
				ticks += 1
			# the first step was taken on the tick the dash started
			var moved: float = absf(sim.fighters[0].position_x - x0) + m.dash_step(forward, 1)
			if absf(moved - m.dash_distance(forward)) > 0.001:
				f.append("%s %s dash covered %.3f m, data says %.3f" % [id, "forward" if forward else "back", moved, m.dash_distance(forward)])
			if ticks != m.dash_ticks(forward):
				f.append("%s %s dash lasted %d ticks, data says %d" % [id, "forward" if forward else "back", ticks, m.dash_ticks(forward)])
			# faster than walking the same time
			var walk: float = (m.walk_forward_speed if forward else m.walk_backward_speed) * m.dash_ticks(forward) / 60.0
			if m.dash_distance(forward) <= walk:
				f.append("%s %s dash is no faster than walking" % [id, "forward" if forward else "back"])
	return f


func test_walking_and_slow_taps_do_not_dash() -> Array[String]:
	var f: Array[String] = []
	var tuning: CombatTuning = load("res://data/rules/combat_tuning.tres")
	# holding a direction
	var hold: CombatSimulation = _sim()
	for _t: int in 40:
		hold.step([_dir(1), _n()])
	# first tap held too long
	var slow: CombatSimulation = _sim()
	for _t: int in tuning.dash_tap_hold_ticks + 3:
		slow.step([_dir(1), _n()])
	slow.step([_n(), _n()])
	slow.step([_dir(1), _n()])
	# second tap too late
	var late: CombatSimulation = _sim()
	late.step([_dir(1), _n()])
	for _t: int in tuning.dash_tap_window_ticks + 3:
		late.step([_n(), _n()])
	late.step([_dir(1), _n()])
	# two different directions
	var mixed: CombatSimulation = _sim()
	for frame: FighterInputFrame in [_dir(1), _n(), _dir(-1), _n(), _dir(1)]:
		mixed.step([frame, _n()])
	# holding block, or down
	var guard: CombatSimulation = _sim()
	for frame: FighterInputFrame in [_dir(1, B), _dir(0, B), _dir(1, B), _dir(1, B)]:
		guard.step([frame, _n()])
	var names: Array[String] = ["holding", "a slow first tap", "a late second tap", "left then right", "holding block"]
	var sims: Array[CombatSimulation] = [hold, slow, late, mixed, guard]
	for k: int in sims.size():
		if _dashes(sims[k], 0) != 0:
			f.append("%s started a dash" % names[k])
	return f


func test_forward_dash_can_be_cut_by_an_attack_but_a_back_dash_is_committed() -> Array[String]:
	var f: Array[String] = []
	var tuning: CombatTuning = load("res://data/rules/combat_tuning.tres")
	var sim: CombatSimulation = _sim()
	_double_tap(sim, 1)
	for _t: int in tuning.dash_cancel_frame:
		sim.step([_n(), _n()])
	sim.step([FighterInputFrame.with_buttons(L), _n()])
	sim.step([_n(), _n()])
	if sim.fighters[0].action != FighterState.Action.ATTACK:
		f.append("an attack should cut a forward dash short (%s)" % sim.fighters[0].action_name())
	var back: CombatSimulation = _sim()
	_double_tap(back, -1)
	back.step([_n(), _n()])
	back.step([FighterInputFrame.with_buttons(L), _n()])
	back.step([_n(), _n()])
	back.step([_n(), _n()])
	if back.fighters[0].action != FighterState.Action.DASH:
		f.append("a back dash must not be cancelled by an attack (%s)" % back.fighters[0].action_name())
	return f


func test_a_dashing_fighter_cannot_block_and_can_be_hit() -> Array[String]:
	var f: Array[String] = []
	# P1 dashes into P2's jab while holding block: the dash does not guard.
	var sim: CombatSimulation = _sim("kairo", "kairo", 1.6)
	for frame: FighterInputFrame in [_dir(1), _dir(1), _n(), _n(), _dir(1)]:
		sim.step([frame, _n()])
	sim.step([_dir(0, B), FighterInputFrame.with_buttons(L)])
	for _t: int in 12:
		sim.step([_dir(0, B), _n()])
	var hit: bool = false
	for e: CombatEvent in sim.combat_log.all_events():
		hit = hit or (e.type == CombatEvent.Type.HIT and e.actor == 1)
	if not hit:
		f.append("a dashing fighter holding block should still be hit. log:\n%s" % sim.combat_log.to_text())
	return f


func test_dash_stops_at_the_opponent_and_the_wall() -> Array[String]:
	var f: Array[String] = []
	var sim: CombatSimulation = _sim("nox", "kairo", 1.0)
	_double_tap(sim, 1)
	for _t: int in 30:
		sim.step([_n(), _n()])
	var min_gap: float = sim.profile(0).pushbox_half_width + sim.profile(1).pushbox_half_width
	if sim.separation() < min_gap - 0.001 or sim.fighters[0].position_x > sim.fighters[1].position_x:
		f.append("a forward dash went through the opponent")
	var wall: CombatSimulation = _sim("seraphina", "kairo", 3.0)
	wall.fighters[0].position_x = wall.arena.left_bound + wall.profile(0).pushbox_half_width + 0.2
	wall.fighters[1].position_x = wall.fighters[0].position_x + 3.0
	_double_tap(wall, -1)
	for _t: int in 30:
		wall.step([_n(), _n()])
	if wall.fighters[0].position_x < wall.arena.left_bound + wall.profile(0).pushbox_half_width - 0.001:
		f.append("a back dash left the arena")
	return f


func test_cpu_dashes_and_fights_stay_deterministic() -> Array[String]:
	var f: Array[String] = []
	var texts: Array[String] = []
	var dashes: int = 0
	for _run: int in 2:
		var sim: CombatSimulation = _sim("kairo", "seraphina", 5.0)
		sim.ko_enabled = false
		var a := AIController.new(load("res://data/ai/expert.tres"), 0, _def("kairo"), _def("seraphina"), 21)
		var b := AIController.new(load("res://data/ai/expert.tres"), 1, _def("seraphina"), _def("kairo"), 22)
		for _t: int in 2400:
			var obs := AIObservation.from_sim(sim)
			a.observe(obs)
			b.observe(obs)
			sim.step([a.next_input(), b.next_input()])
		texts.append(sim.combat_log.to_text() + sim.describe())
		dashes = _dashes(sim, 0) + _dashes(sim, 1)
	if texts[0] != texts[1]:
		f.append("the same CPU fight played out differently twice")
	if dashes == 0:
		f.append("two expert CPUs never dashed in 40 seconds")
	return f


func test_every_fighter_has_dash_animations_of_the_right_length() -> Array[String]:
	var f: Array[String] = []
	for id: String in ROSTER:
		var def: FighterDefinition = _def(id)
		var model: Node = def.model_scene.instantiate()
		var ap: AnimationPlayer = model.find_child("AnimationPlayer", true, false)
		for forward: bool in [true, false]:
			var anim: StringName = def.resolve_anim(def.anim_dash_forward if forward else def.anim_dash_back)
			if not ap.has_animation(anim):
				f.append("%s: missing %s" % [id, anim])
				continue
			var frames: float = ap.get_animation(anim).length * CombatConstants.TICK_RATE + 1.0
			if absf(frames - def.movement.dash_ticks(forward)) > 0.01:
				f.append("%s lasts %.1f frames, the dash %d ticks" % [anim, frames, def.movement.dash_ticks(forward)])
		model.free()
	return f
