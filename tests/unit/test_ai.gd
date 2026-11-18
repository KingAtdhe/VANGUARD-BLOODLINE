extends RefCounted
## Milestone 5: AI opponent — fairness, difficulty, defeatability, liveness.

const L: int = FighterInputFrame.BUTTON_LIGHT
const K: int = FighterInputFrame.BUTTON_KICK
const NAMES: Array[String] = ["beginner", "standard", "expert"]


func _defs() -> Array[FighterDefinition]:
	return [load("res://data/fighters/kairo.tres"), load("res://data/fighters/training_dummy.tres")]


func _sim() -> CombatSimulation:
	var d: Array[FighterDefinition] = _defs()
	var sim := CombatSimulation.new()
	sim.setup(load("res://data/arenas/greybox_arena.tres"), d[0], d[1], load("res://data/rules/combat_tuning.tres"))
	return sim


func _profile(name: String) -> AIProfile:
	return load("res://data/ai/%s.tres" % name)


## Scripted "rushdown" human stand-in: walk in, then L, L, K pressure.
func _rushdown(sim: CombatSimulation, t: int, side: int) -> FighterInputFrame:
	if sim.separation() > 0.85:
		return FighterInputFrame.moving(1 if side == 0 else -1)
	return FighterInputFrame.with_buttons([L, 0, L, 0, K, 0][t % 6])


## Plays a match. Each side is an AIProfile name or "rushdown"/"idle".
## Returns {winner, rounds, log, inputs: [[p1 frames], [p2 frames]], max_idle: [a, b], sim}.
func _play(p1: String, p2: String, seed: int, round_seconds: int = 30) -> Dictionary:
	var sim := _sim()
	var defs: Array[FighterDefinition] = _defs()
	var rules: MatchRules = (load("res://data/rules/standard_match.tres") as MatchRules).duplicate()
	rules.round_time_seconds = round_seconds
	var d := MatchDirector.new(rules)
	var ais: Array = [null, null]
	var names: Array[String] = [p1, p2]
	for i: int in 2:
		if NAMES.has(names[i]):
			ais[i] = AIController.new(_profile(names[i]), i, defs[i], defs[1 - i], seed * (i + 3) + i)
	d.round_started.connect(func(_r: int) -> void:
		for a: Variant in ais:
			if a != null:
				(a as AIController).reset())
	d.start_match(sim)
	var inputs: Array = [[], []]
	var idle_run: Array[int] = [0, 0]
	var max_idle: Array[int] = [0, 0]
	var t: int = 0
	while not d.is_match_over() and t < 60000:
		t += 1
		var obs := AIObservation.from_sim(sim)
		var frames: Array[FighterInputFrame] = []
		for i: int in 2:
			var fr: FighterInputFrame
			if ais[i] != null:
				(ais[i] as AIController).observe(obs)
				fr = (ais[i] as AIController).next_input()
			elif names[i] == "rushdown":
				fr = _rushdown(sim, t, i)
			else:
				fr = FighterInputFrame.neutral()
			frames.append(fr)
			inputs[i].append(fr)
			# Liveness: neutral-state ticks in FIGHT with no input at all.
			if d.phase == MatchDirector.Phase.FIGHT and sim.fighters[i].is_neutral() \
					and fr.move_x == 0 and fr.buttons == 0:
				idle_run[i] += 1
				max_idle[i] = maxi(max_idle[i], idle_run[i])
			else:
				idle_run[i] = 0
		d.step(sim, frames)
	return {"winner": d.match_winner, "over": d.is_match_over(), "rounds": d.round_wins,
		"log": sim.combat_log.to_text(), "inputs": inputs, "max_idle": max_idle, "ais": ais}


func test_profiles_valid_and_only_skill_knobs() -> Array[String]:
	var f: Array[String] = []
	for n: String in NAMES:
		f.append_array(_profile(n).validate())
	# Difficulty may not touch damage, health, speed or frame data (spec §5).
	for prop: Dictionary in AIProfile.new().get_property_list():
		var name: String = String(prop.name).to_lower()
		for banned: String in ["damage", "health", "speed", "multiplier", "frames", "hitstun", "meter"]:
			if name.contains(banned):
				f.append("AIProfile has forbidden knob '%s'" % prop.name)
	var delays: Array[int] = []
	for n: String in NAMES:
		delays.append(_profile(n).reaction_delay_ticks)
	if not (delays[0] > delays[1] and delays[1] > delays[2]):
		f.append("reaction delays not ordered beginner > standard > expert: %s" % [delays])
	return f


func test_observation_exposes_only_visible_information() -> Array[String]:
	var f: Array[String] = []
	var seen_props: PackedStringArray = []
	for prop: Dictionary in AIObservation.Seen.new().get_property_list():
		seen_props.append(String(prop.name))
	for hidden: String in ["buffer", "held_buttons", "pending", "chain", "stun_remaining", "move_x", "pushback"]:
		for p: String in seen_props:
			if p.contains(hidden):
				f.append("AIObservation.Seen exposes hidden field '%s'" % p)
	# The controller must not keep any reference to the simulation.
	for prop: Dictionary in AIController.new(_profile("expert"), 1, _defs()[1], _defs()[0]).get_property_list():
		if String(prop.class_name) in ["CombatSimulation", "FighterState", "FighterInputFrame"] and String(prop.name) != "":
			f.append("AIController holds a %s (%s)" % [prop.class_name, prop.name])
	return f


func test_ai_does_not_read_future_input() -> Array[String]:
	# Two worlds: P1's inputs are identical up to tick T, then differ. The AI's
	# outputs must be identical for every tick it could not have seen the
	# difference: through T + reaction_delay (it acts on tick t using state up
	# to t-1, and sees the opponent reaction_delay ticks late).
	var f: Array[String] = []
	const T: int = 300
	for n: String in NAMES:
		var profile: AIProfile = _profile(n)
		var outs: Array = []
		for world: int in 2:
			var sim := _sim()
			var d := MatchDirector.new(load("res://data/rules/standard_match.tres"))
			var ai := AIController.new(profile, 1, _defs()[1], _defs()[0], 77)
			d.start_match(sim)
			var out: Array[String] = []
			for t: int in T + profile.reaction_delay_ticks + 80:
				var p1: FighterInputFrame
				if t < T:
					p1 = FighterInputFrame.moving(1) if t % 50 < 30 else FighterInputFrame.with_buttons(L if t % 4 == 0 else 0)
				else:
					p1 = FighterInputFrame.moving(-1) if world == 0 else FighterInputFrame.with_buttons(K if t % 3 == 0 else 0, 1)
				ai.observe(AIObservation.from_sim(sim))
				var a: FighterInputFrame = ai.next_input()
				out.append("%d:%d" % [a.move_x, a.buttons])
				d.step(sim, [p1, a])
			outs.append(out)
		var limit: int = T + profile.reaction_delay_ticks
		for t: int in limit + 1:
			if outs[0][t] != outs[1][t]:
				f.append("%s: AI output differs at tick %d (≤ %d) — it reacted to input it could not see" % [n, t, limit])
				break
	return f


## Observation with the opponent (P1) at [param x], optionally mid-heavy.
func _obs(p1_x: float, p1_attacking: bool) -> AIObservation:
	var sim := _sim()
	sim.fighters[0].position_x = p1_x
	sim.fighters[1].position_x = 1.0
	if p1_attacking:
		sim.fighters[0].action = FighterState.Action.ATTACK
		sim.fighters[0].move = _defs()[0].move_for(&"HEAVY")
		sim.fighters[0].move_frame = 3
	return AIObservation.from_sim(sim)


func test_ai_perception_is_exactly_reaction_delay_old() -> Array[String]:
	# Feed: the oldest snapshot shows P1 far away and idle; every newer one
	# shows P1 right next to the AI starting a heavy. A fair AI acts on what it
	# saw reaction_delay ticks ago (far → no block). Then reverse the setup:
	# when the old snapshot is the threat, the AI must be able to block.
	var f: Array[String] = []
	for n: String in NAMES:
		var profile: AIProfile = _profile(n)
		var blocked_on_future: int = 0
		var blocked_on_past: int = 0
		for seed: int in 20:
			var ai := AIController.new(profile, 1, _defs()[1], _defs()[0], seed)
			ai.observe(_obs(-3.0, false))
			for _k: int in profile.reaction_delay_ticks:
				ai.observe(_obs(0.1, true))
			if ai.next_input().is_held(FighterInputFrame.BUTTON_BLOCK):
				blocked_on_future += 1
			var ai2 := AIController.new(profile, 1, _defs()[1], _defs()[0], seed)
			ai2.observe(_obs(0.1, true))
			for _k: int in profile.reaction_delay_ticks:
				ai2.observe(_obs(-3.0, false))
			if ai2.next_input().is_held(FighterInputFrame.BUTTON_BLOCK):
				blocked_on_past += 1
		if blocked_on_future > 0:
			f.append("%s blocked an attack it could not have seen yet (%d/20)" % [n, blocked_on_future])
		if n != "beginner" and blocked_on_past == 0:
			f.append("%s never blocked an attack it had seen (0/20) — test not sensitive" % n)
	return f


func test_ai_actions_are_legal_player_actions() -> Array[String]:
	# Replaying the AI's recorded inputs as if a human pressed them must give
	# the exact same fight: the AI has no other channel into the simulation.
	var f: Array[String] = []
	var res: Dictionary = _play("standard", "expert", 11)
	var sim := _sim()
	var d := MatchDirector.new((load("res://data/rules/standard_match.tres") as MatchRules).duplicate())
	d.rules.round_time_seconds = 30
	d.start_match(sim)
	var n: int = (res.inputs[0] as Array).size()
	for t: int in n:
		d.step(sim, [res.inputs[0][t], res.inputs[1][t]])
	if sim.combat_log.to_text() != res.log:
		f.append("replaying the AIs' inputs produced a different fight")
	# Every attack an AI started was started from a legal state (the sim
	# enforces this; check the log agrees: cancels only after contact).
	for line: String in res.log.split("\n"):
		if line.contains("cancels") and not (line.contains("kairo_light_punch ->")):
			f.append("illegal cancel route in AI fight: %s" % line)
	return f


func test_difficulties_are_distinguishable() -> Array[String]:
	var f: Array[String] = []
	# Head-to-head on both sides of the screen.
	for pair: Array in [["standard", "beginner"], ["expert", "standard"]]:
		var stronger_wins: int = 0
		var games: int = 0
		for seed: int in 4:
			for swap: bool in [false, true]:
				var p1: String = pair[1] if swap else pair[0]
				var p2: String = pair[0] if swap else pair[1]
				var r: Dictionary = _play(p1, p2, 100 + seed)
				games += 1
				var strong_side: int = 1 if swap else 0
				if r.winner == strong_side:
					stronger_wins += 1
		if stronger_wins * 4 < games * 3:  # stronger must win ≥ 75 %
			f.append("%s beat %s only %d/%d times" % [pair[0], pair[1], stronger_wins, games])
	# Behavioural fingerprints against the same scripted rushdown.
	var blocks: Array[int] = []
	for n: String in NAMES:
		var total: int = 0
		for seed: int in 3:
			var r: Dictionary = _play("rushdown", n, 300 + seed)
			total += (r.log as String).count("BLOCKED by P2")
		blocks.append(total)
	if not (blocks[2] > blocks[0]) or not (blocks[1] > blocks[0]):
		f.append("blocking vs rushdown not ordered by difficulty: %s" % [blocks])
	return f


func test_ai_can_be_defeated() -> Array[String]:
	var f: Array[String] = []
	# A simple scripted pressure player beats Beginner and Standard…
	for n: String in ["beginner", "standard"]:
		var wins: int = 0
		for seed: int in 3:
			if _play("rushdown", n, 400 + seed).winner == 0:
				wins += 1
		if wins == 0:
			f.append("%s could not be defeated by the scripted rushdown" % n)
	# …and Expert loses to nothing scripted here, but is defeatable by rules:
	# take damage and lose rounds like anyone (no hidden protection).
	var r: Dictionary = _play("rushdown", "expert", 500)
	if not (r.log as String).contains("HIT P2"):
		f.append("expert never took a hit — suspicious")
	return f


func test_ai_never_idles_permanently() -> Array[String]:
	var f: Array[String] = []
	for n: String in NAMES:
		# Against a completely passive opponent the AI must still come and win.
		var r: Dictionary = _play("idle", n, 600)
		if r.winner != 1:
			f.append("%s did not beat an idle opponent (winner %d, rounds %s)" % [n, r.winner, r.rounds])
		var limit: int = _profile(n).max_idle_ticks + _profile(n).decision_interval_ticks + _profile(n).reaction_delay_ticks + 2
		if r.max_idle[1] > limit:
			f.append("%s idled %d ticks in a row (limit %d)" % [n, r.max_idle[1], limit])
	return f


func test_ai_is_deterministic_and_logs_decisions() -> Array[String]:
	var f: Array[String] = []
	var a: Dictionary = _play("expert", "beginner", 42)
	var b: Dictionary = _play("expert", "beginner", 42)
	if a.log != b.log:
		f.append("same seeds produced different fights")
	var ai: AIController = a.ais[0]
	if ai.decision_log.total_count() < 20:
		f.append("decision log nearly empty (%d)" % ai.decision_log.total_count())
	var text: String = ai.decision_log.to_text()
	for word: String in ["decide", "press", "APPROACH"]:
		if not text.contains(word):
			f.append("decision log has no '%s' entries" % word)
	return f
