class_name AppInfo
extends RefCounted
## Static build/version information.

const GAME_TITLE: String = "VANGUARD: BLOODLINE"
const BUILD_LABEL: String = "Prototype — Milestone 3"

## Engine version this project is pinned to. Must match README.md.
const PINNED_GODOT_VERSION: String = "4.7.2"


static func game_version() -> String:
	return str(ProjectSettings.get_setting("application/config/version", "0.0.0"))


## Returns "major.minor.patch" of the running engine.
static func running_godot_version() -> String:
	var info: Dictionary = Engine.get_version_info()
	return "%d.%d.%d" % [info.major, info.minor, info.patch]


static func is_pinned_engine() -> bool:
	return running_godot_version() == PINNED_GODOT_VERSION


static func renderer_name() -> String:
	return str(RenderingServer.get_current_rendering_method())
