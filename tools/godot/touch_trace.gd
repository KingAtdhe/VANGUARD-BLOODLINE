extends SceneTree
## Training mode, P1 driven through the real touch stick: the thumb lands on
## the stick and is held at `reach` px straight down (+`xoff` px sideways),
## trembling by up to `amp` px every frame. Prints the state, the clip and the
## head height per rendered frame (clock slowed: about one tick per frame).
## Reproduced the phone's shaking crouch (D-095).
##   xvfb-run -a godot --path . --rendering-method mobile --script res://tools/godot/touch_trace.gd -- <amp> <reach> [xoff]
func _initialize() -> void:
	root.size = Vector2i(2400, 1080)
	SaveManager.ensure_loaded()
	var s := MatchSetup.new()
	s.p1_id = &"kairo"; s.p2_id = &"training_dummy"
	s.mode = MatchSetup.Mode.TRAINING; s.rules_path = MatchSetup.RULES_TRAINING
	ModeFlow.setup = s
	var scene: Node = (load(ScenePaths.TRAINING_GREYBOX) as PackedScene).instantiate()
	root.add_child(scene)
	await create_timer(3.0).timeout
	var sim: CombatSimulation = scene.get("simulation")
	var view: FighterView = scene.get("_fighter_views")[0]
	var touch: TouchControls = scene.get("_touch")
	print("ai=", scene.get("ai"), " p2mode=", scene.get("p2_mode"))
	var rest: Vector2 = touch.stick_rest()
	var amp: float = float(OS.get_cmdline_user_args()[0]) if OS.get_cmdline_user_args().size() > 0 else 12.0
	var reach: float = float(OS.get_cmdline_user_args()[1]) if OS.get_cmdline_user_args().size() > 1 else 110.0
	var xoff: float = float(OS.get_cmdline_user_args()[2]) if OS.get_cmdline_user_args().size() > 2 else 0.0
	Engine.time_scale = 0.25
	print("visible=", touch.visible, " rest=", rest)
	touch.call("_touch_down", 0, rest)
	var rng := RandomNumberGenerator.new(); rng.seed = 7
	for i in 160:
		touch.call("_stick_move", rest + Vector2(xoff + rng.randf_range(-amp, amp), reach + rng.randf_range(-amp, amp)))
		await process_frame
		var sk: Skeleton3D = view.skeleton
		var hd: Vector3 = (sk.global_transform * sk.get_bone_global_pose(sk.find_bone("Head"))).origin
		print("t%d %s anim=%s down=%s x=%s head_y=%.3f" % [sim.tick, sim.fighters[0].action_name(), view.animator.current,
			Input.is_action_pressed(&"move_down"), Input.is_action_pressed(&"move_left") or Input.is_action_pressed(&"move_right"), hd.y])
	quit()
