class_name MatchRules
extends Resource
## Match configuration (spec §2.3). Starting values, tuned in playtests.
## Durations are in 60 Hz combat ticks unless named *_seconds.

## Training mode (spec §6.1): no intro, no timer, no rounds, no KO; each
## fighter's health refills once it is back in neutral after a combo.
@export var training: bool = false
@export var rounds_to_win: int = 2
@export var round_time_seconds: int = 90
## "ROUND n / FIGHT!" intro; inputs are ignored.
@export var intro_ticks: int = 90
## Pause after KO or time-out before the next round / results; inputs ignored.
@export var round_end_ticks: int = 150
## Equal health at time-out, or a double KO, is a draw round. If true, both
## fighters are awarded the round (so the match always progresses); if both
## reach rounds_to_win together the match is a draw.
@export var draw_awards_both: bool = true
## Hard cap on rounds. When reached, the fighter with more round wins takes
## the match, otherwise it is a draw. Guarantees the match always ends.
@export var max_rounds: int = 5


func round_ticks() -> int:
	return round_time_seconds * CombatConstants.TICK_RATE


func validate() -> Array[String]:
	var p: Array[String] = []
	if rounds_to_win < 1:
		p.append("rounds_to_win must be >= 1")
	if round_time_seconds < 1:
		p.append("round_time_seconds must be >= 1")
	if intro_ticks < 0 or round_end_ticks < 0:
		p.append("intro/round_end ticks must be >= 0")
	if max_rounds < rounds_to_win * 2 - 1:
		p.append("max_rounds must allow a decisive match (>= 2*rounds_to_win-1)")
	return p
