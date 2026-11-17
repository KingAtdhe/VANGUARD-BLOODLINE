extends RefCounted
## Milestone 0 acceptance checks for project configuration.

const ORIENTATION_SENSOR_LANDSCAPE: int = 4


func test_main_scene_is_boot() -> Array[String]:
	var f: Array[String] = []
	var main: String = ProjectSettings.get_setting("application/run/main_scene", "")
	if main != ScenePaths.BOOT:
		f.append("main_scene is '%s', expected '%s'" % [main, ScenePaths.BOOT])
	return f


func test_landscape_orientation() -> Array[String]:
	var f: Array[String] = []
	var o: int = ProjectSettings.get_setting("display/window/handheld/orientation", -1)
	if o != ORIENTATION_SENSOR_LANDSCAPE:
		f.append("handheld orientation is %d, expected %d (sensor landscape)" % [o, ORIENTATION_SENSOR_LANDSCAPE])
	var w: int = ProjectSettings.get_setting("display/window/size/viewport_width", 0)
	var h: int = ProjectSettings.get_setting("display/window/size/viewport_height", 0)
	if w <= h:
		f.append("viewport %dx%d is not landscape" % [w, h])
	return f


func test_mobile_renderer() -> Array[String]:
	var f: Array[String] = []
	for key: String in ["rendering/renderer/rendering_method", "rendering/renderer/rendering_method.mobile"]:
		var v: String = ProjectSettings.get_setting(key, "")
		if v != "mobile":
			f.append("%s is '%s', expected 'mobile'" % [key, v])
	return f


func test_input_actions_exist_and_bound() -> Array[String]:
	var f: Array[String] = []
	for action: StringName in InputActions.ALL:
		var key: String = "input/" + String(action)
		if not ProjectSettings.has_setting(key):
			f.append("missing input action '%s'" % action)
			continue
		var def: Dictionary = ProjectSettings.get_setting(key)
		var events: Array = def.get("events", [])
		if events.is_empty():
			f.append("input action '%s' has no bindings" % action)
	return f


func test_routable_scenes_load_and_instantiate() -> Array[String]:
	var f: Array[String] = []
	for path: String in ScenePaths.ALL:
		var packed: PackedScene = load(path) as PackedScene
		if packed == null:
			f.append("cannot load %s" % path)
			continue
		var node: Node = packed.instantiate()
		if node == null:
			f.append("cannot instantiate %s" % path)
		else:
			node.free()
	return f


func test_pinned_engine_version() -> Array[String]:
	var f: Array[String] = []
	if not AppInfo.is_pinned_engine():
		f.append("running Godot %s, project pinned to %s" % [AppInfo.running_godot_version(), AppInfo.PINNED_GODOT_VERSION])
	return f
