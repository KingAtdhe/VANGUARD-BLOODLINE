extends SceneTree
## Per frame: the ball of each foot (model space x, z, height) and how far it
## moved since the last frame (D-149). Usage: -- <clip>
func _initialize() -> void:
	_go()

func _go() -> void:
	var m: Node3D = (load("res://assets/characters/kairo/kairo.glb") as PackedScene).instantiate()
	root.add_child(m)
	var ap: AnimationPlayer = m.find_child("AnimationPlayer", true, false)
	var sk: Skeleton3D = m.find_children("*", "Skeleton3D", true, false)[0]
	ap.play(OS.get_cmdline_user_args()[0]); ap.pause()
	await process_frame
	var prev: Dictionary = {}
	print(" f   left ball x/z/h        moved  | right ball x/z/h       moved")
	for f in int(round(ap.current_animation_length * 60.0)) + 1:
		ap.seek(f / 60.0, true)
		sk.force_update_all_bone_transforms()
		var line: String = "%2d " % (f + 1)
		for side in ["Left", "Right"]:
			var i: int = sk.find_bone(side + "Foot")
			var rest: Transform3D = sk.get_bone_global_rest(i)
			var bl: Vector3 = rest.affine_inverse() * Vector3(rest.origin.x, 0.0, rest.origin.z + 0.12)
			var b: Vector3 = sk.get_bone_global_pose(i) * bl
			var mv: float = Vector2(b.x - prev.get(side, b).x, b.z - prev.get(side, b).z).length() * 100.0
			prev[side] = b
			line += " %6.2f %6.2f %5.2f %5.1fcm |" % [b.x, b.z, b.y, mv]
		print(line)
	quit()
