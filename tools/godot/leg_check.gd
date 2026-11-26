extends SceneTree
## One leg through one clip, measured on the game model as Godot plays it
## (D-129): the numbers a kick is validated with. One CSV line per frame
## (frames 1-based; contact = the move's startup number):
##   f, phase, hip (fwd, up, side), knee (fwd, up, side), ankle (fwd, up, side),
##   knee flexion about its measured hinge axis (deg, 0 = straight, + = heel
##   toward the seat, negative would be a knee bending the wrong way), knee rotation that
##   is NOT flexion (deg: twist or sideways bend), thigh out of the body's
##   fore-aft plane (deg, + = outward), ankle angle against rest (deg, + =
##   toes pulled back toward the shin), head (fwd, up), the other ankle
##   (fwd in WORLD = model + the game's travel, up).
## Positions are metres in model space: forward of the model's origin, height
## above the floor, sideways (+ = toward the kicking side, away from centre).
## tools read by .claude/skills/fighter-move-animation/scripts/leg_report.py
##
##   godot --headless --path . --script res://tools/godot/leg_check.gd -- <fighter> <CLIP_SUFFIX> <Right|Left>
var sk: Skeleton3D


func gp(b: String) -> Vector3:
	return (sk.global_transform * sk.get_bone_global_pose(sk.find_bone(b))).origin


func _initialize() -> void:
	var a: PackedStringArray = OS.get_cmdline_user_args()
	if a.size() < 3:
		print("usage: leg_check.gd -- <fighter> <CLIP_SUFFIX> <Right|Left>")
		quit(2)
		return
	var def: FighterDefinition = load("res://data/fighters/%s.tres" % a[0])
	var side: String = a[2]
	var other: String = "Left" if side == "Right" else "Right"
	var model: Node3D = def.model_scene.instantiate()
	root.add_child(model)
	for n: Node in model.find_children("*", "Skeleton3D", true, false):
		sk = n as Skeleton3D
	var ap: AnimationPlayer = model.find_child("AnimationPlayer", true, false)
	var prefix: String = String(def.anim_prefix if def.anim_prefix != &"" else StringName(a[0].to_upper()))
	var anim: StringName = StringName("%s_%s" % [prefix, a[1]])
	await process_frame
	if ap == null or sk == null or not ap.has_animation(anim):
		print("no clip %s on %s" % [anim, a[0]])
		quit(2)
		return
	var mv: MoveData = null
	for m: MoveData in def.moves:
		if m.animation == anim:
			mv = m
	# rest values the per-frame numbers are compared with
	sk.reset_bone_poses()
	sk.force_update_all_bone_transforms()
	var knee_i: int = sk.find_bone(side + "LowerLeg")
	var foot_i: int = sk.find_bone(side + "Foot")
	var knee_rest: Quaternion = sk.get_bone_rest(knee_i).basis.get_rotation_quaternion()
	var foot_rest_ang: float = _ankle(side)
	var knee_rest_bend: float = rad_to_deg((gp(side + "LowerLeg") - gp(side + "UpperLeg")).angle_to(gp(side + "Foot") - gp(side + "LowerLeg")))
	var floor: float = minf(gp("LeftFoot").y, gp("RightFoot").y)
	var sgn: float = -1.0 if side == "Right" else 1.0
	ap.play(anim)
	ap.pause()
	var n: int = int(round(ap.current_animation_length * 60.0))
	print("LEG %s %s %s frames=%d startup=%d active=%d travel=%.3f travel_frames=%d-%d" % [anim, side, a[0], n + 1,
		mv.startup_frames if mv else 0, mv.active_frames if mv else 0, mv.move_distance if mv else 0.0,
		mv.move_start_frame if mv else 0, mv.move_end_frame if mv else 0])
	print("f,phase,hip_f,hip_u,hip_s,knee_f,knee_u,knee_s,ank_f,ank_u,ank_s,knee_flex,knee_other,thigh_out,toes_back,head_f,head_u,sup_world_f,sup_u")
	for f: int in n + 1:
		ap.seek(f / 60.0, true)
		sk.force_update_all_bone_transforms()
		var hip: Vector3 = gp(side + "UpperLeg")
		var knee: Vector3 = gp(side + "LowerLeg")
		var ank: Vector3 = gp(side + "Foot")
		# knee: rotation relative to rest, split into flexion about the hinge (local X, measured by rig_inspect.gd) and the rest
		var q: Quaternion = (knee_rest.inverse() * sk.get_bone_pose_rotation(knee_i)).normalized()
		var tw: Quaternion = Quaternion(q.x, 0.0, 0.0, q.w).normalized()
		var flex: float = rad_to_deg(2.0 * atan2(tw.x, tw.w))
		flex = wrapf(flex, -180.0, 180.0)
		var rest_part: Quaternion = (q * tw.inverse()).normalized()
		var other_ang: float = rad_to_deg(2.0 * acos(clampf(absf(rest_part.w), 0.0, 1.0)))
		# thigh against the body's fore-aft plane (the pelvis' own sideways axis)
		var lat: Vector3 = (gp("LeftUpperLeg") - gp("RightUpperLeg")).normalized()
		var thigh_out: float = rad_to_deg(asin(clampf((knee - hip).normalized().dot(lat) * sgn, -1.0, 1.0)))
		var travel: float = 0.0
		if mv and mv.move_distance != 0.0:
			var per: float = mv.move_distance / float(mv.move_end_frame - mv.move_start_frame + 1)
			travel = per * clampf(float(f + 1 - mv.move_start_frame + 1), 0.0, float(mv.move_end_frame - mv.move_start_frame + 1))
		var sup: Vector3 = gp(other + "Foot")
		var head: Vector3 = gp("Head")
		var ph: String = "-"
		if mv:
			ph = "S" if f + 1 < mv.startup_frames else ("A" if f + 1 < mv.startup_frames + mv.active_frames else "R")
		print("%d,%s,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.1f,%.1f,%.1f,%.1f,%.3f,%.3f,%.3f,%.3f" % [f + 1, ph,
			hip.z, hip.y - floor, hip.x * sgn, knee.z, knee.y - floor, knee.x * sgn, ank.z, ank.y - floor, ank.x * sgn,
			flex + knee_rest_bend, other_ang, thigh_out, _ankle(side) - foot_rest_ang, head.z, head.y - floor, sup.z + travel, sup.y - floor])
	quit()


func _ankle(side: String) -> float:
	## angle between the shin and the foot bone's own long axis (local Y), degrees
	var foot_i: int = sk.find_bone(side + "Foot")
	var foot_axis: Vector3 = (sk.global_transform * sk.get_bone_global_pose(foot_i)).basis.y.normalized()
	var shin: Vector3 = (gp(side + "Foot") - gp(side + "LowerLeg")).normalized()
	return rad_to_deg(shin.angle_to(foot_axis))
