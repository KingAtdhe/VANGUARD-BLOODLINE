extends SceneTree
## Spinning-kick audit (D-149): per frame, the world yaw of the pelvis, chest,
## neck and head (0 = facing the opponent, +X), the neck's twist and bend
## relative to the chest, the head's relative to the neck, and the stretch of the
## neck and head bones (distance to parent vs rest). Usage:
##   godot --headless --path . --script res://tools/godot/spin_audit.gd -- <clip>
func _initialize() -> void:
	_go()

func _yaw(b: Basis) -> float:
	var f: Vector3 = b * Vector3(0, 0, 1)      # bone's model-forward
	return rad_to_deg(atan2(f.x, f.z))

func _go() -> void:
	var m: Node3D = (load("res://assets/characters/kairo/kairo.glb") as PackedScene).instantiate()
	root.add_child(m)
	var ap: AnimationPlayer = m.find_child("AnimationPlayer", true, false)
	var sk: Skeleton3D = m.find_children("*", "Skeleton3D", true, false)[0]
	var clip: String = OS.get_cmdline_user_args()[0]
	for n in ["Hips", "Spine", "Chest", "Neck", "Head"]:
		var i: int = sk.find_bone(n)
		print("bone %-6s idx %d parent %s" % [n, i, sk.get_bone_name(sk.get_bone_parent(i)) if i >= 0 else "-"])
	ap.play(clip); ap.pause()
	await process_frame
	var ids: Dictionary = {}
	for n in ["Hips", "Chest", "Neck", "Head"]:
		ids[n] = sk.find_bone(n)
	var rest_neck: float = (sk.get_bone_global_rest(ids["Neck"]).origin - sk.get_bone_global_rest(ids["Chest"]).origin).length()
	var rest_head: float = (sk.get_bone_global_rest(ids["Head"]).origin - sk.get_bone_global_rest(ids["Neck"]).origin).length()
	# rest yaws: the bones' own frames are not aligned with the model; measure change from rest
	var r: Dictionary = {}
	for n in ids:
		r[n] = _yaw(sk.get_bone_global_rest(ids[n]).basis)
	print(" f  hips  chest  neck  head | neck-chest head-neck head-chest | neck pitch head pitch | stretch neck head")
	for f in int(round(ap.current_animation_length * 60.0)) + 1:
		ap.seek(f / 60.0, true)
		sk.force_update_all_bone_transforms()
		var y: Dictionary = {}
		var p: Dictionary = {}
		for n in ids:
			var g: Basis = sk.get_bone_global_pose(ids[n]).basis * sk.get_bone_global_rest(ids[n]).basis.inverse()
			y[n] = wrapf(_yaw(g), -180, 180)
			var up: Vector3 = g * Vector3.UP
			p[n] = rad_to_deg(asin(clampf(up.z, -1, 1)))
		var sn: float = (sk.get_bone_global_pose(ids["Neck"]).origin - sk.get_bone_global_pose(ids["Chest"]).origin).length() / rest_neck
		var sh: float = (sk.get_bone_global_pose(ids["Head"]).origin - sk.get_bone_global_pose(ids["Neck"]).origin).length() / rest_head
		print("%2d %5.0f %6.0f %5.0f %5.0f | %10.0f %9.0f %10.0f | %10.0f %10.0f | %7.2f %5.2f" % [f + 1, y["Hips"], y["Chest"], y["Neck"], y["Head"],
			wrapf(y["Neck"] - y["Chest"], -180, 180), wrapf(y["Head"] - y["Neck"], -180, 180), wrapf(y["Head"] - y["Chest"], -180, 180), p["Neck"], p["Head"], sn, sh])
	quit()
