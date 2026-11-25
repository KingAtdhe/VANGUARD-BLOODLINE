extends SceneTree
## Body angles per frame of a clip, measured on the game model as Godot plays
## it (D-124): what a pose brief needs for its "now" column and what the
## build log cannot give (the log has wrists and ankles only).
##
##   godot --headless --path . --script res://tools/godot/body_angles.gd -- <fighter> <CLIP_SUFFIX>
##   e.g. ... -- kairo KICK_LOW_01
##
## One line per frame. Frames are 1-based, like the move's frame data (frame
## = startup number is the contact). ph: S startup, A active, R recovery.
##   knee L/R     bend in degrees, 0 = straight (same as knee_angles.gd)
##   pelvis       how far the hip line is turned side-on, degrees; + = his
##                left side toward the opponent. (d) = change from frame 1.
##   chest        the same for the shoulder line
##   twist        chest minus pelvis: above ~45 reads as a body twisted
##                against itself (D-086, D-108)
##   lean         trunk (hips to neck) from upright, degrees: fwd + = toward
##                the opponent, - = back; side + = to his left (away from the
##                game camera when he is P1 facing right)
##   ankle L/R    forward of the hips' start (m) / height off the floor (m)
##   head         height of the head joint (m)
## The fighter stands unrotated: forward +Z, his left +X, up +Y.


func _initialize() -> void:
	var a: PackedStringArray = OS.get_cmdline_user_args()
	if a.size() < 2:
		print("usage: body_angles.gd -- <fighter> <CLIP_SUFFIX>")
		quit(2)
		return
	var def: FighterDefinition = load("res://data/fighters/%s.tres" % a[0])
	var model: Node3D = def.model_scene.instantiate()
	root.add_child(model)
	var ap: AnimationPlayer = model.find_child("AnimationPlayer", true, false)
	var sk: Skeleton3D = null
	for n: Node in model.find_children("*", "Skeleton3D", true, false):
		sk = n as Skeleton3D
	var prefix: String = String(def.anim_prefix if def.anim_prefix != &"" else StringName(a[0].to_upper()))
	var anim: StringName = StringName("%s_%s" % [prefix, a[1]])
	if ap == null or sk == null or not ap.has_animation(anim):
		print("no clip %s on %s" % [anim, a[0]])
		quit(2)
		return
	var startup: int = 0
	var active: int = 0
	for m: MoveData in def.moves:
		if m.animation == anim:
			startup = m.startup_frames
			active = m.active_frames
	ap.play(anim)
	ap.pause()                                  # frames are set by seek() only, never by playback
	await process_frame
	var n: int = int(round(ap.current_animation_length * 60.0))
	var base: Dictionary = {}
	print("%s  %d frames%s" % [anim, n + 1, ("  startup %d, active %d: contact = frame %d" % [startup, active, startup]) if startup > 0 else ""])
	print("  f ph | knee L   R | pelvis  (d)  chest  (d)  twist | lean fwd  side | ankle L fwd/h   R fwd/h  | head")
	for f: int in n + 1:
		ap.seek(f / 60.0, true)
		sk.force_update_all_bone_transforms()
		var p: Dictionary = {}
		for b: String in ["Hips", "Neck", "Head", "LeftUpperLeg", "RightUpperLeg", "LeftLowerLeg", "RightLowerLeg",
				"LeftFoot", "RightFoot", "LeftUpperArm", "RightUpperArm"]:
			var i: int = sk.find_bone(b)
			if i < 0:
				print("bone missing: " + b)
				quit(2)
				return
			p[b] = (sk.global_transform * sk.get_bone_global_pose(i)).origin
		var knee: Array[float] = []
		for side: String in ["Left", "Right"]:
			var thigh: Vector3 = p[side + "LowerLeg"] - p[side + "UpperLeg"]
			var shin: Vector3 = p[side + "Foot"] - p[side + "LowerLeg"]
			knee.append(rad_to_deg(thigh.angle_to(shin)))
		var hip_line: Vector3 = p["LeftUpperLeg"] - p["RightUpperLeg"]
		var sho_line: Vector3 = p["LeftUpperArm"] - p["RightUpperArm"]
		var pelvis: float = rad_to_deg(atan2(hip_line.z, hip_line.x))
		var chest: float = rad_to_deg(atan2(sho_line.z, sho_line.x))
		var trunk: Vector3 = p["Neck"] - p["Hips"]
		var lean_f: float = rad_to_deg(atan2(trunk.z, trunk.y))
		var lean_s: float = rad_to_deg(atan2(trunk.x, trunk.y))
		if f == 0:
			base = {"pelvis": pelvis, "chest": chest, "z": p["Hips"].z, "floor": minf(p["LeftFoot"].y, p["RightFoot"].y)}
		var ph: String = " "
		if startup > 0:
			ph = "S" if f + 1 < startup else ("A" if f + 1 < startup + active else "R")
		print("%3d %s  | %5.0f %4.0f | %5.0f %+5.0f  %5.0f %+5.0f  %5.0f | %7.0f %5.0f | %5.2f/%4.2f  %5.2f/%4.2f | %4.2f%s" % [
			f + 1, ph, knee[0], knee[1], pelvis, wrapf(pelvis - base["pelvis"], -180.0, 180.0), chest,
			wrapf(chest - base["chest"], -180.0, 180.0), wrapf(chest - pelvis, -180.0, 180.0), lean_f, lean_s,
			p["LeftFoot"].z - base["z"], p["LeftFoot"].y - base["floor"], p["RightFoot"].z - base["z"],
			p["RightFoot"].y - base["floor"], p["Head"].y - base["floor"], "   <- contact" if f + 1 == startup else ""])
	quit()
