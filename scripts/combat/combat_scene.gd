extends Node
## Greybox combat scene controller (Milestone 1).
##
## Each render frame:
##   1. CombatClock converts the render delta into N fixed 60 Hz ticks.
##   2. For each tick: sample inputs, snapshot previous state, step simulation.
##   3. Views interpolate between previous and current tick by clock.alpha().
##   4. Camera follows the interpolated positions.
## Gameplay never reads render delta directly.

@export var arena_config: ArenaConfig
@export var p1_profile: FighterMovementProfile
@export var p2_profile: FighterMovementProfile
## Log simulation state to stdout every N ticks (0 = off). Debug aid.
@export var log_every_ticks: int = 0

@onready var _fighter_views: Array[FighterView] = [%Fighter1, %Fighter2]
@onready var _camera_rig: CameraRig = %CameraRig
@onready var _overlay: DebugOverlay = %DebugOverlay

var simulation := CombatSimulation.new()
var clock := CombatClock.new()
var _previous: Array[FighterState] = []


func _ready() -> void:
	var problems: Array[String] = []
	if arena_config == null or p1_profile == null or p2_profile == null:
		problems.append("missing arena or fighter data")
	else:
		problems.append_array(arena_config.validate())
		problems.append_array(p1_profile.validate())
		problems.append_array(p2_profile.validate())
	if not problems.is_empty():
		push_error("CombatScene: invalid setup: %s" % ", ".join(problems))
		set_process(false)
		return

	simulation.setup(arena_config, p1_profile, p2_profile)
	_previous = simulation.snapshot()
	_camera_rig.configure(arena_config)
	_overlay.back_requested.connect(_return_to_menu)
	_render(0.0)
	print("[Combat] greybox ready: arena=%s P1=%s P2=%s tick=%dHz" % [
		arena_config.arena_id, p1_profile.fighter_id, p2_profile.fighter_id,
		CombatConstants.TICK_RATE])


func _process(delta: float) -> void:
	var ticks: int = clock.advance(delta)
	for _i: int in ticks:
		_previous = simulation.snapshot()
		simulation.step(_gather_inputs())
		if log_every_ticks > 0 and simulation.tick % log_every_ticks == 0:
			_log_state()
	_render(delta)


func _notification(what: int) -> void:
	# Android back gesture/button returns to the menu (no pause menu until M3).
	if what == NOTIFICATION_WM_GO_BACK_REQUEST:
		_return_to_menu()


func _gather_inputs() -> Array[FighterInputFrame]:
	# P2 is an idle training dummy until the AI milestone (M5).
	return [LocalInputReader.read(), FighterInputFrame.neutral()]


func _render(delta: float) -> void:
	var alpha: float = clock.alpha()
	for i: int in 2:
		_fighter_views[i].sync(_previous[i], simulation.fighters[i], alpha)
	_camera_rig.follow(_fighter_views[0].position.x, _fighter_views[1].position.x, delta)
	_overlay.set_text(_debug_text())


func _debug_text() -> String:
	var f: Array[FighterState] = simulation.fighters
	return "\n".join([
		"MILESTONE 1 GREYBOX  —  P1 Kairo (placeholder, red) vs P2 Training Dummy (blue)  —  F3 hides",
		"tick %d  (%d Hz fixed)  fps %d  dropped ticks %d" % [
			simulation.tick, CombatConstants.TICK_RATE,
			Engine.get_frames_per_second(), clock.dropped_ticks()],
		"P1 x=%+.3f  facing=%s  move=%+d" % [f[0].position_x, _facing_str(f[0].facing), f[0].move_x],
		"P2 x=%+.3f  facing=%s  move=%+d" % [f[1].position_x, _facing_str(f[1].facing), f[1].move_x],
		"separation %.3f / max %.1f   walls [%.1f, %.1f]" % [
			simulation.separation(), arena_config.max_separation,
			arena_config.left_bound, arena_config.right_bound],
		"camera x=%+.2f dist=%.2f" % [_camera_rig.center_x(), _camera_rig.distance()],
	])


func _facing_str(facing: int) -> String:
	return "RIGHT" if facing > 0 else "LEFT"


func _log_state() -> void:
	var f: Array[FighterState] = simulation.fighters
	print("[Combat] tick=%d p1=%.4f(%d) p2=%.4f(%d)" % [
		simulation.tick, f[0].position_x, f[0].facing, f[1].position_x, f[1].facing])


func _return_to_menu() -> void:
	SceneRouter.goto(ScenePaths.MAIN_MENU)
