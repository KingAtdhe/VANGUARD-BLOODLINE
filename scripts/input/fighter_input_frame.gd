class_name FighterInputFrame
extends RefCounted
## One tick of logical input for one fighter. Players, the training dummy
## and (Milestone 5) the AI all produce these, so every controller drives the
## simulation through exactly the same interface.
##
## Buttons are HELD states; the simulation detects presses itself by comparing
## with the previous tick, so press detection is deterministic for every
## controller type.

const BUTTON_LIGHT: int = 1
const BUTTON_HEAVY: int = 2
const BUTTON_KICK: int = 4
const BUTTON_BLOCK: int = 8
const BUTTON_SPECIAL: int = 16
const BUTTON_ULTIMATE: int = 32
## Internal buffer command (never pressed directly): SPECIAL pressed while
## holding toward the opponent. Resolved by the simulation from move_x+facing.
const CMD_FORWARD_SPECIAL: int = 64

## World-space horizontal direction: -1 = left, 0 = none, +1 = right.
var move_x: int = 0
## Bitmask of BUTTON_* currently held.
var buttons: int = 0


func is_held(button: int) -> bool:
	return (buttons & button) != 0


static func neutral() -> FighterInputFrame:
	return FighterInputFrame.new()


static func moving(direction: int) -> FighterInputFrame:
	var f := FighterInputFrame.new()
	f.move_x = clampi(direction, -1, 1)
	return f


static func with_buttons(held: int, direction: int = 0) -> FighterInputFrame:
	var f := moving(direction)
	f.buttons = held
	return f
