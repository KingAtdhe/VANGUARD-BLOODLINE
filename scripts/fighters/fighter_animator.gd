class_name FighterAnimator
extends RefCounted
## Chooses and positions the fighter's animation from SIMULATION state.
##
## The simulation is the only combat clock (spec §9.3: "do not use animation
## playback position as the only authoritative combat timer"):
##   - attacks are SEEKED to their move frame (frame N == tick N of the
##     move), so the striking limb is exactly where the hitbox is on its
##     active frames, and hitstop freezes the pose;
##   - reactions (hit, block, knockdown, get-up) play from the moment the
##     state is entered and are frozen during hitstop;
##   - idle/walk loop on render time.
## Short cross-fades smooth state changes; attack poses are fully reached
## before their first active frame (blend < startup).

const BLEND_DEFAULT: float = 0.08
const BLEND_ATTACK: float = 0.04
const BLEND_REACTION: float = 0.03
## Initial hitstun at or above this uses the heavy hit reaction.
const HEAVY_HITSTUN: int = 20

var player: AnimationPlayer
var def: FighterDefinition
var current: StringName = &""
var _time: float = 0.0
var _last_action: int = -1
var _last_attack_key: String = ""
var _heavy_hit: bool = false
var _last_combo: int = 0
var _override: StringName = &""


func _init(anim_player: AnimationPlayer, definition: FighterDefinition) -> void:
	player = anim_player
	def = definition
	for a: StringName in [def.anim_idle, def.anim_walk_forward, def.anim_walk_backward]:
		var anim_name: StringName = def.resolve_anim(a)
		if player.has_animation(anim_name):
			player.get_animation(anim_name).loop_mode = Animation.LOOP_LINEAR


## Match-end pose (victory/defeat) overrides state-driven choice; &"" clears.
func set_override(anim_name: StringName) -> void:
	_override = anim_name


## Called once per render frame. [param alpha] = tick interpolation.
func update(s: FighterState, alpha: float, frozen: bool, delta: float) -> void:
	var dt: float = 0.0 if frozen else delta
	if _override != &"":
		_show(_override, BLEND_DEFAULT, _advance_if_same(_override, dt), false)
		return
	match s.action:
		FighterState.Action.ATTACK:
			if s.move == null:
				return
			var key: String = "%s:%d" % [s.move.id, s.chain.size()]
			var t: float = (s.move_frame - 1 + (0.0 if frozen else alpha)) / CombatConstants.TICK_RATE
			_show(s.move.animation, BLEND_ATTACK if key != _last_attack_key else 0.0, t, false)
			_last_attack_key = key
		FighterState.Action.HITSTUN:
			# Each new hit of a combo restarts the reaction.
			var new_hit: bool = _last_action != s.action or s.combo_hits != _last_combo
			if new_hit:
				_heavy_hit = s.stun_remaining >= HEAVY_HITSTUN
			var anim: StringName = def.anim_hit_heavy if _heavy_hit else def.anim_hit_light
			_show(anim, BLEND_REACTION, 0.0 if new_hit else _entered_time(s, anim, dt), false)
		FighterState.Action.BLOCK, FighterState.Action.BLOCKSTUN:
			var block_anim: StringName = def.anim_block_low \
					if (s.block_low and def.anim_block_low != &"") else def.anim_block
			_show(block_anim, BLEND_REACTION, _entered_time(s, block_anim, dt), false)
		FighterState.Action.LAUNCHED:
			# Reeling in the air; each new hit restarts the reaction.
			var air_hit: bool = _last_action != s.action or s.combo_hits != _last_combo
			_show(def.anim_hit_heavy, BLEND_REACTION, 0.0 if air_hit else _entered_time(s, def.anim_hit_heavy, dt), false)
		FighterState.Action.KNOCKDOWN, FighterState.Action.KO:
			_show(def.anim_knockdown, BLEND_REACTION, _entered_time(s, def.anim_knockdown, dt), false)
		FighterState.Action.WAKEUP:
			_show(def.anim_getup, BLEND_DEFAULT, _entered_time(s, def.anim_getup, dt), false)
		FighterState.Action.WALK:
			var walk: StringName = def.anim_walk_forward if s.is_moving_forward() else def.anim_walk_backward
			_show(walk, BLEND_DEFAULT, _advance_if_same(walk, dt), true)
		_:
			_show(def.anim_idle, BLEND_DEFAULT, _advance_if_same(def.anim_idle, dt), true)
	if s.action != FighterState.Action.ATTACK:
		_last_attack_key = ""
	_last_action = s.action
	_last_combo = s.combo_hits


func _entered_time(s: FighterState, anim: StringName, dt: float) -> float:
	if _last_action != s.action or current != anim:
		return 0.0
	return _time + dt


func _advance_if_same(anim: StringName, dt: float) -> float:
	return _time + dt if current == anim else 0.0


func _show(logical: StringName, blend: float, t: float, loop: bool) -> void:
	# Definitions and moves name clips logically; the model may use its own
	# fighter token (see FighterDefinition.anim_prefix).
	var anim: StringName = def.resolve_anim(logical)
	if anim == &"" or not player.has_animation(anim):
		return
	var length: float = player.get_animation(anim).length
	_time = fposmod(t, length) if loop and length > 0.0 else clampf(t, 0.0, length)
	if logical != current:
		player.play(anim, blend)
		current = logical
	player.seek(_time, true)
