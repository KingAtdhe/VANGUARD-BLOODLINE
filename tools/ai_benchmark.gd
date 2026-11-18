extends SceneTree
## Headless AI tuning benchmark: plays seeded AI-vs-AI matches and prints
## win rates and behaviour stats per difficulty.
##
## Run:  godot --headless --path . --script res://tools/ai_benchmark.gd
## (Uses shortened 30 s rounds so it finishes quickly.)

const PROFILES: Array[String] = ["beginner", "standard", "expert"]
const MATCHES: int = 10


func _initialize() -> void:
	for a: int in 3:
		for b: int in range(a + 1, 3):
			var wins: Array[int] = [0, 0, 0]  # P1, P2, draw
			var stats: Array[Dictionary] = [{}, {}]
			for m: int in MATCHES:
				var r: Dictionary = play(PROFILES[a], PROFILES[b], 1000 + m)
				wins[r.winner if r.winner >= 0 else 2] += 1
				for i: int in 2:
					for k: String in r.stats[i]:
						stats[i][k] = stats[i].get(k, 0) + r.stats[i][k]
			print("%s vs %s: %d-%d (draws %d)" % [PROFILES[a], PROFILES[b], wins[0], wins[1], wins[2]])
			for i: int in 2:
				print("   %s %s" % [PROFILES[a] if i == 0 else PROFILES[b], stats[i]])
	quit()


## Plays one match; returns {winner, stats: [p1, p2]}.
static func play(p1_name: String, p2_name: String, seed: int, round_seconds: int = 30) -> Dictionary:
	var sim := CombatSimulation.new()
	var kairo: FighterDefinition = load("res://data/fighters/kairo.tres")
	var dummy: FighterDefinition = load("res://data/fighters/training_dummy.tres")
	sim.setup(load("res://data/arenas/greybox_arena.tres"), kairo, dummy, load("res://data/rules/combat_tuning.tres"))
	var rules: MatchRules = (load("res://data/rules/standard_match.tres") as MatchRules).duplicate()
	rules.round_time_seconds = round_seconds
	var d := MatchDirector.new(rules)
	var ais: Array[AIController] = [
		AIController.new(load("res://data/ai/%s.tres" % p1_name), 0, kairo, dummy, seed),
		AIController.new(load("res://data/ai/%s.tres" % p2_name), 1, dummy, kairo, seed * 7 + 3),
	]
	d.round_started.connect(func(_r: int) -> void:
		for ai: AIController in ais:
			ai.reset())
	d.start_match(sim)
	var guard: int = 0
	while not d.is_match_over() and guard < 60000:
		var obs := AIObservation.from_sim(sim)
		var inputs: Array[FighterInputFrame] = []
		for ai: AIController in ais:
			ai.observe(obs)
			inputs.append(ai.next_input())
		d.step(sim, inputs)
		guard += 1
	var stats: Array[Dictionary] = [{"hits": 0, "blocks": 0, "whiffs": 0, "cancels": 0}, {"hits": 0, "blocks": 0, "whiffs": 0, "cancels": 0}]
	for e: CombatEvent in sim.combat_log.all_events():
		if e.actor < 0:
			continue
		match e.type:
			CombatEvent.Type.HIT:
				stats[e.actor].hits += 1
			CombatEvent.Type.BLOCK:
				stats[e.target].blocks += 1
			CombatEvent.Type.WHIFF:
				stats[e.actor].whiffs += 1
			CombatEvent.Type.ATTACK_START:
				if e.cancel_from != &"":
					stats[e.actor].cancels += 1
	return {"winner": d.match_winner, "stats": stats, "ticks": guard, "over": d.is_match_over()}
