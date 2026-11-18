extends RefCounted
## Milestone 4: multi-touch controls, training scene, HUD combo counter.

const FRAME: float = 1.0 / 60.0


func _tree() -> SceneTree:
	return Engine.get_main_loop() as SceneTree


func _frames(scene: Node, count: int) -> void:
	for _i: int in count:
		scene._process(FRAME)


func _touch(tc: TouchControls, index: int, pos: Vector2, pressed: bool) -> void:
	var e := InputEventScreenTouch.new()
	e.index = index
	e.position = pos
	e.pressed = pressed
	tc._input(e)


func _drag(tc: TouchControls, index: int, pos: Vector2) -> void:
	var e := InputEventScreenDrag.new()
	e.index = index
	e.position = pos
	tc._input(e)


func _spawn(path: String) -> Node:
	var scene: Node = (load(path) as PackedScene).instantiate()
	_tree().root.add_child(scene)
	return scene


func _ready_failures(scene: Node) -> Array[String]:
	if not scene.is_node_ready() or scene.director == null:
		return ["scene did not initialise"]
	return []


func test_touch_walk_and_attack_with_two_fingers() -> Array[String]:
	var f: Array[String] = []
	var tc := TouchControls.new()
	_tree().root.add_child(tc)
	var stick: Vector2 = tc.stick_rest()
	var light: Vector2 = tc.button_center(InputActions.ATTACK_LIGHT)
	_touch(tc, 0, stick, true)
	_drag(tc, 0, stick + Vector2(120, 0))
	_touch(tc, 1, light, true)
	if not Input.is_action_pressed(InputActions.MOVE_RIGHT) or not Input.is_action_pressed(InputActions.ATTACK_LIGHT):
		f.append("two fingers: right=%s light=%s" % [
			Input.is_action_pressed(InputActions.MOVE_RIGHT), Input.is_action_pressed(InputActions.ATTACK_LIGHT)])
	# A frame of input as the simulation sees it carries both.
	var frame: FighterInputFrame = LocalInputReader.read()
	if frame.move_x != 1 or not frame.is_held(FighterInputFrame.BUTTON_LIGHT):
		f.append("LocalInputReader missed simultaneous input (move %d buttons %d)" % [frame.move_x, frame.buttons])
	_touch(tc, 1, light, false)
	if Input.is_action_pressed(InputActions.ATTACK_LIGHT) or not Input.is_action_pressed(InputActions.MOVE_RIGHT):
		f.append("lifting the attack finger affected the stick")
	_drag(tc, 0, stick + Vector2(-120, 0))
	if not Input.is_action_pressed(InputActions.MOVE_LEFT) or Input.is_action_pressed(InputActions.MOVE_RIGHT):
		f.append("stick did not switch to left")
	_drag(tc, 0, stick + Vector2(10, 0))  # inside dead zone
	if Input.is_action_pressed(InputActions.MOVE_LEFT) or Input.is_action_pressed(InputActions.MOVE_RIGHT):
		f.append("dead zone still walking")
	_touch(tc, 0, stick, false)
	# A finger that slides off a button keeps it held until lifted.
	var block: Vector2 = tc.button_center(InputActions.BLOCK)
	_touch(tc, 2, block, true)
	_drag(tc, 2, block + Vector2(400, 0))
	if not Input.is_action_pressed(InputActions.BLOCK):
		f.append("block released when finger slid off")
	tc.release_all()
	for a: StringName in InputActions.ALL:
		if Input.is_action_pressed(a):
			f.append("release_all left %s pressed" % a)
	tc.free()
	return f


func test_touch_left_handed_mirrors_layout() -> Array[String]:
	var f: Array[String] = []
	var tc := TouchControls.new()
	_tree().root.add_child(tc)
	var w: float = tc.get_viewport().get_visible_rect().size.x
	var right_light: Vector2 = tc.button_center(InputActions.ATTACK_LIGHT)
	var right_stick: Vector2 = tc.stick_rest()
	tc.set_left_handed(true)
	var left_light: Vector2 = tc.button_center(InputActions.ATTACK_LIGHT)
	if absf(left_light.x - (w - right_light.x)) > 0.5 or absf(left_light.y - right_light.y) > 0.5:
		f.append("light not mirrored: %s vs %s (w %.0f)" % [right_light, left_light, w])
	if absf(tc.stick_rest().x - (w - right_stick.x)) > 0.5:
		f.append("stick not mirrored")
	# Buttons stay inside the screen and away from the edges.
	var h: float = tc.get_viewport().get_visible_rect().size.y
	for a: StringName in [InputActions.ATTACK_LIGHT, InputActions.ATTACK_HEAVY, InputActions.ATTACK_KICK,
			InputActions.BLOCK, InputActions.SPECIAL, InputActions.ULTIMATE]:
		var c: Vector2 = tc.button_center(a)
		if c.x < 100 or c.x > w - 100 or c.y < 100 or c.y > h - 100:
			f.append("%s too close to the screen edge at %s" % [a, c])
	tc.free()
	return f


func test_versus_touch_combo_and_hud_counter() -> Array[String]:
	var scene: Node = _spawn(ScenePaths.COMBAT_GREYBOX)
	var f: Array[String] = _ready_failures(scene)
	if not f.is_empty():
		scene.free()
		return f
	scene.p2_mode = scene.P2Mode.DUMMY_STAND
	scene._apply_p2_mode()
	var sim: CombatSimulation = scene.simulation
	var d: MatchDirector = scene.director
	while d.phase == MatchDirector.Phase.INTRO:
		_frames(scene, 1)
	sim.fighters[0].position_x = -0.45
	sim.fighters[1].position_x = 0.45
	var tc: TouchControls = scene.get_node("%TouchControls")
	var light: Vector2 = tc.button_center(InputActions.ATTACK_LIGHT)
	# Tap light every other frame through the touch layer → L, L cancel.
	var best: String = ""
	for t: int in 40:
		_touch(tc, 1, light, t % 2 == 0)
		_frames(scene, 1)
		var txt: String = (scene.get_node("%MatchHUD") as MatchHUD).combo_text(0)
		if txt != "":
			best = txt
	_touch(tc, 1, light, false)
	if best != "2 HITS":
		f.append("HUD combo counter showed '%s', expected '2 HITS'. log:\n%s" % [best, sim.combat_log.to_text()])
	scene.pause()
	if Input.is_action_pressed(InputActions.ATTACK_LIGHT):
		f.append("pause did not release touch input")
	scene.resume()
	scene.free()
	return f


func test_training_scene() -> Array[String]:
	var scene: Node = _spawn(ScenePaths.TRAINING_GREYBOX)
	var f: Array[String] = _ready_failures(scene)
	if not f.is_empty():
		scene.free()
		return f
	var sim: CombatSimulation = scene.simulation
	var d: MatchDirector = scene.director
	if d.phase != MatchDirector.Phase.FIGHT:
		f.append("training not in FIGHT at start (%s)" % d.phase_name())
	var hud: MatchHUD = scene.get_node("%MatchHUD")
	_frames(scene, 2)
	if (hud.get_node("%TimerLabel") as Label).text != "∞":
		f.append("training timer label is not ∞")
	var panel: TrainingPanel = scene.get_node("%TrainingPanel")
	if not panel.visible:
		f.append("training panel hidden")
	sim.fighters[0].position_x = -0.45
	sim.fighters[1].position_x = 0.45
	Input.action_press(InputActions.ATTACK_KICK)
	_frames(scene, 12)
	Input.action_release(InputActions.ATTACK_KICK)
	_frames(scene, 2)
	var stats: String = (panel.get_node("%StatsLabel") as Label).text
	if not stats.contains("kairo_kick") or not stats.contains("on hit +2"):
		f.append("training panel missing move/frame data:\n%s" % stats)
	var hist: String = (panel.get_node("%HistoryLabel") as Label).text
	if not hist.contains("K"):
		f.append("input history missing the kick press:\n%s" % hist)
	_frames(scene, 60)
	if sim.fighters[1].health != sim.definitions[1].base_health:
		f.append("dummy health did not refill in training")
	sim.fighters[0].position_x = 3.0
	scene.restart()
	if sim.fighters[0].position_x != sim.arena.p1_spawn_x or d.phase != MatchDirector.Phase.FIGHT:
		f.append("training reset did not restore positions")
	scene.free()
	return f


func test_versus_p2_is_ai_by_default_and_acts() -> Array[String]:
	var scene: Node = _spawn(ScenePaths.COMBAT_GREYBOX)
	var f: Array[String] = _ready_failures(scene)
	if not f.is_empty():
		scene.free()
		return f
	if scene.ai == null:
		f.append("versus P2 is not the AI")
	var hud: MatchHUD = scene.get_node("%MatchHUD")
	if not hud.fighter_name(1).contains("CPU"):
		f.append("HUD does not show the CPU difficulty: '%s'" % hud.fighter_name(1))
	var sim: CombatSimulation = scene.simulation
	_frames(scene, 600)  # 10 s: intro + fight
	var p2_acted: bool = false
	for e: CombatEvent in sim.combat_log.all_events():
		if e.actor == 1 and e.type == CombatEvent.Type.ATTACK_START:
			p2_acted = true
	if not p2_acted and absf(sim.fighters[1].position_x - sim.arena.p2_spawn_x) < 0.01:
		f.append("AI P2 never moved or attacked in 10 s")
	# Cycling P2 reaches the dummy and back to AI.
	for _k: int in 3:
		scene.cycle_dummy_mode()
	if scene.ai != null or not hud.fighter_name(1).contains("Dummy"):
		f.append("cycling did not reach the dummy modes")
	scene.free()
	return f
