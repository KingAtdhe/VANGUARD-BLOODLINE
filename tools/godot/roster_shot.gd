extends SceneTree
## Renders the playable roster standing in an arena, each in its idle loop,
## as the game prepares them (ModelUtil.prepare).
##   godot --path . --rendering-method mobile --script res://tools/godot/roster_shot.gd \
##         -- <arena.tscn> <out.png> [width] [height] [anim_suffix]
## Needs a display (use xvfb-run on a headless machine).

func _initialize() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	var arena_path: String = args[0] if args.size() > 0 else "res://scenes/arenas/ascendant_arena.tscn"
	var out: String = args[1] if args.size() > 1 else "/tmp/roster_shot.png"
	var w: int = int(args[2]) if args.size() > 2 else 1600
	var h: int = int(args[3]) if args.size() > 3 else 720
	var suffix: String = args[4] if args.size() > 4 else "IDLE_A"
	root.size = Vector2i(w, h)
	root.add_child((load(arena_path) as PackedScene).instantiate())
	var ids: Array[StringName] = Catalog.ROSTER
	for i: int in ids.size():
		var def: FighterDefinition = Catalog.fighter(ids[i])
		if def == null or def.model_scene == null:
			continue
		var f: Node3D = def.model_scene.instantiate()
		ModelUtil.prepare(f)
		f.position = Vector3(-3.75 + 1.5 * i, 0, 0)
		f.rotation.y = deg_to_rad(25.0 if i < ids.size() / 2 else -25.0)
		root.add_child(f)
		var ap: AnimationPlayer = f.find_child("AnimationPlayer", true, false)
		var anim: String = "%s_%s" % [String(ids[i]).to_upper(), suffix]
		if ap != null and ap.has_animation(anim):
			ap.play(anim)
			ap.seek(0.35 * ap.get_animation(anim).length, true)
			ap.pause()
	var cam := Camera3D.new()
	cam.fov = 34.0
	cam.position = Vector3(0, 1.25, 10.5)
	cam.rotation_degrees = Vector3(-3, 0, 0)
	root.add_child(cam)
	cam.make_current()
	for _f: int in 40:
		await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(out)
	print("saved ", out)
	quit()
