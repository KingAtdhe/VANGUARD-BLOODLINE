class_name FighterState
extends RefCounted
## Authoritative per-fighter simulation state for one combat tick.
## Plain data only — no nodes — so it can be copied, compared and tested.

## High-level action state. Neutral states (IDLE, WALK, BLOCK) can act.
enum Action { IDLE, WALK, BLOCK, ATTACK, HITSTUN, BLOCKSTUN, KO, KNOCKDOWN, WAKEUP, LAUNCHED }

## Position of the fighter's centre on the fighting plane (metres).
var position_x: float = 0.0
## +1 = facing right (toward +X), -1 = facing left.
var facing: int = 1
## World-space movement direction applied this tick (-1, 0, +1).
var move_x: int = 0
## Distance moved during the last tick (metres, signed).
var last_displacement: float = 0.0

var action: Action = Action.IDLE
var health: int = 1000

## Current attack (ATTACK state only) and its 1-based frame number.
var move: MoveData = null
var move_frame: int = 0
## True once the current attack has hit or been blocked: it cannot connect
## again (one hit per attack per target).
var move_connected: bool = false

## Remaining hitstun/blockstun ticks. The fighter becomes actionable on the
## tick AFTER this reaches 0, so a stun of N means N full ticks of no control.
var stun_remaining: int = 0
## Guard height while in BLOCK / BLOCKSTUN: true = low block (down held).
## A low block stops LOW and MID attacks and loses to HIGH (overheads); a
## standing block stops HIGH and MID and loses to LOW.
var block_low: bool = false
## Hits the current move's armour can still absorb (set when the move starts).
var armor_left: int = 0
## LAUNCHED: hits taken in the air so far, and the length of the current
## float (stun_remaining counts it down) — the view draws the arc from these.
var juggle_hits: int = 0
var launch_total: int = 0
var juggle_exhausted: bool = false

## Buttons held on the last processed tick (for press-edge detection).
var held_buttons: int = 0
## Input buffer: recent attack presses as Vector2i(button, age_in_ticks),
## oldest first. Ages advance only on non-hitstop ticks; entries older than
## CombatTuning.input_buffer_ticks are dropped. A press is consumed when it
## starts (or cancels into) an attack.
var buffer: Array[Vector2i] = []
## Move ids in the current cancel chain (for repeat limits).
var chain: Array[StringName] = []

## Origin meter (0..CombatTuning.meter_max) and remaining Origin Surge ticks.
var meter: int = 0
var surge_remaining: int = 0

## Combo being suffered by THIS fighter (as defender): hits and damage since
## it was last neutral. Reset when it recovers to neutral.
var combo_hits: int = 0
var combo_damage: int = 0

## Pushback still to slide (signed metres) and slide amount per tick.
var pushback_remaining: float = 0.0
var pushback_step: float = 0.0


func copy() -> FighterState:
	var s := FighterState.new()
	s.position_x = position_x
	s.facing = facing
	s.move_x = move_x
	s.last_displacement = last_displacement
	s.action = action
	s.health = health
	s.move = move
	s.move_frame = move_frame
	s.move_connected = move_connected
	s.stun_remaining = stun_remaining
	s.block_low = block_low
	s.armor_left = armor_left
	s.juggle_hits = juggle_hits
	s.launch_total = launch_total
	s.juggle_exhausted = juggle_exhausted
	s.held_buttons = held_buttons
	s.buffer = buffer.duplicate()
	s.chain = chain.duplicate()
	s.meter = meter
	s.surge_remaining = surge_remaining
	s.combo_hits = combo_hits
	s.combo_damage = combo_damage
	s.pushback_remaining = pushback_remaining
	s.pushback_step = pushback_step
	return s


func is_neutral() -> bool:
	return action == Action.IDLE or action == Action.WALK or action == Action.BLOCK


func in_surge() -> bool:
	return surge_remaining > 0


## On the ground or getting up: cannot be hit.
## Height above the floor (m) of a launched fighter: a simple arc over the
## current float. Presentation only — hurtboxes do not move.
func launch_height() -> float:
	if action != Action.LAUNCHED or launch_total <= 0:
		return 0.0
	var u: float = clampf(1.0 - float(stun_remaining) / float(launch_total), 0.0, 1.0)
	return sin(u * PI) * (0.95 if juggle_hits == 0 else 0.45)


func is_downed() -> bool:
	return action == Action.KNOCKDOWN or action == Action.WAKEUP


func is_blocking() -> bool:
	return action == Action.BLOCK or action == Action.BLOCKSTUN


## True when the fighter is walking toward the side it faces.
func is_moving_forward() -> bool:
	return move_x != 0 and move_x == facing


func action_name() -> String:
	return Action.keys()[action]


## Compact, exact text form — used for determinism checks and debugging.
func describe() -> String:
	return "%s x=%s f=%d hp=%d mv=%s:%d stun=%d push=%s buf=%s combo=%d/%d meter=%d surge=%d" % [
		action_name(), var_to_str(position_x), facing, health,
		move.id if move != null else "-", move_frame, stun_remaining,
		var_to_str(pushback_remaining), buffer, combo_hits, combo_damage, meter, surge_remaining]
