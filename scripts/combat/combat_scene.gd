extends Node
## Greybox combat scene controller.
##
## Each render frame:
##   1. CombatClock converts the render delta into N fixed 60 Hz ticks.
##   2. For each tick: sample inputs, snapshot previous state, step simulation.
##   3. New combat-log events drive presentation (sparks, flash, camera shake).
##   4. Views interpolate between previous and current tick by clock.alpha().
## Gameplay never reads render delta directly.

@export var arena_config: ArenaConfig
@export var p1_definition: FighterDefinition
@export var p2_definition: FighterDefinition
## Print combat-log events to stdout as they happen.
@export var print_combat_log: bool = true

@onready var _fighter_views: Array[FighterView] = [%Fighter1, %Fighter2]
@onready var _camera_rig: CameraRig = %CameraRig
@onready var _overlay: DebugOverlay = %DebugOverlay
@onready var _hitbox_view: HitboxDebugView = %HitboxDebugView
@onready var _effects: EffectsManager = %EffectsManager

var simulation := CombatSimulation.new()
var clock := CombatClock.new()
var dummy := TrainingDummyController.new()
var _previous: Array[FighterState] = []
var _seen_events: int = 0


func _ready() -> void:
	var problems: Array[String] = []
	if arena_config == null or p1_definition == null or p2_definition == null:
		problems.append("missing arena or fighter data")
	else:
		problems.append_array(arena_config.validate())
		problems.append_array(p1_definition.validate())
		problems.append_array(p2_definition.validate())
	if not problems.is_empty():
		push_error("CombatScene: invalid setup: %s" % ", ".join(problems))
		set_process(false)
		return

	simulation.combat_log.echo_to_stdout = print_combat_log
	simulation.setup(arena_config, p1_definition, p2_definition)
	_previous = simulation.snapshot()
	_seen_events = simulation.combat_log.total_count()
	_camera_rig.configure(arena_config)
	_overlay.back_requested.connect(_return_to_menu)
	_overlay.reset_requested.connect(reset_round)
	_overlay.dummy_cycle_requested.connect(cycle_dummy_mode)
	_overlay.hitboxes_toggle_requested.connect(func() -> void: _hitbox_view.visible = not _hitbox_view.visible)
	_overlay.set_dummy_mode(dummy.mode_name())
	_render(0.0)
	print("[Combat] greybox ready: arena=%s P1=%s P2=%s tick=%dHz" % [
		arena_config.arena_id, p1_definition.fighter_id, p2_definition.fighter_id,
		CombatConstants.TICK_RATE])


func _process(delta: float) -> void:
	var ticks: int = clock.advance(delta)
	for _i: int in ticks:
		_previous = simulation.snapshot()
		simulation.step(_gather_inputs())
	_present_new_events()
	_render(delta)


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed(InputActions.DEBUG_RESET):
		reset_round()
	elif event.is_action_pressed(InputActions.DEBUG_CYCLE_DUMMY):
		cycle_dummy_mode()


func _notification(what: int) -> void:
	# Android back gesture/button returns to the menu (no pause menu until M3).
	if what == NOTIFICATION_WM_GO_BACK_REQUEST:
		_return_to_menu()


## Training reset: spawn positions, full health. Logged as RESET.
func reset_round() -> void:
	simulation.reset()
	_previous = simulation.snapshot()


func cycle_dummy_mode() -> void:
	dummy.next_mode()
	_overlay.set_dummy_mode(dummy.mode_name())


func _gather_inputs() -> Array[FighterInputFrame]:
	# P2 is a scripted training dummy until the AI milestone (M5).
	return [LocalInputReader.read(), dummy.input_for_tick(simulation.tick + 1)]


func _present_new_events() -> void:
	var combat_log: CombatLog = simulation.combat_log
	for ev: CombatEvent in combat_log.events_since(_seen_events):
		match ev.type:
			CombatEvent.Type.HIT:
				_effects.spawn_for(ev)
				_fighter_views[ev.target].flash()
				_camera_rig.add_shake(0.015 + ev.damage / 2500.0)
			CombatEvent.Type.BLOCK:
				_effects.spawn_for(ev)
				_camera_rig.add_shake(0.008)
	_seen_events = combat_log.total_count()


func _render(delta: float) -> void:
	var alpha: float = clock.alpha()
	var frozen: bool = simulation.hitstop_remaining > 0
	var xs: Array[float] = []
	for i: int in 2:
		_fighter_views[i].sync(_previous[i], simulation.fighters[i], alpha, frozen, delta)
		xs.append(lerpf(_previous[i].position_x, simulation.fighters[i].position_x, alpha))
	_hitbox_view.show_boxes(simulation, xs)
	_camera_rig.follow(xs[0], xs[1], delta)
	_overlay.set_text(_debug_text(), _log_text())


func _debug_text() -> String:
	var f: Array[FighterState] = simulation.fighters
	return "\n".join([
		"MILESTONE 2 GREYBOX — P1 Kairo (red) vs P2 Dummy (blue) — F3 panel  F4 boxes  R reset  T dummy",
		"tick %d (60 Hz)  fps %d  hitstop %d  dropped %d   sep %.2f" % [
			simulation.tick, Engine.get_frames_per_second(), simulation.hitstop_remaining,
			clock.dropped_ticks(), simulation.separation()],
		_fighter_line(0, f[0]),
		_fighter_line(1, f[1]),
	])


func _fighter_line(i: int, s: FighterState) -> String:
	var detail: String = ""
	if s.action == FighterState.Action.ATTACK and s.move != null:
		var phase: String = "startup"
		if s.move.is_active_frame(s.move_frame):
			phase = "ACTIVE"
		elif s.move_frame > s.move.startup_frames:
			phase = "recovery"
		detail = "  %s f%d/%d %s" % [s.move.id, s.move_frame, s.move.total_frames(), phase]
	elif s.stun_remaining > 0:
		detail = "  stun %d" % s.stun_remaining
	return "P%d hp %4d  x %+.2f  %s%s" % [i + 1, s.health, s.position_x, s.action_name(), detail]


func _log_text() -> String:
	var lines: PackedStringArray = []
	for ev: CombatEvent in simulation.combat_log.recent(5):
		lines.append(ev.to_text())
	return "\n".join(lines)


func _return_to_menu() -> void:
	SceneRouter.goto(ScenePaths.MAIN_MENU)
