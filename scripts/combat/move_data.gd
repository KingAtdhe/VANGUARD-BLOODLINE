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

@export_group("Movement")
## Negative = backward (evasive steps).
## Distance (m) the attacker travels forward during the move, spread evenly
## over frames move_start_frame..move_end_frame. Pushboxes still apply.
@export var move_distance: float = 0.0
@export var move_start_frame: int = 1
@export var move_end_frame: int = 1

@export_group("Origin meter")
@export var meter_gain_on_hit: int = 0
@export var meter_gain_on_block: int = 0
## Meter spent when the move starts (minimum required when consumes_all_meter).
@export var meter_cost: int = 0
## Ultimate: spends ALL remaining meter and ends Origin Surge.
@export var consumes_all_meter: bool = false
## Only usable while Origin Surge is active.
@export var requires_surge: bool = false
## Origin Surge activation (needs a full meter, has no hitbox).
@export var activates_surge: bool = false

@export_group("Reaction")
## On hit (not block): defender is knocked down, then gets up (both
## invulnerable), ending any combo.
@export var knockdown: bool = false

@export_group("Counter-hit")
## Extra hitstun on top of CombatTuning.counter_hit_extra_hitstun when this
## move lands as a counter-hit (a stagger: Vexa's Cut Kick).
@export var counter_hit_stagger_frames: int = 0
## As a counter-hit this move knocks down (a crumple: Ryuen's Sinking Elbow).
@export var counter_hit_knockdown: bool = false

@export_group("Counter")
## Counter stance (D-062): while this move is on frames counter_start_frame..
## counter_end_frame, an incoming attack whose hit level is listed in
## counter_levels does no damage; its user is frozen for counter_stun_frames
## and this fighter immediately starts counter_followup. 0 = not a counter.
## A counter move has no hitbox of its own.
## Parry (D-066): a counter with NO counter_followup. The stance ends at once
## and its user is free to act while the attacker is still frozen.
## Projectiles are never countered or parried, whatever counter_levels says.
@export var counter_start_frame: int = 0
@export var counter_end_frame: int = 0
@export var counter_levels: Array[HitLevel] = []
@export var counter_followup: MoveData = null
@export var counter_stun_frames: int = 16
## The caught attacker is turned past this fighter and ends up on the other
## side with its back to them; the follow-up strikes from behind (D-068).
@export var counter_switches_sides: bool = false

@export_group("Armour")
## Armour (D-063): on frames armor_start_frame..armor_end_frame the move
## absorbs up to armor_hits attacks — damage is taken, but the move is not
## interrupted and there is no stun or pushback. Throws ignore armour.
@export var armor_start_frame: int = 0
@export var armor_end_frame: int = 0
@export var armor_hits: int = 0

@export_group("Evasion")
## The user has no hurtbox on frames invuln_start_frame..invuln_end_frame
## (0 = never). D-064.
@export var invuln_start_frame: int = 0
@export var invuln_end_frame: int = 0

## The user's pushbox is ignored while this move is moving it, so it can
## pass through the opponent and end up behind them (side switch). D-065.
@export var passes_through: bool = false
## A pure movement move: it never has a hitbox.
@export var no_hitbox: bool = false

@export_group("Launch")
## On hit the defender is launched: airborne for launch_frames, can be hit
## again while in the air (juggle, limits in CombatTuning), then lands
## knocked down. D-064.
@export var launch: bool = false
@export var launch_frames: int = 46

@export_group("Multi-hit")
## > 0: the move hits again every this many frames while it is active
## (D-068). active_frames 6 with rehit_interval 2 = three hits ("2+2+2").
## Each hit is a full contact of its own (damage, stun, hitstop, meter).
@export var rehit_interval: int = 0
## Hitstop of every hit except the last (0 = hitstop_frames for all). Lets a
## multi-hit ultimate keep its long freeze for the final blow only (D-087).
## A multi-hit move with `knockdown` knocks down on its LAST hit only, so the
## earlier hits keep the defender standing for the rest.
@export var rehit_hitstop_frames: int = 0

@export_group("Projectile")
## > 0: this move fires a projectile (D-066) on its first active frame instead
## of having a hitbox on the fighter. Speed in metres per second. The
## projectile spawns at hitbox_center (in front of the fighter) with
## hitbox_size as its box and carries this move's damage, stun and hit level.
## A fighter can have only one of its own projectiles on screen: the move
## cannot start while one is still flying.
@export var projectile_speed: float = 0.0
## Distance (m) after which the projectile disappears (it also ends at the
## arena walls).
@export var projectile_range: float = 0.0
## Presentation only: colour of the placeholder projectile effect.
@export var projectile_color: Color = Color(0.25, 0.9, 1.0)

@export_group("Air")
## A jumping attack (D-087): input_pattern AIR, started with any attack
## button while airborne, one per jump. Its hitbox rides with the jump and
## the move ends when the fighter lands.
@export var airborne_allowed: bool = false

@export_group("Reserved for later milestones")
## Only if the move design genuinely needs one (0 = none).
@export var cooldown_frames: int = 0


## Which hit of a multi-hit move [param frame] belongs to (0 = first).
func hit_window(frame: int) -> int:
	if rehit_interval <= 0:
		return 0
	return maxi(0, frame - startup_frames) / rehit_interval


## True if [param frame] is in the move's last hit window (always true for a
## single-hit move).
func is_last_hit(frame: int) -> bool:
	return rehit_interval <= 0 or hit_window(frame) >= hit_count() - 1


## Hitstop for a contact on [param frame].
func hitstop_on(frame: int) -> int:
	if rehit_hitstop_frames > 0 and not is_last_hit(frame):
		return rehit_hitstop_frames
	return hitstop_frames


func hit_count() -> int:
	if rehit_interval <= 0:
		return 1
	return (active_frames + rehit_interval - 1) / rehit_interval


func is_projectile() -> bool:
	return projectile_speed > 0.0


func is_throw() -> bool:
	return hit_level == HitLevel.THROW


func has_armor_on(frame: int) -> bool:
	return armor_hits > 0 and frame >= armor_start_frame and frame <= armor_end_frame


func is_counter() -> bool:
	return counter_end_frame > 0


## True if this counter stance catches an attack of [param level] on [param frame].
func counters(frame: int, level: HitLevel) -> bool:
	return is_counter() and frame >= counter_start_frame and frame <= counter_end_frame \
			and counter_levels.has(level)


func total_frames() -> int:
	return startup_frames + active_frames - 1 + recovery_frames


## True when [param frame] (1-based frame of the move) has an active hitbox.
func is_active_frame(frame: int) -> bool:
	return frame >= startup_frames and frame < startup_frames + active_frames


func moves_on_frame(frame: int) -> bool:
	return move_distance != 0.0 and frame >= move_start_frame and frame <= move_end_frame


func is_invulnerable_on(frame: int) -> bool:
	return invuln_end_frame > 0 and frame >= invuln_start_frame and frame <= invuln_end_frame


## Forward distance per moving frame (negative = backward, an evasive step).
func move_step() -> float:
	return move_distance / float(move_end_frame - move_start_frame + 1)


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


## True if a standing block stops this move.
func is_blockable_standing() -> bool:
	return blocked_by(false)


## Guard rule (docs/COMBAT_FRAME_DATA.md): MID and PROJECTILE are stopped by
## either guard; HIGH (overheads) only by a standing block; LOW only by a low
## block; THROW by neither.
func blocked_by(low_block: bool) -> bool:
	match hit_level:
		HitLevel.MID, HitLevel.PROJECTILE:
			return true
		HitLevel.HIGH:
			return not low_block
		HitLevel.LOW:
			return low_block
	return false


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
	if damage < 0 or chip_damage < 0 or chip_damage > damage or meter_cost < 0:
		p.append("%s: invalid damage/chip" % id)
	if pushback < 0.0:
		p.append("%s: pushback must be >= 0" % id)
	if tags.is_empty():
		p.append("%s: tags is empty" % id)
	if is_counter() and (counter_start_frame < 1 or counter_end_frame < counter_start_frame
			or counter_end_frame > total_frames() or counter_levels.is_empty()):
		p.append("%s: invalid counter window" % id)
	if armor_hits > 0 and (armor_start_frame < 1 or armor_end_frame < armor_start_frame):
		p.append("%s: invalid armour window" % id)
	if is_projectile() and (hit_level != HitLevel.PROJECTILE or projectile_range <= 0.0
			or move_distance != 0.0 or is_counter() or no_hitbox):
		p.append("%s: invalid projectile move" % id)
	if hit_level == HitLevel.PROJECTILE and not is_projectile():
		p.append("%s: PROJECTILE hit level needs projectile_speed" % id)
	if counter_levels.has(HitLevel.PROJECTILE) or counter_levels.has(HitLevel.THROW):
		p.append("%s: projectiles and throws cannot be countered" % id)
	if rehit_interval < 0 or (rehit_interval > 0 and (is_projectile() or is_throw() or is_counter())):
		p.append("%s: invalid multi-hit move" % id)
	if rehit_hitstop_frames < 0 or (rehit_hitstop_frames > 0 and rehit_interval <= 0):
		p.append("%s: rehit_hitstop_frames needs a multi-hit move" % id)
	if (input_pattern == &"AIR") != airborne_allowed:
		p.append("%s: an AIR move must be airborne_allowed (and only an AIR move)" % id)
	if counter_hit_stagger_frames < 0:
		p.append("%s: invalid counter-hit stagger" % id)
	if is_throw() and chip_damage != 0:
		p.append("%s: a throw cannot be blocked, chip must be 0" % id)
	if not activates_surge and not is_counter() and not no_hitbox and (hitbox_size.x <= 0.0 or hitbox_size.y <= 0.0):
		p.append("%s: hitbox_size must be positive" % id)
	if move_end_frame < move_start_frame:
		p.append("%s: invalid movement" % id)
	if activates_surge and requires_surge:
		p.append("%s: cannot both activate and require surge" % id)
	return p
