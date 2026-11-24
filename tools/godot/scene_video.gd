extends SceneTree
## Records the real training scene (camera, arena, effects, both fighters)
## while P1 runs a scripted list of inputs. Run with Godot's movie writer so
## every frame is captured at a fixed 60 fps (D-101):
##   xvfb-run -a godot --path . --rendering-driver opengl3 --resolution 1280x576 --fixed-fps 60 \
##         --write-movie /tmp/frames/f.png --script res://tools/godot/scene_video.gd -- <script> [fighter]
## <script>: comma list of steps, each ACTION[+ACTION]:frames (actions are
## InputActions names; "wait" presses nothing), e.g.
##   wait:60,move_down+special:4,wait:90,move_right:40,ultimate:4,wait:200
## "meter" as a step fills P1's Origin meter and starts Origin Surge.

func _initialize() -> void:
	var a: PackedStringArray = OS.get_cmdline_user_args()
	SaveManager.ensure_loaded()
	var s := MatchSetup.new()
	s.p1_id = StringName(a[1]) if a.size() > 1 else &"kairo"
	s.p2_id = &"training_dummy"
	s.mode = MatchSetup.Mode.TRAINING
	s.rules_path = MatchSetup.RULES_TRAINING
	ModeFlow.setup = s
	var scene: Node = (load(ScenePaths.TRAINING_GREYBOX) as PackedScene).instantiate()
	root.add_child(scene)
	var sim: CombatSimulation = scene.get("simulation")
	for step: String in (a[0] if a.size() > 0 else "wait:120").split(","):
		var parts: PackedStringArray = step.split(":")
		var n: int = int(parts[1]) if parts.size() > 1 else 1
		if parts[0] == "meter":
			sim.fighters[0].meter = sim.tuning.meter_max
			sim.fighters[0].surge_remaining = 900
			continue
		var acts: PackedStringArray = [] if parts[0] == "wait" else parts[0].split("+")
		for act: String in acts:
			Input.action_press(StringName(act))
		for i: int in n:
			await process_frame
		for act: String in acts:
			Input.action_release(StringName(act))
	quit()
