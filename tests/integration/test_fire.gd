extends RefCounted
## D-101: Kairo's Fireball and fire effects (presentation of fire is
## checked for existence and switching; the look is judged from video).

const FRAME: float = 1.0 / 60.0


func _tree() -> SceneTree:
	return Engine.get_main_loop() as SceneTree


func test_fireball_move_data() -> Array[String]:
	var f: Array[String] = []
	var def: FighterDefinition = load("res://data/fighters/kairo.tres")
	var m: MoveData = def.move_for_id(&"kairo_fireball")
	if m == null:
		return ["Kairo has no kairo_fireball move"]
	if m.input_pattern != &"DOWN_SPECIAL":
		f.append("fireball input is %s, expected DOWN_SPECIAL" % m.input_pattern)
	if not m.is_projectile():
		f.append("fireball is not a projectile")
	for t: String in ["fire", "fire_hands", "ignite_short"]:
		if not m.tags.has(t):
			f.append("fireball lacks tag %s" % t)
	if def.moves_for(&"DOWN_SPECIAL").size() != 1:
		f.append("DOWN_SPECIAL has %d moves" % def.moves_for(&"DOWN_SPECIAL").size())
	var ult: MoveData = def.move_for_id(&"kairo_origin_break")
	if ult == null or not ult.tags.has("fire_limbs") or not ult.tags.has("ignite"):
		f.append("Origin Break is not tagged fire_limbs + ignite")
	return f


func test_down_special_fires_a_fireball() -> Array[String]:
	var f: Array[String] = []
	var sim := CombatSimulation.new()
	sim.setup(load("res://data/arenas/greybox_arena.tres"), load("res://data/fighters/kairo.tres"),
			load("res://data/fighters/training_dummy.tres"), load("res://data/rules/combat_tuning.tres"))
	var press := FighterInputFrame.new()
	press.move_y = -1
	press.buttons = FighterInputFrame.BUTTON_SPECIAL
	var idle := FighterInputFrame.new()
	var fired: bool = false
	var hit: bool = false
	for t: int in 120:
		var ins: Array[FighterInputFrame] = [press if t < 2 else idle, idle]
		sim.step(ins)
		if not sim.projectiles.is_empty():
			fired = true
		for ev: CombatEvent in sim.combat_log.events_since(0):
			if ev.type == CombatEvent.Type.HIT and ev.move_id == &"kairo_fireball":
				hit = true
	if not fired:
		f.append("down + special did not fire a projectile")
	if not hit:
		f.append("the fireball did not hit the standing dummy")
	return f


func test_fire_switches_with_the_move_and_ignite() -> Array[String]:
	var f: Array[String] = []
	var view: FighterView = (load("res://scenes/fighters/placeholder_fighter.tscn") as PackedScene).instantiate()
	_tree().root.add_child(view)
	view.setup(load("res://data/fighters/kairo.tres"))
	var s := FighterState.new()
	s.action = FighterState.Action.ATTACK
	s.move = (load("res://data/fighters/kairo.tres") as FighterDefinition).move_for_id(&"kairo_origin_break")
	s.move_frame = 10
	view.sync(s, s, 1.0, false, FRAME)
	var burning: int = 0
	for p: Node in view.find_children("*", "CPUParticles3D", true, false):
		if (p as CPUParticles3D).emitting:
			burning += 1
	if burning < 8:                       # 4 limbs x (flames + embers)
		f.append("ultimate: %d fire emitters on, expected 8" % burning)
	s.action = FighterState.Action.IDLE
	s.move = null
	view.sync(s, s, 1.0, false, FRAME)
	for p: Node in view.find_children("*", "CPUParticles3D", true, false):
		if (p as CPUParticles3D).emitting:
			f.append("a limb is still on fire after the move")
			break
	view.ignite(0.1)
	if not view.is_burning():
		f.append("ignite did not set the fighter burning")
	for i: int in 10:
		view.sync(s, s, 1.0, false, FRAME)
	if view.is_burning():
		f.append("still burning after the ignite time ran out")
	view.queue_free()
	return f


## D-102: hit, block and knockdown effects spawn and clear themselves.
func test_impact_effects_spawn() -> Array[String]:
	var f: Array[String] = []
	var fx := EffectsManager.new()
	_tree().root.add_child(fx)
	for type: int in [CombatEvent.Type.HIT, CombatEvent.Type.BLOCK, CombatEvent.Type.PROJECTILE_CLASH]:
		var ev := CombatEvent.new()
		ev.type = type
		ev.damage = 80
		ev.point = Vector2(0.5, 1.2)
		var before: int = fx.get_child_count()
		fx.spawn_for(ev, 1.0, null)
		if fx.get_child_count() <= before:
			f.append("no effect for event type %d" % type)
	var before_slam: int = fx.get_child_count()
	fx.spawn_ground_slam(0.0, 0.0, 1.5)
	if fx.get_child_count() < before_slam + 3:
		f.append("ground slam spawned %d parts" % (fx.get_child_count() - before_slam))
	for i: int in 60:                     # the sprites fade and free themselves
		fx._process(FRAME)
	var sprites: int = 0
	for c: Node in fx.get_children():
		if c is MeshInstance3D and not c.is_queued_for_deletion():
			sprites += 1
	if sprites > 0:
		f.append("%d effect sprites still alive after a second" % sprites)
	fx.queue_free()
	return f
