class_name FighterState
extends RefCounted
## Authoritative per-fighter simulation state for one combat tick.
## Plain data only — no nodes — so it can be copied, compared and tested.

## High-level action state. Neutral states (IDLE, WALK, BLOCK) can act.
## CROUCH (holding down) is neutral too. JUMP covers the whole jump: the
## crouch before take-off, the air time and the landing (D-087).
enum Action { IDLE, WALK, BLOCK, ATTACK, HITSTUN, BLOCKSTUN, KO, KNOCKDOWN, WAKEUP, LAUNCHED, DASH, CROUCH, JUMP }

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
## Multi-hit moves (MoveData.rehit_interval): the hit window that last
## connected (-1 = none yet). The move can connect again in a later window.
var last_hit_window: int = -1

## Where the last hit landed, for the reaction shown (presentation reads it;
## the simulation never does).
enum HitZone { HEAD, BODY, LEGS }
var hit_zone: HitZone = HitZone.HEAD
## The last hit was a counter-hit (cleared when the fighter recovers).
var counter_hit: bool = false

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

## DASH: 1-based tick of the dash, its world direction and whether it goes
## toward the opponent.
var dash_frame: int = 0
var dash_dir: int = 0
var dash_forward: bool = false
## Double-tap detection: direction held last tick and for how long, the
## direction of the last short tap and ticks since it was released (-1 =
## none), and a detected dash waiting for the fighter to be free (with age).
var stick_dir: int = 0
var stick_held_ticks: int = 0
var tap_dir: int = 0
var tap_age: int = -1
var dash_pending: int = 0
var dash_pending_age: int = 0

## Jump (D-087): 1-based tick of the jump (0 = not jumping), its world
## direction (-1, 0, +1, fixed at take-off), the height of the feet above
## the floor (metres; the simulation moves hurtbox and hitbox with it) and
## whether this jump's one air attack has been used. jump_frame keeps
## counting while an air attack (action ATTACK) is in progress.
var jump_frame: int = 0
var jump_dir: int = 0
var height: float = 0.0
var air_attacked: bool = false

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
## False when the current pushback came from a projectile: a cornered
## defender then simply stops at the wall instead of sliding the (possibly
## far away) attacker back.
var pushback_transfers: bool = true
## Throw hold (D-103): the fighter holding this one (-1 = none) and, on the
## thrower, the fighter it holds (-1 = none).
var held_by: int = -1
var throw_target: int = -1


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
	s.last_hit_window = last_hit_window
	s.stun_remaining = stun_remaining
	s.hit_zone = hit_zone
	s.counter_hit = counter_hit
	s.block_low = block_low
	s.armor_left = armor_left
	s.juggle_hits = juggle_hits
	s.launch_total = launch_total
	s.juggle_exhausted = juggle_exhausted
	s.dash_frame = dash_frame
	s.dash_dir = dash_dir
	s.dash_forward = dash_forward
	s.jump_frame = jump_frame
	s.jump_dir = jump_dir
	s.height = height
	s.air_attacked = air_attacked
	s.stick_dir = stick_dir
	s.stick_held_ticks = stick_held_ticks
	s.tap_dir = tap_dir
	s.tap_age = tap_age
	s.dash_pending = dash_pending
	s.dash_pending_age = dash_pending_age
	s.held_buttons = held_buttons
	s.buffer = buffer.duplicate()
	s.chain = chain.duplicate()
	s.meter = meter
	s.surge_remaining = surge_remaining
	s.combo_hits = combo_hits
	s.combo_damage = combo_damage
	s.pushback_remaining = pushback_remaining
	s.pushback_step = pushback_step
	s.pushback_transfers = pushback_transfers
	s.held_by = held_by
	s.throw_target = throw_target
	return s


func is_neutral() -> bool:
	return action == Action.IDLE or action == Action.WALK or action == Action.BLOCK or action == Action.CROUCH


## In a jump (including its take-off and landing ticks on the ground).
func is_jumping() -> bool:
	return jump_frame > 0


func is_airborne() -> bool:
	return height > 0.0


func end_jump() -> void:
	jump_frame = 0
	jump_dir = 0
	height = 0.0
	air_attacked = false


## Ticks left in a float of [param total] ticks at the moment its arc
## (launch_height) comes down through [param h] metres: where a fighter hit
## out of a jump joins the fall.
static func float_ticks_left(h: float, total: int) -> int:
	var u: float = asin(clampf(h / 0.95, 0.0, 1.0)) / PI   # share of the arc still to fall
	return clampi(int(round(u * total)), 6, total)


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
	var text: String = "%s x=%s f=%d hp=%d mv=%s:%d stun=%d push=%s buf=%s combo=%d/%d meter=%d surge=%d" % [
		action_name(), var_to_str(position_x), facing, health,
		move.id if move != null else "-", move_frame, stun_remaining,
		var_to_str(pushback_remaining), buffer, combo_hits, combo_damage, meter, surge_remaining]
	if jump_frame > 0:
		text += " jump=%d/%d h=%s" % [jump_frame, jump_dir, var_to_str(height)]
	return text
