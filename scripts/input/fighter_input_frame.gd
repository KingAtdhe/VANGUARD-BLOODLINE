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
## Internal buffer commands for the other direction + button presses. Down
## wins over forward/back. A fighter without a move for the command falls
## back to the plain button (see CombatSimulation._FALLBACK).
const CMD_BACK_SPECIAL: int = 128
const CMD_DOWN_SPECIAL: int = 256
const CMD_DOWN_LIGHT: int = 512
const CMD_DOWN_HEAVY: int = 1024
const CMD_DOWN_KICK: int = 2048
## Light + Kick pressed together (within CombatSimulation.THROW_WINDOW = 1 tick): a throw (D-103, D-105).
const CMD_THROW: int = 4096

## World-space horizontal direction: -1 = left, 0 = none, +1 = right.
var move_x: int = 0
## Vertical direction: -1 = down (low block, down + button moves), 0 = none,
## +1 = up (reserved).
var move_y: int = 0
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


static func with_buttons(held: int, direction: int = 0, vertical: int = 0) -> FighterInputFrame:
	var f := moving(direction)
	f.move_y = clampi(vertical, -1, 1)
	f.buttons = held
	return f
