extends SceneTree
## Screenshot of a real versus fight (HUD, camera, arena, both fighters).
##   xvfb-run -a godot --path . --rendering-method mobile --script res://tools/godot/fight_shot.gd \
##         -- <out.png> [p1] [p2] [arena] [seconds] [p1_hp_pct] [p2_hp_pct]
## The fight runs for [seconds] with the CPU controlling P2; the health
## values can then be set by percentage to show the bars mid-fight.

func _initialize() -> void:
	var a: PackedStringArray = OS.get_cmdline_user_args()
	var out: String = a[0] if a.size() > 0 else "/tmp/fight_shot.png"
	root.size = Vector2i(1600, 720)
	SaveManager.ensure_loaded()
	var s := MatchSetup.new()
	s.p1_id = StringName(a[1]) if a.size() > 1 else &"kairo"
	s.p2_id = StringName(a[2]) if a.size() > 2 else &"drakon"
	s.arena_id = StringName(a[3]) if a.size() > 3 else &"ascendant"
	ModeFlow.setup = s
	var scene: Node = (load(ScenePaths.COMBAT_GREYBOX) as PackedScene).instantiate()
	root.add_child(scene)
	var secs: float = float(a[4]) if a.size() > 4 else 4.0
	await create_timer(secs).timeout
	if a.size() > 6:
		var sim: CombatSimulation = scene.get("simulation")
		for i: int in 2:
			var pct: float = float(a[5 + i]) / 100.0
			sim.fighters[i].health = int(sim.fighters[i].health * pct)
			sim.fighters[i].meter = int(sim.tuning.meter_max * (0.35 + 0.6 * i))
	for _f: int in 30:
		await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(out)
	print("saved ", out)
	quit()
