extends RefCounted
## Milestone 1 acceptance, driven through the real combat scene:
## both fighters stay in the arena, face each other and stay on camera.

const FRAME: float = 1.0 / 60.0


func _tree() -> SceneTree:
	return Engine.get_main_loop() as SceneTree


## Versus scene with P2 forced to the passive dummy, so these movement /
## camera / match-flow tests are deterministic (AI behaviour has its own tests).
func _spawn_scene() -> Node:
	var scene: Node = (load(ScenePaths.COMBAT_GREYBOX) as PackedScene).instantiate()
	_tree().root.add_child(scene)
	if scene.is_node_ready():
		scene.p2_mode = scene.P2Mode.DUMMY_STAND
		scene._apply_p2_mode()
	return scene


## Runs the "ROUND 1 / FIGHT!" intro so inputs reach the simulation.
func _skip_intro(scene: Node) -> void:
	var d: MatchDirector = scene.director
	while d.phase == MatchDirector.Phase.INTRO:
		_frames(scene, 1)


## Fails fast if the scene did not initialise (prevents false passes).
func _ready_failures(scene: Node) -> Array[String]:
	var f: Array[String] = []
	if not scene.is_node_ready():
		f.append("combat scene _ready() did not run")
	elif (scene.simulation as CombatSimulation).fighters.size() != 2:
		f.append("combat simulation not set up")
	return f


func _frames(scene: Node, count: int, delta: float = FRAME) -> void:
	for _i: int in count:
		scene._process(delta)


func _visible(cam: Camera3D, x: float) -> bool:
	# Check the fighter's feet, centre and head.
	for y: float in [0.05, 0.9, 1.75]:
		if not cam.is_position_in_frustum(Vector3(x, y, 0.0)):
			return false
	return true


func _check(scene: Node, label: String) -> Array[String]:
	var f: Array[String] = []
	var sim: CombatSimulation = scene.simulation
	var cam: Camera3D = (scene.get_node("%CameraRig") as CameraRig).camera
	for i: int in 2:
		var hw: float = sim.profile(i).pushbox_half_width
		var x: float = sim.fighters[i].position_x
		if x - hw < sim.arena.left_bound - 1e-5 or x + hw > sim.arena.right_bound + 1e-5:
			f.append("%s: P%d outside arena (x=%.3f)" % [label, i + 1, x])
		if not _visible(cam, x):
			f.append("%s: P%d not fully on camera (x=%.3f, cam x=%.2f dist=%.2f)" % [
				label, i + 1, x, cam.global_position.x, cam.global_position.z])
	if sim.fighters[0].facing != -sim.fighters[1].facing:
		f.append("%s: fighters not facing each other" % label)
	return f


func test_walk_to_left_wall_stays_visible() -> Array[String]:
	var scene: Node = _spawn_scene()
	var f: Array[String] = _ready_failures(scene)
	if not f.is_empty():
		scene.free()
		return f
	_skip_intro(scene)
	Input.action_press(InputActions.MOVE_LEFT)
	for step: int in 12:  # 6 s, checked every 0.5 s
		_frames(scene, 30)
		f.append_array(_check(scene, "left t=%.1fs" % ((step + 1) * 0.5)))
	Input.action_release(InputActions.MOVE_LEFT)
	scene.free()
	return f


func test_push_dummy_to_right_wall_stays_visible() -> Array[String]:
	var scene: Node = _spawn_scene()
	var f: Array[String] = _ready_failures(scene)
	if not f.is_empty():
		scene.free()
		return f
	_skip_intro(scene)
	Input.action_press(InputActions.MOVE_RIGHT)
	for step: int in 12:
		_frames(scene, 30)
		f.append_array(_check(scene, "right t=%.1fs" % ((step + 1) * 0.5)))
	var sim: CombatSimulation = scene.simulation
	var expected: float = sim.arena.right_bound - sim.profile(1).pushbox_half_width
	if absf(sim.fighters[1].position_x - expected) > 1e-4:
		f.append("dummy not pushed to right wall (x=%.3f)" % sim.fighters[1].position_x)
	Input.action_release(InputActions.MOVE_RIGHT)
	scene.free()
	return f


func test_scene_same_result_at_30_and_144_fps() -> Array[String]:
	var f: Array[String] = []
	var results: Array[float] = []
	for fps: float in [30.0, 144.0]:
		var scene: Node = _spawn_scene()
		var not_ready: Array[String] = _ready_failures(scene)
		if not not_ready.is_empty():
			scene.free()
			return not_ready
		_skip_intro(scene)
		var start_tick: int = (scene.simulation as CombatSimulation).tick
		Input.action_press(InputActions.MOVE_LEFT)
		_frames(scene, int(fps), 1.0 / fps)  # 1 s
		Input.action_release(InputActions.MOVE_LEFT)
		var sim: CombatSimulation = scene.simulation
		# Normalise to exactly 60 fight ticks for comparison.
		while sim.tick - start_tick < 60:  # bounded: step() always increments tick
			sim.step([FighterInputFrame.moving(-1), FighterInputFrame.neutral()])
		if sim.tick - start_tick > 61:
			f.append("%d fps ran %d ticks in 1 s" % [int(fps), sim.tick - start_tick])
		results.append(sim.fighters[0].position_x if sim.tick - start_tick == 60 else NAN)
		scene.free()
	if is_nan(results[0]) or is_nan(results[1]):
		return f
	if results[0] != results[1]:
		f.append("P1 position differs: 30fps=%.6f 144fps=%.6f" % results)
	return f


func test_scene_light_attack_hits_dummy_with_effects() -> Array[String]:
	var scene: Node = _spawn_scene()
	var f: Array[String] = _ready_failures(scene)
	if not f.is_empty():
		scene.free()
		return f
	var sim: CombatSimulation = scene.simulation
	_skip_intro(scene)
	# Walk into range.
	Input.action_press(InputActions.MOVE_RIGHT)
	for _i: int in 120:
		_frames(scene, 1)
		if sim.separation() < 1.0:
			break
	Input.action_release(InputActions.MOVE_RIGHT)
	_frames(scene, 2)
	# Press light through the real input action.
	Input.action_press(InputActions.ATTACK_LIGHT)
	_frames(scene, 10)
	Input.action_release(InputActions.ATTACK_LIGHT)
	var hits: int = 0
	for e: CombatEvent in sim.combat_log.all_events():
		if e.type == CombatEvent.Type.HIT and e.actor == 0:
			hits += 1
	if hits != 1:
		f.append("expected 1 P1 hit, log:\n%s" % sim.combat_log.to_text())
	var fx: EffectsManager = scene.get_node("%EffectsManager")
	if fx.get_child_count() == 0:
		f.append("no hit spark spawned")
	var boxes: HitboxDebugView = scene.get_node("%HitboxDebugView")
	if boxes.get_child_count() != 4:
		f.append("hitbox debug view should hold 4 boxes, has %d" % boxes.get_child_count())
	# HUD health bar shows the simulation's health.
	var hud: MatchHUD = scene.get_node("%MatchHUD")
	if hud.health_bar_value(1) != sim.fighters[1].health:
		f.append("HUD P2 bar %.0f != health %d" % [hud.health_bar_value(1), sim.fighters[1].health])
	# Restart (debug R / pause menu) restores a clean match.
	scene.start_match()
	if sim.fighters[1].health != sim.definitions[1].base_health:
		f.append("start_match did not restore health")
	scene.free()
	return f



func test_hud_timer_and_announcer() -> Array[String]:
	var scene: Node = _spawn_scene()
	var f: Array[String] = _ready_failures(scene)
	if not f.is_empty():
		scene.free()
		return f
	var hud: MatchHUD = scene.get_node("%MatchHUD")
	var timer: Label = hud.get_node("%TimerLabel")
	if timer.text != "90":
		f.append("timer shows '%s' at start" % timer.text)
	if hud.announce_text() != "ROUND 1":
		f.append("announcer shows '%s' during intro" % hud.announce_text())
	_skip_intro(scene)
	_frames(scene, 1)
	if hud.announce_text() != "FIGHT!":
		f.append("announcer shows '%s' after intro" % hud.announce_text())
	_frames(scene, 61)
	if timer.text != "89":
		f.append("timer shows '%s' after ~1 s of fight" % timer.text)
	scene.free()
	return f


func test_pause_stops_simulation_and_resume_continues() -> Array[String]:
	var scene: Node = _spawn_scene()
	var f: Array[String] = _ready_failures(scene)
	if not f.is_empty():
		scene.free()
		return f
	_skip_intro(scene)
	var sim: CombatSimulation = scene.simulation
	var d: MatchDirector = scene.director
	scene.pause()
	var menu: PauseMenu = scene.get_node("%PauseMenu")
	if not _tree().paused or not menu.visible:
		f.append("pause() did not pause the tree / show the menu")
	var tick: int = sim.tick
	var timer: int = d.timer_ticks
	_frames(scene, 120)
	if sim.tick != tick or d.timer_ticks != timer:
		f.append("simulation/timer advanced while paused")
	scene.resume()
	if _tree().paused or menu.visible:
		f.append("resume() did not unpause / hide menu")
	_frames(scene, 10)
	if sim.tick <= tick:
		f.append("simulation did not continue after resume")
	# Backgrounding the app pauses automatically.
	scene._notification(Node.NOTIFICATION_APPLICATION_FOCUS_OUT)
	if not _tree().paused:
		f.append("app focus-out did not pause")
	scene.resume()
	_tree().paused = false
	scene.free()
	return f


func test_match_end_results_and_rematch() -> Array[String]:
	var scene: Node = _spawn_scene()
	var f: Array[String] = _ready_failures(scene)
	if not f.is_empty():
		scene.free()
		return f
	var sim: CombatSimulation = scene.simulation
	var d: MatchDirector = scene.director
	# Fast-forward: each fight phase, knock P2 out directly through the rules.
	var guard: int = 0
	while not d.is_match_over() and guard < 5000:
		if d.phase == MatchDirector.Phase.FIGHT:
			sim.fighters[1].health = 1
			sim.fighters[0].position_x = sim.fighters[1].position_x - 0.9
			Input.action_press(InputActions.ATTACK_LIGHT)
			_frames(scene, 1)
			Input.action_release(InputActions.ATTACK_LIGHT)
		_frames(scene, 1)
		guard += 1
	var results: MatchResults = scene.get_node("%MatchResults")
	if not d.is_match_over() or not results.visible:
		f.append("match did not end with results shown (phase %s)" % d.phase_name())
	elif results.title_text() != "P1 WINS":
		f.append("results title '%s'" % results.title_text())
	# Pause is disabled on the results screen.
	scene.pause()
	if _tree().paused:
		f.append("pause allowed after match end")
		_tree().paused = false
	# Rematch via the results button.
	(results.get_node("%RematchButton") as Button).pressed.emit()
	if results.visible or d.round_number != 1 or d.round_wins != [0, 0] \
			or sim.fighters[1].health != sim.definitions[1].base_health:
		f.append("rematch did not start a clean match")
	scene.free()
	return f
