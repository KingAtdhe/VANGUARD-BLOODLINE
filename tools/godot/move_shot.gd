extends SceneTree
## Contact sheets for checking a fighter's attack animations by eye: one PNG
## per move, columns = frames of the move (start, wind-up, first and last
## active frame, recovery, end), rows = camera angles (the game's side view,
## three-quarter front, straight from the front). The move's hitbox is drawn
## as a red box where the simulation tests it (a projectile move: where the
## projectile appears), so a strike that misses its box is obvious.
##
##   xvfb-run -a godot --path . --rendering-driver opengl3 --script res://tools/godot/move_shot.gd \
##         -- <fighter_id> <out_dir> [cell_px] [move id filter] [frames, e.g. 9,14,18,22]
## Needs a display (xvfb-run on a headless machine).

const VIEWS: Array = [
	["side (game camera)", Vector3(0.3, 1.0, 3.9)],
	["three-quarter", Vector3(2.9, 1.3, 2.7)],
	["front", Vector3(3.9, 1.05, 0.0)],
]


func _initialize() -> void:
	var a: PackedStringArray = OS.get_cmdline_user_args()
	var fighter: String = a[0] if a.size() > 0 else "kairo"
	var out_dir: String = a[1] if a.size() > 1 else "/tmp/move_shots"
	var cell: int = int(a[2]) if a.size() > 2 else 300
	var only: String = a[3] if a.size() > 3 else ""
	var custom: PackedStringArray = a[4].split(",") if a.size() > 4 else PackedStringArray()
	DirAccess.make_dir_recursive_absolute(out_dir)
	root.size = Vector2i(cell, cell)

	var def: FighterDefinition = load("res://data/fighters/%s.tres" % fighter)
	var world := Node3D.new()
	root.add_child(world)
	var env := WorldEnvironment.new()
	env.environment = Environment.new()
	env.environment.background_mode = Environment.BG_COLOR
	env.environment.background_color = Color(0.36, 0.38, 0.42)
	env.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.environment.ambient_light_color = Color(1, 1, 1)
	env.environment.ambient_light_energy = 0.75
	world.add_child(env)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-45, 35, 0)
	world.add_child(sun)
	var floor_mesh := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(6, 3)
	floor_mesh.mesh = plane
	var floor_mat := StandardMaterial3D.new()
	floor_mat.albedo_color = Color(0.22, 0.23, 0.26)
	floor_mesh.material_override = floor_mat
	world.add_child(floor_mesh)

	var model: Node3D = def.model_scene.instantiate()
	ModelUtil.prepare(model)
	model.rotation.y = deg_to_rad(90.0)       # faces +X, like P1 in a match
	world.add_child(model)
	var ap: AnimationPlayer = model.find_child("AnimationPlayer", true, false)

	var box := MeshInstance3D.new()
	box.mesh = BoxMesh.new()
	var box_mat := StandardMaterial3D.new()
	box_mat.albedo_color = Color(1, 0.1, 0.1, 0.3)
	box_mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	box_mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	box_mat.cull_mode = BaseMaterial3D.CULL_DISABLED
	box.material_override = box_mat
	world.add_child(box)

	var cam := Camera3D.new()
	cam.fov = 32.0
	world.add_child(cam)
	cam.make_current()

	await process_frame
	for m: MoveData in def.moves:
		if m.activates_surge or (only != "" and not String(m.id).contains(only)):
			continue
		var anim: StringName = def.resolve_anim(m.animation)
		if not ap.has_animation(anim):
			print("MISSING ", anim)
			continue
		var first: int = m.startup_frames
		var last: int = m.startup_frames + m.active_frames - 1
		if m.is_counter():
			first = m.counter_start_frame
			last = m.counter_end_frame
		var total: int = m.total_frames()
		var frames: Array[int] = [1, maxi(2, first - 3), first, last, mini(total, last + maxi(2, (total - last) / 2)), total]
		if not custom.is_empty():
			frames.clear()
			for c: String in custom:
				frames.append(clampi(int(c), 1, total))
		box.scale = Vector3(m.hitbox_size.x, m.hitbox_size.y, 0.5)
		box.position = Vector3(m.hitbox_center.x, m.hitbox_center.y, 0.0)
		var sheet := Image.create(cell * frames.size(), cell * VIEWS.size(), false, Image.FORMAT_RGBA8)
		ap.play(anim)
		ap.pause()
		for col: int in frames.size():
			# frame N of a move is shown from tick N-1 to N; sample its end pose
			ap.seek(float(frames[col] - 1) / CombatConstants.TICK_RATE, true)
			box.visible = not m.is_counter() and not m.no_hitbox and frames[col] >= first and frames[col] <= last
			for row: int in VIEWS.size():
				cam.position = VIEWS[row][1]
				cam.look_at(Vector3(0.3, 0.95, 0.0))
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
		var path: String = out_dir.path_join("%s%s.png" % [m.id, "" if custom.is_empty() else "_frames"])
		sheet.save_png(path)
		print("saved %s  frames %s (active %d-%d of %d)" % [path, frames, first, last, total])
	quit()
