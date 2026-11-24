extends SceneTree
## Close-up of a fighter's head (D-107): the model in its rest pose and on a
## frame of an animation, seen from the front, three-quarter and the game's
## side view, to judge the face and how the neck and head bend it.
##   xvfb-run -a godot --path . --rendering-driver opengl3 --script res://tools/godot/face_shot.gd \
##         -- <fighter_id> <out.png> <SUFFIX|REST,...> [frame] [cell_px]
func _initialize() -> void:
	var a: PackedStringArray = OS.get_cmdline_user_args()
	var fid: String = a[0]
	var out: String = a[1]
	var anims: PackedStringArray = (a[2] if a.size() > 2 else "REST,IDLE_A").split(",")
	var frame: int = int(a[3]) if a.size() > 3 else 0
	var cell: int = int(a[4]) if a.size() > 4 else 420
	var def: FighterDefinition = load("res://data/fighters/%s.tres" % fid)
	var yaws: Array[float] = [0.0, 40.0, 78.0]
	var img := Image.create(cell * yaws.size(), cell * anims.size(), false, Image.FORMAT_RGBA8)
	var vp := SubViewport.new()
	vp.size = Vector2i(cell, cell)
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	root.add_child(vp)
	var env := WorldEnvironment.new()
	env.environment = Environment.new()
	env.environment.background_mode = Environment.BG_COLOR
	env.environment.background_color = Color(0.36, 0.38, 0.42)
	env.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.environment.ambient_light_color = Color(0.55, 0.55, 0.6)
	vp.add_child(env)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-35, 30, 0)
	vp.add_child(sun)
	var cam := Camera3D.new()
	cam.fov = 22.0
	vp.add_child(cam)
	for r: int in anims.size():
		var model: Node3D = def.model_scene.instantiate()
		ModelUtil.prepare(model)
		vp.add_child(model)
		var sk: Skeleton3D = model.find_children("*", "Skeleton3D", true, false)[0]
		var ap: AnimationPlayer = model.find_child("AnimationPlayer", true, false)
		if anims[r] != "REST" and ap != null:
			var name: StringName = StringName("%s_%s" % [fid.to_upper(), anims[r]])
			ap.play(name)
			ap.seek(frame / 60.0, true)
			ap.pause()
		else:
			sk.reset_bone_poses()
		await process_frame
		var head: Vector3 = (sk.global_transform * sk.get_bone_global_pose(sk.find_bone("Head"))).origin + Vector3(0, 0.09, 0)
		for c: int in yaws.size():
			var yaw: float = deg_to_rad(yaws[c])
			cam.position = head + Vector3(sin(yaw), 0.02, cos(yaw)) * 1.1
			cam.look_at(head, Vector3.UP)
			await process_frame
			await process_frame
			img.blit_rect(vp.get_texture().get_image(), Rect2i(0, 0, cell, cell), Vector2i(c * cell, r * cell))
		model.queue_free()
	img.save_png(out)
	quit()
