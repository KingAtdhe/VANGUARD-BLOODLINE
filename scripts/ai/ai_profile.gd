class_name AIProfile
extends Resource
## One AI difficulty (spec §5). Difficulty comes ONLY from reaction time,
## decision quality and move selection — never from damage, health, speed or
## frame-data changes. Lives in data/ai/.

@export var difficulty_name: String = "Standard"

@export_group("Perception")
## Ticks between something happening to the opponent and the AI seeing it.
@export_range(0, 60) var reaction_delay_ticks: int = 10
## 0..1: how much of the reaction delay the AI compensates by projecting the
## opponent's visible walking velocity ("reading" an approach). Spacing skill.
@export_range(0.0, 1.0) var anticipation: float = 0.5
## How often a new neutral decision is made (ticks).
@export_range(1, 60) var decision_interval_ticks: int = 12

@export_group("Offence")
## Chance to attack (in range) or approach (out of range) at each decision.
@export_range(0.0, 1.0) var aggression: float = 0.6
## Relative weights for choosing LIGHT / HEAVY / KICK among moves in range.
@export var attack_weights: Dictionary = {&"LIGHT": 4.0, &"HEAVY": 3.0, &"KICK": 3.0}
## Weight multiplier for LIGHT when the opponent is in Light range (fastest
## move wins exchanges up close). Decision-quality knob.
@export_range(1.0, 5.0) var close_light_bias: float = 1.0
## Chance to pick a move without checking its range (a beginner mistake).
@export_range(0.0, 1.0) var range_mistake_chance: float = 0.0
## Chance to commit to the combo route when opening with its first move.
@export_range(0.0, 1.0) var combo_chance: float = 0.5
## Combo route by input pattern (must be legal cancels for the fighter).
@export var combo_route: PackedStringArray = PackedStringArray(["LIGHT", "LIGHT", "KICK"])

@export_group("Origin meter")
## Chance per decision to activate Origin Surge when the meter is full.
@export_range(0.0, 1.0) var surge_chance: float = 0.3
## Outside Surge, stop spending meter on specials once it reaches this
## (saving for Origin Surge). 101+ = never saves.
@export_range(0, 101) var save_for_surge_above: int = 80
## Chance per decision to throw the ultimate when in Surge and in range.
@export_range(0.0, 1.0) var ultimate_chance: float = 0.3

@export_group("Defence")
## Chance to block an attack it SEES starting (subject to reaction delay).
@export_range(0.0, 1.0) var block_reaction_chance: float = 0.6
## Chance that a block against a LOW attack it sees is a low block (and a
## standing one against an overhead); otherwise it guards at the wrong height.
@export_range(0.0, 1.0) var low_block_chance: float = 0.5
## Chance to answer an attack it would have blocked with a counter stance
## instead (only fighters that have one).
@export_range(0.0, 1.0) var counter_chance: float = 0.0
## When only a projectile is in range (far away), chance per decision to
## fire it rather than play the distance like other fighters (walk in, back
## off, wait). Only fighters with a projectile. D-066.
@export_range(0.0, 1.0) var projectile_chance: float = 0.5
## Chance to pre-emptively guard when close and undecided.
@export_range(0.0, 1.0) var guard_chance: float = 0.3
@export_range(1, 120) var guard_ticks: int = 18
## Chance to punish an opponent attack it sees in recovery.
@export_range(0.0, 1.0) var punish_chance: float = 0.6
## True: punish with the most damaging move that still fits; false: Light.
@export var punish_optimally: bool = false
## Chance, per stun, to mash Light during hitstun/blockstun so a reversal
## comes out on the first actionable tick (legal: the input buffer holds it).
@export_range(0.0, 1.0) var mash_out_chance: float = 0.5
## Chance to back off at a decision instead of waiting.
@export_range(0.0, 1.0) var retreat_chance: float = 0.15

@export_group("Style")
## Beginner: fixed approach → attack → back-off cycle (spec: predictable).
@export var predictable_pattern: bool = false
## Expert: adapts guard/aggression to the opponent's observed habits.
@export var adaptive: bool = false
## Anti-idle: after this many ticks without doing anything, approach/attack.
@export_range(10, 300) var max_idle_ticks: int = 60


func validate() -> Array[String]:
	var p: Array[String] = []
	if combo_route.is_empty():
		p.append("%s: combo_route is empty" % difficulty_name)
	var total: float = 0.0
	for k: Variant in attack_weights:
		total += float(attack_weights[k])
	if total <= 0.0:
		p.append("%s: attack_weights must have a positive total" % difficulty_name)
	return p
