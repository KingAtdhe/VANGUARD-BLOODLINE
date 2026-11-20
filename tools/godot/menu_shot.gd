extends SceneTree
## Screenshot of a menu screen as the game shows it (autoloads, theme,
## live backdrop). Phone landscape aspect by default.
##   xvfb-run -a godot --path . --rendering-method mobile --script res://tools/godot/menu_shot.gd \
##         -- <scene.tscn> <out.png> [width] [height] [frames]

func _initialize() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	var scene: String = args[0]
	var out: String = args[1]
	var w: int = int(args[2]) if args.size() > 2 else 1600
	var h: int = int(args[3]) if args.size() > 3 else 720
	var frames: int = int(args[4]) if args.size() > 4 else 60
	root.size = Vector2i(w, h)
	root.content_scale_size = Vector2i(2400, 1080)
	await process_frame
	change_scene_to_file(scene)
	for i: int in frames:
		await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(out)
	print("saved ", out)
	quit()
