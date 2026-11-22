extends RefCounted
## Jumping, crouching and air attacks (D-087).

const L: int = FighterInputFrame.BUTTON_LIGHT
const K: int = FighterInputFrame.BUTTON_KICK
const B: int = FighterInputFrame.BUTTON_BLOCK


func _kairo() -> FighterDefinition:
	return load("res://data/fighters/kairo.tres")


func _sim(gap: float = 0.9) -> CombatSimulation:
	var sim := CombatSimulation.new()
	sim.setup(load("res://data/arenas/greybox_arena.tres"), _kairo(), _kairo(),
		load("res://data/rules/combat_tuning.tres"))
	sim.fighters[0].position_x = -gap * 0.5
	sim.fighters[1].position_x = gap * 0.5
	return sim


func _in(buttons: int = 0, x: int = 0, y: int = 0) -> FighterInputFrame:
	return FighterInputFrame.with_buttons(buttons, x, y)


func _hits(sim: CombatSimulation, actor: int, move_id: StringName = &"") -> int:
	var n: int = 0
	for e: CombatEvent in sim.combat_log.all_events():
		if e.type == CombatEvent.Type.HIT and e.actor == actor and (move_id == &"" or e.move_id == move_id):
			n += 1
	return n


func test_jump_follows_its_arc_and_lands() -> Array[String]:
	var f: Array[String] = []
	var sim: CombatSimulation = _sim(4.0)
	var m: FighterMovementProfile = _kairo().movement
	sim.step([_in(0, 0, 1), _in()])
	var p: FighterState = sim.fighters[0]
	if p.action != FighterState.Action.JUMP:
		return ["up did not start a jump (%s)" % p.action_name()]
	var x0: float = p.position_x
	var peak: float = 0.0
	var left_ground: int = -1
	for t: int in m.jump_total_ticks() + 2:
		sim.step([_in(), _in()])
		peak = maxf(peak, p.height)
		if p.height > 0.0 and left_ground < 0:
			left_ground = t
		if p.action != FighterState.Action.JUMP:
			if t != m.jump_total_ticks() - 1:
				f.append("jump ended after %d ticks, expected %d" % [t + 1, m.jump_total_ticks()])
			break
	if absf(peak - m.jump_height) > 0.02:
		f.append("peak %.3f, expected %.3f" % [peak, m.jump_height])
	if p.height != 0.0 or p.jump_frame != 0 or not p.is_neutral():
		f.append("did not land cleanly: %s" % p.describe())
	if absf(p.position_x - x0) > 1e-6:
		f.append("a neutral jump moved sideways")
	if left_ground != m.jump_prejump_ticks - 1:
		f.append("left the ground on tick %d of the jump" % (left_ground + 2))
	return f


func test_forward_and_back_jumps_cover_their_distance() -> Array[String]:
	var f: Array[String] = []
	var m: FighterMovementProfile = _kairo().movement
	for dir: int in [1, -1]:
		var sim: CombatSimulation = _sim(5.0 if dir == 1 else 1.5)
		var x0: float = sim.fighters[0].position_x
		sim.step([_in(0, dir, 1), _in()])
		for _t: int in m.jump_total_ticks() + 2:
			sim.step([_in(), _in()])
		var want: float = m.jump_forward_distance if dir == 1 else -m.jump_back_distance
		# the last air tick is already on the floor, so one step is not taken
		var step: float = absf(want) / m.jump_air_ticks
		if absf((sim.fighters[0].position_x - x0) - want) > step + 1e-4:
			f.append("dir %d: moved %.3f, expected %.3f" % [dir, sim.fighters[0].position_x - x0, want])
	return f


func test_jump_goes_over_a_low_kick_and_cannot_block() -> Array[String]:
	var f: Array[String] = []
	# P2 low kicks (active on frame 9); P1 jumps on the same tick.
	var sim: CombatSimulation = _sim(1.2)
	sim.step([_in(0, 0, 1), _in(K)])
	for _t: int in 30:
		sim.step([_in(), _in()])
	if _hits(sim, 1) != 0:
		f.append("the low kick hit a jumping fighter")
	# Same, but P1 stands: the kick lands.
	var sim2: CombatSimulation = _sim(1.2)
	sim2.step([_in(), _in(K)])
	for _t: int in 30:
		sim2.step([_in(), _in()])
	if _hits(sim2, 1, &"kairo_low_kick") != 1:
		f.append("setup: the low kick should hit a standing fighter")
	# Holding block in the air does nothing: an air-to-air kick hits.
	var sim3: CombatSimulation = _sim(1.0)
	sim3.step([_in(0, 0, 1), _in(0, 0, 1)])
	for t: int in 40:
		sim3.step([_in(K if t == 8 else 0), _in(B)])
	if _hits(sim3, 0, &"kairo_jump_attack") != 1:
		f.append("air attack did not hit a jumping fighter holding block")
	elif sim3.fighters[1].action != FighterState.Action.LAUNCHED and not sim3.fighters[1].is_downed():
		f.append("a fighter hit in the air should fall and land knocked down, is %s" % sim3.fighters[1].action_name())
	return f


func test_air_attack_once_per_jump_and_ends_on_landing() -> Array[String]:
	var f: Array[String] = []
	var sim: CombatSimulation = _sim(4.0)
	var m: FighterMovementProfile = _kairo().movement
	sim.step([_in(0, 0, 1), _in()])
	var starts: int = 0
	for t: int in m.jump_total_ticks() + 4:
		# press kick twice in the air
		sim.step([_in(K if (t == 6 or t == 30) else 0), _in()])
		var p: FighterState = sim.fighters[0]
		if p.action == FighterState.Action.ATTACK and not p.is_airborne() and p.move != null \
				and p.move.input_pattern == &"AIR":
			f.append("the air attack carried on after landing (tick %d)" % t)
			break
	for e: CombatEvent in sim.combat_log.all_events():
		if e.type == CombatEvent.Type.ATTACK_START and e.move_id == &"kairo_jump_attack":
			starts += 1
	if starts != 1:
		f.append("%d air attacks in one jump, expected 1" % starts)
	if not sim.fighters[0].is_neutral():
		f.append("not neutral after landing: %s" % sim.fighters[0].describe())
	# No air attack from the ground.
	var sim2: CombatSimulation = _sim(4.0)
	sim2.step([_in(K), _in()])
	if sim2.fighters[0].move == null or sim2.fighters[0].move.input_pattern == &"AIR":
		f.append("kick on the ground should be the ground kick")
	return f


func test_jump_in_attack_hits_standing_and_is_blocked_standing_only() -> Array[String]:
	var f: Array[String] = []
	for guard: int in [0, 1, 2]:   # none, standing block, low block
		var sim: CombatSimulation = _sim(2.4)
		var p2: FighterInputFrame = _in() if guard == 0 else _in(B, 0, -1 if guard == 2 else 0)
		sim.step([_in(0, 1, 1), p2])
		for t: int in 50:
			sim.step([_in(K if t == 22 else 0), p2])
		var hits: int = _hits(sim, 0, &"kairo_jump_attack")
		if guard == 1 and hits != 0:
			f.append("a standing block should stop the jumping attack")
		if guard != 1 and hits != 1:
			f.append("guard %d: %d hits, expected 1\n%s" % [guard, hits, sim.combat_log.to_text()])
	return f


func test_crouch_ducks_a_jab_but_not_a_front_kick() -> Array[String]:
	var f: Array[String] = []
	# P2 crouches; P1 jabs (hitbox bottom 1.30 m, crouch height 62% of 1.8 = 1.12 m).
	var sim: CombatSimulation = _sim(0.9)
	sim.step([_in(), _in(0, 0, -1)])
	if sim.fighters[1].action != FighterState.Action.CROUCH:
		return ["down did not crouch (%s)" % sim.fighters[1].action_name()]
	sim.step([_in(L), _in(0, 0, -1)])
	for _t: int in 25:
		sim.step([_in(), _in(0, 0, -1)])
	if _hits(sim, 0) != 0:
		f.append("the jab hit a crouching fighter")
	# down + heavy (front kick to the body, hitbox 0.875..1.225) still connects.
	var sim2: CombatSimulation = _sim(0.9)
	sim2.step([_in(), _in(0, 0, -1)])
	sim2.step([_in(FighterInputFrame.BUTTON_HEAVY, 0, -1), _in(0, 0, -1)])
	for _t: int in 25:
		sim2.step([_in(), _in(0, 0, -1)])
	if _hits(sim2, 0, &"kairo_body_hook") != 1:
		f.append("the front kick should hit a crouching fighter")
	# Crouching is neutral: letting go stands up, and it cannot walk.
	var sim3: CombatSimulation = _sim(3.0)
	var x0: float = sim3.fighters[0].position_x
	for _t: int in 10:
		sim3.step([_in(0, 1, -1), _in()])
	if sim3.fighters[0].position_x != x0:
		f.append("a crouching fighter walked")
	sim3.step([_in(), _in()])
	if sim3.fighters[0].action != FighterState.Action.IDLE:
		f.append("did not stand up")
	return f


func test_jump_can_cross_over_and_fighters_turn_round() -> Array[String]:
	var f: Array[String] = []
	var sim: CombatSimulation = _sim(1.2)
	sim.step([_in(0, 1, 1), _in()])
	for _t: int in _kairo().movement.jump_total_ticks() + 3:
		sim.step([_in(), _in()])
	var a: FighterState = sim.fighters[0]
	var b: FighterState = sim.fighters[1]
	if a.position_x <= b.position_x:
		f.append("did not land behind the opponent (%.2f vs %.2f)" % [a.position_x, b.position_x])
	elif a.facing != -1 or b.facing != 1:
		f.append("fighters did not turn to face each other after the cross-over")
	var gap: float = absf(a.position_x - b.position_x)
	if gap < _kairo().movement.pushbox_half_width * 2.0 - 1e-4:
		f.append("fighters overlap after landing (gap %.3f)" % gap)
	return f


func test_jumping_is_deterministic() -> Array[String]:
	var texts: Array[String] = []
	for _run: int in 2:
		var sim: CombatSimulation = _sim(2.4)
		var text: String = ""
		for t: int in 120:
			var p1: FighterInputFrame = _in(K if t % 17 == 9 else 0, 1 if t % 50 < 3 else 0, 1 if t % 50 < 2 else 0)
			var p2: FighterInputFrame = _in(L if t % 13 == 0 else 0, 0, -1 if t % 40 > 30 else 0)
			sim.step([p1, p2])
			text += sim.describe() + "\n"
		texts.append(text)
	return [] if texts[0] == texts[1] else ["two identical runs differ"]
