extends SceneTree
## Contact sheet of any animations of a fighter (reactions, idle, walks...):
## one row pair per animation (side view as the game shows it, three-quarter),
## columns = evenly spaced frames. For attacks use move_shot.gd, which also
## draws the hitbox.
##
##   xvfb-run -a godot --path . --rendering-driver opengl3 --script res://tools/godot/anim_shot.gd \
##         -- <fighter_id> <out.png> <SUFFIX,SUFFIX,...> [columns] [cell_px]
## e.g. ... -- kairo /tmp/reactions.png HIT_LIGHT,HIT_BODY,HIT_LOW 6

const VIEWS: Array = [
	["side (game camera)", Vector3(0.3, 1.0, 3.9)],
	["three-quarter", Vector3(2.9, 1.3, 2.7)],
]



func _initialize() -> void:
	var a: PackedStringArray = OS.get_cmdline_user_args()
	var fighter: String = a[0]
	var out: String = a[1]
	var names: PackedStringArray = a[2].split(",")
	var cols: int = int(a[3]) if a.size() > 3 else 6
	var cell: int = int(a[4]) if a.size() > 4 else 300
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
	plane.size = Vector2(6, 3)
	floor_mesh.mesh = plane
	var floor_mat := StandardMaterial3D.new()
	floor_mat.albedo_color = Color(0.22, 0.23, 0.26)
	floor_mesh.material_override = floor_mat
	root.add_child(floor_mesh)
	var model: Node3D = def.model_scene.instantiate()
	ModelUtil.prepare(model)
	model.rotation.y = deg_to_rad(90.0)
	root.add_child(model)
	var ap: AnimationPlayer = model.find_child("AnimationPlayer", true, false)
	var cam := Camera3D.new()
	cam.fov = 32.0
	root.add_child(cam)
	cam.make_current()
	await process_frame
	var sheet := Image.create(cell * cols, cell * VIEWS.size() * names.size(), false, Image.FORMAT_RGBA8)
	for n: int in names.size():
		var anim: StringName = StringName("%s_%s" % [String(def.anim_prefix if def.anim_prefix != &"" else &"KAIRO"), names[n]])
		if not ap.has_animation(anim):
			print("MISSING ", anim)
			continue
		ap.play(anim)
		ap.pause()
		var length: float = ap.get_animation(anim).length
		for col: int in cols:
			ap.seek(length * col / float(maxi(1, cols - 1)), true)
			for row: int in VIEWS.size():
				cam.position = VIEWS[row][1]
				cam.look_at(Vector3(0.3, 0.95, 0.0))
				for _f: int in 3:
					await process_frame
				await RenderingServer.frame_post_draw
				var shot: Image = root.get_texture().get_image()
				shot.convert(Image.FORMAT_RGBA8)
				var side: int = mini(shot.get_width(), shot.get_height())
				shot = shot.get_region(Rect2i((shot.get_width() - side) / 2, (shot.get_height() - side) / 2, side, side))
				shot.resize(cell, cell, Image.INTERPOLATE_LANCZOS)
				sheet.blit_rect(shot, Rect2i(0, 0, cell, cell), Vector2i(col * cell, (n * VIEWS.size() + row) * cell))
		print("%s: %.0f frames" % [anim, length * CombatConstants.TICK_RATE + 1.0])
	sheet.save_png(out)
	print("saved ", out)
	quit()
