class_name TrainingDummyController
extends RefCounted
## Scripted training-dummy behaviour (spec §6.1 Training: dummy settings).
## Not AI — no decisions, no reading of the opponent. Deterministic: output
## depends only on the simulation tick. The AI arrives in Milestone 5.

enum Mode { STAND, BLOCK, JAB }

## JAB mode presses Light once every this many ticks (when able).
const JAB_INTERVAL_TICKS: int = 40

var mode: Mode = Mode.STAND


func next_mode() -> void:
	mode = ((mode + 1) % Mode.size()) as Mode


func mode_name() -> String:
	return Mode.keys()[mode]


## Input for the coming tick. [param tick] is the tick about to be simulated.
func input_for_tick(tick: int) -> FighterInputFrame:
	match mode:
		Mode.BLOCK:
			return FighterInputFrame.with_buttons(FighterInputFrame.BUTTON_BLOCK)
		Mode.JAB:
			# Held for 2 ticks then released, so each cycle is a fresh press.
			if tick % JAB_INTERVAL_TICKS < 2:
				return FighterInputFrame.with_buttons(FighterInputFrame.BUTTON_LIGHT)
	return FighterInputFrame.neutral()
