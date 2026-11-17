extends Control
## Main menu placeholder (Milestone 0). Gameplay entries are present but
## disabled until their milestone is approved and implemented.

@onready var _fight_button: Button = %FightButton
@onready var _training_button: Button = %TrainingButton
@onready var _settings_button: Button = %SettingsButton
@onready var _quit_button: Button = %QuitButton
@onready var _info_label: Label = %InfoLabel


func _ready() -> void:
	# Not implemented yet — kept visible so the layout can be judged on device.
	_fight_button.disabled = true
	_training_button.disabled = true
	_settings_button.disabled = true
	_quit_button.pressed.connect(_on_quit_pressed)
	_quit_button.grab_focus()
	get_viewport().size_changed.connect(_refresh_info)
	_refresh_info()


func _refresh_info() -> void:
	var vp: Vector2 = get_viewport_rect().size
	_info_label.text = "v%s  |  Godot %s  |  renderer: %s  |  viewport %dx%d  |  %s" % [
		AppInfo.game_version(), AppInfo.running_godot_version(),
		AppInfo.renderer_name(), int(vp.x), int(vp.y), OS.get_name()]


func _on_quit_pressed() -> void:
	get_tree().quit()
