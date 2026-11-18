class_name CombatClock
extends RefCounted
## Fixed-timestep accumulator (spec §9.4).
##
## Feed it the render delta every frame; it returns how many fixed combat ticks
## to run. Rendering then interpolates between the last two tick states using
## [method alpha]. Gameplay therefore behaves identically at 30, 60, 90, 120 or
## 144 Hz displays — only the number of ticks per frame changes.

## Tolerance so float rounding (e.g. 1/144 steps) doesn't lose a tick.
const _EPSILON: float = 1e-9

var _accumulator: float = 0.0
var _total_ticks: int = 0
var _dropped_ticks: int = 0


## Adds [param delta] seconds and returns the number of ticks to simulate now.
func advance(delta: float) -> int:
	if delta <= 0.0:
		return 0
	_accumulator += delta
	var ticks: int = int(floor((_accumulator + _EPSILON) / CombatConstants.TICK_DELTA))
	if ticks > CombatConstants.MAX_CATCH_UP_TICKS:
		# Too far behind: run the cap and discard the rest instead of
		# trying to catch up (which would make the next frame even slower).
		_dropped_ticks += ticks - CombatConstants.MAX_CATCH_UP_TICKS
		ticks = CombatConstants.MAX_CATCH_UP_TICKS
		_accumulator = 0.0
	else:
		_accumulator = maxf(0.0, _accumulator - ticks * CombatConstants.TICK_DELTA)
	_total_ticks += ticks
	return ticks


## Fraction (0..1) of the way from the previous tick to the next one.
func alpha() -> float:
	return clampf(_accumulator / CombatConstants.TICK_DELTA, 0.0, 1.0)


func total_ticks() -> int:
	return _total_ticks


func dropped_ticks() -> int:
	return _dropped_ticks


func reset() -> void:
	_accumulator = 0.0
	_total_ticks = 0
	_dropped_ticks = 0
