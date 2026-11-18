class_name FighterInputFrame
extends RefCounted
## One tick of logical input for one fighter. Players, the training dummy
## and (Milestone 5) the AI all produce these, so every controller drives the
## simulation through exactly the same interface.

## World-space horizontal direction: -1 = left, 0 = none, +1 = right.
var move_x: int = 0


static func neutral() -> FighterInputFrame:
	return FighterInputFrame.new()


static func moving(direction: int) -> FighterInputFrame:
	var f := FighterInputFrame.new()
	f.move_x = clampi(direction, -1, 1)
	return f
