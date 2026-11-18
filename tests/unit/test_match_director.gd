extends RefCounted
## Milestone 3: match loop — rounds, timer, results, transitions, rematch.

const L: int = FighterInputFrame.BUTTON_LIGHT
const H: int = FighterInputFrame.BUTTON_HEAVY
const K: int = FighterInputFrame.BUTTON_KICK
const B: int = FighterInputFrame.BUTTON_BLOCK


func _rules() -> MatchRules:
	return (load("res://data/rules/standard_match.tres") as MatchRules).duplicate()


func _setup(rules: MatchRules = null) -> Array:
	var sim := CombatSimulation.new()
	sim.setup(load("res://data/arenas/greybox_arena.tres"),
		load("res://data/fighters/kairo.tres"), load("res://data/fighters/training_dummy.tres"))
	var director := MatchDirector.new(rules if rules != null else _rules())
	director.start_match(sim)
	return [sim, director]


## Worst-case ticks for a whole match (every round goes to time).
func _max_match_ticks(r: MatchRules) -> int:
	return r.max_rounds * (r.intro_ticks + r.round_ticks() + r.round_end_ticks) + 10


## Checks the invariants that must hold on every tick. Returns problems.
func _invariants(sim: CombatSimulation, d: MatchDirector) -> Array[String]:
	var p: Array[String] = []
	for i: int in 2:
		var hp: int = sim.fighters[i].health
		if hp < 0 or hp > sim.definitions[i].base_health:
			p.append("P%d health %d out of range" % [i + 1, hp])
		if d.round_wins[i] < 0 or d.round_wins[i] > d.rules.rounds_to_win:
			p.append("P%d round wins %d out of range" % [i + 1, d.round_wins[i]])
	if d.timer_ticks < 0 or d.timer_ticks > d.rules.round_ticks():
		p.append("timer %d out of range" % d.timer_ticks)
	if d.round_number < 1 or d.round_number > d.rules.max_rounds:
		p.append("round number %d out of range" % d.round_number)
	if d.phase == MatchDirector.Phase.MATCH_END and d.match_winner < -1:
		p.append("invalid match winner")
	return p


## P1 walks in; once in heavy range it mashes heavy. (Pressing from out of
## range would just buffer whiffs forever, so a sane player walks in first.)
func _p1_aggressor(sim: CombatSimulation) -> Callable:
	return func(t: int) -> FighterInputFrame:
		if sim.separation() < 1.25:
			return FighterInputFrame.with_buttons(H if t % 2 == 0 else 0)
		return FighterInputFrame.moving(1)


func _run_until_end(sim: CombatSimulation, d: MatchDirector, p1: Callable, p2: Callable) -> Array[String]:
	var problems: Array[String] = []
	var limit: int = _max_match_ticks(d.rules)
	for t: int in limit:
		if d.is_match_over():
			return problems
		d.step(sim, [p1.call(t), p2.call(t)])
		var inv: Array[String] = _invariants(sim, d)
		if not inv.is_empty():
			problems.append("tick %d: %s" % [t, ", ".join(inv)])
			return problems
	problems.append("match did not end within %d ticks (phase %s)" % [limit, d.phase_name()])
	return problems


func test_rules_valid() -> Array[String]:
	return _rules().validate()


func test_p1_wins_two_straight_rounds_by_ko() -> Array[String]:
	var s: Array = _setup()
	var sim: CombatSimulation = s[0]
	var d: MatchDirector = s[1]
	var f: Array[String] = _run_until_end(sim, d, _p1_aggressor(sim), func(_t: int) -> FighterInputFrame: return FighterInputFrame.neutral())
	if d.match_winner != 0 or d.round_wins != [2, 0] or d.results.size() != 2:
		f.append("expected P1 2-0, got winner %d wins %s rounds %d" % [d.match_winner, d.round_wins, d.results.size()])
	for r: MatchDirector.RoundResult in d.results:
		if r.reason != MatchDirector.Reason.KO:
			f.append("expected KO rounds, got %s" % r.describe())
	return f


func test_timeout_with_health_lead() -> Array[String]:
	var s: Array = _setup()
	var sim: CombatSimulation = s[0]
	var d: MatchDirector = s[1]
	var f: Array[String] = []
	# P1 lands one light right after FIGHT, then both idle until time-out.
	sim.fighters[0].position_x = -0.45
	sim.fighters[1].position_x = 0.45
	for _t: int in d.rules.intro_ticks:
		d.step(sim, [FighterInputFrame.neutral(), FighterInputFrame.neutral()])
	# Intro is over; spawn reset happened at round start, so move them close.
	sim.fighters[0].position_x = -0.45
	sim.fighters[1].position_x = 0.45
	d.step(sim, [FighterInputFrame.with_buttons(L), FighterInputFrame.neutral()])
	var guard: int = 0
	while d.phase == MatchDirector.Phase.FIGHT and guard < d.rules.round_ticks() + 10:
		d.step(sim, [FighterInputFrame.neutral(), FighterInputFrame.neutral()])
		guard += 1
	var r: MatchDirector.RoundResult = d.last_result()
	if r == null or r.reason != MatchDirector.Reason.TIME_OUT or r.winner != 0:
		f.append("expected P1 time-out win, got %s" % (r.describe() if r else "none"))
	if d.timer_ticks != 0 or d.timer_seconds() != 0:
		f.append("timer should be exactly 0, got %d ticks" % d.timer_ticks)
	return f


func test_all_timeouts_end_in_match_draw() -> Array[String]:
	var s: Array = _setup()
	var sim: CombatSimulation = s[0]
	var d: MatchDirector = s[1]
	var idle := func(_t: int) -> FighterInputFrame: return FighterInputFrame.neutral()
	var f: Array[String] = _run_until_end(sim, d, idle, idle)
	if d.match_winner != -1 or d.round_wins != [2, 2] or d.results.size() != 2:
		f.append("expected match draw after 2 draw rounds, got winner %d wins %s rounds %d" % [
			d.match_winner, d.round_wins, d.results.size()])
	for r: MatchDirector.RoundResult in d.results:
		if r.reason != MatchDirector.Reason.TIME_OUT_DRAW:
			f.append("expected TIME_OUT_DRAW, got %s" % r.describe())
	return f


func test_double_ko_is_draw_round() -> Array[String]:
	var s: Array = _setup()
	var sim: CombatSimulation = s[0]
	var d: MatchDirector = s[1]
	var f: Array[String] = []
	for _t: int in d.rules.intro_ticks:
		d.step(sim, [FighterInputFrame.neutral(), FighterInputFrame.neutral()])
	sim.fighters[0].position_x = -0.45
	sim.fighters[1].position_x = 0.45
	sim.fighters[0].health = 10
	sim.fighters[1].health = 10
	for _t: int in 5:  # both press light together → trade → double KO
		d.step(sim, [FighterInputFrame.with_buttons(L), FighterInputFrame.with_buttons(L)])
	var r: MatchDirector.RoundResult = d.last_result()
	if r == null or r.reason != MatchDirector.Reason.DOUBLE_KO or r.winner != -1:
		f.append("expected DOUBLE_KO draw, got %s" % (r.describe() if r else "none"))
	if d.round_wins != [1, 1]:
		f.append("draw should award both a round, got %s" % [d.round_wins])
	return f


func test_draws_without_awarding_both_still_end_at_round_cap() -> Array[String]:
	var rules: MatchRules = _rules()
	rules.draw_awards_both = false
	rules.round_time_seconds = 2  # keep the test fast
	var s: Array = _setup(rules)
	var sim: CombatSimulation = s[0]
	var d: MatchDirector = s[1]
	var idle := func(_t: int) -> FighterInputFrame: return FighterInputFrame.neutral()
	var f: Array[String] = _run_until_end(sim, d, idle, idle)
	if d.results.size() != rules.max_rounds or d.match_winner != -1:
		f.append("expected %d draw rounds then match draw, got %d rounds winner %d" % [
			rules.max_rounds, d.results.size(), d.match_winner])
	return f


func test_round_transition_resets_everything() -> Array[String]:
	var s: Array = _setup()
	var sim: CombatSimulation = s[0]
	var d: MatchDirector = s[1]
	var f: Array[String] = []
	var guard: int = 0
	var aggressor: Callable = _p1_aggressor(sim)
	while d.round_number < 2 and guard < 20000:
		d.step(sim, [aggressor.call(guard), FighterInputFrame.neutral()])
		guard += 1
	if d.round_number != 2 or d.phase != MatchDirector.Phase.INTRO or d.phase_ticks != 0:
		return ["did not reach round 2 intro (round %d, %s)" % [d.round_number, d.phase_name()]]
	if d.timer_ticks != d.rules.round_ticks():
		f.append("timer not reset: %d" % d.timer_ticks)
	if sim.hitstop_remaining != 0:
		f.append("hitstop carried over")
	var spawns: Array[float] = [sim.arena.p1_spawn_x, sim.arena.p2_spawn_x]
	for i: int in 2:
		var st: FighterState = sim.fighters[i]
		if st.position_x != spawns[i] or st.health != sim.definitions[i].base_health \
				or st.action != FighterState.Action.IDLE or st.move != null \
				or st.stun_remaining != 0 or st.pushback_remaining != 0.0:
			f.append("P%d not reset: %s" % [i + 1, st.describe()])
	if sim.fighters[0].facing != 1 or sim.fighters[1].facing != -1:
		f.append("facing not reset")
	if d.round_wins != [1, 0]:
		f.append("round wins after round 1: %s" % [d.round_wins])
	return f


func test_inputs_ignored_outside_fight_phase() -> Array[String]:
	var s: Array = _setup()
	var sim: CombatSimulation = s[0]
	var d: MatchDirector = s[1]
	var f: Array[String] = []
	for _t: int in d.rules.intro_ticks - 1:
		d.step(sim, [FighterInputFrame.with_buttons(H, 1), FighterInputFrame.with_buttons(L, -1)])
	for e: CombatEvent in sim.combat_log.all_events():
		if e.type == CombatEvent.Type.ATTACK_START:
			f.append("attack started during intro")
	if sim.fighters[0].position_x != sim.arena.p1_spawn_x:
		f.append("P1 moved during intro")
	return f


func test_rematch_starts_clean_match() -> Array[String]:
	var s: Array = _setup()
	var sim: CombatSimulation = s[0]
	var d: MatchDirector = s[1]
	var f: Array[String] = _run_until_end(sim, d, _p1_aggressor(sim), func(_t: int) -> FighterInputFrame: return FighterInputFrame.neutral())
	d.start_match(sim)
	if d.round_number != 1 or d.round_wins != [0, 0] or not d.results.is_empty():
		f.append("rematch round/wins/results not reset")
	if d.phase != MatchDirector.Phase.INTRO or d.timer_ticks != d.rules.round_ticks() or d.match_winner != -1:
		f.append("rematch phase/timer/winner not reset")
	for i: int in 2:
		if sim.fighters[i].health != sim.definitions[i].base_health or sim.fighters[i].action != FighterState.Action.IDLE:
			f.append("P%d not fresh after rematch" % (i + 1))
	if sim.combat_log.total_count() != 1:  # just the RESET event
		f.append("combat log not cleared (%d events)" % sim.combat_log.total_count())
	# And the rematch plays out to a valid end too.
	f.append_array(_run_until_end(sim, d, _p1_aggressor(sim), func(_t: int) -> FighterInputFrame: return FighterInputFrame.neutral()))
	return f


func test_random_matches_always_end_validly() -> Array[String]:
	# Seeded random button mashing for both players, short rounds so many
	# matches run; invariants are checked on every tick.
	var f: Array[String] = []
	var rng := RandomNumberGenerator.new()
	rng.seed = 20261118
	var rules: MatchRules = _rules()
	rules.round_time_seconds = 20
	var outcomes: Dictionary = {}
	for m: int in 12:
		var s: Array = _setup(rules)
		var sim: CombatSimulation = s[0]
		var d: MatchDirector = s[1]
		var buttons: Array[int] = [0, L, H, K, B, B, 0, 0]
		# Each player drifts toward the other (+1 for P1, -1 for P2) so they
		# actually fight; per-match aggression differs so outcomes vary.
		var p1_dirs: Array[int] = [-1, 0, 1, 1]
		var p2_dirs: Array[int] = [1, 0, -1, -1]
		# Out of range they walk (with random hesitation); in range they mash.
		var gen1 := func(_t: int) -> FighterInputFrame:
			if sim.separation() > 1.5:
				return FighterInputFrame.moving(p1_dirs[rng.randi() % 4])
			return FighterInputFrame.with_buttons(buttons[rng.randi() % buttons.size()], p1_dirs[rng.randi() % 4])
		var gen2 := func(_t: int) -> FighterInputFrame:
			if sim.separation() > 1.5:
				return FighterInputFrame.moving(p2_dirs[rng.randi() % 4])
			return FighterInputFrame.with_buttons(buttons[rng.randi() % buttons.size()], p2_dirs[rng.randi() % 4])
		f.append_array(_run_until_end(sim, d, gen1, gen2))
		outcomes[d.match_winner] = outcomes.get(d.match_winner, 0) + 1
		if d.is_match_over():
			var max_wins: int = maxi(d.round_wins[0], d.round_wins[1])
			if d.match_winner >= 0 and d.round_wins[d.match_winner] != max_wins:
				f.append("match %d: winner %d does not have most round wins %s" % [m, d.match_winner, d.round_wins])
	if outcomes.size() < 2:
		f.append("random matches all had the same outcome %s — scenario too weak" % [outcomes])
	return f


func test_meter_carries_between_rounds_not_matches() -> Array[String]:
	var f: Array[String] = []
	var s: Array = _setup()
	var sim: CombatSimulation = s[0]
	var d: MatchDirector = s[1]
	var guard: int = 0
	var aggressor: Callable = _p1_aggressor(sim)
	var meter_at_ko: int = -1
	while d.round_number < 2 and guard < 20000:
		d.step(sim, [aggressor.call(guard), FighterInputFrame.neutral()])
		if d.phase == MatchDirector.Phase.ROUND_END and meter_at_ko < 0:
			meter_at_ko = sim.fighters[0].meter
		guard += 1
	if meter_at_ko <= 0:
		return ["setup: P1 built no meter in round 1"]
	if sim.fighters[0].meter != meter_at_ko:
		f.append("meter not carried into round 2 (%d -> %d)" % [meter_at_ko, sim.fighters[0].meter])
	d.start_match(sim)
	if sim.fighters[0].meter != 0 or sim.fighters[1].meter != 0:
		f.append("a new match must start with empty meters")
	return f
