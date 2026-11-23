extends SceneTree
## Runs the real training scene (TRAINING_GREYBOX; before D-095 this loaded the versus scene, whose AI attacked), holds one input action and prints,
## for every rendered frame, P1's state and where a few of its joints are on
## screen-space world axes. For jitter that only exists in the running game
## (state flicker, blending), which a clip on its own does not show (D-094).
##   xvfb-run -a godot --path . --rendering-method mobile --script res://tools/godot/hold_trace.gd \
##         -- <fighter_id> <action e.g. move_down> [frames] [time_scale, e.g. 0.15 on a slow machine]

func _initialize() -> void:
	var a: PackedStringArray = OS.get_cmdline_user_args()
	root.size = Vector2i(1280, 576)
	SaveManager.ensure_loaded()
	var s := MatchSetup.new()
	s.p1_id = StringName(a[0]) if a.size() > 0 else &"kairo"
	s.p2_id = &"training_dummy"
	s.mode = MatchSetup.Mode.TRAINING
	s.rules_path = MatchSetup.RULES_TRAINING
	ModeFlow.setup = s
	var scene: Node = (load(ScenePaths.TRAINING_GREYBOX) as PackedScene).instantiate()
	root.add_child(scene)
	await create_timer(3.0).timeout
	var action: StringName = StringName(a[1]) if a.size() > 1 else &"move_down"
	var frames: int = int(a[2]) if a.size() > 2 else 150
	var view: FighterView = scene.get("_fighter_views")[0]
	var sim: CombatSimulation = scene.get("simulation")
	# slow the clock so that every rendered frame is about one combat tick
	Engine.time_scale = float(a[3]) if a.size() > 3 else 1.0
	Input.action_press(action)
	for i: int in frames:
		await process_frame
		var sk: Skeleton3D = view.skeleton
		var line: String = "r%03d tick=%d %s anim=%s" % [i, sim.tick, sim.fighters[0].action_name(),
			view.animator.current if view.animator != null else &"-"]
		for b: String in ["Hips", "Head", "LeftHand", "RightFoot"]:
			var p: Vector3 = (sk.global_transform * sk.get_bone_global_pose(sk.find_bone(b))).origin
			line += "  %s(%.3f %.3f %.3f)" % [b.substr(0, 5), p.x, p.y, p.z]
		print(line)
	Input.action_release(action)
	quit()
