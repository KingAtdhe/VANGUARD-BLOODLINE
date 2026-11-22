class_name FighterDefinition
extends Resource
## Data-driven fighter definition (spec §9.5). Grows per milestone:
## animation mapping, specials, Origin Surge, audio and cosmetics come later.

@export var fighter_id: StringName = &""
@export var display_name: String = ""
@export var base_health: int = 1000
## Share of chip damage this fighter takes while blocking (100 = normal).
@export_range(0, 200) var chip_taken_percent: int = 100
## Deflecting guard: every strike this fighter blocks slides the attacker
## back by this many metres (0 = an ordinary block). D-068.
@export var block_pushes_attacker: float = 0.0
@export var movement: FighterMovementProfile
## Standing hurtbox: half-width around the centre and height from the floor.
@export var hurtbox_half_width: float = 0.3
@export var hurtbox_height: float = 1.8
## Height of the hurtbox while crouching (holding down, D-087), as a percent
## of hurtbox_height: attacks whose hitbox is entirely above it miss.
@export_range(30, 100) var crouch_height_percent: int = 62
## Move list. Each move is selected by its input_pattern (several moves may
## share a pattern when their meter/surge conditions differ, e.g. ULTIMATE).
@export var moves: Array[MoveData] = []
## False = shown in fighter select but not selectable yet.
@export var playable: bool = true
## Why a fighter is locked (shown in fighter select).
@export var locked_note: String = ""

@export_group("Presentation")
## Character model (glTF scene with Skeleton3D + AnimationPlayer). Null =
## placeholder capsule. Attack animations come from each MoveData.animation.
@export var model_scene: PackedScene
## Reaction/locomotion animation names (FIGHTER_ACTION_VARIANT).
@export var anim_idle: StringName = &""
@export var anim_walk_forward: StringName = &""
@export var anim_walk_backward: StringName = &""
@export var anim_block: StringName = &""
## Dashes (D-071). Empty = the walk in that direction is shown instead.
@export var anim_dash_forward: StringName = &""
@export var anim_dash_back: StringName = &""
## Low block pose (down + block). Empty = the standing block is shown.
@export var anim_block_low: StringName = &""
## Crouch pose and the whole jump (take-off, air, landing) — D-087. Empty =
## idle is shown (the jump still lifts the model).
@export var anim_crouch: StringName = &""
@export var anim_jump: StringName = &""
@export var anim_hit_light: StringName = &""
@export var anim_hit_heavy: StringName = &""
## Reactions to a hit on the body and on the legs (D-069). Empty = the
## light/heavy (head) reaction is shown instead.
@export var anim_hit_body: StringName = &""
@export var anim_hit_low: StringName = &""
@export var anim_knockdown: StringName = &""
@export var anim_getup: StringName = &""
@export var anim_victory: StringName = &""
@export var anim_defeat: StringName = &""
## When set, every animation name above and in the moves is looked up with
## its fighter token replaced (KAIRO_ATTACK_LIGHT_01 -> SENTINEL_ATTACK_LIGHT_01),
## so a fighter can borrow a moveset while keeping its own model and clips.
@export var anim_prefix: StringName = &""
## The fighter's own Origin-energy colour (aura, accents, menus).
@export var accent_color: Color = Color(1.0, 0.08, 0.06)
## Short line shown in fighter select.
@export_multiline var tagline: String = ""

@export_group("Origin Surge")
## Duration of the enhanced state; the meter drains from full to 0 over it.
@export var surge_duration_ticks: int = 300
## Damage percent while in Surge (Kairo: Origin-charged strikes).
@export var surge_damage_percent: int = 115
## Specials cost no meter during Surge.
@export var surge_free_specials: bool = true


func move_for(pattern: StringName) -> MoveData:
	for m: MoveData in moves:
		if m != null and m.input_pattern == pattern:
			return m
	return null


func moves_for(pattern: StringName) -> Array[MoveData]:
	var out: Array[MoveData] = []
	for m: MoveData in moves:
		if m != null and m.input_pattern == pattern:
			out.append(m)
	return out


func move_for_id(id: StringName) -> MoveData:
	for m: MoveData in moves:
		if m != null and m.id == id:
			return m
	return null


## Animation clip name for [param anim] in this fighter's model.
func resolve_anim(anim: StringName) -> StringName:
	if anim_prefix == &"" or anim == &"":
		return anim
	var s: String = String(anim)
	var cut: int = s.find("_")
	return StringName(String(anim_prefix) + (s.substr(cut) if cut >= 0 else "_" + s))


## Every animation clip this fighter needs (reactions + all moves), resolved.
func required_animations() -> Array[StringName]:
	var out: Array[StringName] = []
	for a: StringName in [anim_idle, anim_walk_forward, anim_walk_backward, anim_block,
			anim_hit_light, anim_hit_heavy, anim_knockdown, anim_getup, anim_victory, anim_defeat]:
		out.append(resolve_anim(a))
	for extra: StringName in [anim_block_low, anim_hit_body, anim_hit_low, anim_dash_forward, anim_dash_back,
			anim_crouch, anim_jump]:
		if extra != &"":
			out.append(resolve_anim(extra))
	for m: MoveData in moves:
		if m != null:
			out.append(resolve_anim(m.animation))
	return out


func validate() -> Array[String]:
	var p: Array[String] = []
	if fighter_id == &"":
		p.append("fighter_id is empty")
	if base_health <= 0:
		p.append("%s: base_health must be positive" % fighter_id)
	if movement == null:
		p.append("%s: movement profile missing" % fighter_id)
	else:
		p.append_array(movement.validate())
	if surge_duration_ticks < 1 or surge_damage_percent < 1:
		p.append("%s: invalid surge settings" % fighter_id)
	if hurtbox_half_width <= 0.0 or hurtbox_height <= 0.0:
		p.append("%s: invalid hurtbox" % fighter_id)
	var patterns: Dictionary = {}
	for m: MoveData in moves:
		if m == null:
			p.append("%s: null move entry" % fighter_id)
			continue
		p.append_array(m.validate())
		# Shared patterns must be told apart by their surge requirement.
		var key: String = "%s/%s/%s" % [m.input_pattern, m.requires_surge, m.activates_surge]
		if patterns.has(key):
			p.append("%s: duplicate input_pattern %s" % [fighter_id, m.input_pattern])
		patterns[key] = true
	return p
