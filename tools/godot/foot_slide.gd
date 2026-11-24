extends SceneTree
## Foot slide while walking (D-106): the real training scene, P1 holds a
## direction; every frame the world position of both feet is taken and, for a
## foot on the floor (its lowest point: heel, or ball once the heel is up),
## how far that point moved along the fighting plane since the last frame. Prints the average and worst slide per planted frame (cm).
##   xvfb-run -a godot --path . --rendering-driver opengl3 --fixed-fps 60 --script res://tools/godot/foot_slide.gd -- [fighter] [move_right|move_left]
func _initialize() -> void:
	var a: PackedStringArray = OS.get_cmdline_user_args()
	SaveManager.ensure_loaded()
	var s := MatchSetup.new()
	s.p1_id = StringName(a[0]) if a.size() > 0 else &"kairo"
	s.p2_id = &"training_dummy"
	s.mode = MatchSetup.Mode.TRAINING
	s.rules_path = MatchSetup.RULES_TRAINING
	ModeFlow.setup = s
	var scene: Node = (load(ScenePaths.TRAINING_GREYBOX) as PackedScene).instantiate()
	root.add_child(scene)
	for i in 30:
		await process_frame
	var view: FighterView = scene.get("_fighter_views")[0]
	var sk: Skeleton3D = view.skeleton
	var act: StringName = StringName(a[1]) if a.size() > 1 else &"move_right"
	if act == &"move_right":                     # walk forward from further back
		scene.get("simulation").fighters[0].position_x -= 1.0
	Input.action_press(act)
	var prev := {}
	var slides: Array[float] = []
	var signed := 0.0
	var hips_prev: float = INF
	var hips_moves: Array[float] = []
	for i in 60:
		await process_frame
		if i < 12:
			continue
		for b in ["LeftFoot", "RightFoot"]:
			# the point touching the floor: the ball of the foot once the heel is
			# up, the heel otherwise (the ankle moves forward as the heel rolls)
			var g: Transform3D = sk.global_transform * sk.get_bone_global_pose(sk.find_bone(b))
			var ankle: Vector3 = g.origin
			var ball: Vector3 = ankle + g.basis.y.normalized() * 0.13
			var p: Vector3 = ball if ankle.y - ball.y > 0.03 else ankle
			p.y = minf(ankle.y, ball.y)
			if prev.has(b) and p.y < 0.07 and (prev[b] as Vector3).y < 0.07:
				slides.append(absf(p.x - (prev[b] as Vector3).x))
				signed += p.x - (prev[b] as Vector3).x
			prev[b] = p
		var hx: float = view.global_position.x
		if hips_prev != INF:
			hips_moves.append(hx - hips_prev)
		hips_prev = hx
	Input.action_release(act)
	slides.sort()
	var tot := 0.0
	for v in slides: tot += v
	print("SLIDE %s planted-frames=%d mean=%.2f cm  p90=%.2f cm  max=%.2f cm  (body moves %.2f cm/frame)" % [act, slides.size(),
		100.0 * tot / maxf(1, slides.size()), 100.0 * slides[int(slides.size() * 0.9)], 100.0 * slides[-1],
		100.0 * scene.get("simulation").profile(0).walk_forward_speed / 60.0])
	var hm := 0.0
	for v in hips_moves: hm += v
	print("SIGNED mean planted foot dx %.2f cm/frame, body dx %.2f cm/frame" % [100.0 * signed / maxf(1, slides.size()), 100.0 * hm / maxf(1, hips_moves.size())])
	quit()
