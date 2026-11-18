class_name LocalInputReader
extends RefCounted
## Samples the local device's logical actions into a FighterInputFrame.
## Pressing both directions at once cancels out (neutral).


static func read() -> FighterInputFrame:
	var frame := FighterInputFrame.new()
	var left: bool = Input.is_action_pressed(InputActions.MOVE_LEFT)
	var right: bool = Input.is_action_pressed(InputActions.MOVE_RIGHT)
	frame.move_x = int(right) - int(left)
	if Input.is_action_pressed(InputActions.ATTACK_LIGHT):
		frame.buttons |= FighterInputFrame.BUTTON_LIGHT
	if Input.is_action_pressed(InputActions.ATTACK_HEAVY):
		frame.buttons |= FighterInputFrame.BUTTON_HEAVY
	if Input.is_action_pressed(InputActions.ATTACK_KICK):
		frame.buttons |= FighterInputFrame.BUTTON_KICK
	if Input.is_action_pressed(InputActions.BLOCK):
		frame.buttons |= FighterInputFrame.BUTTON_BLOCK
	if Input.is_action_pressed(InputActions.SPECIAL):
		frame.buttons |= FighterInputFrame.BUTTON_SPECIAL
	if Input.is_action_pressed(InputActions.ULTIMATE):
		frame.buttons |= FighterInputFrame.BUTTON_ULTIMATE
	return frame
