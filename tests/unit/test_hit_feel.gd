extends RefCounted
## Counter-hits and hit zones (D-069).

const L: int = FighterInputFrame.BUTTON_LIGHT
const H: int = FighterInputFrame.BUTTON_HEAVY
const K: int = FighterInputFrame.BUTTON_KICK
const S: int = FighterInputFrame.BUTTON_SPECIAL
const B: int = FighterInputFrame.BUTTON_BLOCK
const ROSTER: Array[String] = ["kairo", "drakon", "seraphina", "nox", "vexa", "ryuen"]


func _def(id: String) -> FighterDefinition:
	return load("res://data/fighters/%s.tres" % id)


func _sim(p1: String, p2: String, gap: float = 0.9) -> CombatSimulation:
	var sim := CombatSimulation.new()
	sim.setup(load("res://data/arenas/greybox_arena.tres"), _def(p1), _def(p2),
		load("res://data/rules/combat_tuning.tres"))
	sim.fighters[0].position_x = -gap * 0.5
	sim.fighters[1].position_x = gap * 0.5
	return sim


func _n() -> FighterInputFrame:
	return FighterInputFrame.neutral()


func _first_hit(sim: CombatSimulation, actor: int) -> CombatEvent:
	for e: CombatEvent in sim.combat_log.all_events():
		if e.type == CombatEvent.Type.HIT and e.actor == actor:
			return e
	return null


func _run(sim: CombatSimulation, ticks: int) -> void:
	for _i: int in ticks:
		sim.step([_n(), _n()])


func test_hit_during_startup_is_a_counter_hit_with_more_damage_and_stun() -> Array[String]:
	var f: Array[String] = []
	var tuning: CombatTuning = load("res://data/rules/combat_tuning.tres")
	var jab: MoveData = _def("kairo").move_for(&"LIGHT")
	# P2 starts a slow heavy; P1's jab (5 f) interrupts its 12-frame startup.
	var sim: CombatSimulation = _sim("kairo", "kairo")
	sim.step([FighterInputFrame.with_buttons(L), FighterInputFrame.with_buttons(H)])
	var stun_seen: int = -1
	for _t: int in 30:
		sim.step([_n(), _n()])
		if stun_seen < 0 and sim.fighters[1].action == FighterState.Action.HITSTUN:
			stun_seen = sim.fighters[1].stun_remaining
	var hit: CombatEvent = _first_hit(sim, 0)
	if hit == null or not hit.counter_hit:
		f.append("a jab into a heavy's startup should be a counter-hit. log:\n%s" % sim.combat_log.to_text())
		return f
	if hit.damage != jab.damage * tuning.counter_hit_damage_percent / 100:
		f.append("counter-hit damage %d, expected %d" % [hit.damage, jab.damage * tuning.counter_hit_damage_percent / 100])
	if hit.hitstop != jab.hitstop_frames:
		f.append("the event should report the move's own hitstop")
	if stun_seen != jab.hitstun_frames + tuning.counter_hit_extra_hitstun:
		f.append("counter-hit hitstun %d, expected %d" % [stun_seen, jab.hitstun_frames + tuning.counter_hit_extra_hitstun])
	# The same jab on a standing opponent is an ordinary hit.
	var plain: CombatSimulation = _sim("kairo", "kairo")
	plain.step([FighterInputFrame.with_buttons(L), _n()])
	_run(plain, 30)
	var normal: CombatEvent = _first_hit(plain, 0)
	if normal == null or normal.counter_hit or normal.damage != jab.damage:
		f.append("a hit on an idle fighter must not be a counter-hit")
	return f


func test_hit_during_recovery_is_a_punish_not_a_counter_hit() -> Array[String]:
	var f: Array[String] = []
	var heavy: MoveData = _def("kairo").move_for(&"HEAVY")
	# P2 whiffs a heavy out of range; P1 walks in and jabs its recovery.
	var sim: CombatSimulation = _sim("kairo", "kairo", 0.9)
	sim.fighters[1].action = FighterState.Action.ATTACK
	sim.fighters[1].move = heavy
	sim.fighters[1].move_frame = heavy.startup_frames + heavy.active_frames   # first recovery frame
	sim.fighters[1].move_connected = true
	sim.step([FighterInputFrame.with_buttons(L), _n()])
	_run(sim, 12)
	var hit: CombatEvent = _first_hit(sim, 0)
	if hit == null:
		f.append("the punish did not land. log:\n%s" % sim.combat_log.to_text())
	elif hit.counter_hit:
		f.append("a hit on a recovering attack must not be a counter-hit")
	return f


func test_blocks_throws_armour_and_counters_are_never_counter_hits() -> Array[String]:
	var f: Array[String] = []
	# throw into an attack's startup
	var sim: CombatSimulation = _sim("drakon", "kairo")
	sim.step([FighterInputFrame.with_buttons(S), _n()])
	_run(sim, 4)
	sim.step([_n(), FighterInputFrame.with_buttons(H)])
	_run(sim, 40)
	var grab: CombatEvent = _first_hit(sim, 0)
	if grab == null or grab.counter_hit:
		f.append("a throw should connect and never be a counter-hit")
	# armour: Forge Charge absorbs a jab
	var arm: CombatSimulation = _sim("kairo", "drakon", 1.2)
	arm.fighters[1].meter = 100
	arm.step([_n(), FighterInputFrame.with_buttons(S, -1)])
	_run(arm, 3)
	arm.step([FighterInputFrame.with_buttons(L), _n()])
	_run(arm, 40)
	var absorbed: CombatEvent = _first_hit(arm, 0)
	if absorbed != null and absorbed.armored and absorbed.counter_hit:
		f.append("an armoured hit must not be a counter-hit")
	# trade: both attacks land on the same tick, both are counter-hits
	var trade: CombatSimulation = _sim("kairo", "kairo")
	trade.step([FighterInputFrame.with_buttons(L), FighterInputFrame.with_buttons(L)])
	_run(trade, 20)
	var a: CombatEvent = _first_hit(trade, 0)
	var b: CombatEvent = _first_hit(trade, 1)
	if a == null or b == null or not a.counter_hit or not b.counter_hit or a.damage != b.damage:
		f.append("a trade should counter-hit both fighters equally")
	return f


func test_cut_kick_staggers_and_sinking_elbow_crumples_on_counter_hit() -> Array[String]:
	var f: Array[String] = []
	var tuning: CombatTuning = load("res://data/rules/combat_tuning.tres")
	var kick: MoveData = _def("vexa").move_for(&"KICK")
	var sim: CombatSimulation = _sim("vexa", "kairo")
	# Kairo's heavy (12 f startup) is still winding up when the Cut Kick (10 f) lands.
	sim.step([FighterInputFrame.with_buttons(K), FighterInputFrame.with_buttons(H)])
	var stun_seen: int = -1
	for _t: int in 30:
		sim.step([_n(), _n()])
		if stun_seen < 0 and sim.fighters[1].action == FighterState.Action.HITSTUN:
			stun_seen = sim.fighters[1].stun_remaining
	if stun_seen != kick.hitstun_frames + tuning.counter_hit_extra_hitstun + kick.counter_hit_stagger_frames \
			or kick.counter_hit_stagger_frames <= 0:
		f.append("Cut Kick counter-hit stagger: stun %d" % stun_seen)
	var elbow: CombatSimulation = _sim("ryuen", "kairo")
	elbow.step([FighterInputFrame.with_buttons(H, 0, -1), FighterInputFrame.with_buttons(H)])
	var floored: bool = false
	for _t: int in 40:
		elbow.step([_n(), _n()])
		floored = floored or elbow.fighters[1].action == FighterState.Action.KNOCKDOWN
	var hit: CombatEvent = _first_hit(elbow, 0)
	if hit == null or not hit.counter_hit or not floored:
		f.append("Sinking Elbow should knock down on counter-hit. log:\n%s" % elbow.combat_log.to_text())
	var plain: CombatSimulation = _sim("ryuen", "kairo")
	plain.step([FighterInputFrame.with_buttons(H, 0, -1), _n()])
	var down: bool = false
	for _t: int in 40:
		plain.step([_n(), _n()])
		down = down or plain.fighters[1].action == FighterState.Action.KNOCKDOWN
	if down:
		f.append("Sinking Elbow should not knock down on a normal hit")
	return f


func test_hit_zone_follows_where_the_move_lands() -> Array[String]:
	var f: Array[String] = []
	# [attacker, pattern button, down, expected zone]
	for c: Array in [["kairo", L, false, FighterState.HitZone.HEAD], ["kairo", H, true, FighterState.HitZone.BODY],
			["kairo", K, false, FighterState.HitZone.BODY], ["vexa", K, false, FighterState.HitZone.LEGS],
			["vexa", H, false, FighterState.HitZone.BODY]]:   # D-138: Kairo's Kick is a chest-high front kick now; Vexa's Cut Kick is the low
		var sim: CombatSimulation = _sim(c[0], "drakon")
		sim.step([FighterInputFrame.with_buttons(c[1], 0, -1 if c[2] else 0), _n()])
		var zone: int = -1
		for _t: int in 30:
			sim.step([_n(), _n()])
			if zone < 0 and sim.fighters[1].action == FighterState.Action.HITSTUN:
				zone = sim.fighters[1].hit_zone
		if zone != c[3]:
			f.append("%s button %d: zone %d, expected %d" % [c[0], c[1], zone, c[3]])
	return f


func test_every_fighter_has_body_and_leg_reactions() -> Array[String]:
	var f: Array[String] = []
	for id: String in ROSTER:
		var def: FighterDefinition = _def(id)
		var model: Node = def.model_scene.instantiate()
		var ap: AnimationPlayer = model.find_child("AnimationPlayer", true, false)
		for a: StringName in [def.anim_hit_body, def.anim_hit_low]:
			if a == &"" or not ap.has_animation(def.resolve_anim(a)):
				f.append("%s: missing reaction %s" % [id, a])
		model.free()
	return f
