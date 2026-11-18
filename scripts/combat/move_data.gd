class_name MoveData
extends Resource
## One attack definition (spec §4.3). Balance data — lives in data/moves/.
##
## FRAME CONVENTION (fighting-game standard, see docs/COMBAT_FRAME_DATA.md):
##   - Frames are 60 Hz combat ticks, never render frames.
##   - startup_frames INCLUDES the first active frame. A 5f move hits on
##     frame 5 of the move (4 frames of wind-up, then the hitbox appears).
##   - Total duration = startup + active - 1 + recovery.
##   - Advantage on hit  = hitstun_frames  - (active_frames - 1 + recovery_frames)
##     Advantage on block = blockstun_frames - (active_frames - 1 + recovery_frames)
##     (assuming contact on the first active frame; hitstop freezes both sides
##     equally so it does not change advantage).

enum HitLevel { HIGH, MID, LOW, THROW, PROJECTILE }

@export var id: StringName = &""
@export var display_name: String = ""
## Logical input that triggers the move. Milestone 2 patterns: LIGHT, HEAVY,
## KICK. Motion inputs (specials) arrive with the input buffer in M4.
@export var input_pattern: StringName = &""
## Animation name, FIGHTER_ACTION_VARIANT convention (used from M6).
@export var animation: StringName = &""

@export_group("Frame data")
@export var startup_frames: int = 5
@export var active_frames: int = 3
@export var recovery_frames: int = 10
@export var hitstun_frames: int = 14
@export var blockstun_frames: int = 11
## Global freeze applied to both fighters when the move connects.
@export var hitstop_frames: int = 6

@export_group("Damage")
@export var damage: int = 35
## Damage dealt through block. Chip damage can KO.
@export var chip_damage: int = 0
## Distance (m) the defender slides back on hit/block. If the defender is
## against a wall, the attacker is pushed back instead.
@export var pushback: float = 0.25
@export var hit_level: HitLevel = HitLevel.MID

@export_group("Hitbox profile")
## Hitbox centre relative to the fighter origin: x = forward (mirrored by
## facing), y = height above floor. Metres.
@export var hitbox_center: Vector2 = Vector2(0.6, 1.45)
@export var hitbox_size: Vector2 = Vector2(0.5, 0.3)

@export_group("Cancels")
## What this move IS, e.g. ["normal", "light"].
@export var tags: PackedStringArray = PackedStringArray()
## Tags of moves this move may be cancelled INTO on contact (spec §4.5).
## Empty = this move cannot be cancelled.
@export var cancel_tags: PackedStringArray = PackedStringArray()

@export_group("Reserved for later milestones")
## Origin meter (M6).
@export var meter_gain_on_hit: int = 0
@export var meter_gain_on_block: int = 0
@export var meter_cost: int = 0
## Knockdown/launch states (M3+).
@export var knockdown: bool = false
@export var launch: bool = false
@export var airborne_allowed: bool = false
## Only if the move design genuinely needs one (0 = none).
@export var cooldown_frames: int = 0


func total_frames() -> int:
	return startup_frames + active_frames - 1 + recovery_frames


## True when [param frame] (1-based frame of the move) has an active hitbox.
func is_active_frame(frame: int) -> bool:
	return frame >= startup_frames and frame < startup_frames + active_frames


## True if [param target] may cancel this move (tag match only; timing and
## repeat limits are checked by the simulation).
func can_cancel_into(target: MoveData) -> bool:
	if target == null:
		return false
	for t: String in target.tags:
		if cancel_tags.has(t):
			return true
	return false


func advantage_on_hit() -> int:
	return hitstun_frames - (active_frames - 1 + recovery_frames)


func advantage_on_block() -> int:
	return blockstun_frames - (active_frames - 1 + recovery_frames)


## True if a standing block stops this move. Crouch-block (lows) and throws
## arrive with crouching/throws; until then LOW and THROW are not blockable.
func is_blockable_standing() -> bool:
	return hit_level == HitLevel.HIGH or hit_level == HitLevel.MID \
			or hit_level == HitLevel.PROJECTILE


func validate() -> Array[String]:
	var p: Array[String] = []
	if id == &"":
		p.append("id is empty")
	if input_pattern == &"":
		p.append("%s: input_pattern is empty" % id)
	if startup_frames < 1 or active_frames < 1 or recovery_frames < 0:
		p.append("%s: invalid frame counts" % id)
	if hitstun_frames < 1 or blockstun_frames < 1 or hitstop_frames < 0:
		p.append("%s: invalid stun/hitstop frames" % id)
	if damage < 0 or chip_damage < 0 or chip_damage > damage:
		p.append("%s: invalid damage/chip" % id)
	if pushback < 0.0:
		p.append("%s: pushback must be >= 0" % id)
	if tags.is_empty():
		p.append("%s: tags is empty" % id)
	if hitbox_size.x <= 0.0 or hitbox_size.y <= 0.0:
		p.append("%s: hitbox_size must be positive" % id)
	return p
