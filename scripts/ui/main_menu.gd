extends Control
## Main menu placeholder. "Fight" opens the Milestone 1 greybox scene; other
## entries stay disabled until their milestone is approved and implemented.

@onready var _fight_button: Button = %FightButton
@onready var _training_button: Button = %TrainingButton
@onready var _settings_button: Button = %SettingsButton
@onready var _quit_button: Button = %QuitButton
@onready var _info_label: Label = %InfoLabel
@onready var _difficulty_button: Button = %DifficultyButton


func _ready() -> void:
	_difficulty_button.pressed.connect(_on_difficulty_pressed)
	_refresh_difficulty()
	_fight_button.disabled = false
	_fight_button.pressed.connect(_on_fight_pressed)
	_training_button.disabled = false
	_training_button.pressed.connect(func() -> void: SceneRouter.goto(ScenePaths.TRAINING_GREYBOX))
	# Not implemented yet — kept visible so the layout can be judged on device.
	_settings_button.disabled = true
	_quit_button.pressed.connect(_on_quit_pressed)
	_fight_button.grab_focus()
	get_viewport().size_changed.connect(_refresh_info)
	_refresh_info()


func _refresh_info() -> void:
	var vp: Vector2 = get_viewport_rect().size
	_info_label.text = "v%s  |  Godot %s  |  renderer: %s  |  viewport %dx%d  |  %s" % [
		AppInfo.game_version(), AppInfo.running_godot_version(),
		AppInfo.renderer_name(), int(vp.x), int(vp.y), OS.get_name()]


func _on_quit_pressed() -> void:
	get_tree().quit()


func _on_difficulty_pressed() -> void:
	SessionSettings.cycle_ai_difficulty()
	_refresh_difficulty()


func _refresh_difficulty() -> void:
	_difficulty_button.text = "AI: %s" % SessionSettings.AI_DIFFICULTY_NAMES[SessionSettings.ai_difficulty]


func _on_fight_pressed() -> void:
	SceneRouter.goto(ScenePaths.COMBAT_GREYBOX)
