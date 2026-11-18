extends RefCounted
## Milestone 7: save/load. Progress and settings persist across an app
## restart (simulated by dropping the in-memory copy and re-reading the
## file); bad data never crashes the game or leaks into it.


func _write(text: String) -> void:
	var f: FileAccess = FileAccess.open(SaveManager.path, FileAccess.WRITE)
	f.store_string(text)
	f.close()


func _restart() -> void:
	SaveManager.unload()
	SaveManager.load_save()


func test_new_save_has_defaults_and_persists_after_restart() -> Array[String]:
	var f: Array[String] = []
	SaveManager.load_save()
	if SaveManager.setting("left_handed") != false or int(SaveManager.setting("ai_difficulty")) != 1:
		f.append("fresh save does not have the default settings")
	SaveManager.set_setting("left_handed", true)
	SaveManager.set_setting("controls_scale", 1.2)
	SaveManager.section("progress")["story_cleared"] = 3
	SaveManager.section("profile")["currency"] = 450
	SaveManager.section("mastery")["kairo"] = 1234
	SaveManager.save()
	_restart()
	if SaveManager.setting("left_handed") != true or absf(float(SaveManager.setting("controls_scale")) - 1.2) > 0.001:
		f.append("settings did not survive a restart")
	if int(SaveManager.section("progress")["story_cleared"]) != 3 or int(SaveManager.section("profile")["currency"]) != 450:
		f.append("progress/currency did not survive a restart")
	if int(SaveManager.section("mastery").get("kairo", 0)) != 1234:
		f.append("mastery did not survive a restart")
	if FileAccess.file_exists(SaveManager.path + ".tmp"):
		f.append("atomic write left its temp file behind")
	return f


func test_corrupt_file_falls_back_and_is_kept() -> Array[String]:
	var f: Array[String] = []
	_write("{ this is not json")
	_restart()
	if SaveManager.last_load_issue == "":
		f.append("corruption was not reported")
	if SaveManager.setting("cinematics") != true:
		f.append("corrupt save did not fall back to defaults")
	if not FileAccess.file_exists(SaveManager.path.get_basename() + ".corrupt.json"):
		f.append("the corrupt file was not kept for support")
	var reread: Variant = JSON.parse_string(FileAccess.get_file_as_string(SaveManager.path))
	if typeof(reread) != TYPE_DICTIONARY:
		f.append("a clean save was not rewritten after recovery")
	return f


func test_bad_values_are_sanitized_per_field() -> Array[String]:
	var f: Array[String] = []
	_write(JSON.stringify({
		"version": 1,
		"settings": {"left_handed": "yes", "controls_scale": 9.0, "master_volume": -3, "ai_difficulty": 7,
			"sfx_volume": 0.25, "evil_key": 1},
		"progress": {"story_cleared": 99, "unlocked_arenas": ["neon", 5, "neon"]},
		"profile": "oops",
		"mastery": {"kairo": 10, "x": "bad"},
	}))
	_restart()
	var s: Dictionary = SaveManager.section("settings")
	if s["left_handed"] != false:
		f.append("wrong-typed bool not reset")
	if float(s["controls_scale"]) > 1.4 or float(s["master_volume"]) < 0.0 or int(s["ai_difficulty"]) > 2:
		f.append("out-of-range values not clamped: %s" % s)
	if absf(float(s["sfx_volume"]) - 0.25) > 0.001:
		f.append("a valid value was lost while sanitising")
	if s.has("evil_key"):
		f.append("unknown keys were kept")
	if int(SaveManager.section("progress")["story_cleared"]) != 6:
		f.append("story_cleared not clamped to 6")
	if SaveManager.section("progress")["unlocked_arenas"] != ["neon"]:
		f.append("array not cleaned: %s" % SaveManager.section("progress")["unlocked_arenas"])
	if typeof(SaveManager.section("profile")) != TYPE_DICTIONARY or int(SaveManager.section("profile")["currency"]) != 0:
		f.append("a wrong-typed section was not replaced by defaults")
	if SaveManager.section("mastery") != {"kairo": 10}:
		f.append("mastery map not cleaned: %s" % SaveManager.section("mastery"))
	return f


func test_migration_from_unversioned_layout() -> Array[String]:
	var f: Array[String] = []
	_write(JSON.stringify({"left_handed": true, "sfx_volume": 0.4}))
	_restart()
	if SaveManager.setting("left_handed") != true or absf(float(SaveManager.setting("sfx_volume")) - 0.4) > 0.001:
		f.append("v0 top-level settings were not migrated")
	if int(SaveManager.data["version"]) != SaveManager.VERSION:
		f.append("version not updated after migration")
	return f


func test_reset_all() -> Array[String]:
	var f: Array[String] = []
	SaveManager.load_save()
	SaveManager.section("profile")["currency"] = 99
	SaveManager.set_setting("reduced_shake", true)
	SaveManager.reset_all()
	_restart()
	if int(SaveManager.section("profile")["currency"]) != 0 or SaveManager.setting("reduced_shake") != false:
		f.append("reset_all did not erase progress and settings")
	return f


func test_unknown_setting_is_rejected() -> Array[String]:
	SaveManager.load_save()
	SaveManager.set_setting("not_a_setting", 5)  # push_error only, no crash
	return [] if not SaveManager.section("settings").has("not_a_setting") else ["unknown setting stored"]
