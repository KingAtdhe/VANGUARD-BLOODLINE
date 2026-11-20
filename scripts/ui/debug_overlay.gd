class_name DebugOverlay
extends CanvasLayer
## Development overlay for the greybox combat scene.
## F3 (debug_toggle_overlay) shows/hides the text panel.
##
## Touch gameplay controls live in TouchControls (Milestone 4); this overlay
## only shows debug text and the Hitboxes / Dummy toggles.

signal dummy_cycle_requested
signal hitboxes_toggle_requested

@onready var _info: Label = %InfoLabel
@onready var _log: Label = %LogLabel
@onready var _panel: Control = %InfoPanel
@onready var _dummy_button: Button = %DummyButton
@onready var _hitbox_button: Button = %HitboxButton


func _ready() -> void:
	_dummy_button.pressed.connect(func() -> void: dummy_cycle_requested.emit())
	_hitbox_button.pressed.connect(func() -> void: hitboxes_toggle_requested.emit())
	for b: Button in [_dummy_button, _hitbox_button]:
		b.theme = UiTheme.get_theme()
		b.add_theme_font_size_override("font_size", 30)
		b.alignment = HORIZONTAL_ALIGNMENT_CENTER
	_panel.theme = UiTheme.get_theme()


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed(InputActions.DEBUG_TOGGLE_OVERLAY):
		_panel.visible = not _panel.visible


func set_text(text: String, log_text: String) -> void:
	if _panel.visible:
		_info.text = text
		_log.text = log_text


func set_dummy_mode(mode_name: String) -> void:
	_dummy_button.text = "P2: %s" % mode_name


## The Hitboxes / P2 buttons are training tools; hidden in other modes.
func set_tools_visible(value: bool) -> void:
	_dummy_button.visible = value
	_hitbox_button.visible = value


func set_panel_visible(value: bool) -> void:
	_panel.visible = value
