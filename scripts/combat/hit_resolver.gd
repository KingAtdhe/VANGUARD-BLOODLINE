class_name HitResolver
extends RefCounted
## Applies detected contacts: hit vs block, damage, stun, pushback, hitstop
## and KO. Rules (docs/COMBAT_FRAME_DATA.md):
##   - Blocked if the defender is in BLOCK or BLOCKSTUN and the move is
##     standing-blockable (HIGH, MID, PROJECTILE). Fighters always face each
##     other, so every attack comes from the front.
##   - Hit: defender loses `damage`, enters HITSTUN for hitstun_frames; any
##     attack it was performing is interrupted.
##   - Block: defender loses `chip_damage` (can KO), enters BLOCKSTUN.
##   - Either way the attack is spent (one connection per attack) and the
##     defender slides back by `pushback` over PUSHBACK_TICKS ticks.
##   - Global hitstop = largest hitstop among this tick's contacts.
##   - Health reaching 0 → KO (no hurtbox, ignores input).
## All hit/block decisions are taken from the state BEFORE any contact is
## applied, so simultaneous hits trade fairly regardless of P1/P2 order.

const PUSHBACK_TICKS: int = 6


## Returns the hitstop (ticks) to apply. Adds events to [param combat_log].
static func resolve(contacts: Array[HitboxSystem.Contact], states: Array[FighterState],
		tick: int, combat_log: CombatLog) -> int:
	if contacts.is_empty():
		return 0
	# Snapshot moves and block decisions first: applying one contact clears
	# the defender's own move, which a trade still needs.
	var moves: Array[MoveData] = []
	var blocked: Array[bool] = []
	for c: HitboxSystem.Contact in contacts:
		var move: MoveData = states[c.attacker].move
		moves.append(move)
		blocked.append(states[c.defender].is_blocking() and move.is_blockable_standing())

	var hitstop: int = 0
	for i: int in contacts.size():
		var c: HitboxSystem.Contact = contacts[i]
		var attacker: FighterState = states[c.attacker]
		var defender: FighterState = states[c.defender]
		var move: MoveData = moves[i]
		attacker.move_connected = true
		hitstop = maxi(hitstop, move.hitstop_frames)

		var dmg: int = move.chip_damage if blocked[i] else move.damage
		defender.health = maxi(0, defender.health - dmg)

		var ev := CombatEvent.new()
		ev.tick = tick
		ev.type = CombatEvent.Type.BLOCK if blocked[i] else CombatEvent.Type.HIT
		ev.actor = c.attacker
		ev.target = c.defender
		ev.move_id = move.id
		ev.damage = dmg
		ev.target_health = defender.health
		ev.point = c.point
		ev.hitstop = move.hitstop_frames
		combat_log.add(ev)

		if defender.health == 0:
			_knock_out(defender, c.defender, tick, combat_log)
			continue

		# Interrupt whatever the defender was doing (including its own attack,
		# unless that attack already connected this tick — a trade).
		defender.move = null
		defender.move_frame = 0
		defender.move_connected = false
		defender.move_x = 0
		if blocked[i]:
			defender.action = FighterState.Action.BLOCKSTUN
			defender.stun_remaining = move.blockstun_frames
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


static func _knock_out(f: FighterState, index: int, tick: int, combat_log: CombatLog) -> void:
	f.action = FighterState.Action.KO
	f.move = null
	f.move_frame = 0
	f.stun_remaining = 0
	f.move_x = 0
	f.pushback_remaining = 0.0
	var ev := CombatEvent.new()
	ev.tick = tick
	ev.type = CombatEvent.Type.KO
	ev.target = index
	combat_log.add(ev)
