extends SceneTree
## Writes one fighter's move timings + hitbox centres to JSON for the Blender
## build script, so animation timing always comes from the real move data.
##
## Run: godot --headless --path . --script res://tools/blender/export_move_timing.gd -- <out.json> [fighter_id]


func _initialize() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	var out_path: String = args[0] if args.size() > 0 else "/tmp/kairo_moves.json"
	# Second argument: fighter id (each fighter's own move set, D-062).
	var fighter: String = args[1] if args.size() > 1 else "kairo"
	var def: FighterDefinition = load("res://data/fighters/%s.tres" % fighter)
	var data: Dictionary = {}
	for m: MoveData in def.moves:
		var entry: Dictionary = {"startup": m.startup_frames, "active": m.active_frames,
			"recovery": m.recovery_frames, "hc": [m.hitbox_center.x, m.hitbox_center.y],
			"animation": String(m.animation), "counter": [m.counter_start_frame, m.counter_end_frame],
			"rehit": m.rehit_interval}
		# Standard slots by input (SURGE = the surge activation), plus every
		# move under its own id without the owner prefix ("body_hook").
		var slot: String = "SURGE" if m.activates_surge else String(m.input_pattern)
		if not data.has(slot):
			data[slot] = entry
		data[String(m.id).substr(String(m.id).find("_") + 1)] = entry
	if def.movement != null:
		data["walk"] = [def.movement.walk_forward_speed, def.movement.walk_backward_speed]
		data["dash"] = [def.movement.dash_forward_ticks, def.movement.dash_back_ticks]
	var f := FileAccess.open(out_path, FileAccess.WRITE)
	f.store_string(JSON.stringify(data, "  "))
	f.close()
	print("wrote %d moves to %s" % [data.size(), out_path])
	quit()
