extends RefCounted
## Milestone 1 acceptance, driven through the real combat scene:
## both fighters stay in the arena, face each other and stay on camera.

const FRAME: float = 1.0 / 60.0


func _tree() -> SceneTree:
	return Engine.get_main_loop() as SceneTree


func _spawn_scene() -> Node:
	var scene: Node = (load(ScenePaths.COMBAT_GREYBOX) as PackedScene).instantiate()
	_tree().root.add_child(scene)
	return scene


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
		var hw: float = sim.profiles[i].pushbox_half_width
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
	Input.action_press(InputActions.MOVE_RIGHT)
	for step: int in 12:
		_frames(scene, 30)
		f.append_array(_check(scene, "right t=%.1fs" % ((step + 1) * 0.5)))
	var sim: CombatSimulation = scene.simulation
	var expected: float = sim.arena.right_bound - sim.profiles[1].pushbox_half_width
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
		Input.action_press(InputActions.MOVE_LEFT)
		_frames(scene, int(fps), 1.0 / fps)  # 1 s
		Input.action_release(InputActions.MOVE_LEFT)
		var sim: CombatSimulation = scene.simulation
		# Normalise to exactly 60 ticks for comparison.
		while sim.tick < 60:  # bounded: step() always increments tick
			sim.step([FighterInputFrame.moving(-1), FighterInputFrame.neutral()])
		if sim.tick > 61:
			f.append("%d fps ran %d ticks in 1 s" % [int(fps), sim.tick])
		results.append(sim.fighters[0].position_x if sim.tick == 60 else NAN)
		scene.free()
	if is_nan(results[0]) or is_nan(results[1]):
		return f
	if results[0] != results[1]:
		f.append("P1 position differs: 30fps=%.6f 144fps=%.6f" % results)
	return f
