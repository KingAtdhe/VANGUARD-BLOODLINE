class_name CombatTuning
extends Resource
## Global combat-system tuning (not per fighter). Lives in data/rules/.

@export_group("Input buffer")
## A button press stays usable for this many ticks (0 = this tick only).
## Buffer age does not advance during hitstop.
@export var input_buffer_ticks: int = 6

@export_group("Cancels")
## Cancels are allowed on contact (hit or block), from the contact frame until
## this many frames after the move's last active frame.
@export var cancel_grace_frames: int = 3
## The same move may appear at most this many times in one cancel chain
## (e.g. 2 → Light, Light is allowed, a third Light is not).
@export var max_same_move_in_chain: int = 2

@export_group("Origin meter")
@export var meter_max: int = 100
## Defender gains this percent of damage taken as meter.
@export var meter_on_damage_taken_percent: int = 12
## Defender gains this much meter per blocked attack.
@export var meter_on_block_taken: int = 2

@export_group("Knockdown")
## Ticks on the ground after a knockdown hit, then ticks getting up. The
## fighter has no hurtbox during both.
@export var knockdown_ticks: int = 45
@export var wakeup_ticks: int = 20

@export_group("Combo scaling")
## Damage percent for the 1st, 2nd, 3rd… hit of a combo.
@export var combo_scaling_percent: PackedInt32Array = PackedInt32Array([100, 100, 80, 70, 60, 50])
## Percent used for hits beyond the table.
@export var combo_scaling_floor_percent: int = 40


## Damage percent for the [param hit_number]-th hit (1-based) of a combo.
func scaling_percent(hit_number: int) -> int:
	var idx: int = hit_number - 1
	if idx >= 0 and idx < combo_scaling_percent.size():
		return combo_scaling_percent[idx]
	return combo_scaling_floor_percent


## Integer damage after scaling; a connecting hit always deals at least 1.
func scaled_damage(base: int, hit_number: int) -> int:
	if base <= 0:
		return 0
	return maxi(1, base * scaling_percent(hit_number) / 100)


func validate() -> Array[String]:
	var p: Array[String] = []
	if input_buffer_ticks < 0:
		p.append("input_buffer_ticks must be >= 0")
	if cancel_grace_frames < 0:
		p.append("cancel_grace_frames must be >= 0")
	if max_same_move_in_chain < 1:
		p.append("max_same_move_in_chain must be >= 1")
	for v: int in combo_scaling_percent:
		if v < 1 or v > 100:
			p.append("combo scaling percents must be 1..100")
			break
	if meter_max < 1 or meter_on_damage_taken_percent < 0 or meter_on_block_taken < 0:
		p.append("invalid meter settings")
	if knockdown_ticks < 1 or wakeup_ticks < 1:
		p.append("knockdown/wakeup ticks must be >= 1")
	if combo_scaling_floor_percent < 1 or combo_scaling_floor_percent > 100:
		p.append("combo_scaling_floor_percent must be 1..100")
	return p
