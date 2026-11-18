class_name DebugOverlay
extends CanvasLayer
## Development overlay for the greybox combat scene.
## F3 (debug_toggle_overlay) shows/hides the text panel.
##
## The on-screen ◀ ▶ buttons are TEMPORARY debug controls so movement can be
## tried on a phone before real touch controls arrive in Milestone 4. They
## press the same logical actions as the keyboard, so no combat logic lives here.

signal back_requested

@onready var _info: Label = %InfoLabel
@onready var _panel: Control = %InfoPanel
@onready var _left_button: Button = %DebugLeftButton
@onready var _right_button: Button = %DebugRightButton
@onready var _back_button: Button = %BackButton


func _ready() -> void:
	_bind_hold(_left_button, InputActions.MOVE_LEFT)
	_bind_hold(_right_button, InputActions.MOVE_RIGHT)
	_back_button.pressed.connect(func() -> void: back_requested.emit())


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed(InputActions.DEBUG_TOGGLE_OVERLAY):
		_panel.visible = not _panel.visible


func set_text(text: String) -> void:
	if _panel.visible:
		_info.text = text


func _bind_hold(button: Button, action: StringName) -> void:
	# button_down fires on touch-down (spec §2.4), release on lift.
	button.button_down.connect(func() -> void: Input.action_press(action))
	button.button_up.connect(func() -> void: Input.action_release(action))
	button.tree_exiting.connect(func() -> void: Input.action_release(action))
