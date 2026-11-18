class_name DebugOverlay
extends CanvasLayer
## Development overlay for the greybox combat scene.
## F3 (debug_toggle_overlay) shows/hides the text panel.
##
## All on-screen buttons labelled DEBUG are TEMPORARY so the prototype can be
## tried on a phone before real touch controls arrive in Milestone 4. They
## press the same logical actions as the keyboard, so no combat logic lives here.

signal back_requested
signal reset_requested
signal dummy_cycle_requested
signal hitboxes_toggle_requested

@onready var _info: Label = %InfoLabel
@onready var _log: Label = %LogLabel
@onready var _panel: Control = %InfoPanel
@onready var _back_button: Button = %BackButton
@onready var _reset_button: Button = %ResetButton
@onready var _dummy_button: Button = %DummyButton
@onready var _hitbox_button: Button = %HitboxButton


func _ready() -> void:
	_bind_hold(%DebugLeftButton, InputActions.MOVE_LEFT)
	_bind_hold(%DebugRightButton, InputActions.MOVE_RIGHT)
	_bind_hold(%DebugLightButton, InputActions.ATTACK_LIGHT)
	_bind_hold(%DebugHeavyButton, InputActions.ATTACK_HEAVY)
	_bind_hold(%DebugKickButton, InputActions.ATTACK_KICK)
	_bind_hold(%DebugBlockButton, InputActions.BLOCK)
	_back_button.pressed.connect(func() -> void: back_requested.emit())
	_reset_button.pressed.connect(func() -> void: reset_requested.emit())
	_dummy_button.pressed.connect(func() -> void: dummy_cycle_requested.emit())
	_hitbox_button.pressed.connect(func() -> void: hitboxes_toggle_requested.emit())


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed(InputActions.DEBUG_TOGGLE_OVERLAY):
		_panel.visible = not _panel.visible


func set_text(text: String, log_text: String) -> void:
	if _panel.visible:
		_info.text = text
		_log.text = log_text


func set_dummy_mode(mode_name: String) -> void:
	_dummy_button.text = "Dummy: %s" % mode_name


func _bind_hold(button: Button, action: StringName) -> void:
	# button_down fires on touch-down (spec §2.4), release on lift.
	button.button_down.connect(func() -> void: Input.action_press(action))
	button.button_up.connect(func() -> void: Input.action_release(action))
	button.tree_exiting.connect(func() -> void: Input.action_release(action))
