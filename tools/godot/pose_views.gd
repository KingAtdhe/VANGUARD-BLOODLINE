extends SceneTree
## Pose inspection sheet (D-075): one animation of a fighter seen from every
## side, to judge a stance or a keyed pose by eye. Columns = front,
## three-quarter, side (the game camera), rear three-quarter, top; rows =
## evenly spaced frames of the animation (1 row = its first frame).
##
##   xvfb-run -a godot --path . --rendering-driver opengl3 --script res://tools/godot/pose_views.gd \
##         -- <fighter_id> <out.png> <SUFFIX> [rows] [cell_px] [model.glb]
## e.g. ... -- kairo /tmp/kairo_idle.png IDLE_A 1 520
## [model.glb]: look at a model file that is not installed in the project
## (a quick stance build), instead of the fighter's own scene.
## The fighter faces +X, as P1 does in a match. Needs a display.

const VIEWS: Array = [
	["front", Vector3(4.3, 1.0, 0.0), Vector3.UP],
	["three-quarter", Vector3(3.0, 1.25, 3.0), Vector3.UP],
	["side (game camera)", Vector3(0.0, 1.0, 4.3), Vector3.UP],
	["rear three-quarter", Vector3(-3.0, 1.25, 3.0), Vector3.UP],
	["top", Vector3(0.0, 5.2, 0.001), Vector3(1, 0, 0)],
]


func _initialize() -> void:
	var a: PackedStringArray = OS.get_cmdline_user_args()
	var fighter: String = a[0]
	var out: String = a[1]
	var suffix: String = a[2]
	var rows: int = int(a[3]) if a.size() > 3 else 1
	var cell: int = int(a[4]) if a.size() > 4 else 480
	var file: String = a[5] if a.size() > 5 else ""
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
		ap.seek(length * row / float(maxi(1, rows - 1)) if rows > 1 else 0.0, true)
		for col: int in VIEWS.size():
			cam.position = VIEWS[col][1]
			cam.look_at(Vector3(0.0, 0.92 if col != 4 else 0.0, 0.0), VIEWS[col][2])
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
