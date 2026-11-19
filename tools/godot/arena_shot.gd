extends SceneTree
## Renders an arena from the gameplay camera with two fighters for scale.
##   godot --path . --rendering-method mobile --script res://tools/godot/arena_shot.gd \
##         -- <arena.tscn> <out.png> [distance] [width] [height]
## Needs a display (use xvfb-run on a headless machine).

func _initialize() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	var arena_path: String = args[0] if args.size() > 0 else "res://scenes/arenas/neon_district.tscn"
	var out: String = args[1] if args.size() > 1 else "/tmp/arena_shot.png"
	var dist: float = float(args[2]) if args.size() > 2 else 8.0
	var w: int = int(args[3]) if args.size() > 3 else 1280
	var h: int = int(args[4]) if args.size() > 4 else 720
	root.size = Vector2i(w, h)
	var arena: Node3D = (load(arena_path) as PackedScene).instantiate()
	root.add_child(arena)
	for i: int in 2:
		var f: Node3D = (load("res://assets/characters/kairo/kairo.glb") as PackedScene).instantiate()
		f.position = Vector3(-1.5 + 3.0 * i, 0, 0)
		f.rotation.y = PI / 2 if i == 0 else -PI / 2
		root.add_child(f)
	var cam := Camera3D.new()
	cam.fov = 30.0
	cam.position = Vector3(0, 1.5, dist)
	cam.rotation_degrees = Vector3(-5, 0, 0)
	root.add_child(cam)
	cam.make_current()
	for _f: int in 40:
		await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(out)
	print("saved ", out)
	# Free the scene before quitting so render resources are released cleanly.
	arena.queue_free()
	cam.queue_free()
	await process_frame
	await process_frame
	quit()
