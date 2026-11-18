class_name MatchDirector
extends RefCounted
## Deterministic best-of-N match flow on top of CombatSimulation (spec §2.3).
##
## Owns rounds, the round timer and results; the simulation owns fighting.
## Every combat tick goes through [method step], which decides which inputs
## reach the simulation:
##
##   INTRO      "ROUND n" / "FIGHT!"   inputs ignored        → FIGHT
##   FIGHT      timer counts down      player inputs used    → ROUND_END on KO / time-out
##   ROUND_END  "K.O." / "TIME"        inputs ignored        → INTRO (next round) or MATCH_END
##   MATCH_END  results shown          inputs ignored        → (rematch via start_match)
##
## Round results:
##   - KO: the other fighter wins the round. Both KO on the same tick = draw.
##   - Time-out: more health wins; equal health = draw.
##   - Draw: both fighters get the round if rules.draw_awards_both.
## The match ends as soon as a fighter reaches rounds_to_win (both at once =
## match draw) or after rules.max_rounds, so it always reaches an end state.

signal round_started(round_number: int)
signal fight_started(round_number: int)
signal round_ended(result: RoundResult)
signal match_ended(winner: int)

enum Phase { INTRO, FIGHT, ROUND_END, MATCH_END }
enum Reason { KO, DOUBLE_KO, TIME_OUT, TIME_OUT_DRAW }

## Outcome of one round. winner = 0/1, or -1 for a draw.
class RoundResult:
	var round_number: int
	var winner: int
	var reason: Reason

	func describe() -> String:
		var who: String = "draw" if winner < 0 else "P%d" % (winner + 1)
		return "R%d %s (%s)" % [round_number, who, Reason.keys()[reason]]


var rules: MatchRules
var phase: Phase = Phase.INTRO
var round_number: int = 0
var round_wins: Array[int] = [0, 0]
## Remaining round time in ticks. Never negative.
var timer_ticks: int = 0
## Ticks spent in the current phase.
var phase_ticks: int = 0
var results: Array[RoundResult] = []
## Match winner (0/1) or -1 for a draw. Valid only in MATCH_END.
var match_winner: int = -1


func _init(match_rules: MatchRules) -> void:
	assert(match_rules != null)
	rules = match_rules


## Starts a clean match: round 1, no wins, full timer, simulation reset and
## combat log cleared.
func start_match(sim: CombatSimulation) -> void:
	round_wins = [0, 0]
	results.clear()
	match_winner = -1
	round_number = 0
	sim.combat_log.clear()
	_start_round(sim)


## Advances one combat tick. [param inputs] are the raw P1/P2 inputs.
func step(sim: CombatSimulation, inputs: Array[FighterInputFrame]) -> void:
	phase_ticks += 1
	match phase:
		Phase.INTRO:
			sim.step(_neutral())
			if phase_ticks >= rules.intro_ticks:
				_set_phase(Phase.FIGHT)
				fight_started.emit(round_number)
		Phase.FIGHT:
			sim.step(inputs)
			timer_ticks = maxi(0, timer_ticks - 1)
			_check_round_end(sim)
		Phase.ROUND_END:
			sim.step(_neutral())
			if phase_ticks >= rules.round_end_ticks:
				_after_round(sim)
		Phase.MATCH_END:
			sim.step(_neutral())


## Whole seconds left, rounded up (90.0 → 90, 0.01 → 1, 0 → 0).
func timer_seconds() -> int:
	return ceili(float(timer_ticks) / CombatConstants.TICK_RATE)


func is_match_over() -> bool:
	return phase == Phase.MATCH_END


func phase_name() -> String:
	return Phase.keys()[phase]


func last_result() -> RoundResult:
	return results[-1] if not results.is_empty() else null


# --- internals ----------------------------------------------------------------

func _start_round(sim: CombatSimulation) -> void:
	round_number += 1
	timer_ticks = rules.round_ticks()
	sim.reset()
	_set_phase(Phase.INTRO)
	round_started.emit(round_number)


func _check_round_end(sim: CombatSimulation) -> void:
	var ko: Array[bool] = [
		sim.fighters[0].action == FighterState.Action.KO,
		sim.fighters[1].action == FighterState.Action.KO,
	]
	var result: RoundResult = null
	if ko[0] and ko[1]:
		result = _result(-1, Reason.DOUBLE_KO)
	elif ko[0] or ko[1]:
		result = _result(1 if ko[0] else 0, Reason.KO)
	elif timer_ticks == 0:
		var h0: int = sim.fighters[0].health
		var h1: int = sim.fighters[1].health
		if h0 == h1:
			result = _result(-1, Reason.TIME_OUT_DRAW)
		else:
			result = _result(0 if h0 > h1 else 1, Reason.TIME_OUT)
	if result == null:
		return
	if result.winner >= 0:
		round_wins[result.winner] += 1
	elif rules.draw_awards_both:
		round_wins[0] += 1
		round_wins[1] += 1
	results.append(result)
	_set_phase(Phase.ROUND_END)
	round_ended.emit(result)


func _after_round(sim: CombatSimulation) -> void:
	var p1_done: bool = round_wins[0] >= rules.rounds_to_win
	var p2_done: bool = round_wins[1] >= rules.rounds_to_win
	var capped: bool = round_number >= rules.max_rounds
	if p1_done or p2_done or capped:
		if p1_done and p2_done:
			match_winner = -1
		elif p1_done or p2_done:
			match_winner = 0 if p1_done else 1
		else:
			# Round cap reached without a decisive winner.
			match_winner = -1 if round_wins[0] == round_wins[1] else (0 if round_wins[0] > round_wins[1] else 1)
		_set_phase(Phase.MATCH_END)
		match_ended.emit(match_winner)
	else:
		_start_round(sim)


func _result(winner: int, reason: Reason) -> RoundResult:
	var r := RoundResult.new()
	r.round_number = round_number
	r.winner = winner
	r.reason = reason
	return r


func _set_phase(p: Phase) -> void:
	phase = p
	phase_ticks = 0


func _neutral() -> Array[FighterInputFrame]:
	return [FighterInputFrame.neutral(), FighterInputFrame.neutral()]
