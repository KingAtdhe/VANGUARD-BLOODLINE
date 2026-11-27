extends SceneTree
## Weight, chain and spacing per frame of a clip, as CSV (D-131): what a
## critique of "weightless", "isolated limb" or "linear" needs as numbers.
##
##   godot --headless --path . --script res://tools/godot/weight_check.gd -- <fighter> <CLIP_SUFFIX>
##
## Columns (metres, degrees; the fighter stands unrotated: forward +Z, his
## left +X, up +Y; frames 1-based):
##   hips_f hips_x hips_h         pelvis joint
##   pel chest                    hip line and shoulder line, side-on angle
##   lean_f lean_s                trunk from upright
##   head_f head_x head_h
##   la_f la_x la_h / ra_*        left / right ankle
##   lt_h rt_h lt_f rt_f          left / right toe height and forward
##   lw_f lw_x lw_h / rw_*        left / right wrist
##   trv                          metres the game has moved him (moves with move_distance)
##   fore                         angle between the two forearms as the side camera sees them (0 = parallel)
##   bend                         bend of the back between waist and chest (0 = a straight rod)
## Read it with .claude/skills/fighter-move-animation/scripts/weight_report.py.


func _initialize() -> void:
	var a: PackedStringArray = OS.get_cmdline_user_args()
	if a.size() < 2:
		print("usage: weight_check.gd -- <fighter> <CLIP_SUFFIX>")
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
	var mv: MoveData = null
	for m: MoveData in def.moves:
		if m.animation == anim:
			startup = m.startup_frames
			active = m.active_frames
			mv = m
	ap.play(anim)
	ap.pause()
	await process_frame
	var n: int = int(round(ap.current_animation_length * 60.0))
	print("#CLIP %s frames %d startup %d active %d" % [anim, n + 1, startup, active])
	print("f,hips_f,hips_x,hips_h,pel,chest,lean_f,lean_s,head_f,head_x,head_h,la_f,la_x,la_h,ra_f,ra_x,ra_h,lt_h,rt_h,lt_f,rt_f,lw_f,lw_x,lw_h,rw_f,rw_x,rw_h,trv,fore,bend")
	var floor_y: float = 0.0
	var trv: float = 0.0
	for f: int in n + 1:
		if mv != null and mv.moves_on_frame(f + 1):
			trv += mv.move_step()               # metres the game has carried him when this frame shows
		ap.seek(f / 60.0, true)
		sk.force_update_all_bone_transforms()
		var p: Dictionary = {}
		for b: String in ["Hips", "Neck", "Head", "LeftUpperLeg", "RightUpperLeg", "LeftFoot", "RightFoot",
				"LeftUpperArm", "RightUpperArm", "LeftHand", "RightHand", "LeftLowerArm", "RightLowerArm", "Spine", "Chest"]:
			var i: int = sk.find_bone(b)
			if i < 0:
				print("bone missing: " + b)
				quit(2)
				return
			var gt: Transform3D = sk.global_transform * sk.get_bone_global_pose(i)
			p[b] = gt.origin
			if b.ends_with("Foot"):
				# no toe bone on this rig: the ball of the foot is 15 cm along the foot bone
				p[b.replace("Foot", "Toes")] = gt * Vector3(0.0, 0.15, 0.0)
		if f == 0:
			floor_y = minf(p["LeftToes"].y, p["RightToes"].y)
		var hip_line: Vector3 = p["LeftUpperLeg"] - p["RightUpperLeg"]
		var sho_line: Vector3 = p["LeftUpperArm"] - p["RightUpperArm"]
		var trunk: Vector3 = p["Neck"] - p["Hips"]
		var row: Array = [f + 1, p["Hips"].z, p["Hips"].x, p["Hips"].y - floor_y,
			rad_to_deg(atan2(hip_line.z, hip_line.x)), rad_to_deg(atan2(sho_line.z, sho_line.x)),
			rad_to_deg(atan2(trunk.z, trunk.y)), rad_to_deg(atan2(trunk.x, trunk.y)),
			p["Head"].z, p["Head"].x, p["Head"].y - floor_y,
			p["LeftFoot"].z, p["LeftFoot"].x, p["LeftFoot"].y - floor_y,
			p["RightFoot"].z, p["RightFoot"].x, p["RightFoot"].y - floor_y,
			p["LeftToes"].y - floor_y, p["RightToes"].y - floor_y, p["LeftToes"].z, p["RightToes"].z,
			p["LeftHand"].z, p["LeftHand"].x, p["LeftHand"].y - floor_y,
			p["RightHand"].z, p["RightHand"].x, p["RightHand"].y - floor_y, trv,
			rad_to_deg(_side(p["LeftHand"] - p["LeftLowerArm"]).angle_to(_side(p["RightHand"] - p["RightLowerArm"]))),
			rad_to_deg((p["Chest"] - p["Spine"]).angle_to(p["Neck"] - p["Chest"]))]
		var s: PackedStringArray = []
		for v: Variant in row:
			s.append(str(v) if v is int else "%.4f" % float(v))
		print(",".join(s))
	quit()


## A direction as the game's side camera sees it (forward and up only).
static func _side(v: Vector3) -> Vector2:
	return Vector2(v.z, v.y)
