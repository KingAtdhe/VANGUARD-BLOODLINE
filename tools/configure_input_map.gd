extends SceneTree
## Regenerates the default input map in project.godot.
##
## Run:  godot --headless --path . --script res://tools/configure_input_map.gd
##
## Keyboard/gamepad bindings exist for editor and desktop testing (spec §2.4).
## Touch controls arrive in Milestone 4 and will emit these same actions.

const DEADZONE: float = 0.2


func _initialize() -> void:
	_set_action(InputActions.MOVE_LEFT, [_key(KEY_A), _key(KEY_LEFT),
		_joy_button(JOY_BUTTON_DPAD_LEFT), _joy_axis(JOY_AXIS_LEFT_X, -1.0)])
	_set_action(InputActions.MOVE_RIGHT, [_key(KEY_D), _key(KEY_RIGHT),
		_joy_button(JOY_BUTTON_DPAD_RIGHT), _joy_axis(JOY_AXIS_LEFT_X, 1.0)])
	_set_action(InputActions.MOVE_UP, [_key(KEY_W), _key(KEY_UP),
		_joy_button(JOY_BUTTON_DPAD_UP), _joy_axis(JOY_AXIS_LEFT_Y, -1.0)])
	_set_action(InputActions.MOVE_DOWN, [_key(KEY_S), _key(KEY_DOWN),
		_joy_button(JOY_BUTTON_DPAD_DOWN), _joy_axis(JOY_AXIS_LEFT_Y, 1.0)])
	_set_action(InputActions.ATTACK_LIGHT, [_key(KEY_J), _joy_button(JOY_BUTTON_X)])
	_set_action(InputActions.ATTACK_HEAVY, [_key(KEY_K), _joy_button(JOY_BUTTON_Y)])
	_set_action(InputActions.ATTACK_KICK, [_key(KEY_L), _joy_button(JOY_BUTTON_A)])
	_set_action(InputActions.BLOCK, [_key(KEY_SPACE), _joy_button(JOY_BUTTON_B)])
	_set_action(InputActions.SPECIAL, [_key(KEY_U), _joy_button(JOY_BUTTON_RIGHT_SHOULDER)])
	_set_action(InputActions.ULTIMATE, [_key(KEY_O), _joy_axis(JOY_AXIS_TRIGGER_RIGHT, 1.0)])
	_set_action(InputActions.PAUSE, [_key(KEY_ESCAPE), _key(KEY_P), _joy_button(JOY_BUTTON_START)])
	_set_action(InputActions.DEBUG_TOGGLE_OVERLAY, [_key(KEY_F3)])

	var err: Error = ProjectSettings.save()
	if err != OK:
		push_error("Failed to save project settings: %d" % err)
		quit(1)
		return
	print("Input map written for %d actions." % InputActions.ALL.size())
	quit(0)


func _set_action(action: StringName, events: Array[InputEvent]) -> void:
	ProjectSettings.set_setting("input/" + String(action), {
		"deadzone": DEADZONE,
		"events": events,
	})


func _key(keycode: Key) -> InputEventKey:
	var e := InputEventKey.new()
	e.device = -1  # any device
	e.physical_keycode = keycode
	return e


func _joy_button(button: JoyButton) -> InputEventJoypadButton:
	var e := InputEventJoypadButton.new()
	e.device = -1  # any device
	e.button_index = button
	return e


func _joy_axis(axis: JoyAxis, value: float) -> InputEventJoypadMotion:
	var e := InputEventJoypadMotion.new()
	e.device = -1  # any device
	e.axis = axis
	e.axis_value = value
	return e
