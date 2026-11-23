extends SceneTree
## Hand close-up (D-091): one hand of a fighter on one frame of an animation,
## seen from five sides at arm's length, to judge how a fist closes.
##
##   xvfb-run -a godot --path . --rendering-driver opengl3 --script res://tools/godot/hand_shot.gd \
##         -- <fighter_id> <out.png> <SUFFIX> <frame> <Left|Right> [cell_px] [model.glb]
## The fighter faces +X, as P1 does in a match. Needs a display.

const VIEWS: Array = [
	["front", Vector3(0.75, 0.05, 0.0), Vector3.UP],
	["side (game camera)", Vector3(0.0, 0.05, 0.75), Vector3.UP],
	["far side", Vector3(0.0, 0.05, -0.75), Vector3.UP],
	["below", Vector3(0.05, -0.75, 0.1), Vector3(1, 0, 0)],
	["top", Vector3(0.05, 0.75, 0.1), Vector3(1, 0, 0)],
]


func _initialize() -> void:
	var a: PackedStringArray = OS.get_cmdline_user_args()
	var fighter: String = a[0]
	var out: String = a[1]
	var suffix: String = a[2]
	var frame: int = int(a[3])
	var hand: String = a[4] + "Hand"
	var rows: int = 1
	var cell: int = int(a[5]) if a.size() > 5 else 480
	var file: String = a[6] if a.size() > 6 else ""
	root.size = Vector2i(cell, cell)
	var def: FighterDefinition = load("res://data/fighters/%s.tres" % fighter)
	var env := WorldEnvironment.new()
	env.environment = Environment.new()
	env.environment.background_mode = Environment.BG_COLOR
	env.environment.background_color = Color(0.36, 0.38, 0.42)
	env.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.environment.ambient_light_color = Color(1, 1, 1)
	env.environment.ambient_light_energy = 0.75
	root.add_child(env)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-45, 35, 0)
	root.add_child(sun)
	var floor_mesh := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(4, 4)
	floor_mesh.mesh = plane
	var floor_mat := StandardMaterial3D.new()
	floor_mat.albedo_color = Color(0.22, 0.23, 0.26)
	floor_mesh.material_override = floor_mat
	root.add_child(floor_mesh)
	var model: Node3D
	if file != "":
		var doc := GLTFDocument.new()
		var state := GLTFState.new()
		if doc.append_from_file(file, state) != OK:
			push_error("cannot read %s" % file)
			quit(1)
			return
		model = doc.generate_scene(state)
	else:
		model = def.model_scene.instantiate()
		ModelUtil.prepare(model)
	model.rotation.y = deg_to_rad(90.0)       # faces +X, like P1 in a match
	root.add_child(model)
	var ap: AnimationPlayer = model.find_child("AnimationPlayer", true, false)
	var cam := Camera3D.new()
	cam.fov = 30.0
	root.add_child(cam)
	cam.make_current()
	await process_frame
	var anim: StringName = StringName("%s_%s" % [fighter.to_upper(), suffix])
	if ap == null or not ap.has_animation(anim):
		push_error("MISSING %s" % anim)
		quit(1)
		return
	ap.play(anim)
	ap.pause()
	var length: float = ap.get_animation(anim).length
	var sheet := Image.create(cell * VIEWS.size(), cell * rows, false, Image.FORMAT_RGBA8)
	for row: int in rows:
		ap.seek(minf(length, (frame - 1) / 60.0), true)
		var sk: Skeleton3D = model.find_children("*", "Skeleton3D", true, false)[0]
		var hb: int = sk.find_bone(hand)
		var g: Transform3D = sk.global_transform * sk.get_bone_global_pose(hb)
		var centre: Vector3 = g.origin + g.basis.y.normalized() * 0.06
		for col: int in VIEWS.size():
			cam.position = centre + VIEWS[col][1]
			cam.look_at(centre, VIEWS[col][2])
			for _f: int in 3:
				await process_frame
			await RenderingServer.frame_post_draw
			var shot: Image = root.get_texture().get_image()
			shot.convert(Image.FORMAT_RGBA8)
			# the window may not take the requested size: use its central square
			var side: int = mini(shot.get_width(), shot.get_height())
			shot = shot.get_region(Rect2i((shot.get_width() - side) / 2, (shot.get_height() - side) / 2, side, side))
			shot.resize(cell, cell, Image.INTERPOLATE_LANCZOS)
			sheet.blit_rect(shot, Rect2i(0, 0, cell, cell), Vector2i(col * cell, row * cell))
	sheet.save_png(out)
	print("saved ", out)
	quit()
