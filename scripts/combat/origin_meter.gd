class_name OriginMeter
extends RefCounted
## Origin meter and Origin Surge rules (spec §4.6). Pure functions on
## FighterState so the simulation stays readable.
##
##   - Meter 0..tuning.meter_max. Never purchasable.
##   - Gains: attacker per move (meter_gain_on_hit / _on_block); defender a
##     percentage of damage taken, or a flat amount per blocked attack.
##     No gains while in Surge (the meter is draining).
##   - Origin Surge: needs a full meter; activation is a move with a
##     readable startup; afterwards the meter drains linearly to 0 over the
##     fighter's surge_duration_ticks. While active: damage x surge_damage_percent,
##     specials free (per fighter), and the ultimate becomes available.
##   - Ultimate (requires_surge + consumes_all_meter): needs at least its
##     meter_cost, spends everything, ends Surge.


## Can fighter [param f] use [param m] right now (meter/surge conditions)?
static func can_use(f: FighterState, def: FighterDefinition, m: MoveData, tuning: CombatTuning) -> bool:
	if m.activates_surge:
		return not f.in_surge() and f.meter >= tuning.meter_max
	if m.requires_surge and not f.in_surge():
		return false
	return f.meter >= cost_of(f, def, m)


## Meter actually charged when [param m] starts.
static func cost_of(f: FighterState, def: FighterDefinition, m: MoveData) -> int:
	if m.activates_surge:
		return 0  # the full meter becomes the draining Surge meter
	if f.in_surge() and def.surge_free_specials and m.tags.has("special"):
		return 0
	return m.meter_cost


## Applies the cost of a starting move. Returns true if Surge ended.
static func pay(f: FighterState, def: FighterDefinition, m: MoveData) -> bool:
	if m.consumes_all_meter:
		f.meter = 0
		var was: bool = f.in_surge()
		f.surge_remaining = 0
		return was
	f.meter = maxi(0, f.meter - cost_of(f, def, m))
	return false


static func start_surge(f: FighterState, def: FighterDefinition, tuning: CombatTuning) -> void:
	f.surge_remaining = def.surge_duration_ticks
	f.meter = tuning.meter_max


## One non-hitstop tick of Surge drain. Returns true when Surge just ended.
static func tick_surge(f: FighterState, def: FighterDefinition, tuning: CombatTuning) -> bool:
	if not f.in_surge():
		return false
	f.surge_remaining -= 1
	f.meter = ceili(float(tuning.meter_max) * f.surge_remaining / def.surge_duration_ticks)
	return f.surge_remaining == 0


static func gain(f: FighterState, amount: int, tuning: CombatTuning) -> void:
	if f.in_surge() or amount <= 0:
		return
	f.meter = mini(tuning.meter_max, f.meter + amount)


## Damage after the attacker's Surge bonus (before combo scaling).
static func surge_damage(base: int, attacker: FighterState, def: FighterDefinition) -> int:
	if base <= 0 or not attacker.in_surge():
		return base
	return base * def.surge_damage_percent / 100
