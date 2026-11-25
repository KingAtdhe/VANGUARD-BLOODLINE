extends RefCounted
## D-114: throw escape. A fighter held by a throw (Kairo's Knee Throw) breaks
## it with Light + Kick within the break window after the grab: no damage,
## both pushed apart, a THROW_BREAK event. Too late, or one button only, and
## the throw lands.

const L: int = FighterInputFrame.BUTTON_LIGHT
const K: int = FighterInputFrame.BUTTON_KICK


func _sim() -> CombatSimulation:
	var sim := CombatSimulation.new()
	# Kairo against Kairo so the victim has the same buttons as a real player
	sim.setup(load("res://data/arenas/greybox_arena.tres"), load("res://data/fighters/kairo.tres"),
			load("res://data/fighters/kairo.tres"), load("res://data/rules/combat_tuning.tres"))
	sim.fighters[0].position_x = -0.45
	sim.fighters[1].position_x = 0.45
	return sim


func _in(buttons: int) -> FighterInputFrame:
	var f := FighterInputFrame.new()
	f.buttons = buttons
	return f


## P1 throws on tick 0; P2 presses [param p2_buttons] [param delay] ticks
## after the grab. Returns {broke, hit, gap, grab_tick}.
func _run(p2_buttons: int, delay: int) -> Dictionary:
	var sim := _sim()
	var idle := FighterInputFrame.new()
	var grab_tick: int = -1
	for t: int in 70:
		var p1: FighterInputFrame = _in(L | K) if t == 0 else idle
		var p2: FighterInputFrame = idle
		if grab_tick >= 0 and sim.tick == grab_tick + delay:
			p2 = _in(p2_buttons)
		sim.step([p1, p2])
		if grab_tick < 0 and sim.fighters[1].held_by == 0:
			grab_tick = sim.tick
	var broke: bool = false
	var hit: bool = false
	for ev: CombatEvent in sim.combat_log.all_events():
		broke = broke or ev.type == CombatEvent.Type.THROW_BREAK
		hit = hit or (ev.type == CombatEvent.Type.HIT and ev.actor == 0)
	return {"broke": broke, "hit": hit, "gap": sim.separation(), "grab_tick": grab_tick,
		"hp": sim.fighters[1].health, "held": sim.fighters[1].held_by}


func test_light_kick_breaks_the_throw() -> Array[String]:
	var f: Array[String] = []
	var r: Dictionary = _run(L | K, 3)
	if r.grab_tick < 0:
		return ["the throw never grabbed"]
	if not r.broke or r.hit or r.hp != 1000:
		f.append("Light+Kick 3 ticks after the grab should break it (broke %s, hit %s, hp %d)" % [r.broke, r.hit, r.hp])
	if r.held != -1:
		f.append("still held after the break")
	if r.gap < 0.9:
		f.append("fighters not pushed apart after the break (gap %.2f)" % r.gap)
	return f


func test_too_late_or_one_button_does_not_break() -> Array[String]:
	var f: Array[String] = []
	var late: Dictionary = _run(L | K, (load("res://data/rules/combat_tuning.tres") as CombatTuning).throw_break_window + 2)
	if late.broke or not late.hit:
		f.append("a break after the window still worked (broke %s, hit %s)" % [late.broke, late.hit])
	var light_only: Dictionary = _run(L, 2)
	if light_only.broke or not light_only.hit:
		f.append("Light alone broke the throw")
	return f


func test_break_is_deterministic() -> Array[String]:
	var a: Dictionary = _run(L | K, 4)
	var b: Dictionary = _run(L | K, 4)
	return [] if str(a) == str(b) else ["two identical breaks differ: %s vs %s" % [a, b]]
