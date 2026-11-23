extends SceneTree
## Prints where a few joints are on every frame of one animation of a
## fighter's installed model (what the game will actually play), to find
## jitter that the build's own poses do not show (D-093).
##   godot --headless --path . --script res://tools/godot/clip_trace.gd -- <fighter_id> <SUFFIX> [bone,bone,...]

func _initialize() -> void:
	var a: PackedStringArray = OS.get_cmdline_user_args()
	var def: FighterDefinition = load("res://data/fighters/%s.tres" % a[0])
	var bones: PackedStringArray = (a[2] if a.size() > 2 else "Hips,Head,LeftHand,RightHand,LeftFoot,RightFoot").split(",")
	var model: Node3D = def.model_scene.instantiate()
	root.add_child(model)
	var ap: AnimationPlayer = model.find_child("AnimationPlayer", true, false)
	var sk: Skeleton3D = model.find_children("*", "Skeleton3D", true, false)[0]
	var anim: Animation = ap.get_animation(StringName("%s_%s" % [a[0].to_upper(), a[1]]))
	var frames: int = int(round(anim.length * 60.0)) + 1
	for i: int in frames:
		AnimationSampler.apply(anim, sk, i / 60.0)
		var line: String = "f%02d" % (i + 1)
		for b: String in bones:
			var p: Vector3 = AnimationSampler.bone_global(sk, sk.find_bone(b)).origin
			line += "  %s(%.3f %.3f %.3f)" % [b.substr(0, 6), p.x, p.y, p.z]
		print(line)
	quit()
