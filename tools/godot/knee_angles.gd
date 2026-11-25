extends SceneTree
## Knee bend (degrees between thigh and shin) per frame of a clip, as Godot
## plays it (D-114): the build log's leg extension is measured on the
## retarget skeleton, this on the game model.
## Usage: godot --headless --path . --script res://tools/godot/knee_angles.gd -- <fighter> <CLIP_SUFFIX>


func _initialize() -> void:
	var a: PackedStringArray = OS.get_cmdline_user_args()
	var def: FighterDefinition = load("res://data/fighters/%s.tres" % a[0])
	var model: Node3D = def.model_scene.instantiate()
	root.add_child(model)
	var ap: AnimationPlayer = model.find_child("AnimationPlayer", true, false)
	var sk: Skeleton3D = model.find_child("*", true, false) as Skeleton3D
	if sk == null:
		for n: Node in model.find_children("*", "Skeleton3D", true, false):
			sk = n as Skeleton3D
	var anim: StringName = StringName("%s_%s" % [String(def.anim_prefix if def.anim_prefix != &"" else &"KAIRO"), a[1]])
	ap.play(anim)
	var length: float = ap.current_animation_length
	var n: int = int(round(length * 60.0))
	var line: String = ""
	for f: int in n + 1:
		ap.seek(f / 60.0, true)
		await process_frame
		var parts: Array[String] = []
		for side: String in ["Left", "Right"]:
			var hip: Vector3 = sk.get_bone_global_pose(sk.find_bone(side + "UpperLeg")).origin
			var knee: Vector3 = sk.get_bone_global_pose(sk.find_bone(side + "LowerLeg")).origin
			var ankle: Vector3 = sk.get_bone_global_pose(sk.find_bone(side + "Foot")).origin
			parts.append("%s%.0f" % [side[0], rad_to_deg((knee - hip).angle_to(ankle - knee))])
		line += "%d:%s " % [f, ",".join(parts)]
	print(line)
	quit()
