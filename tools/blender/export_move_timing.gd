extends SceneTree
## Writes Kairo's move timings + hitbox centres to JSON for the Blender
## build script, so animation timing always comes from the real move data.
##
## Run: godot --headless --path . --script res://tools/blender/export_move_timing.gd -- <out.json>

const KEYS: Dictionary = {
	&"kairo_light_punch": "LIGHT", &"kairo_heavy_punch": "HEAVY", &"kairo_kick": "KICK",
	&"kairo_origin_palm": "SPECIAL", &"kairo_rift_break": "FORWARD_SPECIAL",
	&"kairo_origin_surge": "SURGE", &"kairo_origin_break": "ULTIMATE",
}


func _initialize() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	var out_path: String = args[0] if args.size() > 0 else "/tmp/kairo_moves.json"
	var def: FighterDefinition = load("res://data/fighters/kairo.tres")
	var data: Dictionary = {}
	for m: MoveData in def.moves:
		if KEYS.has(m.id):
			data[KEYS[m.id]] = {"startup": m.startup_frames, "active": m.active_frames,
				"recovery": m.recovery_frames, "hc": [m.hitbox_center.x, m.hitbox_center.y],
				"animation": String(m.animation)}
	var f := FileAccess.open(out_path, FileAccess.WRITE)
	f.store_string(JSON.stringify(data, "  "))
	f.close()
	print("wrote %d moves to %s" % [data.size(), out_path])
	quit()
