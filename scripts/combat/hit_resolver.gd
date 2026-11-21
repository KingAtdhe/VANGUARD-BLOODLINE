class_name HitResolver
extends RefCounted
## Applies detected contacts: hit vs block, damage, combo scaling, stun,
## pushback, hitstop and KO. Rules (docs/COMBAT_FRAME_DATA.md):
##   - Blocked if the defender is in BLOCK or BLOCKSTUN and its guard height
##     stops the move (MoveData.blocked_by): MID/PROJECTILE either guard, HIGH
##     standing only, LOW low block only. Fighters always face each other, so
##     every attack comes from the front.
##   - Hit: if the defender was already in HITSTUN it is the next hit of a
##     combo, otherwise a new combo starts at hit 1. Damage is scaled by the
##     hit number (CombatTuning). Defender enters HITSTUN; any attack it was
##     performing is interrupted.
##   - Block: defender loses unscaled `chip_damage` (can KO), enters BLOCKSTUN,
##     and any combo on it ends.
##   - Either way the attack is spent (one connection per attack) and the
##     defender slides back by `pushback` over PUSHBACK_TICKS ticks.
##   - Global hitstop = largest hitstop among this tick's contacts.
##   - Attacker in Origin Surge: damage and chip x surge_damage_percent
##     (before combo scaling).
##   - Meter: attacker gains the move's meter_gain_on_hit/_on_block; the
##     defender gains a percentage of damage taken / a flat amount on block.
##   - A `knockdown` move that HITS knocks the defender down (no hurtbox while
##     down and getting up), which ends the combo.
##   - Armour: a defender whose move has armour on this frame takes the
##     damage but is not interrupted, stunned or pushed (throws ignore it).
##   - Throws (HitLevel.THROW) cannot be blocked and do not connect on a
##     fighter in hitstun or blockstun (HitboxSystem).
##   - Blocking fighters take chip x their definition's chip_taken_percent.
##   - Counter: if the defender is in a counter stance that catches the move
##     (MoveData.counters), nothing above applies — see _counter().
##   - Health reaching 0 → KO (no hurtbox, ignores input). With
##     sim.ko_enabled == false (training) health stops at 1.
## All decisions are taken from the state BEFORE any contact is applied, so
## simultaneous hits trade fairly regardless of P1/P2 order.

const PUSHBACK_TICKS: int = 6


## Returns the hitstop (ticks) to apply. Adds events to the sim's combat log.
static func resolve(contacts: Array[HitboxSystem.Contact], sim: CombatSimulation) -> int:
	if contacts.is_empty():
		return 0
	var states: Array[FighterState] = sim.fighters
	# Snapshot moves, block decisions and combo state first: applying one
	# contact changes the defender, which a trade still needs unchanged.
	var moves: Array[MoveData] = []
	var blocked: Array[bool] = []
	var in_combo: Array[bool] = []
	var countered: Array[bool] = []
	var armored: Array[bool] = []
	for c: HitboxSystem.Contact in contacts:
		var move: MoveData = states[c.attacker].move
		moves.append(move)
		blocked.append(states[c.defender].is_blocking() and move.blocked_by(states[c.defender].block_low))
		in_combo.append(states[c.defender].action == FighterState.Action.HITSTUN)
		var d: FighterState = states[c.defender]
		countered.append(d.action == FighterState.Action.ATTACK and d.move != null
				and d.move.counters(d.move_frame, move.hit_level))
		armored.append(d.action == FighterState.Action.ATTACK and d.move != null and d.armor_left > 0
				and d.move.has_armor_on(d.move_frame) and not move.is_throw())

	var hitstop: int = 0
	for i: int in contacts.size():
		var c: HitboxSystem.Contact = contacts[i]
		var attacker: FighterState = states[c.attacker]
		var defender: FighterState = states[c.defender]
		var move: MoveData = moves[i]
		attacker.move_connected = true
		hitstop = maxi(hitstop, move.hitstop_frames)
		if countered[i]:
			_counter(c, sim)
			continue

		var attacker_def: FighterDefinition = sim.definitions[c.attacker]
		var dmg: int
		var percent: int = 100
		if blocked[i]:
			dmg = OriginMeter.surge_damage(move.chip_damage, attacker, attacker_def) \
					* sim.definitions[c.defender].chip_taken_percent / 100
			defender.combo_hits = 0
			defender.combo_damage = 0
		else:
			defender.combo_hits = defender.combo_hits + 1 if in_combo[i] else 1
			if not in_combo[i]:
				defender.combo_damage = 0
			percent = sim.tuning.scaling_percent(defender.combo_hits)
			dmg = sim.tuning.scaled_damage(
				OriginMeter.surge_damage(move.damage, attacker, attacker_def), defender.combo_hits)
		var floor_hp: int = 0 if sim.ko_enabled else 1
		var before_hp: int = defender.health
		defender.health = maxi(mini(floor_hp, before_hp), defender.health - dmg)
		dmg = before_hp - defender.health
		if not blocked[i]:
			defender.combo_damage += dmg
		OriginMeter.gain(attacker, move.meter_gain_on_block if blocked[i] else move.meter_gain_on_hit, sim.tuning)
		OriginMeter.gain(defender, sim.tuning.meter_on_block_taken if blocked[i]
			else dmg * sim.tuning.meter_on_damage_taken_percent / 100, sim.tuning)

		var ev := CombatEvent.new()
		ev.tick = sim.tick
		ev.type = CombatEvent.Type.BLOCK if blocked[i] else CombatEvent.Type.HIT
		ev.actor = c.attacker
		ev.target = c.defender
		ev.move_id = move.id
		ev.damage = dmg
		ev.target_health = defender.health
		ev.point = c.point
		ev.hitstop = move.hitstop_frames
		ev.combo_hits = 0 if blocked[i] else defender.combo_hits
		ev.scaling_percent = percent
		ev.armored = armored[i] and defender.health > 0
		sim.combat_log.add(ev)

		if defender.health == 0:
			_knock_out(defender, c.defender, sim)
			continue
		if armored[i]:
			# Armour: the damage above stands, the move carries on.
			defender.armor_left -= 1
			defender.combo_hits = 0
			defender.combo_damage = 0
			continue

		# Interrupt whatever the defender was doing (including its own attack,
		# unless that attack already connected this tick — a trade).
		defender.move = null
		defender.move_frame = 0
		defender.move_connected = false
		defender.move_x = 0
		defender.chain.clear()
		if blocked[i]:
			defender.action = FighterState.Action.BLOCKSTUN
			defender.stun_remaining = move.blockstun_frames
		elif move.knockdown:
			defender.action = FighterState.Action.KNOCKDOWN
			defender.stun_remaining = sim.tuning.knockdown_ticks
			var kd := CombatEvent.new()
			kd.tick = sim.tick
			kd.type = CombatEvent.Type.KNOCKDOWN
			kd.actor = c.attacker
			kd.target = c.defender
			kd.move_id = move.id
			sim.combat_log.add(kd)
		else:
			defender.action = FighterState.Action.HITSTUN
			defender.stun_remaining = move.hitstun_frames
		# Push away from the attacker.
		var away: float = signf(defender.position_x - attacker.position_x)
		if away == 0.0:
			away = float(attacker.facing)
		defender.pushback_remaining = away * move.pushback
		defender.pushback_step = move.pushback / PUSHBACK_TICKS
	return hitstop


## The defender's counter stance caught the attack: no damage, the attacker
## is frozen (a zero-damage stagger that the follow-up combos from) and the
## defender goes straight into the counter's follow-up attack.
static func _counter(c: HitboxSystem.Contact, sim: CombatSimulation) -> void:
	var attacker: FighterState = sim.fighters[c.attacker]
	var defender: FighterState = sim.fighters[c.defender]
	var stance: MoveData = defender.move
	var ev := CombatEvent.new()
	ev.tick = sim.tick
	ev.type = CombatEvent.Type.COUNTER
	ev.actor = c.defender
	ev.target = c.attacker
	ev.move_id = stance.id
	ev.point = c.point
	ev.target_health = attacker.health
	sim.combat_log.add(ev)
	attacker.move = null
	attacker.move_frame = 0
	attacker.move_x = 0
	attacker.chain.clear()
	attacker.combo_hits = 0
	attacker.combo_damage = 0
	attacker.action = FighterState.Action.HITSTUN
	attacker.stun_remaining = stance.counter_stun_frames
	defender.move_connected = true
	if stance.counter_followup != null:
		sim.start_followup(c.defender, stance.counter_followup)


static func _knock_out(f: FighterState, index: int, sim: CombatSimulation) -> void:
	f.action = FighterState.Action.KO
	f.move = null
	f.move_frame = 0
	f.stun_remaining = 0
	f.move_x = 0
	f.pushback_remaining = 0.0
	f.chain.clear()
	f.buffer.clear()
	var ev := CombatEvent.new()
	ev.tick = sim.tick
	ev.type = CombatEvent.Type.KO
	ev.target = index
	sim.combat_log.add(ev)
