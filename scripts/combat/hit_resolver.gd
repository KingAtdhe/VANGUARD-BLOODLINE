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
##   - Launch: a `launch` move that HITS puts the defender in LAUNCHED for
##     launch_frames; hits on a launched fighter continue the combo and
##     re-float it (CombatTuning juggle values); a knockdown move spikes it
##     straight to KNOCKDOWN; when the float ends it lands knocked down.
##   - Armour: a defender whose move has armour on this frame takes the
##     damage but is not interrupted, stunned or pushed (throws ignore it).
##   - Throws (HitLevel.THROW) cannot be blocked and do not connect on a
##     fighter in hitstun or blockstun (HitboxSystem).
##   - Blocking fighters take chip x their definition's chip_taken_percent.
##   - Counter: if the defender is in a counter stance that catches the move
##     (MoveData.counters), nothing above applies — see _counter(). A counter
##     without a follow-up is a parry: its user is free at once.
##   - Projectiles (D-066) resolve like any other hit with the move they were
##     fired with, wherever their owner is now: blocked by either guard,
##     absorbed by armour (damage taken, one armour hit used), never caught
##     by a counter stance or parry, and they pass through a fighter with no
##     hurtbox (invulnerable frames, knocked down). The projectile is used
##     up by the contact. Pushback follows its direction of travel and is
##     not handed to the attacker when the defender is against a wall.
##   - Multi-hit moves (MoveData.rehit_interval) connect once per hit window;
##     every hit is resolved on its own like a separate attack.
##   - A counter with counter_switches_sides puts the caught attacker behind
##     the countering fighter before the follow-up starts.
##   - A defender whose definition has block_pushes_attacker slides the
##     attacker back by that distance on every blocked strike.
##   - Counter-hit: a hit on a fighter whose own attack is in startup or
##     active frames deals CombatTuning.counter_hit_damage_percent, adds
##     hitstun and hitstop, and some moves stagger longer or knock down
##     (MoveData.counter_hit_*). Throws, armoured and countered contacts are
##     never counter-hits.
##   - A multi-hit move with `knockdown` knocks down on its last hit only,
##     and may use a shorter hitstop for the hits before it (D-087).
##   - A fighter hit out of a jump cannot block; it falls (LAUNCHED, from
##     the height it was at) and lands knocked down (D-087).
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
	var counter_hit: Array[bool] = []
	var stop: Array[int] = []
	var last_hit: Array[bool] = []
	var air_height: Array[float] = []
	for c: HitboxSystem.Contact in contacts:
		var move: MoveData = c.move
		moves.append(move)
		# Multi-hit moves: which hit this is decides hitstop and knockdown.
		var on_frame: int = states[c.attacker].move_frame if c.projectile == null else move.startup_frames
		stop.append(move.hitstop_on(on_frame))
		last_hit.append(move.is_last_hit(on_frame))
		air_height.append(states[c.defender].height)
		blocked.append(states[c.defender].is_blocking() and move.blocked_by(states[c.defender].block_low))
		in_combo.append(states[c.defender].action == FighterState.Action.HITSTUN
				or states[c.defender].action == FighterState.Action.LAUNCHED)
		var d: FighterState = states[c.defender]
		countered.append(c.projectile == null and d.action == FighterState.Action.ATTACK
				and d.move != null and d.move.counters(d.move_frame, move.hit_level))
		armored.append(d.action == FighterState.Action.ATTACK and d.move != null and d.armor_left > 0
				and d.move.has_armor_on(d.move_frame) and not move.is_throw())
		# Counter-hit: the defender was attacking and had not reached recovery.
		# Not for throws, armoured or countered contacts, or pure movement moves.
		counter_hit.append(d.action == FighterState.Action.ATTACK and d.move != null and not move.is_throw()
				and not armored[-1] and not countered[-1] and not d.move.activates_surge
				and d.move_frame < d.move.startup_frames + d.move.active_frames)

	var hitstop: int = 0
	for i: int in contacts.size():
		var c: HitboxSystem.Contact = contacts[i]
		var attacker: FighterState = states[c.attacker]
		var defender: FighterState = states[c.defender]
		var move: MoveData = moves[i]
		if c.projectile != null:
			c.projectile.spent = true
		else:
			attacker.move_connected = true
			attacker.last_hit_window = move.hit_window(attacker.move_frame)
		if defender.action == FighterState.Action.KO:
			continue  # already knocked out by an earlier contact this tick
		hitstop = maxi(hitstop, stop[i]
				+ (sim.tuning.counter_hit_extra_hitstop if counter_hit[i] and not countered[i] else 0))
		# A second contact on the same defender in one tick (a projectile
		# arriving together with a strike) continues the combo the first began.
		if not blocked[i] and (defender.action == FighterState.Action.HITSTUN
				or defender.action == FighterState.Action.LAUNCHED):
			in_combo[i] = true
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
			var base: int = OriginMeter.surge_damage(move.damage, attacker, attacker_def)
			if counter_hit[i]:
				base = base * sim.tuning.counter_hit_damage_percent / 100
			dmg = sim.tuning.scaled_damage(base, defender.combo_hits)
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
		ev.hitstop = stop[i]
		ev.combo_hits = 0 if blocked[i] else defender.combo_hits
		ev.scaling_percent = percent
		ev.armored = armored[i] and defender.health > 0
		ev.counter_hit = counter_hit[i] and not blocked[i]
		if not blocked[i]:
			defender.counter_hit = counter_hit[i]
			defender.hit_zone = _zone(move, sim.definitions[c.defender])
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
		defender.end_jump()
		var airborne: bool = defender.action == FighterState.Action.LAUNCHED
		var knocks_down: bool = move.knockdown and last_hit[i]
		if blocked[i]:
			defender.action = FighterState.Action.BLOCKSTUN
			defender.stun_remaining = move.blockstun_frames
		elif airborne and not knocks_down:
			# Juggle: another hit in the air gives a shorter float, up to the limit.
			defender.juggle_hits += 1
			defender.juggle_exhausted = defender.juggle_hits >= sim.tuning.max_juggle_hits
			defender.stun_remaining = sim.tuning.juggle_refloat_ticks
			defender.launch_total = defender.stun_remaining
		elif move.launch:
			defender.action = FighterState.Action.LAUNCHED
			defender.juggle_hits = 0
			defender.juggle_exhausted = false
			defender.stun_remaining = move.launch_frames
			defender.launch_total = move.launch_frames
		elif air_height[i] > 0.0 and not knocks_down:
			# Hit out of a jump (D-087): falls from where it was and lands
			# knocked down. The float is entered part-way through, at the
			# point of its arc that matches the height the fighter was at.
			defender.action = FighterState.Action.LAUNCHED
			defender.juggle_hits = 0
			defender.juggle_exhausted = false
			defender.launch_total = sim.tuning.air_hit_float_ticks
			defender.stun_remaining = FighterState.float_ticks_left(air_height[i], defender.launch_total)
		elif knocks_down or (counter_hit[i] and move.counter_hit_knockdown):
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
			if counter_hit[i]:
				defender.stun_remaining += sim.tuning.counter_hit_extra_hitstun + move.counter_hit_stagger_frames
		# A deflecting guard (Ryuen) sends the attacker sliding back as well.
		if blocked[i] and c.projectile == null and sim.definitions[c.defender].block_pushes_attacker > 0.0 \
				and attacker.action != FighterState.Action.KO:
			var back: float = signf(attacker.position_x - defender.position_x)
			if back == 0.0:
				back = -float(attacker.facing)
			attacker.pushback_transfers = false
			attacker.pushback_remaining = back * sim.definitions[c.defender].block_pushes_attacker
			attacker.pushback_step = sim.definitions[c.defender].block_pushes_attacker / PUSHBACK_TICKS
		# Push away from the attacker.
		var away: float = signf(defender.position_x - attacker.position_x)
		if away == 0.0:
			away = float(attacker.facing)
		if c.projectile != null:
			away = float(c.projectile.direction)
		defender.pushback_transfers = c.projectile == null
		defender.pushback_remaining = away * move.pushback
		defender.pushback_step = move.pushback / PUSHBACK_TICKS
	return hitstop


## Which part of the defender a move strikes (for the reaction animation):
## LOW moves and anything below 35% of its height hit the legs, anything
## from 72% up the head, the rest the body.
static func _zone(move: MoveData, def: FighterDefinition) -> FighterState.HitZone:
	var h: float = move.hitbox_center.y / maxf(0.01, def.hurtbox_height)
	if move.hit_level == MoveData.HitLevel.LOW or h <= 0.35:
		return FighterState.HitZone.LEGS
	return FighterState.HitZone.HEAD if h >= 0.72 else FighterState.HitZone.BODY


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
	attacker.pushback_remaining = 0.0
	if stance.counter_switches_sides:
		sim.switch_sides(c.defender)
	defender.move_connected = true
	if stance.counter_followup != null:
		sim.start_followup(c.defender, stance.counter_followup)
	else:
		# Parry: the stance ends here; its user acts first.
		sim.end_move(c.defender)


static func _knock_out(f: FighterState, index: int, sim: CombatSimulation) -> void:
	f.action = FighterState.Action.KO
	f.end_jump()
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
