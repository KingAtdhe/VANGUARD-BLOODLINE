class_name LocalInputReader
extends RefCounted
## Samples the local device's logical actions into a FighterInputFrame.
## Pressing both directions at once cancels out (neutral).


static func read() -> FighterInputFrame:
	var frame := FighterInputFrame.new()
	var left: bool = Input.is_action_pressed(InputActions.MOVE_LEFT)
	var right: bool = Input.is_action_pressed(InputActions.MOVE_RIGHT)
	frame.move_x = int(right) - int(left)
	return frame
