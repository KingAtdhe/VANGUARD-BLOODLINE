extends Control
## Boot screen: shows the build label, checks the engine version against the
## pinned version, then routes to the main menu.

## Seconds the boot screen stays visible. Tap/click/any key skips it.
@export var hold_seconds: float = 1.0

@onready var _status_label: Label = %StatusLabel

var _left: bool = false


func _ready() -> void:
	var engine_note: String = ""
	if not AppInfo.is_pinned_engine():
		engine_note = "  [WARNING: engine %s, pinned %s]" % [
			AppInfo.running_godot_version(), AppInfo.PINNED_GODOT_VERSION]
		push_warning("Running Godot %s but project is pinned to %s" % [
			AppInfo.running_godot_version(), AppInfo.PINNED_GODOT_VERSION])
	_status_label.text = "%s  •  v%s%s" % [AppInfo.BUILD_LABEL, AppInfo.game_version(), engine_note]
	print("[Boot] %s v%s | Godot %s | renderer=%s" % [
		AppInfo.GAME_TITLE, AppInfo.game_version(),
		AppInfo.running_godot_version(), AppInfo.renderer_name()])
	get_tree().create_timer(hold_seconds).timeout.connect(_leave)


func _unhandled_input(event: InputEvent) -> void:
	if event.is_pressed() and not event.is_echo():
		_leave()


func _leave() -> void:
	if _left:
		return
	_left = true
	SceneRouter.goto(ScenePaths.MAIN_MENU)
