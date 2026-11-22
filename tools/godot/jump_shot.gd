extends SceneTree
## Screenshots of a real fight scene while P1 jumps (camera framing check, D-089).
##   xvfb-run -a godot --path . --rendering-method mobile --script res://tools/godot/jump_shot.gd \
##         -- <out_prefix> [p1] [p2] [arena]
## Writes <out_prefix>_0.png .. _3.png: before the jump, rising, apex, falling.

func _initialize() -> void:
	var a: PackedStringArray = OS.get_cmdline_user_args()
	var out: String = a[0] if a.size() > 0 else "/tmp/jump_shot"
	root.size = Vector2i(1600, 720)
	SaveManager.ensure_loaded()
	var s := MatchSetup.new()
	s.p1_id = StringName(a[1]) if a.size() > 1 else &"kairo"
	s.p2_id = StringName(a[2]) if a.size() > 2 else &"training_dummy"
	s.arena_id = StringName(a[3]) if a.size() > 3 else &"ascendant"
	s.mode = MatchSetup.Mode.TRAINING
	s.rules_path = MatchSetup.RULES_TRAINING
	ModeFlow.setup = s
	var scene: Node = (load(ScenePaths.COMBAT_GREYBOX) as PackedScene).instantiate()
	root.add_child(scene)
	await create_timer(2.5).timeout
	await _shot(out + "_0.png")
	Input.action_press(InputActions.MOVE_UP)
	await create_timer(0.18).timeout
	Input.action_release(InputActions.MOVE_UP)
	await _shot(out + "_1.png")
	await create_timer(0.18).timeout
	await _shot(out + "_2.png")
	await create_timer(0.2).timeout
	await _shot(out + "_3.png")
	quit()


func _shot(path: String) -> void:
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(path)
	print("saved ", path)
